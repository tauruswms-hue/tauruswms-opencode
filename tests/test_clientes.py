"""Clientes: datos, validaciones, estado, contactos, ruta y transporte, importación y exportación."""

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
    cur.execute("DELETE FROM pedidos_cabecera WHERE nro_pedido LIKE %s", (PREFIJO + '%',))
    cur.execute("DELETE FROM clientes WHERE codigo LIKE %s OR (codigo = 'CLI001' AND razonsocial = %s)",
                (PREFIJO + '%', EJEMPLO))
    cur.execute("DELETE FROM transporte_rutas WHERE id_transporte IN (SELECT id_transporte FROM transportes WHERE codigo LIKE %s)",
                (PREFIJO + '%',))
    cur.execute("DELETE FROM transportes WHERE codigo LIKE %s", (PREFIJO + '%',))
    cur.execute("DELETE FROM rutas WHERE nombre_ruta LIKE %s", (PREFIJO + '%',))
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
                    email='ventas@elalmacen.com.ar', direccion='Av. Siempre Viva 742',
                    activo='1') == ['Cliente guardado correctamente']
    c = _cliente(wms, codigo)
    assert c['nombre_fantasia'] == 'El Almacén'
    assert c['sitio_web'] == 'https://www.elalmacen.com.ar'     # sin protocolo, se completa con https://
    assert c['email'] == 'ventas@elalmacen.com.ar' and c['direccion'] == 'Av. Siempre Viva 742'
    assert c['activo']

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


def _contactos(conn, codigo):
    conn.commit()  # refresca el snapshot de la transacción
    cur = conn.cursor()
    cur.execute("""SELECT cc.nombre, cc.apellido, cc.departamento, cc.rol, cc.telefono, cc.email
                   FROM cliente_contactos cc JOIN clientes c ON c.id_cliente = cc.id_cliente
                   WHERE c.codigo = %s ORDER BY cc.id""", (codigo,))
    return cur.fetchall()


def _filas_de_contactos(*contactos):
    """Datos del formulario para una lista de contactos (nombre, apellido, departamento, rol, teléfono, mail)."""
    campos = ('nombre', 'apellido', 'departamento', 'rol', 'telefono', 'email')
    return {f'contacto_{campo}[]': [c[i] if i < len(c) else '' for c in contactos] for i, campo in enumerate(campos)}


# --- Contactos: un cliente puede tener varios ---

@requires_db
def test_cliente_con_varios_contactos(logged_client, wms):
    codigo = _codigo()
    assert _guardar(logged_client, codigo=codigo, **_filas_de_contactos(
        ('Ana', 'Pérez', 'Compras', 'Jefa de compras', '011-4444-5555', 'ana@cliente.com'),
        ('Luis', 'Gómez', 'Pagos', 'Analista'),
        ('', '', '', ''),                               # fila vacía: se ignora
        ('Marta', '', 'Recepción', ''),
    )) == ['Cliente guardado correctamente']
    contactos = _contactos(wms, codigo)
    assert [(c['nombre'], c['apellido'], c['departamento'], c['rol']) for c in contactos] == [
        ('Ana', 'Pérez', 'Compras', 'Jefa de compras'), ('Luis', 'Gómez', 'Pagos', 'Analista'),
        ('Marta', None, 'Recepción', None)]
    assert contactos[0]['email'] == 'ana@cliente.com' and contactos[0]['telefono'] == '011-4444-5555'
    # El primero es el contacto principal: su nombre queda también en el cliente (exportación, Intercambio)
    assert _cliente(wms, codigo)['contacto_nombre'] == 'Ana Pérez'

    html = logged_client.get('/clientes').get_data(as_text=True)
    fila = html[html.index(f'<code>{codigo}</code>'):]
    fila = fila[:fila.index('</tr>')]
    assert 'Ana Pérez' in fila and '+2</span>' in fila and 'Jefa de compras' in fila
    # El formulario recibe los contactos y tiene la pestaña para cargarlos
    assert 'const contactosClientes = ' in html and '"departamento": "Compras"' in html
    assert 'id="tab-cli-contactos"' in html and 'Departamento o sección' in html


