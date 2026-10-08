"""Pedidos: numeración, validaciones, edición, anulación, cambio masivo, verificación de stock e importación."""

import io
import re
import uuid

import pytest

from tests.conftest import requires_db

PREFIJO = 'ZZX'   # los códigos de prueba empiezan así, para poder limpiarlos
HOY = '2026-10-08'


def _codigo():
    return PREFIJO + uuid.uuid4().hex[:8].upper()


@pytest.fixture
def wms(usuario_wms):
    """Conexión al WMS; al terminar borra lo que los tests hayan creado."""
    from modules.db_config import get_db_connection
    conn = get_db_connection()
    yield conn
    conn.commit()
    cur = conn.cursor()
    patron = PREFIJO + '%'
    cur.execute("SELECT id_pedido FROM pedidos_cabecera WHERE id_cliente IN (SELECT id_cliente FROM clientes WHERE codigo LIKE %s)", (patron,))
    for p in cur.fetchall():
        cur.execute("DELETE FROM omc_contenedores WHERE id_omc IN (SELECT id_omc FROM omc WHERE id_pedido = %s)", (p['id_pedido'],))
        cur.execute("DELETE FROM omc WHERE id_pedido = %s", (p['id_pedido'],))
        cur.execute("DELETE FROM pedidos_detalle WHERE id_pedido = %s", (p['id_pedido'],))
        cur.execute("DELETE FROM pedidos_cabecera WHERE id_pedido = %s", (p['id_pedido'],))
    cur.execute("DELETE FROM stockcontable WHERE IDContenedor LIKE %s", (patron,))
    cur.execute("DELETE FROM clientes WHERE codigo LIKE %s", (patron,))
    cur.execute("DELETE FROM materiales WHERE codigo LIKE %s", (patron,))
    cur.execute("DELETE FROM transportes WHERE codigo LIKE %s", (patron,))
    cur.execute("DELETE FROM rutas WHERE nombre_ruta LIKE %s", (patron,))
    cur.execute("DELETE FROM clases_pedido WHERE nombre LIKE %s", (patron,))
    cur.execute("DELETE FROM ubicaciones WHERE codigo LIKE %s", (patron,))
    cur.execute("DELETE FROM tipoubicacion WHERE descripcion LIKE %s", (patron,))
    conn.commit()
    conn.close()


def _flashes(client):
    with client.session_transaction() as s:
        # sin el saludo que deja el login
        mensajes = [m for _, m in s.get('_flashes', []) if not m.startswith('Bienvenido')]
        s['_flashes'] = []
    return mensajes


def _alta(conn, sql, parametros, tabla, columna_id, columna, valor):
    cur = conn.cursor()
    cur.execute(sql, parametros)
    conn.commit()
    cur.execute(f"SELECT {columna_id} AS id FROM {tabla} WHERE {columna} = %s ORDER BY {columna_id} DESC", (valor,))
    return cur.fetchone()['id']


