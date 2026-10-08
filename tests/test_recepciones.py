"""Recepciones: cabecera, renglones, cierre, confirmación por OMC, numeración por empresa e importación."""

import io
import re
import uuid

import pytest

from tests.conftest import requires_db

PREFIJO = 'ZZQ'   # los códigos de prueba empiezan así, para poder limpiarlos


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
    cur.execute("SELECT id FROM materiales WHERE codigo LIKE %s", (patron,))
    for m in cur.fetchall():
        cur.execute("DELETE FROM stock_movimientos WHERE id_material = %s", (m['id'],))
        cur.execute("DELETE FROM stockcontable WHERE Material = %s", (m['id'],))
    cur.execute("""SELECT id_recepcion FROM recepciones_cabecera
                   WHERE id_proveedor IN (SELECT id FROM proveedores WHERE codigo LIKE %s)""", (patron,))
    for r in cur.fetchall():
        cur.execute("DELETE FROM omc_contenedores WHERE id_omc IN (SELECT id_omc FROM omc WHERE id_recepcion = %s)", (r['id_recepcion'],))
        cur.execute("DELETE FROM omc WHERE id_recepcion = %s", (r['id_recepcion'],))
        cur.execute("DELETE FROM recepciones_cabecera WHERE id_recepcion = %s", (r['id_recepcion'],))   # arrastra el detalle
    cur.execute("DELETE FROM materiales WHERE codigo LIKE %s", (patron,))                               # arrastra material_proveedor
    cur.execute("DELETE FROM proveedores WHERE codigo LIKE %s", (patron,))
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


def _insertar(conn, sql, parametros, tabla, columna_id, codigo_col, codigo):
    cur = conn.cursor()
    cur.execute(sql, parametros)
    conn.commit()
    cur.execute(f"SELECT {columna_id} AS id FROM {tabla} WHERE {codigo_col} = %s ORDER BY {columna_id} DESC", (codigo,))
    return cur.fetchone()['id']


@pytest.fixture
def datos(wms, usuario_wms):
    """Proveedor, ubicaciones (recepción, destino y otras) y materiales del tenant de prueba."""
    tenant = usuario_wms['tenant_id']
    d = {'tenant': tenant}

    def tipo(operacion):
        nombre = _codigo()
        return _insertar(wms, "INSERT INTO tipoubicacion (descripcion, operacion, tenant_id) VALUES (%s, %s, %s)",
                         (nombre, operacion, tenant), 'tipoubicacion', 'id', 'descripcion', nombre)

    def ubicacion(id_tipo, activo=1, de=None):
        codigo = _codigo()
        d.setdefault('codigos', {})
        id_ubi = _insertar(wms, """INSERT INTO ubicaciones (codigo, descipcion, tipoubicacion, capacidad_maxima, ocupado,
                                                            orden_picking, activo, tenant_id)
                                   VALUES (%s, 'Ubicación de prueba', %s, 0, 0, 0, %s, %s)""",
                           (codigo, id_tipo, activo, de or tenant), 'ubicaciones', 'id', 'codigo', codigo)
        d['codigos'][id_ubi] = codigo
        return id_ubi

    def proveedor(activo=1):
        codigo = _codigo()
        d.setdefault('prov_codigos', {})
        id_prov = _insertar(wms, "INSERT INTO proveedores (codigo, razonsocial, activo, tenant_id) VALUES (%s, 'Proveedor de prueba', %s, %s)",
                            (codigo, activo, tenant), 'proveedores', 'id', 'codigo', codigo)
        d['prov_codigos'][id_prov] = codigo
        return id_prov

    def material(trazabilidad='ninguna', activo=1, del_proveedor=True):
        codigo = _codigo()
        d.setdefault('mat_codigos', {})
        id_mat = _insertar(wms, """INSERT INTO materiales (codigo, nombre, trazabilidad, metodo_picking, activo, tenant_id)
                                   VALUES (%s, 'Material de prueba', %s, 'libre', %s, %s)""",
                           (codigo, trazabilidad, activo, tenant), 'materiales', 'id', 'codigo', codigo)
        if del_proveedor:
            cur = wms.cursor()
            cur.execute("INSERT INTO material_proveedor (id_material, id_proveedor, es_habitual, tenant_id) VALUES (%s, %s, 1, %s)",
                        (id_mat, d['proveedor'], tenant))
            wms.commit()
        d['mat_codigos'][id_mat] = codigo
        return id_mat

    tipo_r, tipo_a = tipo('R'), tipo(None)
    d['recep'], d['destino'] = ubicacion(tipo_r), ubicacion(tipo_a)
    d['recep_inactiva'], d['recep_ajena'] = ubicacion(tipo_r, activo=0), ubicacion(tipo_r, de=tenant + 100000)
    d['proveedor'], d['proveedor_inactivo'] = proveedor(), proveedor(activo=0)
    d['material'], d['material_lote'] = material(), material('lote')
    d['material_ajeno_al_proveedor'], d['material_inactivo'] = material(del_proveedor=False), material(activo=0)
    return d