@requires_db
def test_editar_reemplaza_los_contactos_y_los_puede_quitar_todos(logged_client, wms):
    codigo = _codigo()
    _guardar(logged_client, codigo=codigo, **_filas_de_contactos(('Ana', 'Pérez'), ('Luis', 'Gómez')))
    cid = _cliente(wms, codigo)['id_cliente']

    _guardar(logged_client, id_cliente=cid, codigo=codigo, activo='1', **_filas_de_contactos(('Luis', 'Gómez', 'Pagos', 'Jefe')))
    assert [(c['nombre'], c['rol']) for c in _contactos(wms, codigo)] == [('Luis', 'Jefe')]
    assert _cliente(wms, codigo)['contacto_nombre'] == 'Luis Gómez'

    _guardar(logged_client, id_cliente=cid, codigo=codigo, activo='1')
    assert _contactos(wms, codigo) == () and _cliente(wms, codigo)['contacto_nombre'] is None


@requires_db
@pytest.mark.parametrize('contacto, mensaje', [
    (('', 'Pérez', 'Compras'), 'Contacto 1: falta el nombre.'),
    (('Ana', '', '', '', '', 'sin-arroba'), 'Contacto 1: el mail no tiene formato de dirección de correo.'),
    (('Ana', '', 'x' * 101), 'Contacto 1: departamento o sección admite hasta 100 caracteres.'),
])
def test_contacto_invalido_no_guarda_el_cliente(logged_client, wms, contacto, mensaje):
    codigo = _codigo()
    assert _guardar(logged_client, codigo=codigo, **_filas_de_contactos(contacto)) == [mensaje]
    assert _cliente(wms, codigo) is None


@requires_db
def test_borrar_el_cliente_de_la_base_borra_sus_contactos(logged_client, wms):
    codigo = _codigo()
    _guardar(logged_client, codigo=codigo, **_filas_de_contactos(('Ana', 'Pérez')))
    cid = _cliente(wms, codigo)['id_cliente']
    cur = wms.cursor()
    cur.execute("DELETE FROM clientes WHERE id_cliente = %s", (cid,))
    wms.commit()
    cur.execute("SELECT COUNT(*) AS n FROM cliente_contactos WHERE id_cliente = %s", (cid,))
    assert cur.fetchone()['n'] == 0


@requires_db
def test_el_contacto_de_la_importacion_y_del_intercambio_queda_en_la_lista(logged_client, wms, usuario_wms):
    importado, externo = _codigo(), _codigo()
    csv = f'codigo,razonsocial,contacto_nombre\n{importado},Importado S.A.,Juan Pérez\n'
    logged_client.post('/clientes/importar', data={
        'archivo': (io.BytesIO(csv.encode('utf-8')), 'clientes.csv')}, content_type='multipart/form-data')
    assert [c['nombre'] for c in _contactos(wms, importado)] == ['Juan Pérez']

    from modules import intercambio
    from modules.db_config import _get_admin_connection
    admin = _get_admin_connection()
    try:
        cur_admin = admin.cursor()
        cur_admin.execute("SELECT codigo FROM tenants WHERE id = %s", (usuario_wms['tenant_id'],))
        reg = {'tenant_codigo': cur_admin.fetchone()['codigo'], 'codigo': externo, 'razonsocial': 'Externo S.A.',
               'accion': 'alta', 'activo': 1, 'contacto_nombre': 'Carla Ruiz'}
        cur = wms.cursor()
        intercambio._aplicar_registro_cliente(reg, wms, cur, cur_admin)
        wms.commit()
        assert [c['nombre'] for c in _contactos(wms, externo)] == ['Carla Ruiz']
        # Una modificación posterior no pisa ni duplica los contactos que ya tiene
        intercambio._aplicar_registro_cliente({**reg, 'accion': 'modificacion', 'contacto_nombre': 'Otra Persona'},
                                              wms, cur, cur_admin)
        wms.commit()
        assert [c['nombre'] for c in _contactos(wms, externo)] == ['Carla Ruiz']
    finally:
        admin.close()


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


# --- Validaciones del servidor, ruta y transporte, inactivación ---

def _importar(client, contenido):
    r = client.post('/clientes/importar', data={
        'archivo': (io.BytesIO(contenido.encode('utf-8')), 'clientes.csv')}, content_type='multipart/form-data')
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()


