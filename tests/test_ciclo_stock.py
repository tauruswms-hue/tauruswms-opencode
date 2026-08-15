"""Test de integración del ciclo de stock (Fase 2.3).

Flujo HTTP: crear material/proveedor/ubicaciones -> recepcion -> guardar_item
-> cerrar (genera OMC + StockEntrando) -> confirmar_stock (StockDisponible).
Requiere MySQL. Crea y limpia todos los datos de prueba.
"""

import uuid

import pytest
from conftest import DB_OK, requires_db
from werkzeug.security import generate_password_hash

from modules.db_config import _get_admin_connection, get_db_connection


@pytest.fixture(scope='module')
def usuario_superadmin():
    """Crea un usuario SUPERADMIN temporal en taurus_admin."""
    if not DB_OK:
        pytest.skip('MySQL no disponible')
    username = 'teststock' + uuid.uuid4().hex[:8]
    conn = _get_admin_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM tenants WHERE activo = 1 ORDER BY id LIMIT 1")
        tid = cur.fetchone()['id']
        cur.execute("""
            INSERT INTO usuarios (username, password_hash, nombre, rol, tenant_id, activo)
            VALUES (%s, %s, %s, 'SUPERADMIN', %s, 1)
        """, (username, generate_password_hash('Test@2024!'), 'Test stock', tid))
        conn.commit()
        yield {'username': username, 'password': 'Test@2024!', 'tenant_id': tid}
    finally:
        cur = conn.cursor()
        cur.execute("DELETE FROM usuarios WHERE username = %s", (username,))
        conn.commit()
        conn.close()


@pytest.fixture
def datos_stock(usuario_superadmin):
    """Crea material, proveedor, tipo ubicacion y 2 ubicaciones de prueba."""
    conn = get_db_connection()
    sufijo = uuid.uuid4().hex[:8]
    datos = {'sufijo': sufijo}
    try:
        cur = conn.cursor()
        tid = usuario_superadmin['tenant_id']

        cur.execute("INSERT INTO tipoubicacion (descripcion, operacion, tenant_id) VALUES (%s, 'R', %s)",
                    ('TEST-TIPO-' + sufijo, tid))
        datos['id_tipo'] = cur.lastrowid

        cur.execute("""
            INSERT INTO ubicaciones (codigo, nombre, tipoubicacion, activo, tenant_id)
            VALUES (%s, %s, %s, 1, %s)
        """, ('TEST-UB-ORIG-' + sufijo, 'Origen test', datos['id_tipo'], tid))
        datos['id_ubic_recep'] = cur.lastrowid

        cur.execute("""
            INSERT INTO ubicaciones (codigo, nombre, tipoubicacion, activo, tenant_id)
            VALUES (%s, %s, %s, 1, %s)
        """, ('TEST-UB-DEST-' + sufijo, 'Destino test', datos['id_tipo'], tid))
        datos['id_ubic_dest'] = cur.lastrowid

        cur.execute("""
            INSERT INTO proveedores (codigo, razonsocial, activo, tenant_id)
            VALUES (%s, %s, 1, %s)
        """, ('TEST-PROV-' + sufijo, 'Proveedor test', tid))
        datos['id_proveedor'] = cur.lastrowid

        cur.execute("""
            INSERT INTO materiales (codigo, nombre, trazabilidad, metodo_picking, activo, tenant_id)
            VALUES (%s, %s, 'lote', 'fifo', 1, %s)
        """, ('TEST-MAT-' + sufijo, 'Material ciclo stock', tid))
        datos['id_material'] = cur.lastrowid

        datos['tenant_id'] = tid
        conn.commit()
        yield datos
    finally:
        cur = conn.cursor()
        tid = datos.get('tenant_id')
        if datos.get('id_material'):
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


