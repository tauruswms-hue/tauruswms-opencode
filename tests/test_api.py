"""Test de integración de la API REST /api/v1 (Fase 5.2).

Requiere MySQL. Genera un token Bearer por tenant (hash sha256 en
taurus_admin.tenants.api_token) y verifica autenticación, consultas y el
flujo completo de recepción -> stock -> confirmación de OMC.
"""

import re
import uuid

import pytest
from conftest import DB_OK, requires_db

from modules.api import _hash_token
from modules.db_config import _get_admin_connection, get_db_connection


@pytest.fixture(scope='module')
def tenant_api():
    """Tenant activo con un token API temporal en taurus_admin."""
    if not DB_OK:
        pytest.skip('MySQL no disponible')
    token = 'api-test-' + uuid.uuid4().hex
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
def datos_api(tenant_api):
    """Material, proveedor, tipo de ubicación y 2 ubicaciones de prueba."""
    conn = get_db_connection()
    sufijo = uuid.uuid4().hex[:8]
    datos = {'sufijo': sufijo}
    try:
        cur = conn.cursor()
        tid = tenant_api['tenant_id']

        cur.execute("INSERT INTO tipoubicacion (descripcion, operacion, tenant_id) VALUES (%s, 'R', %s)",
                    ('TEST-TIPO-API-' + sufijo, tid))
        datos['id_tipo'] = cur.lastrowid

        cur.execute("""
            INSERT INTO ubicaciones (codigo, nombre, tipoubicacion, activo, tenant_id)
            VALUES (%s, %s, %s, 1, %s)
        """, ('TEST-API-RECEP-' + sufijo, 'Recepcion api', datos['id_tipo'], tid))
        datos['id_ubic_recep'] = cur.lastrowid

        cur.execute("""
            INSERT INTO ubicaciones (codigo, nombre, tipoubicacion, activo, tenant_id)
            VALUES (%s, %s, %s, 1, %s)
        """, ('TEST-API-DEST-' + sufijo, 'Destino api', datos['id_tipo'], tid))
        datos['id_ubic_dest'] = cur.lastrowid

        cur.execute("""
            INSERT INTO proveedores (codigo, razonsocial, activo, tenant_id)
            VALUES (%s, %s, 1, %s)
        """, ('TEST-API-PROV-' + sufijo, 'Proveedor api', tid))
        datos['id_proveedor'] = cur.lastrowid

        cur.execute("""
            INSERT INTO materiales (codigo, codigo_barras, nombre, trazabilidad,
                                    metodo_picking, activo, tenant_id)
            VALUES (%s, %s, %s, 'lote', 'fifo', 1, %s)
        """, ('TEST-API-MAT-' + sufijo, '899999999999' + sufijo[-4:],
              'Material api', tid))
        datos['id_material'] = cur.lastrowid
        datos['barcode'] = '899999999999' + sufijo[-4:]

        cur.execute("""
            INSERT INTO material_proveedor (id_material, id_proveedor, codigo_referencia_prov, es_habitual, tenant_id)
            VALUES (%s, %s, %s, 1, %s)
        """, (datos['id_material'], datos['id_proveedor'],
              'REF-API-' + sufijo, tid))

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


def _auth(token):
    return {'Authorization': f'Bearer {token}'}


@requires_db
def test_api_autenticacion(client, tenant_api):
    # Sin header -> 401
    resp = client.get('/api/v1/materiales')
    assert resp.status_code == 401

    # Token inválido -> 401
    resp = client.get('/api/v1/materiales', headers=_auth('token-invalido'))
    assert resp.status_code == 401

    # Token válido -> 200
    resp = client.get('/api/v1/materiales', headers=_auth(tenant_api['token']))
    assert resp.status_code == 200
    assert resp.get_json()['ok'] is True