@pytest.fixture
def logistica(wms, usuario_wms):
    """Una ruta y un transporte de la empresa de prueba, y una ruta de otra empresa."""
    tenant = usuario_wms['tenant_id']
    nombre, ajena, codigo = 'Ruta ' + _codigo(), 'Ajena ' + _codigo(), _codigo()
    cur = wms.cursor()
    cur.execute("INSERT INTO rutas (nombre_ruta, tenant_id, activo) VALUES (%s, %s, 1)", (PREFIJO + nombre, tenant))
    cur.execute("INSERT INTO rutas (nombre_ruta, tenant_id, activo) VALUES (%s, %s, 1)", (PREFIJO + ajena, tenant + 100000))
    cur.execute("INSERT INTO transportes (codigo, razonsocial, tenant_id, activo) VALUES (%s, 'Transporte de prueba', %s, 1)",
                (codigo, tenant))
    wms.commit()
    ids = {}
    for clave, valor in (('ruta', PREFIJO + nombre), ('ruta_ajena', PREFIJO + ajena)):
        cur.execute("SELECT id_ruta FROM rutas WHERE nombre_ruta = %s", (valor,))
        ids[clave] = cur.fetchone()['id_ruta']
    cur.execute("SELECT id_transporte FROM transportes WHERE codigo = %s", (codigo,))
    return {**ids, 'transporte': cur.fetchone()['id_transporte'], 'ruta_nombre': PREFIJO + nombre,
            'transporte_codigo': codigo}


@requires_db
def test_datos_sin_espacios_en_los_extremos(logged_client, wms):
    codigo = _codigo()
    assert _guardar(logged_client, codigo=f'  {codigo}  ', razonsocial='  Uno S.A.  ', localidad='  Rosario  ',
                    provincia='  Santa Fe  ', telefono='  0341 1  ') == ['Cliente guardado correctamente']
    c = _cliente(wms, codigo)
    assert (c['codigo'], c['razonsocial'], c['localidad'], c['provincia'], c['telefono']) == (
        codigo, 'Uno S.A.', 'Rosario', 'Santa Fe', '0341 1')


@requires_db
@pytest.mark.parametrize('datos, mensaje', [
    ({'codigo': '   '}, 'Código: es obligatorio.'),
    ({'razonsocial': '   '}, 'Razón Social: es obligatorio.'),
    ({'codigo': PREFIJO + 'x' * 100}, 'Código: admite hasta 100 caracteres.'),
    ({'razonsocial': 'x' * 201}, 'Razón Social: admite hasta 200 caracteres.'),
    ({'localidad': 'x' * 101}, 'Localidad: admite hasta 100 caracteres.'),
    ({'provincia': 'x' * 101}, 'Provincia: admite hasta 100 caracteres.'),
    ({'telefono': '1' * 51}, 'Teléfono: admite hasta 50 caracteres.'),
    ({'id_ruta': '999999999'}, 'Ruta de entrega: no existe.'),
    ({'id_ruta': 'abc'}, 'Ruta de entrega: no existe.'),
    ({'id_transporte_predeterminado': '999999999'}, 'Transporte habitual: no existe.'),
    ({'id_cliente': 'abc'}, 'El cliente que se intenta modificar no existe.'),
    ({'id_cliente': '999999999'}, 'El cliente que se intenta modificar no existe.'),
])
def test_el_servidor_valida_lo_que_antes_rechazaba_la_base(logged_client, wms, datos, mensaje):
    """Antes se guardaba tal cual o salía el error de la base (Data too long, foreign key constraint fails)."""
    codigo = _codigo()
    assert _guardar(logged_client, **{'codigo': codigo, **datos}) == [mensaje]
    assert _cliente(wms, codigo) is None


@requires_db
def test_codigo_repetido_se_rechaza(logged_client, wms):
    codigo, otro = _codigo(), _codigo()
    _guardar(logged_client, codigo=codigo)
    _guardar(logged_client, codigo=otro)
    assert _guardar(logged_client, codigo=f' {codigo} ') == [f'Ya existe un cliente con el código "{codigo}".']
    assert _guardar(logged_client, id_cliente=_cliente(wms, otro)['id_cliente'], codigo=codigo) == [
        f'Ya existe un cliente con el código "{codigo}".']
    # Guardar el mismo cliente con su propio código sí se puede
    assert _guardar(logged_client, id_cliente=_cliente(wms, codigo)['id_cliente'], codigo=codigo,
                    razonsocial='Renombrado') == ['Cliente guardado correctamente']


