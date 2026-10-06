"""Clientes: nombre de fantasía, sitio web, mail principal, domicilio y estado."""

import io
import uuid

import pytest

from tests.conftest import requires_db

PREFIJO = 'ZZK'   # los códigos de prueba empiezan así, para poder limpiarlos
EJEMPLO = 'Cliente de Ejemplo S.A.'   # razón social de la fila de ejemplo de la plantilla


def _codigo():
    return PREFIJO + uuid.uuid4().hex[:8].upper()


@pytest.fixture
def wms(usuario_wms):
    """Conexión al WMS; al terminar borra los clientes que los tests hayan creado."""
    from modules.db_config import get_db_connection
    conn = get_db_connection()
    yield conn
    cur = conn.cursor()
    # El CLI001 de la plantilla se borra solo si es el de ejemplo, por si existe un cliente real con ese código
    cur.execute("DELETE FROM clientes WHERE codigo LIKE %s OR (codigo = 'CLI001' AND razonsocial = %s)",
                (PREFIJO + '%', EJEMPLO))
    conn.commit()
    conn.close()


def _flashes(client):
    with client.session_transaction() as s:
        # sin el saludo que deja el login
        mensajes = [m for _, m in s.get('_flashes', []) if not m.startswith('Bienvenido')]
        s['_flashes'] = []
    return mensajes


def _cliente(conn, codigo):
    conn.commit()  # refresca el snapshot de la transacción
    cur = conn.cursor()
    cur.execute("SELECT * FROM clientes WHERE codigo = %s", (codigo,))
    return cur.fetchone()


def _guardar(client, **datos):
    datos.setdefault('razonsocial', 'Cliente de prueba S.A.')
    client.post('/clientes/guardar', data=datos)
    return _flashes(client)


@requires_db
def test_alta_con_todos_los_datos(logged_client, wms):
    codigo = _codigo()
    assert _guardar(logged_client, codigo=codigo, nombre_fantasia=' El Almacén ', sitio_web='www.elalmacen.com.ar',
                    email='ventas@elalmacen.com.ar', direccion='Av. Siempre Viva 742', contacto_nombre='Ana Pérez',
                    activo='1') == ['Cliente guardado correctamente']
    c = _cliente(wms, codigo)
    assert c['nombre_fantasia'] == 'El Almacén'
    assert c['sitio_web'] == 'https://www.elalmacen.com.ar'     # sin protocolo, se completa con https://
    assert c['email'] == 'ventas@elalmacen.com.ar' and c['direccion'] == 'Av. Siempre Viva 742'
    assert c['contacto_nombre'] == 'Ana Pérez' and c['activo']

    html = logged_client.get('/clientes').get_data(as_text=True)
    fila = html[html.index(f'<code>{codigo}</code>'):]
    fila = fila[:fila.index('</tr>')]
    assert 'El Almacén' in fila and 'href="https://www.elalmacen.com.ar"' in fila
    assert 'href="mailto:ventas@elalmacen.com.ar"' in fila and 'Activo</span>' in fila
    # El formulario tiene los campos con los rótulos pedidos
    for rotulo in ('Nombre de Fantasía', 'Sitio Web', 'Mail principal', 'Domicilio', 'Estado'):
        assert f'>{rotulo}</label>' in html
    lista = html[html.index('id="form_activo"'):]
    lista = lista[:lista.index('</select>')]
    assert '<option value="1">Activo</option>' in lista and '<option value="0">Inactivo</option>' in lista


@requires_db
def test_estado_activo_o_inactivo(logged_client, wms):
    activo, inactivo, sin_estado = _codigo(), _codigo(), _codigo()
    _guardar(logged_client, codigo=activo, activo='1')
    _guardar(logged_client, codigo=inactivo, activo='0')     # se puede dar de alta ya inactivo
    _guardar(logged_client, codigo=sin_estado)                # sin indicarlo, nace activo
    assert _cliente(wms, activo)['activo'] and _cliente(wms, sin_estado)['activo']
    assert not _cliente(wms, inactivo)['activo']

    # Cambiar el estado al editar, en los dos sentidos
    cid = _cliente(wms, inactivo)['id_cliente']
    _guardar(logged_client, id_cliente=cid, codigo=inactivo, activo='1')
    assert _cliente(wms, inactivo)['activo']
    _guardar(logged_client, id_cliente=cid, codigo=inactivo, activo='0')
    assert not _cliente(wms, inactivo)['activo']
    fila = logged_client.get('/clientes').get_data(as_text=True)
    fila = fila[fila.index(f'<code>{inactivo}</code>'):]
    assert 'Inactivo</span>' in fila[:fila.index('</tr>')]


