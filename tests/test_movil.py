"""Test de integración del módulo móvil (Fase 5.1).

Flujo HTTP móvil: login ADMIN -> /movil (hub) -> crear recepción -> detalle ->
buscar por código -> agregar ítem -> cerrar (genera OMC) -> picking ->
confirmar OMC (stock disponible). Requiere MySQL. Crea y limpia los datos.
"""

import re
import uuid

import pytest
from conftest import DB_OK, requires_db
from werkzeug.security import generate_password_hash

from modules.db_config import _get_admin_connection, get_db_connection


@pytest.fixture(scope='module')
def usuario_admin_movil():
    """Usuario ADMIN temporal en taurus_admin (rol ADMIN = acceso total)."""
    if not DB_OK:
        pytest.skip('MySQL no disponible')
    username = 'testmovil' + uuid.uuid4().hex[:8]
    conn = _get_admin_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM tenants WHERE activo = 1 ORDER BY id LIMIT 1")
        tid = cur.fetchone()['id']
        cur.execute("""
            INSERT INTO usuarios (username, password_hash, nombre, rol, tenant_id, activo)
            VALUES (%s, %s, %s, 'ADMIN', %s, 1)
        """, (username, generate_password_hash('Test@2024!'), 'Test movil', tid))
        conn.commit()
        yield {'username': username, 'password': 'Test@2024!', 'tenant_id': tid}
    finally:
        cur = conn.cursor()
        cur.execute("DELETE FROM usuarios WHERE username = %s", (username,))
        conn.commit()
        conn.close()


@pytest.fixture
def datos_movil(usuario_admin_movil):
    """Material, proveedor, tipo de ubicación y 2 ubicaciones de prueba."""
    conn = get_db_connection()
    sufijo = uuid.uuid4().hex[:8]
    datos = {'sufijo': sufijo}
    try:
        cur = conn.cursor()
        tid = usuario_admin_movil['tenant_id']

        cur.execute("INSERT INTO tipoubicacion (descripcion, operacion, tenant_id) VALUES (%s, 'R', %s)",
                    ('TEST-TIPO-MOVIL-' + sufijo, tid))
        datos['id_tipo'] = cur.lastrowid

        cur.execute("""
            INSERT INTO ubicaciones (codigo, nombre, tipoubicacion, activo, tenant_id)
            VALUES (%s, %s, %s, 1, %s)
        """, ('TEST-MOVIL-RECEP-' + sufijo, 'Recepcion movil', datos['id_tipo'], tid))
        datos['id_ubic_recep'] = cur.lastrowid

        cur.execute("""
            INSERT INTO ubicaciones (codigo, nombre, tipoubicacion, activo, tenant_id)
            VALUES (%s, %s, %s, 1, %s)
        """, ('TEST-MOVIL-DEST-' + sufijo, 'Destino movil', datos['id_tipo'], tid))
        datos['id_ubic_dest'] = cur.lastrowid

        cur.execute("""
            INSERT INTO proveedores (codigo, razonsocial, activo, tenant_id)
            VALUES (%s, %s, 1, %s)
        """, ('TEST-MOVIL-PROV-' + sufijo, 'Proveedor movil', tid))
        datos['id_proveedor'] = cur.lastrowid

        cur.execute("""
            INSERT INTO materiales (codigo, codigo_barras, nombre, trazabilidad,
                                    metodo_picking, activo, tenant_id)
            VALUES (%s, %s, %s, 'lote', 'fifo', 1, %s)
        """, ('TEST-MOVIL-MAT-' + sufijo, '890000000000' + sufijo[-4:],
              'Material movil', tid))
        datos['id_material'] = cur.lastrowid
        datos['barcode'] = '890000000000' + sufijo[-4:]

        cur.execute("""
            INSERT INTO material_proveedor (id_material, id_proveedor, codigo_referencia_prov, es_habitual, tenant_id)
            VALUES (%s, %s, %s, 1, %s)
        """, (datos['id_material'], datos['id_proveedor'],
              'REF-' + sufijo, tid))

        datos['tenant_id'] = tid
        conn.commit()
        yield datos
    finally:
        cur = conn.cursor()
        tid = datos.get('tenant_id')
        if datos.get('id_material'):
            cur.execute("DELETE FROM material_proveedor WHERE id_material = %s", (datos['id_material'],))
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


