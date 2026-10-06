"""CUIT con una sola regla (modules/cuit.py) en Clientes, Transportes e Intercambio."""

import io
import uuid

import pytest

from modules.cuit import CUIT_INVALIDO, cuit_para_guardar, cuit_para_mostrar
from tests.conftest import requires_db

PREFIJO = 'ZZC'   # los códigos de prueba empiezan así, para poder limpiarlos

# Cada maestro: ruta, tabla, campo del id en el formulario y mensaje al guardar
MAESTROS = {
    'clientes': {'tabla': 'clientes', 'ok': 'Cliente guardado correctamente'},
    'transportes': {'tabla': 'transportes', 'ok': 'Transporte guardado exitosamente.'},
}


def _codigo():
    return PREFIJO + uuid.uuid4().hex[:8].upper()


@pytest.fixture
def wms(usuario_wms):
    """Conexión al WMS; al terminar borra los clientes y transportes que los tests hayan creado."""
    from modules.db_config import get_db_connection
    conn = get_db_connection()
    yield conn
    cur = conn.cursor()
    cur.execute("DELETE FROM clientes WHERE codigo LIKE %s", (PREFIJO + '%',))
    cur.execute("DELETE FROM transportes WHERE codigo LIKE %s", (PREFIJO + '%',))
    conn.commit()
    conn.close()


def _flashes(client):
    with client.session_transaction() as s:
        # sin el saludo que deja el login
        mensajes = [m for _, m in s.get('_flashes', []) if not m.startswith('Bienvenido')]
        s['_flashes'] = []
    return mensajes


def _registro(conn, tabla, codigo):
    conn.commit()  # refresca el snapshot de la transacción
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {tabla} WHERE codigo = %s", (codigo,))
    return cur.fetchone()


def _guardar(client, maestro, **datos):
    datos.setdefault('razonsocial', 'Registro de prueba')
    datos.setdefault('activo', 'on')
    client.post(f'/{maestro}/guardar', data=datos)
    return _flashes(client)


def test_helpers_del_cuit():
    assert cuit_para_guardar('30123456789') == '30-12345678-9'
    assert cuit_para_guardar('  ') is None and cuit_para_guardar(None) is None
    with pytest.raises(ValueError, match='99-99999999-9'):
        cuit_para_guardar('30-123')
    # Para mostrar: se formatea si se puede y, si no, se deja como está
    assert cuit_para_mostrar('30123456789') == '30-12345678-9'
    assert cuit_para_mostrar('EXT-555') == 'EXT-555' and cuit_para_mostrar(None) is None


@requires_db
@pytest.mark.parametrize('maestro', list(MAESTROS))
@pytest.mark.parametrize('enviado, guardado', [
    ('30-12345678-9', '30-12345678-9'),
    ('30123456789', '30-12345678-9'),   # 11 dígitos sin guiones: se guarda formateado
    ('', None),
])
def test_cuit_valido_se_guarda_con_formato(logged_client, wms, maestro, enviado, guardado):
    codigo = _codigo()
    assert _guardar(logged_client, maestro, codigo=codigo, cuit=enviado) == [MAESTROS[maestro]['ok']]
    assert _registro(wms, MAESTROS[maestro]['tabla'], codigo)['cuit'] == guardado


@requires_db
@pytest.mark.parametrize('maestro', list(MAESTROS))
@pytest.mark.parametrize('cuit', ['30-1234-9', '3012345678', 'ABC', '30 12345678 9'])
def test_cuit_invalido_se_rechaza(logged_client, wms, maestro, cuit):
    codigo = _codigo()
    assert _guardar(logged_client, maestro, codigo=codigo, cuit=cuit) == [CUIT_INVALIDO]
    assert _registro(wms, MAESTROS[maestro]['tabla'], codigo) is None


@requires_db
@pytest.mark.parametrize('maestro', list(MAESTROS))
def test_cuit_cargado_antes_sin_guiones_se_muestra_formateado(logged_client, wms, usuario_wms, maestro):
    """Transportes guardaba los 11 dígitos pelados: se tienen que ver y editar con el formato nuevo."""
    codigo = _codigo()
    cur = wms.cursor()
    cur.execute(f"INSERT INTO {MAESTROS[maestro]['tabla']} (codigo, razonsocial, cuit, tenant_id) "
                "VALUES (%s, 'Viejo', '20180039822', %s)", (codigo, usuario_wms['tenant_id']))
    wms.commit()
    html = logged_client.get(f'/{maestro}').get_data(as_text=True)
    assert '"cuit": "20-18003982-2"' in html and '"cuit": "20180039822"' not in html
    # El campo del formulario exige el formato y carga el script compartido
    assert 'pattern="\\d{2}-\\d{8}-\\d"' in html and 'data-cuit' in html and 'js/cuit.js' in html
    assert 'pattern="[0-9]{11}"' not in html


@requires_db
@pytest.mark.parametrize('maestro', list(MAESTROS))
def test_importar_valida_el_cuit(logged_client, wms, maestro):
    bueno, sin_guiones, malo = _codigo(), _codigo(), _codigo()
    csv = '\n'.join([
        'codigo,razonsocial,cuit',
        f'{bueno},Uno,30-12345678-9',
        f'{sin_guiones},Dos,30123456789',
        f'{malo},Tres,30-123',
    ])
    r = logged_client.post(f'/{maestro}/importar', data={
        'archivo': (io.BytesIO(csv.encode('utf-8')), 'datos.csv')}, content_type='multipart/form-data')
    resultado = r.get_json()
    assert resultado['insertados'] == 2, resultado
    assert [e['razon'] for e in resultado['errores']] == [CUIT_INVALIDO]
    tabla = MAESTROS[maestro]['tabla']
    assert _registro(wms, tabla, sin_guiones)['cuit'] == '30-12345678-9'
    assert _registro(wms, tabla, malo) is None


@requires_db
def test_intercambio_aplica_la_misma_regla(wms, usuario_wms):
    """Lo que llega del sistema externo se guarda con el mismo formato; un CUIT inválido deja el registro en error."""
    from modules import intercambio
    from modules.db_config import _get_admin_connection
    admin = _get_admin_connection()
    try:
        cur_admin = admin.cursor()
        cur_admin.execute("SELECT codigo FROM tenants WHERE id = %s", (usuario_wms['tenant_id'],))
        tenant_codigo = cur_admin.fetchone()['codigo']
        cur = wms.cursor()
        for aplicar, tabla in ((intercambio._aplicar_registro_transporte, 'transportes'),
                               (intercambio._aplicar_registro_cliente, 'clientes')):
            codigo = _codigo()
            reg = {'tenant_codigo': tenant_codigo, 'codigo': codigo, 'razonsocial': 'Externo', 'accion': 'alta',
                   'activo': 1, 'cuit': '30123456789'}
            aplicar(reg, wms, cur, cur_admin)
            wms.commit()
            assert _registro(wms, tabla, codigo)['cuit'] == '30-12345678-9'

            with pytest.raises(ValueError, match='99-99999999-9'):
                aplicar({**reg, 'codigo': _codigo(), 'cuit': '30-123'}, wms, cur, cur_admin)
            wms.rollback()
    finally:
        admin.close()