def _nueva(client, datos, **cambios):
    """Crea una recepción; devuelve (id o None, mensajes)."""
    form = {'id_proveedor': datos['proveedor'], 'id_ubicacion_recep': datos['recep'], **cambios}
    r = client.post('/recepciones/guardar', data=form)
    m = re.search(r'/recepciones/ver/(\d+)', r.headers.get('Location', ''))
    return (int(m.group(1)) if m else None), _flashes(client)


def _item(client, id_recepcion, id_material, **cambios):
    r = client.post('/recepciones/guardar_item', json={
        'id_recepcion': id_recepcion, 'id_material': id_material, 'cantidad_esperada': 10, 'cantidad_recibida': 10,
        'tipo_stock': 'Libre Venta', **cambios})
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    return r.get_json()


def _stock(conn, datos, id_material):
    """Stock del material: {RECEP|DEST: (lote, total, disponible, entrando, saliendo)}."""
    conn.commit()
    cur = conn.cursor()
    cur.execute("""SELECT Ubicacion, Lote, StockTotal, StockDisponible, StockEntrando, StockSaliendo
                   FROM stockcontable WHERE Material = %s""", (id_material,))
    nombres = {datos['recep']: 'RECEP', datos['destino']: 'DEST'}
    return {nombres.get(r['Ubicacion'], r['Ubicacion']): (r['Lote'], float(r['StockTotal']), float(r['StockDisponible']),
                                                         float(r['StockEntrando']), float(r['StockSaliendo']))
            for r in cur.fetchall()}


def _recepcion(conn, id_recepcion):
    conn.commit()
    cur = conn.cursor()
    cur.execute("SELECT * FROM recepciones_cabecera WHERE id_recepcion = %s", (id_recepcion,))
    return cur.fetchone()


def _omc(conn, id_recepcion):
    conn.commit()
    cur = conn.cursor()
    cur.execute("SELECT id_omc, numero, estado FROM omc WHERE id_recepcion = %s ORDER BY id_omc DESC", (id_recepcion,))
    return cur.fetchone()


def _cerrar(client, id_recepcion, id_destino):
    client.post(f'/recepciones/cerrar/{id_recepcion}', data={'id_ubicacion_destino': id_destino})
    return _flashes(client)


# --- Cabecera ---

@requires_db
def test_alta(logged_client, wms, datos):
    id_recepcion, mensajes = _nueva(logged_client, datos, id_ubicacion_destino=datos['destino'], observaciones='  Remito 123  ')
    assert id_recepcion and 'creada' in mensajes[0]
    r = _recepcion(wms, id_recepcion)
    assert re.fullmatch(r'REC-\d{4}-\d{5}', r['numero']) and r['id_contenedor'] == f'RC{id_recepcion:05d}'
    assert (r['id_proveedor'], r['id_ubicacion_recep'], r['id_ubicacion_destino'], r['observaciones']) == (
        datos['proveedor'], datos['recep'], datos['destino'], 'Remito 123')
    assert r['estado'].capitalize() == 'Abierta' and r['tenant_id'] == datos['tenant']


