"""Test de Reportes (Fase 5.3) y auditoría de stock (Fase 5.4).

Requiere MySQL. Crea un usuario WMS temporal con rol CONSULTA (accede a
/reportes gracias a la migración add_reportes_ruta.sql) y verifica:
la página /reportes, las exportaciones CSV/XLSX/JSON y que el flujo de la
API (recepción -> confirmar OMC) deja el historial en stock_movimientos.
"""

import uuid

import pytest
from conftest import DB_OK, requires_db
from werkzeug.security import generate_password_hash

from modules.api import _hash_token
from modules.db_config import _get_admin_connection, get_db_connection


@pytest.fixture(scope='module')
def user_consulta():
    """Usuario WMS temporal con rol CONSULTA (permite /reportes y exportar)."""
    if not DB_OK:
        pytest.skip('MySQL no disponible')
    conn = _get_admin_connection()
    username = 'rep-' + uuid.uuid4().hex[:8]
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO usuarios (username, password_hash, nombre, rol, tenant_id, activo)
            VALUES (%s, %s, 'Usuario Reportes Test', 'CONSULTA', 1, 1)
        """, (username, generate_password_hash('Test@2024!')))
        conn.commit()
        yield username
    finally:
        cur = conn.cursor()
        cur.execute("DELETE FROM usuarios WHERE username = %s", (username,))
        conn.commit()
        conn.close()


@pytest.fixture(scope='module')
def tenant_api():
    """Tenant activo con token API temporal (para el flujo que audita)."""
    if not DB_OK:
        pytest.skip('MySQL no disponible')
    token = 'rep-api-' + uuid.uuid4().hex
    conn = _get_admin_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM tenants WHERE activo = 1 ORDER BY id LIMIT 1")
        tid = cur.fetchone()['id']
        cur.execute("UPDATE tenants SET api_token = %s WHERE id = %s",
                    (_hash_token(token), tid))
        conn.commit()
        yield {'tenant_id': tid, 'token': token}
    finally:
        cur = conn.cursor()
        cur.execute("UPDATE tenants SET api_token = NULL WHERE id = %s", (tid,))
        conn.commit()
        conn.close()


@pytest.fixture
def datos_auditoria(tenant_api):
    """Material y 2 ubicaciones de prueba para el flujo auditado."""
    conn = get_db_connection()
    sufijo = uuid.uuid4().hex[:8]
    datos = {'sufijo': sufijo}
    try:
        cur = conn.cursor()
        tid = tenant_api['tenant_id']

        cur.execute("INSERT INTO tipoubicacion (descripcion, operacion, tenant_id) VALUES (%s, 'R', %s)",
                    ('TEST-AUD-TIPO-' + sufijo, tid))
        datos['id_tipo'] = cur.lastrowid

        cur.execute("""
            INSERT INTO ubicaciones (codigo, nombre, tipoubicacion, activo, tenant_id)
            VALUES (%s, %s, %s, 1, %s)
        """, ('TEST-AUD-RECEP-' + sufijo, 'Recepcion aud', datos['id_tipo'], tid))
        datos['id_ubic_recep'] = cur.lastrowid

        cur.execute("""
            INSERT INTO ubicaciones (codigo, nombre, tipoubicacion, activo, tenant_id)
            VALUES (%s, %s, %s, 1, %s)
        """, ('TEST-AUD-DEST-' + sufijo, 'Destino aud', datos['id_tipo'], tid))
        datos['id_ubic_dest'] = cur.lastrowid

        cur.execute("""
            INSERT INTO proveedores (codigo, razonsocial, activo, tenant_id)
            VALUES (%s, %s, 1, %s)
        """, ('TEST-AUD-PROV-' + sufijo, 'Proveedor aud', tid))
        datos['id_proveedor'] = cur.lastrowid

        cur.execute("""
            INSERT INTO materiales (codigo, codigo_barras, nombre, trazabilidad,
                                    metodo_picking, activo, tenant_id)
            VALUES (%s, %s, %s, 'lote', 'fifo', 1, %s)
        """, ('TEST-AUD-MAT-' + sufijo, '700000000000' + sufijo[-4:],
              'Material aud', tid))
        datos['id_material'] = cur.lastrowid

        datos['tenant_id'] = tid
        conn.commit()
        yield datos
    finally:
        cur = conn.cursor()
        tid = datos.get('tenant_id')
        if datos.get('id_material'):
            cur.execute("DELETE FROM stockcontable WHERE Material = %s AND tenant_id = %s",
                        (datos['id_material'], tid))
            cur.execute("DELETE FROM stock_movimientos WHERE id_material = %s AND tenant_id = %s",
                        (datos['id_material'], tid))
            cur.execute("DELETE FROM materiales WHERE id = %s", (datos['id_material'],))
        if datos.get('id_proveedor'):
            cur.execute("DELETE FROM proveedores WHERE id = %s", (datos['id_proveedor'],))
        for k in ('id_ubic_recep', 'id_ubic_dest'):
            if datos.get(k):
                cur.execute("DELETE FROM ubicaciones WHERE id = %s", (datos[k],))
        if datos.get('id_tipo'):
            cur.execute("DELETE FROM tipoubicacion WHERE id = %s", (datos['id_tipo'],))
        conn.commit()
        conn.close()


def _login(client, user_consulta):
    resp = client.post('/login', data={
        'username': user_consulta, 'password': 'Test@2024!',
    })
    assert resp.status_code in (302, 200)
    return client


@requires_db
def test_reportes_pagina(client, user_consulta):
    _login(client, user_consulta)
    resp = client.get('/reportes')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Stock actual' in html
    assert 'Stock valorizado' in html
    assert 'Auditoría de movimientos' in html
    assert 'Recepciones' in html
    assert 'Pedidos' in html


@requires_db
def test_reportes_exportaciones(client, user_consulta):
    _login(client, user_consulta)
    casos = [
        ('stock', 'csv'), ('stock', 'xlsx'), ('stock', 'json'),
        ('valorizado', 'csv'), ('valorizado', 'xlsx'), ('valorizado', 'json'),
        ('movimientos', 'csv'), ('movimientos', 'xlsx'), ('movimientos', 'json'),
        ('recepciones', 'csv'), ('recepciones', 'xlsx'),
        ('pedidos', 'csv'), ('pedidos', 'xlsx'),
    ]
    for tipo, formato in casos:
        resp = client.get(f'/reportes/exportar/{tipo}/{formato}')
        assert resp.status_code == 200, f'{tipo}/{formato} -> {resp.status_code}'
        assert resp.mimetype.startswith(('text/csv', 'application/json',
                                         'application/vnd.openxmlformats'))


@requires_db
def test_reportes_exportar_movimientos_filtrados(client, user_consulta):
    _login(client, user_consulta)
    resp = client.get('/reportes/exportar/movimientos/csv?accion=RECEPCION&desde=2020-01-01')
    assert resp.status_code == 200
    assert resp.mimetype == 'text/csv'


@requires_db
def test_auditoria_flujo_api(client, tenant_api, datos_auditoria):
    """Cerrar recepción + confirmar OMC deja el historial en stock_movimientos."""
    headers = {'Authorization': f'Bearer {tenant_api["token"]}'}
    suf = datos_auditoria['sufijo']
    tid = tenant_api['tenant_id']

    resp = client.post('/api/v1/recepciones', headers=headers, json={
        'proveedor_codigo': 'TEST-AUD-PROV-' + suf,
        'ubicacion_recep_codigo': 'TEST-AUD-RECEP-' + suf,
        'ubicacion_destino_codigo': 'TEST-AUD-DEST-' + suf,
        'items': [
            {'material_codigo': 'TEST-AUD-MAT-' + suf, 'lote': 'LOTE-AUD-1',
             'cantidad': 40, 'tipo_stock': 'Libre Venta'},
        ],
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)
    numero = resp.get_json()['numero']

    try:
        resp = client.post(f'/api/v1/recepciones/{numero}/cerrar', headers=headers, json={})
        assert resp.status_code == 200, resp.get_data(as_text=True)
        numero_omc = resp.get_json()['numero_omc']

        resp = client.post(f'/api/v1/omcs/{numero_omc}/confirmar', headers=headers, json={})
        assert resp.status_code == 200, resp.get_data(as_text=True)

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            conn.commit()
            cur.execute("""
                SELECT accion, cantidad, id_ubicacion FROM stock_movimientos
                WHERE id_material = %s AND tenant_id = %s
                ORDER BY id
            """, (datos_auditoria['id_material'], tid))
            filas = cur.fetchall()
            acciones = [f['accion'] for f in filas]
            assert acciones.count('API_RECEPCION') == 2
            assert acciones.count('API_CONFIRMAR_OMC') == 1

            for f in filas:
                if f['accion'] == 'API_RECEPCION':
                    # origen (ubicacion_recep) negativo, destino positivo
                    if f['id_ubicacion'] == datos_auditoria['id_ubic_recep']:
                        assert float(f['cantidad']) == -40
                    else:
                        assert float(f['cantidad']) == 40
                else:
                    assert float(f['cantidad']) == 40
        finally:
            cur.close()
            conn.close()
    finally:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id_recepcion FROM recepciones_cabecera WHERE numero = %s", (numero,))
        fila = cur.fetchone()
        if fila:
            id_recepcion = fila['id_recepcion']
            cur.execute("SELECT id_omc FROM omc WHERE id_recepcion = %s", (id_recepcion,))
            for omc in cur.fetchall():
                cur.execute("DELETE FROM omc_contenedores WHERE id_omc = %s", (omc['id_omc'],))
                cur.execute("DELETE FROM omc WHERE id_omc = %s", (omc['id_omc'],))
            cur.execute("DELETE FROM recepciones_detalle WHERE id_recepcion = %s", (id_recepcion,))
            cur.execute("DELETE FROM recepciones_cabecera WHERE id_recepcion = %s", (id_recepcion,))
        conn.commit()
        cur.close()
        conn.close()
