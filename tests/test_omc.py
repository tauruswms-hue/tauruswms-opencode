"""OMC: alta, confirmación, modificación y anulación, con sus efectos sobre el stock y los pedidos."""

import re
import uuid

import pytest

from tests.conftest import requires_db

PREFIJO = 'ZZO'   # los códigos de prueba empiezan así, para poder limpiarlos


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
    cur.execute("DELETE FROM stock_movimientos WHERE id_contenedor LIKE %s", (patron,))
    cur.execute("DELETE FROM stockcontable WHERE IDContenedor LIKE %s", (patron,))
    cur.execute("SELECT DISTINCT id_omc FROM omc_contenedores WHERE id_contenedor LIKE %s", (patron,))
    for o in cur.fetchall():
        cur.execute("DELETE FROM omc_contenedores WHERE id_omc = %s", (o['id_omc'],))
        cur.execute("DELETE FROM omc WHERE id_omc = %s", (o['id_omc'],))
    cur.execute("SELECT id_pedido FROM pedidos_cabecera WHERE nro_pedido LIKE %s", (patron,))
    for p in cur.fetchall():
        cur.execute("DELETE FROM omc WHERE id_pedido = %s", (p['id_pedido'],))
        cur.execute("DELETE FROM pedidos_detalle WHERE id_pedido = %s", (p['id_pedido'],))
        cur.execute("DELETE FROM pedidos_cabecera WHERE id_pedido = %s", (p['id_pedido'],))
    cur.execute("DELETE FROM clientes WHERE codigo LIKE %s", (patron,))
    cur.execute("DELETE FROM materiales WHERE codigo LIKE %s", (patron,))
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
    """Tres ubicaciones (A, B, C), una inactiva y una de otra empresa, y un material."""
    tenant = usuario_wms['tenant_id']
    d = {'tenant': tenant, 'nombres': {}}
    nombre = _codigo()
    tipo = _alta(wms, "INSERT INTO tipoubicacion (descripcion, soporte_picking, tenant_id) VALUES (%s, 1, %s)",
                 (nombre, tenant), 'tipoubicacion', 'id', 'descripcion', nombre)
    for clave, activo, de in (('A', 1, tenant), ('B', 1, tenant), ('C', 1, tenant), ('inactiva', 0, tenant),
                              ('ajena', 1, tenant + 100000)):
        codigo = _codigo()
        d[clave] = _alta(wms, """INSERT INTO ubicaciones (codigo, tipoubicacion, capacidad_maxima, ocupado, orden_picking, activo, tenant_id)
                                 VALUES (%s, %s, 0, 0, 0, %s, %s)""", (codigo, tipo, activo, de), 'ubicaciones', 'id', 'codigo', codigo)
        d['nombres'][d[clave]] = clave
        d['codigo_' + clave] = codigo
    codigo = _codigo()
    d['material'] = _alta(wms, "INSERT INTO materiales (codigo, nombre, activo, tenant_id) VALUES (%s, 'Material de prueba', 1, %s)",
                          (codigo, tenant), 'materiales', 'id', 'codigo', codigo)
    return d


def _poner(conn, datos, ubicacion, cantidad, tipo_stock='Libre Venta'):
    """Deja stock disponible en un contenedor nuevo y devuelve su código."""
    contenedor = _codigo()[:10]
    cur = conn.cursor()
    cur.execute("""INSERT INTO stockcontable (Ubicacion, Material, Lote, TipoStock, StockTotal, StockDisponible, IDContenedor, tenant_id)
                   VALUES (%s, %s, 'UNICO', %s, %s, %s, %s, %s)""",
                (datos[ubicacion], datos['material'], tipo_stock, cantidad, cantidad, contenedor, datos['tenant']))
    conn.commit()
    return contenedor