@requires_db
@pytest.mark.parametrize('cambio, mensaje', [
    ({'id_proveedor': ''}, 'Debe seleccionar un proveedor.'),
    ({'id_proveedor': '999999999'}, 'El proveedor elegido no existe.'),
    ({'id_proveedor': 'proveedor_inactivo'}, 'El proveedor "Proveedor de prueba" está inactivo.'),
    ({'id_ubicacion_recep': ''}, 'Debe seleccionar la ubicación de recepción.'),
    ({'id_ubicacion_recep': '999999999'}, 'La ubicación de recepción elegida no existe.'),
    ({'id_ubicacion_recep': 'recep_ajena'}, 'La ubicación de recepción elegida no existe.'),
    ({'id_ubicacion_recep': 'recep_inactiva'}, 'está inactiva.'),
    ({'id_ubicacion_recep': 'destino'}, 'no es de recepción: su tipo tiene que tener esa operación.'),
    ({'id_ubicacion_destino': 'recep'}, 'La ubicación destino tiene que ser distinta de la ubicación de recepción.'),
    ({'id_ubicacion_destino': '999999999'}, 'La ubicación destino elegida no existe.'),
])
def test_cabecera_invalida_no_se_crea(logged_client, wms, datos, cambio, mensaje):
    """Antes salía el error de la base (foreign key constraint fails) o se aceptaba una ubicación cualquiera."""
    cambio = {k: datos.get(v, v) for k, v in cambio.items()}
    id_recepcion, mensajes = _nueva(logged_client, datos, **cambio)
    assert id_recepcion is None and len(mensajes) == 1 and mensaje in mensajes[0]


@requires_db
def test_el_numero_es_por_empresa(logged_client, wms, datos):
    """El número se arma por empresa pero era único entre todas: si otra ya lo tenía, no se podía crear."""
    primera, _ = _nueva(logged_client, datos)
    numero = _recepcion(wms, primera)['numero']
    prefijo, seq = numero.rsplit('-', 1)
    proximo = f'{prefijo}-{int(seq) + 1:05d}'
    cur = wms.cursor()
    cur.execute("""INSERT INTO recepciones_cabecera (numero, id_proveedor, id_ubicacion_recep, id_contenedor, usuario_creacion, tenant_id)
                   VALUES (%s, %s, %s, '', 'test', %s)""", (proximo, datos['proveedor'], datos['recep'], datos['tenant'] + 100000))
    wms.commit()
    segunda, mensajes = _nueva(logged_client, datos)
    assert segunda and _recepcion(wms, segunda)['numero'] == proximo, mensajes


def test_los_numeros_de_documentos_son_unicos_por_tenant():
    from modules.schema_generator import WMS_TABLES
    tablas = {t['name']: t for t in WMS_TABLES}
    for tabla, columna in (('recepciones_cabecera', 'numero'), ('omc', 'numero'), ('pedidos_cabecera', 'nro_pedido')):
        unicos = [i['columns'] for i in tablas[tabla]['indexes'] if i.get('unique') and columna in i['columns']]
        assert unicos == [[columna, 'tenant_id']], tabla


# --- Renglones ---

@requires_db
@pytest.mark.parametrize('cambio, mensaje', [
    ({'cantidad_recibida': 'abc'}, 'Cantidad recibida: "abc" no es un número válido.'),
    ({'cantidad_recibida': 'nan'}, 'Cantidad recibida: "nan" no es un número válido.'),
    ({'cantidad_recibida': -5}, 'Cantidad recibida: no puede ser negativa.'),
    ({'cantidad_esperada': -1}, 'Cantidad esperada: no puede ser negativa.'),
    ({'cantidad_recibida': 1e15}, 'Cantidad recibida: el valor es demasiado grande.'),
    ({'tipo_stock': 'Inventado'}, 'Tipo de stock: "Inventado" no es válido.'),
    ({'fecha_vencimiento': '31/12/2026'}, 'Fecha de vencimiento: "31/12/2026" no es una fecha válida'),
    ({'lote': 'x' * 101}, 'Lote: admite hasta 100 caracteres.'),
    ({'id_material': 999999999}, 'El material elegido no existe.'),
    ({'id_material': 'material_ajeno_al_proveedor'}, 'no está asignado al proveedor de la recepción.'),
    ({'id_material': 'material_inactivo'}, 'está inactivo.'),
    ({'id_material': 'material_lote'}, 'lleva trazabilidad por lote: hay que indicar el lote.'),
    ({'id_material': 'material_lote', 'lote': 'unico'}, 'lleva trazabilidad por lote: hay que indicar el lote.'),
])
def test_renglon_invalido_no_se_guarda(logged_client, wms, datos, cambio, mensaje):
    """Antes: error 500 con una cantidad no numérica, cantidades negativas aceptadas y errores crudos de la base."""
    id_recepcion, _ = _nueva(logged_client, datos)
    cambio = {k: datos.get(v, v) if isinstance(v, str) else v for k, v in cambio.items()}
    id_material = cambio.pop('id_material', datos['material'])
    respuesta = _item(logged_client, id_recepcion, id_material, **cambio)
    assert respuesta['ok'] is False and mensaje in respuesta['msg']
    cur = wms.cursor()
    wms.commit()
    cur.execute("SELECT COUNT(*) AS n FROM recepciones_detalle WHERE id_recepcion = %s", (id_recepcion,))
    assert cur.fetchone()['n'] == 0