@pytest.fixture
def datos(wms, usuario_wms):
    """Clientes, materiales, ruta, transporte y clase del tenant de prueba (y un cliente de otra empresa)."""
    tenant = usuario_wms['tenant_id']
    d = {'tenant': tenant, 'codigos': {}}

    def cliente(activo=1, de=None):
        codigo = _codigo()
        id_cli = _alta(wms, "INSERT INTO clientes (codigo, razonsocial, activo, tenant_id) VALUES (%s, 'Cliente de prueba', %s, %s)",
                       (codigo, activo, de or tenant), 'clientes', 'id_cliente', 'codigo', codigo)
        d['codigos'][id_cli] = codigo
        return id_cli

    def material(activo=1):
        codigo = _codigo()
        id_mat = _alta(wms, "INSERT INTO materiales (codigo, nombre, activo, tenant_id) VALUES (%s, 'Material de prueba', %s, %s)",
                       (codigo, activo, tenant), 'materiales', 'id', 'codigo', codigo)
        d['codigos'][id_mat] = codigo
        return id_mat

    d['cliente'], d['cliente_inactivo'], d['cliente_ajeno'] = cliente(), cliente(activo=0), cliente(de=tenant + 100000)
    d['material'], d['material2'], d['material_inactivo'] = material(), material(), material(activo=0)
    nombre = _codigo()
    d['ruta'] = _alta(wms, "INSERT INTO rutas (nombre_ruta, activo, tenant_id) VALUES (%s, 1, %s)", (nombre, tenant),
                      'rutas', 'id_ruta', 'nombre_ruta', nombre)
    nombre = _codigo()
    d['ruta_inactiva'] = _alta(wms, "INSERT INTO rutas (nombre_ruta, activo, tenant_id) VALUES (%s, 0, %s)", (nombre, tenant),
                               'rutas', 'id_ruta', 'nombre_ruta', nombre)
    codigo = _codigo()
    d['transporte'] = _alta(wms, "INSERT INTO transportes (codigo, razonsocial, activo, tenant_id) VALUES (%s, 'Transporte de prueba', 1, %s)",
                            (codigo, tenant), 'transportes', 'id_transporte', 'codigo', codigo)
    nombre = _codigo()
    d['clase'] = _alta(wms, "INSERT INTO clases_pedido (nombre, activo, tenant_id) VALUES (%s, 1, %s)", (nombre, tenant),
                       'clases_pedido', 'id_clase', 'nombre', nombre)
    return d


def _guardar(client, datos, renglones=None, **cambios):
    """Guarda un pedido; `renglones` es una lista de (material, cantidad, tipo de stock)."""
    renglones = [(datos['material'], '5', 'Libre Venta')] if renglones is None else renglones
    form = {'id_cliente': datos['cliente'], 'fecha_pedido': HOY,
            'items[]': [str(r[0]) for r in renglones], 'cantidades[]': [str(r[1]) for r in renglones],
            'tipos_stock[]': [r[2] if len(r) > 2 else '' for r in renglones], **cambios}
    client.post('/pedidos/guardar', data=form)
    return _flashes(client)


def _pedidos(conn, datos, cliente='cliente'):
    conn.commit()
    cur = conn.cursor()
    cur.execute("SELECT * FROM pedidos_cabecera WHERE id_cliente = %s ORDER BY id_pedido", (datos[cliente],))
    return list(cur.fetchall())


def _detalle(conn, id_pedido):
    conn.commit()
    cur = conn.cursor()
    cur.execute("SELECT id_material, cantidad, tipo_stock FROM pedidos_detalle WHERE id_pedido = %s ORDER BY id_detalle", (id_pedido,))
    return [(r['id_material'], float(r['cantidad']), r['tipo_stock']) for r in cur.fetchall()]


def _estado(conn, id_pedido, estado=None):
    cur = conn.cursor()
    if estado:
        cur.execute("UPDATE pedidos_cabecera SET estado = %s WHERE id_pedido = %s", (estado, id_pedido))
    conn.commit()
    cur.execute("SELECT estado FROM pedidos_cabecera WHERE id_pedido = %s", (id_pedido,))
    return cur.fetchone()['estado']


# --- Alta y numeración ---

@requires_db
def test_alta(logged_client, wms, datos):
    mensajes = _guardar(logged_client, datos, [(datos['material'], '5', 'Libre Venta'), (datos['material'], '2,5', 'Calidad'),
                                               (datos['material2'], '1', '')],
                        id_clase=datos['clase'], id_ruta=datos['ruta'], id_transporte=datos['transporte'],
                        direccion_entrega='  Calle 1  ', observaciones='  Urgente  ')
    (p,) = _pedidos(wms, datos)
    assert mensajes == [f'Pedido {p["nro_pedido"]} guardado.'] and re.fullmatch(r'PED-\d{4}-\d{5}', p['nro_pedido'])
    assert (p['id_clase'], p['id_ruta'], p['id_transporte'], p['direccion_entrega'], p['observaciones'], p['estado']) == (
        datos['clase'], datos['ruta'], datos['transporte'], 'Calle 1', 'Urgente', 'Pendiente')
    # El mismo material en dos tipos de stock distintos se puede pedir; sin tipo, es Libre Venta
    assert _detalle(wms, p['id_pedido']) == [(datos['material'], 5.0, 'Libre Venta'), (datos['material'], 2.5, 'Calidad'),
                                            (datos['material2'], 1.0, 'Libre Venta')]