@requires_db
def test_editar_conserva_el_contacto(logged_client, wms):
    """El formulario no tenía el campo de contacto y al guardar lo borraba."""
    codigo = _codigo()
    _guardar(logged_client, codigo=codigo, contacto_nombre='Juan')
    html = logged_client.get('/clientes').get_data(as_text=True)
    assert 'name="contacto_nombre"' in html and '"contacto_nombre": "Juan"' in html


@requires_db
@pytest.mark.parametrize('datos, mensaje', [
    ({'sitio_web': 'no es una web'}, 'Sitio web: tiene que ser una dirección web, por ejemplo www.empresa.com.'),
    ({'sitio_web': 'ftp://empresa.com'}, 'Sitio web: tiene que ser una dirección web, por ejemplo www.empresa.com.'),
    ({'sitio_web': 'javascript:alert(1)'}, 'Sitio web: tiene que ser una dirección web, por ejemplo www.empresa.com.'),
    ({'email': 'sin-arroba'}, 'Mail principal: no tiene formato de dirección de correo.'),
    ({'nombre_fantasia': 'x' * 201}, 'Nombre de fantasía: admite hasta 200 caracteres.'),
    ({'direccion': 'x' * 256}, 'Domicilio: admite hasta 255 caracteres.'),
])
def test_datos_invalidos_no_se_guardan(logged_client, wms, datos, mensaje):
    codigo = _codigo()
    assert _guardar(logged_client, codigo=codigo, **datos) == [mensaje]
    assert _cliente(wms, codigo) is None


@requires_db
@pytest.mark.parametrize('escrito, guardado', [
    ('https://empresa.com/contacto', 'https://empresa.com/contacto'),
    ('http://empresa.com', 'http://empresa.com'),
    ('empresa.com.ar', 'https://empresa.com.ar'),
    ('', None),
])
def test_sitio_web_se_guarda_como_direccion_completa(logged_client, wms, escrito, guardado):
    codigo = _codigo()
    _guardar(logged_client, codigo=codigo, sitio_web=escrito)
    assert _cliente(wms, codigo)['sitio_web'] == guardado


@requires_db
def test_importar_y_exportar_los_campos_nuevos(logged_client, wms):
    bueno, inactivo, malo = _codigo(), _codigo(), _codigo()
    csv = '\n'.join([
        'codigo,razonsocial,nombre_fantasia,sitio_web,email,direccion,activo',
        f'{bueno},Uno S.A.,El Uno,www.uno.com,info@uno.com,Calle 1,1',
        f'{inactivo},Dos S.A.,,,,,0',
        f'{malo},Tres S.A.,,,sin-arroba,,1',
    ])
    r = logged_client.post('/clientes/importar', data={
        'archivo': (io.BytesIO(csv.encode('utf-8')), 'clientes.csv')}, content_type='multipart/form-data')
    resultado = r.get_json()
    assert resultado['insertados'] == 2
    assert [e['razon'] for e in resultado['errores']] == ['Mail principal: no tiene formato de dirección de correo.']
    c = _cliente(wms, bueno)
    assert (c['nombre_fantasia'], c['sitio_web'], c['email']) == ('El Uno', 'https://www.uno.com', 'info@uno.com')
    assert c['activo'] and not _cliente(wms, inactivo)['activo'] and _cliente(wms, malo) is None

    exportado = logged_client.get('/clientes/exportar/csv').get_data(as_text=True)
    encabezado = exportado.splitlines()[0].split(',')
    assert 'nombre_fantasia' in encabezado and 'sitio_web' in encabezado
    assert 'El Uno' in exportado and 'https://www.uno.com' in exportado


@requires_db
@pytest.mark.parametrize('formato', ['csv', 'json', 'xlsx'])
def test_la_plantilla_se_puede_importar(logged_client, wms, formato):
    plantilla = logged_client.get(f'/clientes/plantilla/{formato}')
    r = logged_client.post('/clientes/importar', data={
        'archivo': (io.BytesIO(plantilla.data), f'plantilla.{formato}')}, content_type='multipart/form-data')
    resultado = r.get_json()
    assert resultado['insertados'] == 1 and resultado['errores'] == []
    c = _cliente(wms, 'CLI001')
    assert c['nombre_fantasia'] == 'El Ejemplo' and c['sitio_web'] == 'https://www.ejemplo.com'
    cur = wms.cursor()
    cur.execute("DELETE FROM clientes WHERE codigo = 'CLI001' AND razonsocial = %s", (EJEMPLO,))
    wms.commit()