@requires_db
def test_renglon_valido_y_edicion(logged_client, wms, datos):
    id_recepcion, _ = _nueva(logged_client, datos)
    alta = _item(logged_client, id_recepcion, datos['material_lote'], lote='  L-2026  ', cantidad_recibida='7,5',
                 fecha_vencimiento='2027-01-31')
    assert alta['ok'] is True
    cur = wms.cursor()
    wms.commit()
    cur.execute("SELECT * FROM recepciones_detalle WHERE id_detalle = %s", (alta['id_detalle'],))
    det = cur.fetchone()
    assert (det['lote'], float(det['cantidad_recibida']), str(det['fecha_vencimiento'])) == ('L-2026', 7.5, '2027-01-31')

    edicion = _item(logged_client, id_recepcion, datos['material_lote'], id_detalle=alta['id_detalle'], lote='L-2026',
                    cantidad_recibida=9, tipo_stock='Calidad')
    assert edicion['ok'] is True
    wms.commit()
    cur.execute("SELECT cantidad_recibida, tipo_stock FROM recepciones_detalle WHERE id_detalle = %s", (alta['id_detalle'],))
    det = cur.fetchone()
    assert (float(det['cantidad_recibida']), det['tipo_stock'].lower()) == (9.0, 'calidad')
    # Al editar tampoco se le puede quitar el lote a un material que lo lleva
    sin_lote = _item(logged_client, id_recepcion, datos['material_lote'], id_detalle=alta['id_detalle'], lote='')
    assert sin_lote['ok'] is False and 'hay que indicar el lote' in sin_lote['msg']


@requires_db
def test_el_mismo_material_no_se_carga_dos_veces(logged_client, wms, datos):
    """Con dos lotes del mismo material, al cerrar el segundo se fundía con el primero en el stock."""
    id_recepcion, _ = _nueva(logged_client, datos)
    assert _item(logged_client, id_recepcion, datos['material_lote'], lote='LOTE-A')['ok'] is True
    segundo = _item(logged_client, id_recepcion, datos['material_lote'], lote='LOTE-B')
    assert segundo['ok'] is False and 'ya está cargado en esta recepción' in segundo['msg'] and 'otra recepción' in segundo['msg']
    assert _item(logged_client, id_recepcion, datos['material'])['ok'] is True      # otro material sí


# --- Cierre, OMC y stock ---