@requires_db
def test_la_numeracion_no_depende_de_la_fecha_ni_de_los_borrados(logged_client, wms, datos):
    """El número salía de contar los pedidos con fecha en el año: con uno fechado en otro año (o uno borrado)
    se repetía, y a partir de ahí no se podía crear ningún pedido más."""
    def numeros():
        return [int(p['nro_pedido'].rsplit('-', 1)[1]) for p in _pedidos(wms, datos)]

    _guardar(logged_client, datos)
    _guardar(logged_client, datos, fecha_pedido='2025-12-30')     # fechado el año pasado
    mensajes = _guardar(logged_client, datos)
    assert 'guardado' in mensajes[0], mensajes
    a, b, c = numeros()
    assert (b, c) == (a + 1, a + 2)

    cur = wms.cursor()                                           # se borra el primero (como hace el Intercambio)
    primero = _pedidos(wms, datos)[0]['id_pedido']
    cur.execute("DELETE FROM pedidos_detalle WHERE id_pedido = %s", (primero,))
    cur.execute("DELETE FROM pedidos_cabecera WHERE id_pedido = %s", (primero,))
    wms.commit()
    assert 'guardado' in _guardar(logged_client, datos)[0]
    assert numeros() == [a + 1, a + 2, a + 3]


@requires_db
@pytest.mark.parametrize('cambios, renglones, mensaje', [
    ({'id_cliente': ''}, None, 'Cliente: hay que elegirlo.'),
    ({'id_cliente': '999999999'}, None, 'Cliente: el valor elegido no existe.'),
    ({'id_cliente': 'cliente_ajeno'}, None, 'Cliente: el valor elegido no existe.'),
    ({'id_cliente': 'cliente_inactivo'}, None, 'Cliente: "Cliente de prueba" está inactivo.'),
    ({'fecha_pedido': ''}, None, 'Fecha del pedido: es obligatoria.'),
    ({'fecha_pedido': '31/12/2026'}, None, 'Fecha del pedido: "31/12/2026" no es una fecha válida'),
    ({'id_ruta': '999999999'}, None, 'Ruta: el valor elegido no existe.'),
    ({'id_ruta': 'ruta_inactiva'}, None, 'está inactivo.'),
    ({'id_transporte': 'abc'}, None, 'Transporte: el valor elegido no existe.'),
    ({'id_clase': '999999999'}, None, 'Clase de pedido: el valor elegido no existe.'),
    ({'direccion_entrega': 'x' * 256}, None, 'Dirección de entrega: admite hasta 255 caracteres.'),
    ({}, [], 'El pedido tiene que tener al menos un renglón.'),
    ({}, [('material', 'abc')], 'cantidad: "abc" no es un número válido.'),
    ({}, [('material', '0')], 'cantidad: tiene que ser mayor que cero.'),
    ({}, [('material', '-3')], 'cantidad: tiene que ser mayor que cero.'),
    ({}, [('material', 'nan')], 'no es un número válido.'),
    ({}, [(999999999, '1')], 'Renglones: el material elegido no existe.'),
    ({}, [('material_inactivo', '1')], 'está inactivo.'),
    ({}, [('', '4')], 'Renglones: hay una fila sin material.'),
    ({}, [('material', '1', 'Inventado')], 'Tipo de stock: "Inventado" no es válido.'),
    ({}, [('material', '1', 'Calidad'), ('material', '2', 'Calidad')], 'está repetido con el mismo tipo de stock (Calidad).'),
])
def test_pedido_invalido_no_se_guarda(logged_client, wms, datos, cambios, renglones, mensaje):
    """Antes no había ninguna validación: se guardaba tal cual o salía el error de la base."""
    cambios = {k: datos.get(v, v) for k, v in cambios.items()}
    if renglones is not None:
        renglones = [(datos.get(r[0], r[0]) if isinstance(r[0], str) else r[0], *r[1:]) for r in renglones]
    mensajes = _guardar(logged_client, datos, renglones, **cambios)
    assert len(mensajes) == 1 and mensaje in mensajes[0], mensajes
    for cliente in ('cliente', 'cliente_inactivo', 'cliente_ajeno'):
        assert _pedidos(wms, datos, cliente) == []


