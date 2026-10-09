"""Despacho: al despachar, el stock de los contenedores del pedido sale del depósito."""

from tests.conftest import requires_db
from tests.test_omc import (  # noqa: F401  (fixtures y ayudas de los tests de OMC)
    _confirmar,
    _flashes,
    _omc_de_pedido,
    _pedido,
    _poner,
    _stock,
    datos,
    wms,
)


def _preparado(client, conn, datos, usuario, renglones, cantidades):  # noqa: F811
    """Un pedido Preparado: una OMC confirmada por cada cantidad, de A al muelle B."""
    id_pedido = _pedido(conn, datos, renglones)
    for cantidad in cantidades:
        _confirmar(client, _omc_de_pedido(client, conn, datos, id_pedido, cantidad), usuario)
    return id_pedido


def _pedido_fila(conn, id_pedido):
    conn.commit()
    cur = conn.cursor()
    cur.execute("SELECT nro_pedido, estado, fecha_despacho, usuario_despacho FROM pedidos_cabecera WHERE id_pedido = %s", (id_pedido,))
    return cur.fetchone()


def _despachos(conn, datos):  # noqa: F811
    """Movimientos de despacho del material de prueba en el historial: [cantidad]."""
    conn.commit()
    cur = conn.cursor()
    cur.execute("SELECT cantidad FROM stock_movimientos WHERE id_material = %s AND accion = 'DESPACHO' ORDER BY id",
                (datos['material'],))
    return [float(r['cantidad']) for r in cur.fetchall()]


@requires_db
def test_despachar_saca_el_stock_del_muelle(logged_client, wms, datos, usuario_wms):  # noqa: F811
    """Despachar solo cambiaba el estado: la mercadería entregada seguía disponible en el muelle para siempre."""
    id_pedido = _preparado(logged_client, wms, datos, usuario_wms, [(10, 'Libre Venta')], [4, 6])
    ajeno = _poner(wms, datos, 'B', 3)                               # otro contenedor en el muelle, que no es del pedido
    assert _pedido_fila(wms, id_pedido)['estado'] == 'Preparado'
    assert sorted(v[0] for v in _stock(wms, datos).values()) == [3, 4, 6]

    # La pantalla muestra qué se despacha
    html = logged_client.get('/despacho').get_data(as_text=True)
    fila = html[html.index(_pedido_fila(wms, id_pedido)['nro_pedido']):]
    fila = fila[:fila.index('</tr>')]
    assert f'{datos["codigo_B"]} <span' in fila and '2 contenedores' in fila and 'Completa</span>' in fila

    logged_client.post(f'/despacho/despachar/{id_pedido}')
    nro = _pedido_fila(wms, id_pedido)['nro_pedido']
    assert _flashes(logged_client) == [f'Pedido {nro} despachado.']
    assert _stock(wms, datos) == {('B', ajeno): (3, 3, 0, 0)}        # salió lo del pedido y nada más
    assert sorted(_despachos(wms, datos)) == [-6.0, -4.0]             # y quedó en el historial como salida
    p = _pedido_fila(wms, id_pedido)
    assert p['estado'] == 'Despachado' and p['fecha_despacho'] and p['usuario_despacho']

    logged_client.post(f'/despacho/despachar/{id_pedido}')            # no se despacha dos veces
    assert _flashes(logged_client) == [f'El pedido {nro} no está en estado Preparado (está Despachado).']
    logged_client.post('/despacho/despachar/999999999')
    assert _flashes(logged_client) == ['El pedido no existe.']


@requires_db
def test_despacho_avisa_lo_que_no_pudo_descontar(logged_client, wms, datos, usuario_wms):  # noqa: F811
    id_pedido = _preparado(logged_client, wms, datos, usuario_wms, [(10, 'Libre Venta')], [4])
    cur = wms.cursor()
    cur.execute("DELETE FROM stockcontable WHERE Material = %s", (datos['material'],))   # el contenedor ya no está
    wms.commit()
    logged_client.post(f'/despacho/despachar/{id_pedido}')
    mensajes = _flashes(logged_client)
    assert 'despachado' in mensajes[0] and 'ya no tiene stock en' in mensajes[1]
    assert _pedido_fila(wms, id_pedido)['estado'] == 'Despachado' and _despachos(wms, datos) == []


@requires_db
def test_preparacion_incompleta_se_marca_y_se_puede_despachar(logged_client, wms, datos, usuario_wms):  # noqa: F811
    id_pedido = _preparado(logged_client, wms, datos, usuario_wms, [(10, 'Libre Venta')], [4])   # 4 de 10
    html = logged_client.get('/despacho').get_data(as_text=True)
    fila = html[html.index(_pedido_fila(wms, id_pedido)['nro_pedido']):]
    fila = fila[:fila.index('</tr>')]
    assert 'Incompleta (1)</span>' in fila and 'ATENCIÓN: tiene 1 renglón(es)' in fila
    assert 'data-incompletos="1"' in html

    logged_client.post(f'/despacho/despachar/{id_pedido}')            # una entrega parcial se despacha igual
    assert 'despachado' in _flashes(logged_client)[0]
    assert _stock(wms, datos) == {} and _despachos(wms, datos) == [-4.0]


@requires_db
def test_despacho_masivo(logged_client, wms, datos, usuario_wms):  # noqa: F811
    preparado = _preparado(logged_client, wms, datos, usuario_wms, [(5, 'Libre Venta')], [5])
    otro = _preparado(logged_client, wms, datos, usuario_wms, [(2, 'Libre Venta')], [2])
    pendiente = _pedido(wms, datos, [(1, 'Libre Venta')])             # queda en 'Trabajo OMC': no está Preparado

    r = logged_client.post('/despacho/despachar_masivo', json={'ids': [preparado, otro, pendiente, 999999999, 'abc']})
    assert r.get_json() == {'status': 'success', 'despachados': 2, 'omitidos': 2,
                            'message': '2 pedido(s) despachado(s). 2 no se despacharon porque ya no estaban Preparados.'}
    assert _stock(wms, datos) == {} and sorted(_despachos(wms, datos)) == [-5.0, -2.0]
    assert [_pedido_fila(wms, i)['estado'] for i in (preparado, otro, pendiente)] == ['Despachado', 'Despachado', 'Trabajo OMC']

    assert logged_client.post('/despacho/despachar_masivo').status_code == 400          # sin datos: aviso
    assert logged_client.post('/despacho/despachar_masivo', json={'ids': ['abc']}).status_code == 400
