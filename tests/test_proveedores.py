"""Proveedores: formato del CUIT y largo de la dirección."""

import io
import uuid

import pytest

from modules.cuit import normalizar_cuit
from tests.conftest import requires_db

PREFIJO = 'ZZP'   # los códigos de prueba empiezan así, para poder limpiarlos


def _codigo():
    return PREFIJO + uuid.uuid4().hex[:8].upper()


@pytest.fixture
def wms(usuario_wms):
    """Conexión al WMS; al terminar borra los proveedores que los tests hayan creado."""
    from modules.db_config import get_db_connection
    conn = get_db_connection()
    yield conn
    cur = conn.cursor()
    cur.execute("DELETE FROM proveedores WHERE codigo LIKE %s", (PREFIJO + '%',))
    conn.commit()
    conn.close()


def _flashes(client):
    with client.session_transaction() as s:
        # sin el saludo que deja el login
        mensajes = [m for _, m in s.get('_flashes', []) if not m.startswith('Bienvenido')]
        s['_flashes'] = []
    return mensajes


def _proveedor(conn, codigo):
    conn.commit()  # refresca el snapshot de la transacción
    cur = conn.cursor()
    cur.execute("SELECT * FROM proveedores WHERE codigo = %s", (codigo,))
    return cur.fetchone()


def _guardar(client, **datos):
    datos.setdefault('razonsocial', 'Proveedor de prueba')
    client.post('/proveedores/guardar', data=datos)
    return _flashes(client)


@pytest.mark.parametrize('valor, esperado', [
    ('30-12345678-9', '30-12345678-9'),
    (' 30-12345678-9 ', '30-12345678-9'),
    ('30123456789', '30-12345678-9'),
    ('', ''),
    (None, ''),
    ('30-1234567-9', None),
    ('3012345678', None),
    ('30.12345678.9', None),
    ('AA-12345678-9', None),
])
def test_normalizar_cuit(valor, esperado):
    assert normalizar_cuit(valor) == esperado


@requires_db
@pytest.mark.parametrize('enviado, guardado', [
    ('30-12345678-9', '30-12345678-9'),
    ('30123456789', '30-12345678-9'),   # 11 dígitos sin guiones: se guarda formateado
    ('', None),                          # el CUIT es opcional
])
def test_cuit_valido_se_guarda_con_formato(logged_client, wms, enviado, guardado):
    codigo = _codigo()
    assert _guardar(logged_client, codigo=codigo, cuit=enviado) == ['Proveedor guardado correctamente']
    assert _proveedor(wms, codigo)['cuit'] == guardado


@requires_db
@pytest.mark.parametrize('cuit', ['30-1234-9', '3012345678', 'ABC', '30-12345678-99'])
def test_cuit_invalido_se_rechaza(logged_client, wms, cuit):
    codigo = _codigo()
    assert _guardar(logged_client, codigo=codigo, cuit=cuit) == ['CUIT inválido: debe tener el formato 99-99999999-9.']
    assert _proveedor(wms, codigo) is None


@requires_db
def test_cuit_cargado_antes_sin_guiones_se_muestra_formateado(logged_client, wms, usuario_wms):
    codigo = _codigo()
    cur = wms.cursor()
    cur.execute("INSERT INTO proveedores (codigo, razonsocial, cuit, tenant_id) VALUES (%s, 'Viejo', '20180039822', %s)",
                (codigo, usuario_wms['tenant_id']))
    wms.commit()
    html = logged_client.get('/proveedores').get_data(as_text=True)
    fila = html[html.index(f'<code>{codigo}</code>'):]
    fila = fila[:fila.index('</tr>')]
    assert '<td>20-18003982-2</td>' in fila and '"cuit": "20-18003982-2"' in fila
    # El campo del formulario exige el formato
    assert 'pattern="\\d{2}-\\d{8}-\\d"' in html and 'placeholder="99-99999999-9"' in html


@requires_db
def test_direccion_admite_500_caracteres(logged_client, wms):
    from modules.proveedores import DIRECCION_MAX
    assert DIRECCION_MAX == 500
    codigo, larga = _codigo(), 'Av. Siempre Viva 742, ' * 22   # 484 caracteres: antes el límite era 255
    assert len(larga.strip()) > 255
    assert _guardar(logged_client, codigo=codigo, direccion=larga) == ['Proveedor guardado correctamente']
    assert _proveedor(wms, codigo)['direccion'] == larga.strip()

    otro = _codigo()
    assert _guardar(logged_client, codigo=otro, direccion='x' * 501) == [
        'Dirección: admite hasta 500 caracteres (tiene 501).']
    assert _proveedor(wms, otro) is None
    assert f'maxlength="{DIRECCION_MAX}"' in logged_client.get('/proveedores').get_data(as_text=True)


@requires_db
def test_importar_valida_cuit_y_direccion(logged_client, wms):
    bueno, sin_guiones, malo, largo = _codigo(), _codigo(), _codigo(), _codigo()
    csv = '\n'.join([
        'codigo,razonsocial,cuit,direccion',
        f'{bueno},Uno,30-12345678-9,Calle 1',
        f'{sin_guiones},Dos,30123456789,',
        f'{malo},Tres,30-123,',
        f'{largo},Cuatro,,{"x" * 501}',
    ])
    r = logged_client.post('/proveedores/importar', data={
        'archivo': (io.BytesIO(csv.encode('utf-8')), 'proveedores.csv')}, content_type='multipart/form-data')
    resultado = r.get_json()
    assert resultado['insertados'] == 2
    assert sorted(e['razon'] for e in resultado['errores']) == [
        'CUIT inválido: debe tener el formato 99-99999999-9.',
        'Dirección: admite hasta 500 caracteres (tiene 501).']
    assert _proveedor(wms, sin_guiones)['cuit'] == '30-12345678-9'
    assert _proveedor(wms, malo) is None and _proveedor(wms, largo) is None


def test_el_filtro_datetime_del_panel_formatea_fechas():
    """El filtro 'datetime' había quedado asociado por error a la función del CUIT."""
    import datetime

    import admin
    filtro = admin.app.jinja_env.filters['datetime']
    assert filtro(datetime.datetime(2026, 1, 2, 3, 4)) == '02/01/2026 03:04'
    assert filtro(None) == '-'