@requires_db
def test_ciclo_completo_cerrar_y_confirmar_la_omc(logged_client, wms, datos, usuario_wms):
    id_recepcion, _ = _nueva(logged_client, datos)
    _item(logged_client, id_recepcion, datos['material_lote'], lote='LOTE-A', cantidad_recibida=17)

    for destino, mensaje in ((datos['recep'], 'tiene que ser distinta de la ubicación de recepción'),
                             (999999999, 'La ubicación destino elegida no existe.'),
                             (datos['recep_ajena'], 'La ubicación destino elegida no existe.')):
        (aviso,) = _cerrar(logged_client, id_recepcion, destino)
        assert mensaje in aviso
    assert _recepcion(wms, id_recepcion)['estado'].capitalize() == 'Abierta' and _stock(wms, datos, datos['material_lote']) == {}

    (aviso,) = _cerrar(logged_client, id_recepcion, datos['destino'])
    assert 'cerrada' in aviso and 'OMC' in aviso
    assert _stock(wms, datos, datos['material_lote']) == {'RECEP': ('LOTE-A', 0, 0, 0, 17), 'DEST': ('LOTE-A', 0, 0, 17, 0)}
    omc = _omc(wms, id_recepcion)
    assert omc['estado'].capitalize() == 'Pendiente'

    # La recepción no confirma por su cuenta mientras la OMC está pendiente
    logged_client.post(f'/recepciones/confirmar_stock/{id_recepcion}')
    assert _flashes(logged_client) == [f'La entrada de esta recepción se confirma confirmando la OMC {omc["numero"]}.']
    assert _stock(wms, datos, datos['material_lote'])['DEST'] == ('LOTE-A', 0, 0, 17, 0)

    logged_client.post(f'/omc/confirmar/{omc["id_omc"]}', data={'password_admin': usuario_wms['password']})
    assert 'confirmada' in ' '.join(_flashes(logged_client)).lower()
    assert _stock(wms, datos, datos['material_lote']) == {'DEST': ('LOTE-A', 17, 17, 0, 0)}     # una sola vez, en el destino
    assert _recepcion(wms, id_recepcion)['estado'].capitalize() == 'Confirmada'


@requires_db
def test_anular_la_omc_no_duplica_stock_y_confirma_la_recepcion(logged_client, wms, datos):
    """Se podía confirmar desde la recepción y después anular la OMC: el stock quedaba en las dos ubicaciones.
    Y al anular la OMC la recepción quedaba Cerrada para siempre."""
    id_recepcion, _ = _nueva(logged_client, datos)
    _item(logged_client, id_recepcion, datos['material'], cantidad_recibida=17)
    _cerrar(logged_client, id_recepcion, datos['destino'])
    omc = _omc(wms, id_recepcion)
    logged_client.post(f'/recepciones/confirmar_stock/{id_recepcion}')     # rechazado: la OMC está pendiente
    _flashes(logged_client)

    logged_client.post(f'/omc/anular/{omc["id_omc"]}')
    assert 'anulada' in ' '.join(_flashes(logged_client)).lower()
    stock = _stock(wms, datos, datos['material'])
    assert stock['RECEP'] == ('UNICO', 17, 17, 0, 0)                       # disponible en la ubicación de recepción
    assert stock.get('DEST', ('UNICO', 0, 0, 0, 0))[1:] == (0, 0, 0, 0)    # y nada en el destino
    r = _recepcion(wms, id_recepcion)
    assert r['estado'].capitalize() == 'Confirmada' and r['id_ubicacion_destino'] == datos['recep']


@requires_db
def test_recepcion_cerrada_sin_omc_se_confirma_desde_la_recepcion(logged_client, wms, datos):
    """Recepciones cerradas antes de que existiera la OMC: confirmar pasa el stock al destino y limpia el origen."""
    id_recepcion, _ = _nueva(logged_client, datos)
    _item(logged_client, id_recepcion, datos['material'], cantidad_recibida=5)
    _cerrar(logged_client, id_recepcion, datos['destino'])
    cur = wms.cursor()
    cur.execute("DELETE FROM omc_contenedores WHERE id_omc IN (SELECT id_omc FROM omc WHERE id_recepcion = %s)", (id_recepcion,))
    cur.execute("DELETE FROM omc WHERE id_recepcion = %s", (id_recepcion,))
    wms.commit()

    logged_client.post(f'/recepciones/confirmar_stock/{id_recepcion}')
    assert 'Entrada confirmada' in _flashes(logged_client)[0]
    assert _stock(wms, datos, datos['material']) == {'DEST': ('UNICO', 5, 5, 0, 0)}
    assert _recepcion(wms, id_recepcion)['estado'].capitalize() == 'Confirmada'


# --- Importación ---