def _stock(conn, datos):
    """Stock de prueba: {(ubicación, contenedor): (total, disponible, entrando, saliendo)}."""
    conn.commit()
    cur = conn.cursor()
    cur.execute("""SELECT Ubicacion, IDContenedor, StockTotal, StockDisponible, StockEntrando, StockSaliendo
                   FROM stockcontable WHERE Material = %s""", (datos['material'],))
    return {(datos['nombres'].get(r['Ubicacion'], r['Ubicacion']), r['IDContenedor']):
            (float(r['StockTotal']), float(r['StockDisponible']), float(r['StockEntrando']), float(r['StockSaliendo']))
            for r in cur.fetchall()}


def _crear(client, contenedor, origen, destino, contenedor_destino=''):
    """Crea una OMC; devuelve (id o None, mensajes)."""
    r = client.post('/omc/guardar', data={'id_ubicacion_destino': destino, 'id_contenedor_destino': contenedor_destino,
                                          'contenedores_origen[]': [contenedor], 'origenes[]': [origen]})
    m = re.search(r'/omc/ver/(\d+)', r.headers.get('Location', ''))
    return (int(m.group(1)) if m else None), _flashes(client)


def _omc(conn, id_omc):
    conn.commit()
    cur = conn.cursor()
    cur.execute("SELECT * FROM omc WHERE id_omc = %s", (id_omc,))
    return cur.fetchone()


def _confirmar(client, id_omc, usuario):
    client.post(f'/omc/confirmar/{id_omc}', data={'password_admin': usuario['password']})
    return _flashes(client)


# --- Alta y confirmación ---

@requires_db
def test_crear_y_confirmar(logged_client, wms, datos, usuario_wms):
    cont = _poner(wms, datos, 'A', 10)
    id_omc, mensajes = _crear(logged_client, cont, datos['A'], datos['B'])
    assert id_omc and 'creada con 1 contenedor' in mensajes[0]
    assert _stock(wms, datos) == {('A', cont): (0, 0, 0, 10), ('B', cont): (0, 0, 10, 0)}
    assert _omc(wms, id_omc)['estado'] == 'Pendiente'

    logged_client.post(f'/omc/confirmar/{id_omc}', data={'password_admin': 'otra-clave'})
    assert _flashes(logged_client) == ['Contraseña incorrecta.']
    assert 'confirmada' in _confirmar(logged_client, id_omc, usuario_wms)[0]
    assert _stock(wms, datos) == {('B', cont): (10, 10, 0, 0)}           # una sola vez, en el destino
    assert _omc(wms, id_omc)['estado'] == 'Confirmada'


def test_admin_y_superadmin_pueden_confirmar():
    """La regla estaba escrita solo para ADMIN y dejaba afuera al SUPERADMIN."""
    from modules.omc import ROLES_CONFIRMAN
    assert set(ROLES_CONFIRMAN) == {'ADMIN', 'SUPERADMIN'}


@requires_db
@pytest.mark.parametrize('destino, mensaje', [
    ('', 'Debe seleccionar una ubicación destino.'),
    ('abc', 'Debe seleccionar una ubicación destino.'),
    (999999999, 'La ubicación destino elegida no existe.'),
    ('ajena', 'La ubicación destino elegida no existe.'),
    ('inactiva', 'está inactiva.'),
    ('A', 'origen y destino no pueden ser la misma ubicación.'),
])
def test_destino_invalido_no_crea_la_omc(logged_client, wms, datos, destino, mensaje):
    """Antes: error 500 con un valor no numérico, error crudo de la base, o stock entrando a una ubicación inactiva."""
    cont = _poner(wms, datos, 'A', 5)
    id_omc, mensajes = _crear(logged_client, cont, datos['A'], datos.get(destino, destino))
    assert id_omc is None and len(mensajes) == 1 and mensaje in mensajes[0]
    assert _stock(wms, datos) == {('A', cont): (5, 5, 0, 0)}              # el stock no se tocó