@requires_db
def test_ruta_y_transporte_tienen_que_ser_de_la_empresa(logged_client, wms, logistica):
    codigo, otro = _codigo(), _codigo()
    assert _guardar(logged_client, codigo=codigo, id_ruta=logistica['ruta'],
                    id_transporte_predeterminado=logistica['transporte']) == ['Cliente guardado correctamente']
    c = _cliente(wms, codigo)
    assert (c['id_ruta'], c['id_transporte_predeterminado']) == (logistica['ruta'], logistica['transporte'])
    # Una ruta de otra empresa no se puede asignar: antes quedaba guardada
    assert _guardar(logged_client, codigo=otro, id_ruta=logistica['ruta_ajena']) == ['Ruta de entrega: no existe.']
    assert _cliente(wms, otro) is None


@requires_db
def test_editar_sin_el_estado_lo_conserva(logged_client, wms):
    codigo = _codigo()
    _guardar(logged_client, codigo=codigo, activo='0')
    cid = _cliente(wms, codigo)['id_cliente']
    _guardar(logged_client, id_cliente=cid, codigo=codigo)
    assert not _cliente(wms, codigo)['activo']
    _guardar(logged_client, id_cliente=cid, codigo=codigo, activo='1')
    _guardar(logged_client, id_cliente=cid, codigo=codigo)
    assert _cliente(wms, codigo)['activo']


@requires_db
def test_inactivar(logged_client, wms, usuario_wms):
    codigo = _codigo()
    _guardar(logged_client, codigo=codigo, razonsocial=f'Razon {codigo}')
    cid = _cliente(wms, codigo)['id_cliente']
    cur = wms.cursor()
    for estado in ('Pendiente', 'Despachado'):
        cur.execute("INSERT INTO pedidos_cabecera (nro_pedido, id_cliente, fecha_pedido, estado, tenant_id) "
                    "VALUES (%s, %s, CURRENT_DATE, %s, %s)", (_codigo(), cid, estado, usuario_wms['tenant_id']))
    wms.commit()

    logged_client.post(f'/clientes/eliminar/{cid}')
    (mensaje,) = _flashes(logged_client)
    assert 'quedó inactivo' in mensaje and 'Tiene 1 pedido sin despachar, que sigue su curso.' in mensaje
    assert not _cliente(wms, codigo)['activo']
    logged_client.post(f'/clientes/eliminar/{cid}')
    assert _flashes(logged_client) == [f'El cliente "Razon {codigo}" ya estaba inactivo.']
    logged_client.post('/clientes/eliminar/999999999')
    assert _flashes(logged_client) == ['Cliente no encontrado.']

    # En el listado: con sus pedidos y sin el botón de inactivar
    html = logged_client.get('/clientes').get_data(as_text=True)
    fila = html[html.index(f'<code>{codigo}</code>'):]
    fila = fila[:fila.index('</tr>')]
    assert '>2</td>' in fila and 'Inactivo</span>' in fila and '/clientes/eliminar/' not in fila


@requires_db
def test_importar_no_le_quita_la_ruta_a_un_cliente_existente(logged_client, wms, logistica):
    """Un archivo sin las columnas de ruta y transporte (o vacías) dejaba al cliente sin ellas."""
    codigo = _codigo()
    _guardar(logged_client, codigo=codigo, id_ruta=logistica['ruta'], id_transporte_predeterminado=logistica['transporte'])

    resultado = _importar(logged_client, f'codigo,razonsocial\n{codigo},Otro nombre\n')
    assert (resultado['actualizados'], resultado['omitidos'], resultado['errores']) == (0, [codigo], [])
    resultado = _importar(logged_client, f'codigo,razonsocial,id_ruta,id_transporte_predeterminado\n{codigo},X,,\n')
    assert resultado['omitidos'] == [codigo]
    c = _cliente(wms, codigo)
    assert (c['id_ruta'], c['id_transporte_predeterminado']) == (logistica['ruta'], logistica['transporte'])
    assert c['razonsocial'] == 'Cliente de prueba S.A.'           # el resto de los datos no se toca

    # Con dato en una sola columna, cambia esa y conserva la otra
    cur = wms.cursor()
    cur.execute("UPDATE clientes SET id_ruta = NULL WHERE id_cliente = %s", (c['id_cliente'],))
    wms.commit()
    resultado = _importar(logged_client, f'codigo,razonsocial,id_ruta\n{codigo},X,{logistica["ruta_nombre"]}\n')
    assert resultado['actualizados'] == 1
    c = _cliente(wms, codigo)
    assert (c['id_ruta'], c['id_transporte_predeterminado']) == (logistica['ruta'], logistica['transporte'])