# --- Edición ---

@requires_db
def test_editar_conserva_lo_que_quedo_inactivo(logged_client, wms, datos):
    _guardar(logged_client, datos, id_ruta=datos['ruta'])
    (p,) = _pedidos(wms, datos)
    cur = wms.cursor()
    cur.execute("UPDATE clientes SET activo = 0 WHERE id_cliente = %s", (datos['cliente'],))
    cur.execute("UPDATE materiales SET activo = 0 WHERE id = %s", (datos['material'],))
    cur.execute("UPDATE rutas SET activo = 0 WHERE id_ruta = %s", (datos['ruta'],))
    wms.commit()

    assert _guardar(logged_client, datos, [(datos['material'], '9', 'Libre Venta'), (datos['material2'], '1', 'Libre Venta')],
                    id_pedido=p['id_pedido'], id_ruta=datos['ruta'], observaciones='Editado') == ['Pedido guardado con éxito.']
    assert _detalle(wms, p['id_pedido']) == [(datos['material'], 9.0, 'Libre Venta'), (datos['material2'], 1.0, 'Libre Venta')]
    assert _pedidos(wms, datos)[0]['observaciones'] == 'Editado'
    # Una edición inválida no toca el pedido (antes borraba los renglones antes de fallar)
    (mensaje,) = _guardar(logged_client, datos, [(datos['material'], 'abc', 'Libre Venta')], id_pedido=p['id_pedido'])
    assert 'no es un número válido' in mensaje
    assert len(_detalle(wms, p['id_pedido'])) == 2

    _estado(wms, p['id_pedido'], 'Despachado')
    assert _guardar(logged_client, datos, id_pedido=p['id_pedido']) == ['No se puede modificar un pedido procesado.']


@requires_db
def test_ver_un_pedido_inexistente_avisa(logged_client, wms):
    r = logged_client.get('/pedidos/ver/999999999')
    assert r.status_code == 302 and _flashes(logged_client) == ['El pedido no existe.']


# --- Anulación ---

@requires_db
def test_anular(logged_client, wms, datos):
    for _ in range(4):
        _guardar(logged_client, datos)
    pendiente, trabajo, con_omc, despachado = _pedidos(wms, datos)

    def anular(p):
        logged_client.post(f'/pedidos/eliminar/{p["id_pedido"]}')
        return _flashes(logged_client), _estado(wms, p['id_pedido'])

    assert anular(pendiente) == ([f'Pedido {pendiente["nro_pedido"]} anulado.'], 'Anulado')
    # Un pedido pasado a Trabajo por error se puede anular mientras no tenga una OMC en curso
    _estado(wms, trabajo['id_pedido'], 'Trabajo')
    assert anular(trabajo) == ([f'Pedido {trabajo["nro_pedido"]} anulado.'], 'Anulado')

    _estado(wms, con_omc['id_pedido'], 'Trabajo')
    cur = wms.cursor()
    cur.execute("""INSERT INTO omc (numero, id_ubicacion_destino, id_pedido, estado, usuario_creacion, tenant_id)
                   SELECT %s, MIN(id), %s, 'Pendiente', 'test', %s FROM ubicaciones""",
                (_codigo(), con_omc['id_pedido'], datos['tenant']))
    wms.commit()
    if cur.rowcount:                                              # hace falta alguna ubicación para la OMC
        mensajes, estado = anular(con_omc)
        assert 'tiene una OMC pendiente o confirmada' in mensajes[0] and estado == 'Trabajo'

    _estado(wms, despachado['id_pedido'], 'Despachado')
    mensajes, estado = anular(despachado)
    assert 'está en estado Despachado' in mensajes[0] and estado == 'Despachado'
    logged_client.post('/pedidos/eliminar/999999999')
    assert _flashes(logged_client) == ['El pedido no existe.']