def _importar(client, contenido):
    r = client.post('/recepciones/importar', data={
        'archivo': (io.BytesIO(contenido.encode('utf-8')), 'recepciones.csv')}, content_type='multipart/form-data')
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()


def _recepciones_del_proveedor(conn, datos):
    conn.commit()
    cur = conn.cursor()
    cur.execute("SELECT id_recepcion, id_ubicacion_destino FROM recepciones_cabecera WHERE id_proveedor = %s ORDER BY id_recepcion",
                (datos['proveedor'],))
    return cur.fetchall()


@requires_db
def test_importar(logged_client, wms, datos):
    prov, recep, destino = datos['prov_codigos'][datos['proveedor']], datos['codigos'][datos['recep']], datos['codigos'][datos['destino']]
    mat, mat_lote = datos['mat_codigos'][datos['material']], datos['mat_codigos'][datos['material_lote']]
    ajeno = datos['mat_codigos'][datos['material_ajeno_al_proveedor']]
    encabezado = 'agrupador,proveedor_codigo,ubicacion_recep,ubicacion_destino,material_codigo,lote,fecha_vencimiento,cantidad,tipo_stock'
    resultado = _importar(logged_client, '\n'.join([
        encabezado,
        f'BUENA,{prov},{recep},{destino},{mat},,,100,',
        f'BUENA,{prov},{recep},{destino},{mat_lote},L-1,2027-06-30,"12,5",Calidad',
        # Un grupo con una línea mala no se guarda ni en parte (antes quedaba la recepción a medias, o vacía)
        f'MALA,{prov},{recep},,{mat},,,5,',
        f'MALA,{prov},{recep},,NOEXISTE,,,5,',
        f'MALA,{prov},{recep},,{ajeno},,,5,',
        f'MALA,{prov},{recep},,{mat_lote},,,5,',
        f'MALA,{prov},{recep},,{mat},,,-1,',
        f'REPETIDO,{prov},{recep},,{mat_lote},L-1,,5,',
        f'REPETIDO,{prov},{recep},,{mat_lote},L-2,,5,',
        f'DESTINO,{prov},{recep},NOEXISTE,{mat},,,5,',
        f'UBICACION,{prov},{destino},,{mat},,,5,',
        f'PROVEEDOR,NOEXISTE,{recep},,{mat},,,5,',
    ]))
    assert resultado['insertados'] == 1
    razones = [(e['codigo'], e['fila'], e['razon']) for e in resultado['errores']]
    assert ('MALA', 4, 'Material "NOEXISTE" no encontrado') in razones
    assert any(c == 'MALA' and f == 5 and 'no está asignado al proveedor' in r for c, f, r in razones)
    assert any(c == 'MALA' and f == 6 and 'hay que indicar el lote' in r for c, f, r in razones)
    assert ('MALA', 7, 'Cantidad esperada: no puede ser negativa.') in razones
    assert any(c == 'REPETIDO' and f == 9 and 'está repetido en la recepción' in r for c, f, r in razones)
    assert ('DESTINO', 10, 'Ubicación destino "NOEXISTE" no encontrada') in razones
    assert any(c == 'UBICACION' and 'no es de recepción' in r for c, f, r in razones)
    assert ('PROVEEDOR', 12, 'Proveedor "NOEXISTE" no encontrado') in razones

    creadas = _recepciones_del_proveedor(wms, datos)
    assert len(creadas) == 1 and creadas[0]['id_ubicacion_destino'] == datos['destino']
    cur = wms.cursor()
    cur.execute("""SELECT id_material, lote, cantidad_esperada, cantidad_recibida, tipo_stock, fecha_vencimiento
                   FROM recepciones_detalle WHERE id_recepcion = %s ORDER BY id_detalle""", (creadas[0]['id_recepcion'],))
    lineas = [(r['id_material'], r['lote'], float(r['cantidad_esperada']), float(r['cantidad_recibida']), r['tipo_stock'].lower(),
               str(r['fecha_vencimiento'] or '')) for r in cur.fetchall()]
    assert lineas == [(datos['material'], 'UNICO', 100.0, 0.0, 'libre venta', ''),
                      (datos['material_lote'], 'L-1', 12.5, 0.0, 'calidad', '2027-06-30')]