@requires_db
def test_importar_con_ruta_o_transporte_inexistente_es_un_error(logged_client, wms, logistica):
    bueno, por_id, sin_ruta, sin_transporte, ajena, largo = (_codigo() for _ in range(6))
    resultado = _importar(logged_client, '\n'.join([
        'codigo,razonsocial,localidad,id_ruta,id_transporte_predeterminado',
        f'  {bueno}  ,  Uno  ,  Rosario  ,{logistica["ruta_nombre"]},{logistica["transporte_codigo"]}',
        f'{por_id},Dos,,{logistica["ruta"]},{logistica["transporte"]}',
        f'{sin_ruta},Tres,,No existe,',
        f'{sin_transporte},Cuatro,,,NOEXISTE',
        f'{ajena},Cinco,,{logistica["ruta_ajena"]},',
        f'{largo},Seis,{"x" * 101},,',
    ]))
    assert resultado['insertados'] == 2
    assert [(e['fila'], e['razon']) for e in resultado['errores']] == [
        (3, 'Ruta "No existe": no existe.'),
        (4, 'Transporte "NOEXISTE": no existe.'),
        (5, f'Ruta "{logistica["ruta_ajena"]}": no existe.'),      # el ID de una ruta de otra empresa
        (6, 'Localidad: admite hasta 100 caracteres.')]
    c = _cliente(wms, bueno)
    assert (c['razonsocial'], c['localidad'], c['id_ruta'], c['id_transporte_predeterminado']) == (
        'Uno', 'Rosario', logistica['ruta'], logistica['transporte'])
    assert _cliente(wms, por_id)['id_ruta'] == logistica['ruta']
    assert _cliente(wms, sin_ruta) is None and _cliente(wms, ajena) is None


@requires_db
def test_la_exportacion_se_puede_importar_en_otro_servidor(logged_client, wms, logistica):
    """La ruta sale por su nombre y el transporte por su código: los ID internos cambian de un servidor a otro."""
    import csv as modulo_csv
    codigo = _codigo()
    _guardar(logged_client, codigo=codigo, id_ruta=logistica['ruta'], id_transporte_predeterminado=logistica['transporte'])
    exportado = logged_client.get('/clientes/exportar/csv').get_data(as_text=True)
    fila = next(f for f in modulo_csv.DictReader(io.StringIO(exportado.lstrip('\ufeff'))) if f['codigo'] == codigo)
    assert (fila['id_ruta'], fila['nombre_ruta']) == (logistica['ruta_nombre'], logistica['ruta_nombre'])
    assert (fila['id_transporte_predeterminado'], fila['nombre_transporte']) == (
        logistica['transporte_codigo'], 'Transporte de prueba')

    # Como si fuera otro servidor: se borra el cliente y se lo vuelve a cargar desde esa fila
    cur = wms.cursor()
    cur.execute("DELETE FROM clientes WHERE codigo = %s", (codigo,))
    wms.commit()
    encabezado = exportado.splitlines()[0].lstrip('\ufeff')
    linea = next(x for x in exportado.splitlines() if x.startswith(codigo + ','))
    resultado = _importar(logged_client, f'{encabezado}\n{linea}\n')
    assert resultado['insertados'] == 1 and resultado['errores'] == []
    c = _cliente(wms, codigo)
    assert (c['id_ruta'], c['id_transporte_predeterminado']) == (logistica['ruta'], logistica['transporte'])