# --- Acciones masivas ---

@requires_db
def test_cambio_masivo_de_ruta_y_transporte(logged_client, wms, datos):
    """Antes alcanzaba a pedidos despachados o anulados, y con una ruta inexistente devolvía error 500."""
    for _ in range(3):
        _guardar(logged_client, datos)
    pendiente, despachado, anulado = _pedidos(wms, datos)
    _estado(wms, despachado['id_pedido'], 'Despachado')
    _estado(wms, anulado['id_pedido'], 'Anulado')
    ids = [pendiente['id_pedido'], despachado['id_pedido'], anulado['id_pedido']]

    r = logged_client.post('/pedidos/cambiar_ruta_transporte', json={'ids': ids, 'id_ruta': datos['ruta'],
                                                                     'id_transporte': datos['transporte']})
    assert r.get_json() == {'status': 'success', 'updated': 1,
                            'message': '1 pedido(s) actualizados. 2 no se modificaron por estar despachados o anulados.'}
    rutas = {p['id_pedido']: (p['id_ruta'], p['id_transporte']) for p in _pedidos(wms, datos)}
    assert rutas[pendiente['id_pedido']] == (datos['ruta'], datos['transporte'])
    assert rutas[despachado['id_pedido']] == (None, None) and rutas[anulado['id_pedido']] == (None, None)

    for cambio, mensaje in (({'id_ruta': 999999999}, 'Ruta: el valor elegido no existe.'),
                            ({'id_ruta': datos['ruta_inactiva']}, 'está inactivo.'),
                            ({'id_transporte': 'abc'}, 'Transporte: el valor elegido no existe.')):
        r = logged_client.post('/pedidos/cambiar_ruta_transporte', json={'ids': ids, **cambio})
        assert r.status_code == 400 and mensaje in r.get_json()['message']
    # Vacío quita la ruta
    logged_client.post('/pedidos/cambiar_ruta_transporte', json={'ids': ids, 'id_ruta': ''})
    assert _pedidos(wms, datos)[0]['id_ruta'] is None

    for ruta in ('/pedidos/preparar_masivo', '/pedidos/verificar_stock_masivo', '/pedidos/resumen_preparar',
                 '/pedidos/cambiar_ruta_transporte', '/pedidos/picking_json'):
        assert logged_client.post(ruta).status_code == 400, ruta      # sin datos: aviso, no un error técnico