def _crear_recepcion_movil(client, datos):
    resp = client.post('/movil/recepcion/guardar', data={
        'id_proveedor': datos['id_proveedor'],
        'id_ubicacion_recep': datos['id_ubic_recep'],
        'observaciones': 'test movil',
    }, follow_redirects=True)
    assert resp.status_code == 200
    for h in resp.history:
        mm = re.search(r'/movil/recepcion/(\d+)$', h.headers.get('Location', ''))
        if mm:
            return int(mm.group(1))
    raise AssertionError('No se encontro id_recepcion en la redireccion')


@requires_db
def test_movil_hub_y_recepcion(client, usuario_admin_movil, datos_movil):
    resp = client.post('/login', data={
        'username': usuario_admin_movil['username'],
        'password': usuario_admin_movil['password'],
    })
    assert resp.status_code in (302, 200)

    # Hub
    resp = client.get('/movil')
    assert resp.status_code == 200

    # Lista de recepciones
    resp = client.get('/movil/recepcion')
    assert resp.status_code == 200

    # Crear recepción desde el módulo móvil
    id_recepcion = _crear_recepcion_movil(client, datos_movil)

    try:
        # Detalle
        resp = client.get(f'/movil/recepcion/{id_recepcion}')
        assert resp.status_code == 200

        # Búsqueda por código de barras (código del material)
        resp = client.get(
            f'/movil/recepcion/{id_recepcion}/buscar',
            query_string={'barcode': datos_movil['barcode']},
        )
        assert resp.status_code == 200
        mat = resp.get_json()
        assert mat and mat.get('id') == datos_movil['id_material']

        # Agregar ítem
        resp = client.post(f'/movil/recepcion/{id_recepcion}/agregar', json={
            'id_material': datos_movil['id_material'],
            'lote': 'LOTE-MOVIL',
            'cantidad': 50,
            'tipo_stock': 'Libre Venta',
        })
        assert resp.get_json()['ok'] is True

        # Inventario móvil
        resp = client.get('/movil/inventario')
        assert resp.status_code == 200
        resp = client.get('/movil/inventario/buscar', query_string={'q': datos_movil['barcode']})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['ok'] is True and data['material']['id'] == datos_movil['id_material']

        # Cerrar recepción -> OMC
        resp = client.post(f'/movil/recepcion/{id_recepcion}/cerrar', data={
            'id_ubicacion_destino': datos_movil['id_ubic_dest'],
        }, follow_redirects=True)
        assert resp.status_code == 200

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT id_omc FROM omc WHERE id_recepcion = %s AND tenant_id = %s",
                        (id_recepcion, datos_movil['tenant_id']))
            omc = cur.fetchone()
            assert omc, 'No se genero OMC al cerrar desde movil'
            id_omc = omc['id_omc']

            # Picking: lista y detalle
            resp = client.get('/movil/picking')
            assert resp.status_code == 200
            resp = client.get(f'/movil/picking/{id_omc}')
            assert resp.status_code == 200

            # Confirmar OMC con contraseña incorrecta -> sigue Pendiente
            resp = client.post(f'/movil/picking/{id_omc}/confirmar', data={
                'password_admin': 'password-incorrecta',
            }, follow_redirects=True)
            assert resp.status_code == 200
            cur.execute("SELECT estado FROM omc WHERE id_omc = %s", (id_omc,))
            assert cur.fetchone()['estado'].upper() == 'PENDIENTE'

            # Confirmar OMC con la contraseña correcta
            resp = client.post(f'/movil/picking/{id_omc}/confirmar', data={
                'password_admin': usuario_admin_movil['password'],
            }, follow_redirects=True)
            assert resp.status_code == 200
            conn.commit()
            cur.execute("SELECT estado FROM omc WHERE id_omc = %s", (id_omc,))
            assert cur.fetchone()['estado'].upper() == 'CONFIRMADA'

            # Stock disponible en destino
            cur.execute("""
                SELECT StockDisponible, StockEntrando FROM stockcontable
                WHERE Ubicacion = %s AND Material = %s AND tenant_id = %s
            """, (datos_movil['id_ubic_dest'], datos_movil['id_material'],
                  datos_movil['tenant_id']))
            fila = cur.fetchone()
            assert fila, 'No hay stock en destino tras confirmar OMC movil'
            assert fila['StockDisponible'] == 50
            assert fila['StockEntrando'] == 0
        finally:
            cur.close()
            conn.close()
    finally:
        conn = get_db_connection()
        cur = conn.cursor()
        tid = datos_movil['tenant_id']
        cur.execute("DELETE FROM stockcontable WHERE Material = %s AND tenant_id = %s",
                    (datos_movil['id_material'], tid))
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