@requires_db
def test_api_consultas(client, tenant_api, datos_api):
    headers = _auth(tenant_api['token'])

    resp = client.get('/api/v1/materiales', headers=headers)
    assert resp.status_code == 200
    codigos = [m['codigo'] for m in resp.get_json()['items']]
    assert datos_api['sufijo'] and any(c == 'TEST-API-MAT-' + datos_api['sufijo'] for c in codigos)

    resp = client.get('/api/v1/materiales/TEST-API-MAT-' + datos_api['sufijo'], headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()['material']['id'] == datos_api['id_material']

    # Por código de barras
    resp = client.get('/api/v1/materiales/' + datos_api['barcode'], headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()['material']['id'] == datos_api['id_material']

    # No encontrado
    resp = client.get('/api/v1/materiales/NO-EXISTE-' + datos_api['sufijo'], headers=headers)
    assert resp.status_code == 404

    resp = client.get('/api/v1/ubicaciones', headers=headers)
    assert resp.status_code == 200
    ubi_codigos = [u['codigo'] for u in resp.get_json()['items']]
    assert 'TEST-API-RECEP-' + datos_api['sufijo'] in ubi_codigos
    assert 'TEST-API-DEST-' + datos_api['sufijo'] in ubi_codigos

    resp = client.get('/api/v1/stock', headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()['ok'] is True

    resp = client.get('/api/v1/recepciones', headers=headers)
    assert resp.status_code == 200
    resp = client.get('/api/v1/pedidos', headers=headers)
    assert resp.status_code == 200
    resp = client.get('/api/v1/omcs', headers=headers)
    assert resp.status_code == 200


@requires_db
def test_api_flujo_recepcion_stock(client, tenant_api, datos_api):
    headers = _auth(tenant_api['token'])
    suf = datos_api['sufijo']
    tid = tenant_api['tenant_id']

    # Alta de recepción con ítems
    resp = client.post('/api/v1/recepciones', headers=headers, json={
        'proveedor_codigo': 'TEST-API-PROV-' + suf,
        'ubicacion_recep_codigo': 'TEST-API-RECEP-' + suf,
        'ubicacion_destino_codigo': 'TEST-API-DEST-' + suf,
        'observaciones': 'creada por API',
        'items': [
            {'material_codigo': 'TEST-API-MAT-' + suf, 'lote': 'LOTE-API-1',
             'cantidad': 50, 'tipo_stock': 'Libre Venta'},
            {'material_codigo': 'TEST-API-MAT-' + suf, 'lote': 'LOTE-API-2',
             'cantidad': 25},
        ],
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data['ok'] is True
    numero = data['numero']
    assert numero.startswith('REC-')
    id_recepcion = data['id_recepcion']

    try:
        # Detalle
        resp = client.get(f'/api/v1/recepciones/{numero}', headers=headers)
        assert resp.status_code == 200
        rec = resp.get_json()['recepcion']
        assert rec['numero'] == numero
        assert len(rec['items']) == 2
        assert rec['proveedor_codigo'] == 'TEST-API-PROV-' + suf

        # Agregar otro ítem
        resp = client.post(f'/api/v1/recepciones/{numero}/agregar-item', headers=headers, json={
            'material_codigo': 'TEST-API-MAT-' + suf,
            'lote': 'LOTE-API-3',
            'cantidad': 10,
        })
        assert resp.status_code == 200
        assert resp.get_json()['ok'] is True

        # Cerrar -> genera stock (Saliendo/Entrando) + OMC
        resp = client.post(f'/api/v1/recepciones/{numero}/cerrar', headers=headers, json={})
        assert resp.status_code == 200, resp.get_data(as_text=True)
        data = resp.get_json()
        assert data['ok'] is True
        numero_omc = data['numero_omc']
        assert numero_omc.startswith('OMC-')
        assert data['items'] == 3

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT StockSaliendo FROM stockcontable
                WHERE Ubicacion = %s AND Material = %s AND tenant_id = %s
            """, (datos_api['id_ubic_recep'], datos_api['id_material'], tid))
            assert cur.fetchone()['StockSaliendo'] == 85

            cur.execute("""
                SELECT StockEntrando FROM stockcontable
                WHERE Ubicacion = %s AND Material = %s AND tenant_id = %s
            """, (datos_api['id_ubic_dest'], datos_api['id_material'], tid))
            assert cur.fetchone()['StockEntrando'] == 85

            # OMC listada como Pendiente
            resp = client.get('/api/v1/omcs?estado=Pendiente', headers=headers)
            assert resp.status_code == 200
            nums = [o['numero'] for o in resp.get_json()['items']]
            assert numero_omc in nums

            # Confirmar OMC -> Entrando a Disponible
            resp = client.post(f'/api/v1/omcs/{numero_omc}/confirmar', headers=headers, json={})
            assert resp.status_code == 200, resp.get_data(as_text=True)
            assert resp.get_json()['filas_stock'] >= 1

            conn.commit()
            cur.execute("""
                SELECT StockDisponible, StockEntrando FROM stockcontable
                WHERE Ubicacion = %s AND Material = %s AND tenant_id = %s
            """, (datos_api['id_ubic_dest'], datos_api['id_material'], tid))
            fila = cur.fetchone()
            assert fila['StockDisponible'] == 85
            assert fila['StockEntrando'] == 0

            cur.execute("SELECT estado FROM omc WHERE numero = %s", (numero_omc,))
            assert cur.fetchone()['estado'].upper() == 'CONFIRMADA'
        finally:
            cur.close()
            conn.close()
    finally:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM stockcontable WHERE Material = %s AND tenant_id = %s",
                    (datos_api['id_material'], tid))
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


@requires_db
def test_api_validaciones(client, tenant_api, datos_api):
    headers = _auth(tenant_api['token'])
    suf = datos_api['sufijo']

    # Falta proveedor
    resp = client.post('/api/v1/recepciones', headers=headers, json={
        'ubicacion_recep_codigo': 'TEST-API-RECEP-' + suf,
        'items': [],
    })
    assert resp.status_code == 400

    # Proveedor inexistente
    resp = client.post('/api/v1/recepciones', headers=headers, json={
        'proveedor_codigo': 'NO-EXISTE-' + suf,
        'ubicacion_recep_codigo': 'TEST-API-RECEP-' + suf,
        'items': [],
    })
    assert resp.status_code == 404

    # Material inexistente en los ítems
    resp = client.post('/api/v1/recepciones', headers=headers, json={
        'proveedor_codigo': 'TEST-API-PROV-' + suf,
        'ubicacion_recep_codigo': 'TEST-API-RECEP-' + suf,
        'items': [{'material_codigo': 'NO-EXISTE-' + suf, 'cantidad': 10}],
    })
    assert resp.status_code == 400

    # Cerrar recepción inexistente
    resp = client.post('/api/v1/recepciones/REC-9999-00000/cerrar', headers=headers, json={})
    assert resp.status_code == 404


@requires_db
def test_api_token_desde_admin(admin_client, client, tenant_api, usuario_panel):
    tid = tenant_api['tenant_id']

    resp = admin_client.post('/admin/login', data={
        'username': usuario_panel['username'], 'password': usuario_panel['password'],
    })
    assert resp.status_code in (302, 200)

    resp = admin_client.get(f'/admin/parametros/editar/{tid}')
    assert resp.status_code == 200

    resp = admin_client.post(f'/admin/parametros/{tid}/api-token', follow_redirects=True)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    m = re.search(r'&lt;strong&gt;([A-Za-z0-9_-]{20,})&lt;/strong&gt;', html)
    if not m:
        m = re.search(r'<strong>([A-Za-z0-9_-]{20,})</strong>', html)
    assert m, 'No se encontro el token en el flash del panel admin'
    token = m.group(1)

    # El token generado en el admin funciona contra la API del WMS
    resp = client.get('/api/v1/materiales', headers=_auth(token))
    assert resp.status_code == 200
    assert resp.get_json()['ok'] is True