@requires_db
def test_verificar_stock_cuenta_solo_ubicaciones_de_picking(logged_client, wms, datos):
    """Sumaba el disponible de todas las ubicaciones (recepción, muelles): decía que alcanzaba cuando no."""
    tenant = datos['tenant']
    ubicaciones = {}
    for clave, picking, activo in (('picking', 1, 1), ('recepcion', 0, 1), ('picking_inactiva', 1, 0)):
        nombre, codigo = _codigo(), _codigo()
        id_tipo = _alta(wms, "INSERT INTO tipoubicacion (descripcion, soporte_picking, tenant_id) VALUES (%s, %s, %s)",
                        (nombre, picking, tenant), 'tipoubicacion', 'id', 'descripcion', nombre)
        ubicaciones[clave] = (_alta(wms, """INSERT INTO ubicaciones (codigo, tipoubicacion, capacidad_maxima, ocupado, orden_picking, activo, tenant_id)
                                            VALUES (%s, %s, 0, 0, 0, %s, %s)""", (codigo, id_tipo, activo, tenant),
                                    'ubicaciones', 'id', 'codigo', codigo), codigo)
    cur = wms.cursor()
    for clave, cantidad in (('picking', 4), ('recepcion', 100), ('picking_inactiva', 100)):
        cur.execute("""INSERT INTO stockcontable (Ubicacion, Material, StockTotal, StockDisponible, IDContenedor, tenant_id)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (ubicaciones[clave][0], datos['material'], cantidad, cantidad, PREFIJO + clave[:6].upper(), tenant))
    wms.commit()
    _guardar(logged_client, datos, [(datos['material'], '10', 'Libre Venta')])
    (p,) = _pedidos(wms, datos)

    r = logged_client.post('/pedidos/verificar_stock_masivo', json={'ids': [p['id_pedido']]}).get_json()
    (linea,) = r['lineas']
    assert (linea['cantidad_total'], linea['stock_disponible'], linea['diferencia'], linea['ok']) == (10.0, 4.0, -6.0, False)

    # La búsqueda de contenedores fallaba siempre con un error de sintaxis SQL
    r = logged_client.get('/pedidos/buscar_contenedores', query_string={'q': PREFIJO})
    assert r.status_code == 200
    assert [(c['IDContenedor'], c['total_disponible']) for c in r.get_json()
            if c['ubicacion_codigo'] == ubicaciones['picking'][1]] == [(PREFIJO + 'PICKIN', 4.0)]


# --- Importación ---

def _importar(client, contenido):
    r = client.post('/pedidos/importar', data={
        'archivo': (io.BytesIO(contenido.encode('utf-8')), 'pedidos.csv')}, content_type='multipart/form-data')
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()


@requires_db
def test_importar(logged_client, wms, datos):
    cli, inactivo = datos['codigos'][datos['cliente']], datos['codigos'][datos['cliente_inactivo']]
    mat, mat2, mat_inactivo = (datos['codigos'][datos[k]] for k in ('material', 'material2', 'material_inactivo'))
    resultado = _importar(logged_client, '\n'.join([
        'agrupador,cliente_codigo,fecha_pedido,observaciones,material_codigo,cantidad,tipo_stock',
        f'BUENO,{cli},2026-09-01,Importado,{mat},5,',
        f'BUENO,{cli},2026-09-01,Importado,{mat2},"2,5",Calidad',
        # Un grupo con una línea mala no se guarda ni en parte (antes quedaba el pedido a medias, o vacío)
        f'MALO,{cli},2026-09-01,,{mat},5,',
        f'MALO,{cli},2026-09-01,,NOEXISTE,5,',
        f'MALO,{cli},2026-09-01,,{mat2},-1,',
        f'MALO,{cli},2026-09-01,,{mat_inactivo},1,',
        f'REPETIDO,{cli},2026-09-01,,{mat},1,',
        f'REPETIDO,{cli},2026-09-01,,{mat},2,',
        f'TIPO,{cli},2026-09-01,,{mat},1,Inventado',
        f'FECHA,{cli},01/09/2026,,{mat},1,',
        f'INACTIVO,{inactivo},2026-09-01,,{mat},1,',
        f'CLIENTE,NOEXISTE,2026-09-01,,{mat},1,',
        f'VACIO,{cli},2026-09-01,,,,',
    ]))
    assert resultado['insertados'] == 1
    razones = [(e['codigo'], e['fila'], e['razon']) for e in resultado['errores']]
    assert ('MALO', 4, 'Material "NOEXISTE" no encontrado') in razones
    assert any(c == 'MALO' and f == 5 and 'tiene que ser mayor que cero' in r for c, f, r in razones)
    assert any(c == 'MALO' and f == 6 and 'está inactivo' in r for c, f, r in razones)
    assert any(c == 'REPETIDO' and f == 8 and 'está repetido con el mismo tipo de stock' in r for c, f, r in razones)
    assert any(c == 'TIPO' and 'no es válido' in r for c, f, r in razones)
    assert any(c == 'FECHA' and 'no es una fecha válida' in r for c, f, r in razones)
    assert any(c == 'INACTIVO' and 'está inactivo' in r for c, f, r in razones)
    assert ('CLIENTE', 12, 'Cliente "NOEXISTE" no encontrado') in razones
    assert ('VACIO', 13, 'Ninguna línea de material válida') in razones

    (p,) = _pedidos(wms, datos)
    assert (str(p['fecha_pedido']), p['observaciones'], p['estado']) == ('2026-09-01', 'Importado', 'Pendiente')
    assert _detalle(wms, p['id_pedido']) == [(datos['material'], 5.0, 'Libre Venta'), (datos['material2'], 2.5, 'Calidad')]
    assert _pedidos(wms, datos, 'cliente_inactivo') == []