@requires_db
def test_ciclo_stock_recepcion_confirmacion(client, usuario_superadmin, datos_stock):
    """Recepción -> item -> cerrar (OMC) -> confirmar -> stock disponible."""
    resp = client.post('/login', data={
        'username': usuario_superadmin['username'],
        'password': usuario_superadmin['password'],
    })
    assert resp.status_code in (302, 200)

    # crear recepcion
    resp = client.post('/recepciones/guardar', data={
        'id_ubicacion_recep': datos_stock['id_ubic_recep'],
        'id_ubicacion_destino': datos_stock['id_ubic_dest'],
        'id_proveedor': datos_stock['id_proveedor'],
        'observaciones': 'test ciclo stock',
    }, follow_redirects=True)
    assert resp.status_code == 200
    # extraer id_recepcion de la URL de la respuesta (ultima redirect /recepciones/ver/<id>)
    import re
    html = resp.get_data(as_text=True)
    re.search(r'/recepciones/ver/(\d+)', html)
    # no se puede extraer del body; buscar en history de la respuesta
    id_recepcion = None
    for h in resp.history:
        mm = re.search(r'/recepciones/ver/(\d+)', h.headers.get('Location', ''))
        if mm:
            id_recepcion = int(mm.group(1))
            break
    assert id_recepcion, 'No se encontro id_recepcion'

    try:
        # guardar_item (AJAX json)
        resp = client.post('/recepciones/guardar_item', json={
            'id_recepcion': id_recepcion,
            'id_material': datos_stock['id_material'],
            'lote': 'LOTE-TEST',
            'cantidad_esperada': 100,
            'cantidad_recibida': 100,
            'tipo_stock': 'Libre Venta',
        })
        assert resp.get_json()['ok'] is True

        # cerrar -> genera OMC + StockEntrando en destino
        resp = client.post(f'/recepciones/cerrar/{id_recepcion}', data={
            'id_ubicacion_destino': datos_stock['id_ubic_dest'],
        }, follow_redirects=True)
        assert resp.status_code == 200

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT StockEntrando FROM stockcontable
                WHERE Ubicacion = %s AND Material = %s AND tenant_id = %s
            """, (datos_stock['id_ubic_dest'], datos_stock['id_material'],
                  datos_stock['tenant_id']))
            fila = cur.fetchone()
            assert fila, 'No hay StockEntrando tras cerrar la recepcion'
            assert fila['StockEntrando'] == 100

            cur.execute("SELECT id_omc FROM omc WHERE id_recepcion = %s AND tenant_id = %s",
                        (id_recepcion, datos_stock['tenant_id']))
            omc = cur.fetchone()
            assert omc, 'No se genero OMC al cerrar la recepcion'
        finally:
            cur.close()
            conn.close()

        # confirmar stock -> pasa a Disponible
        resp = client.post(f'/recepciones/confirmar_stock/{id_recepcion}',
                           follow_redirects=True)
        assert resp.status_code == 200

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT StockDisponible, StockEntrando FROM stockcontable
                WHERE Ubicacion = %s AND Material = %s AND tenant_id = %s
            """, (datos_stock['id_ubic_dest'], datos_stock['id_material'],
                  datos_stock['tenant_id']))
            fila = cur.fetchone()
            assert fila, 'No hay registro de stock tras confirmar'
            assert fila['StockDisponible'] == 100
            assert fila['StockEntrando'] == 0
        finally:
            cur.close()
            conn.close()
    finally:
        # limpieza de stockcontable, omc y recepcion
        conn = get_db_connection()
        cur = conn.cursor()
        tid = datos_stock['tenant_id']
        cur.execute("DELETE FROM stockcontable WHERE Material = %s AND tenant_id = %s",
                    (datos_stock['id_material'], tid))
        cur.execute("SELECT id_omc FROM omc WHERE id_recepcion = %s AND tenant_id = %s",
                    (id_recepcion, tid))
        for omc in cur.fetchall():
            cur.execute("DELETE FROM omc_contenedores WHERE id_omc = %s", (omc['id_omc'],))
        cur.execute("DELETE FROM omc WHERE id_recepcion = %s AND tenant_id = %s",
                    (id_recepcion, tid))
        cur.execute("DELETE FROM recepciones_detalle WHERE id_recepcion = %s AND tenant_id = %s",
                    (id_recepcion, tid))
        cur.execute("DELETE FROM recepciones_cabecera WHERE id_recepcion = %s AND tenant_id = %s",
                    (id_recepcion, tid))
        conn.commit()
        cur.close()
        conn.close()