@requires_db
def test_contenedor_destino_tiene_que_estar_en_la_ubicacion_destino(logged_client, wms, datos, usuario_wms):
    """Se podía mandar el contenido a un contenedor que estaba en otra ubicación: quedaba en dos lugares."""
    origen = _poner(wms, datos, 'A', 5)
    en_c = _poner(wms, datos, 'C', 3)
    id_omc, mensajes = _crear(logged_client, origen, datos['A'], datos['B'], en_c)
    assert id_omc is None and f'está en la ubicación {datos["codigo_C"]}' in mensajes[0]
    assert _stock(wms, datos) == {('A', origen): (5, 5, 0, 0), ('C', en_c): (3, 3, 0, 0)}

    # Con el contenedor destino en la ubicación destino, el contenido se suma a él
    id_omc, mensajes = _crear(logged_client, origen, datos['A'], datos['C'], en_c)
    assert id_omc, mensajes
    _confirmar(logged_client, id_omc, usuario_wms)
    assert _stock(wms, datos) == {('C', en_c): (8, 8, 0, 0)}


# --- Modificación ---

@requires_db
def test_modificar_el_destino(logged_client, wms, datos, usuario_wms):
    """Con el origen como destino, al confirmar el stock desaparecía."""
    cont = _poner(wms, datos, 'A', 10)
    id_omc, _ = _crear(logged_client, cont, datos['A'], datos['B'])
    pendiente = {('A', cont): (0, 0, 0, 10), ('B', cont): (0, 0, 10, 0)}

    for destino, mensaje in ((datos['A'], 'origen y destino no pueden ser la misma ubicación.'),
                             (datos['inactiva'], 'está inactiva.'),
                             (datos['ajena'], 'La ubicación destino elegida no existe.'),
                             ('abc', 'Debe seleccionar una ubicación destino.')):
        logged_client.post(f'/omc/modificar/{id_omc}', data={'id_ubicacion_destino': destino})
        (aviso,) = _flashes(logged_client)
        assert mensaje in aviso
        assert _stock(wms, datos) == pendiente and _omc(wms, id_omc)['id_ubicacion_destino'] == datos['B']

    logged_client.post(f'/omc/modificar/{id_omc}', data={'id_ubicacion_destino': datos['C'], 'observaciones': 'Cambio'})
    assert 'modificada correctamente' in _flashes(logged_client)[0]
    # El stock entrando pasa al nuevo destino y en el anterior no queda una fila en cero
    assert _stock(wms, datos) == {('A', cont): (0, 0, 0, 10), ('C', cont): (0, 0, 10, 0)}
    assert (_omc(wms, id_omc)['id_ubicacion_destino'], _omc(wms, id_omc)['observaciones']) == (datos['C'], 'Cambio')

    _confirmar(logged_client, id_omc, usuario_wms)
    assert _stock(wms, datos) == {('C', cont): (10, 10, 0, 0)}


# --- Anulación ---

@requires_db
def test_anular_devuelve_el_stock_al_origen(logged_client, wms, datos):
    cont = _poner(wms, datos, 'A', 10)
    id_omc, _ = _crear(logged_client, cont, datos['A'], datos['B'])
    logged_client.post(f'/omc/anular/{id_omc}')
    assert 'anulada' in _flashes(logged_client)[0]
    assert _stock(wms, datos) == {('A', cont): (10, 10, 0, 0)}            # y en el destino no queda una fila en cero
    assert _omc(wms, id_omc)['estado'] == 'Anulada'
    logged_client.post(f'/omc/anular/{id_omc}')
    assert _flashes(logged_client) == ['La OMC no existe o no está en estado Pendiente.']


# --- OMC de un pedido ---

def _pedido(conn, datos, renglones):
    """Un pedido en 'Trabajo OMC' con los renglones dados: [(cantidad, tipo de stock)]."""
    tenant = datos['tenant']
    codigo, nro = _codigo(), _codigo()
    cliente = _alta(conn, "INSERT INTO clientes (codigo, razonsocial, activo, tenant_id) VALUES (%s, 'Cliente de prueba', 1, %s)",
                    (codigo, tenant), 'clientes', 'id_cliente', 'codigo', codigo)
    id_pedido = _alta(conn, """INSERT INTO pedidos_cabecera (nro_pedido, id_cliente, fecha_pedido, estado, tenant_id)
                               VALUES (%s, %s, CURRENT_DATE, 'Trabajo OMC', %s)""", (nro, cliente, tenant),
                      'pedidos_cabecera', 'id_pedido', 'nro_pedido', nro)
    cur = conn.cursor()
    for cantidad, tipo in renglones:
        cur.execute("INSERT INTO pedidos_detalle (id_pedido, id_material, cantidad, tipo_stock, tenant_id) VALUES (%s, %s, %s, %s, %s)",
                    (id_pedido, datos['material'], cantidad, tipo, tenant))
    conn.commit()
    return id_pedido


def _omc_de_pedido(client, conn, datos, id_pedido, cantidad, tipo_stock='Libre Venta'):
    cont = _poner(conn, datos, 'A', cantidad, tipo_stock)
    id_omc, mensajes = _crear(client, cont, datos['A'], datos['B'])
    assert id_omc, mensajes
    cur = conn.cursor()
    cur.execute("UPDATE omc SET id_pedido = %s WHERE id_omc = %s", (id_pedido, id_omc))
    conn.commit()
    return id_omc


def _renglones(conn, id_pedido):
    conn.commit()
    cur = conn.cursor()
    cur.execute("SELECT tipo_stock, Cantidad_preparada FROM pedidos_detalle WHERE id_pedido = %s ORDER BY id_detalle", (id_pedido,))
    return [(r['tipo_stock'], float(r['Cantidad_preparada'])) for r in cur.fetchall()]


def _estado_pedido(conn, id_pedido):
    conn.commit()
    cur = conn.cursor()
    cur.execute("SELECT estado FROM pedidos_cabecera WHERE id_pedido = %s", (id_pedido,))
    return cur.fetchone()['estado']


@requires_db
def test_lo_preparado_se_suma_al_renglon_de_su_tipo_de_stock(logged_client, wms, datos, usuario_wms):
    """Con el material pedido en dos tipos de stock, lo preparado se sumaba a los dos renglones."""
    id_pedido = _pedido(wms, datos, [(8, 'Libre Venta'), (8, 'Calidad')])
    id_omc = _omc_de_pedido(logged_client, wms, datos, id_pedido, 8, 'Libre Venta')
    _confirmar(logged_client, id_omc, usuario_wms)
    assert _renglones(wms, id_pedido) == [('Libre Venta', 8.0), ('Calidad', 0.0)]


@requires_db
def test_anular_la_omc_de_un_pedido_lo_devuelve_a_pendiente(logged_client, wms, datos, usuario_wms):
    """Antes anulaba el pedido entero, aunque tuviera otras OMC."""
    id_pedido = _pedido(wms, datos, [(10, 'Libre Venta')])
    primera = _omc_de_pedido(logged_client, wms, datos, id_pedido, 4)
    segunda = _omc_de_pedido(logged_client, wms, datos, id_pedido, 6)

    logged_client.post(f'/omc/anular/{primera}')
    _flashes(logged_client)
    assert _estado_pedido(wms, id_pedido) == 'Trabajo OMC'                # le queda otra OMC en curso
    logged_client.post(f'/omc/anular/{segunda}')
    _flashes(logged_client)
    assert _estado_pedido(wms, id_pedido) == 'Pendiente'                  # sin OMC en curso: se puede editar o anular

    # Con una OMC ya confirmada, anular otra no cambia el estado del pedido
    otro = _pedido(wms, datos, [(10, 'Libre Venta')])
    confirmada = _omc_de_pedido(logged_client, wms, datos, otro, 4)
    pendiente = _omc_de_pedido(logged_client, wms, datos, otro, 6)
    _confirmar(logged_client, confirmada, usuario_wms)
    logged_client.post(f'/omc/anular/{pendiente}')
    _flashes(logged_client)
    assert _estado_pedido(wms, otro) == 'Preparado'
    assert _renglones(wms, otro) == [('Libre Venta', 4.0)]
