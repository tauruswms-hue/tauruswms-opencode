"""Stock contable: carga inicial por archivo y edición de una posición (tipo de stock, lote, vencimiento)."""

import io
import json

from tests.conftest import requires_db
from tests.test_omc import (  # noqa: F401  (fixtures y ayudas de los tests de OMC)
    PREFIJO,
    _alta,
    _codigo,
    _crear,
    _poner,
    datos,
    wms,
)

CABECERA = 'ubicacion_codigo,material_codigo,IDContenedor,Lote,TipoStock,StockTotal,StockDisponible,FechaVencimiento\n'


def _material(conn, datos):  # noqa: F811
    cur = conn.cursor()
    cur.execute("SELECT codigo FROM materiales WHERE id = %s", (datos['material'],))
    return cur.fetchone()['codigo']


def _importar(client, contenido, nombre='stock.csv'):
    r = client.post('/stockcontable/importar', data={'archivo': (io.BytesIO(contenido.encode('utf-8')), nombre)},
                    content_type='multipart/form-data')
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()


def _posicion(conn, contenedor):
    conn.commit()
    cur = conn.cursor()
    cur.execute("SELECT * FROM stockcontable WHERE IDContenedor = %s", (contenedor,))
    return cur.fetchone()


def _movimientos(conn, contenedor):
    conn.commit()
    cur = conn.cursor()
    cur.execute("SELECT accion, usuario, cantidad, detalle FROM stock_movimientos WHERE id_contenedor = %s ORDER BY id", (contenedor,))
    return [dict(r) for r in cur.fetchall()]


@requires_db
def test_importar_la_plantilla(logged_client, wms, datos):  # noqa: F811
    """El lector pasa las columnas a minúsculas y se buscaban con mayúsculas: no se importaba ninguna fila."""
    mat, csv_cont, json_cont = _material(wms, datos), _codigo()[:10], _codigo()[:10]
    r = _importar(logged_client, CABECERA + f"{datos['codigo_A']},{mat},{csv_cont},L1,calidad,100,,2027-12-31\n")
    assert r == {'insertados': 1, 'omitidos': [], 'errores': []}
    p = _posicion(wms, csv_cont)
    assert (p['Lote'], p['TipoStock'], str(p['FechaVencimiento'])) == ('L1', 'Calidad', '2027-12-31')
    assert (float(p['StockTotal']), float(p['StockDisponible'])) == (100, 100)       # sin disponible: todo disponible
    assert [(m['accion'], float(m['cantidad'])) for m in _movimientos(wms, csv_cont)] == [('IMPORTACION', 100)]

    r = _importar(logged_client, json.dumps([{'ubicacion_codigo': datos['codigo_A'], 'material_codigo': mat, 'IDContenedor': json_cont,
                                              'StockTotal': '7,5', 'StockDisponible': '5'}]), 'stock.json')
    assert r['insertados'] == 1
    p = _posicion(wms, json_cont)
    assert (p['Lote'], p['TipoStock'], float(p['StockTotal']), float(p['StockDisponible'])) == ('UNICO', 'Libre Venta', 7.5, 5)

    # La misma posición otra vez se omite; el mismo contenedor con otro material en su ubicación se acepta
    r = _importar(logged_client, CABECERA + f"{datos['codigo_A']},{mat},{csv_cont},,,3,,\n")
    assert r == {'insertados': 0, 'omitidos': [f"{datos['codigo_A']}/{mat}/{csv_cont}"], 'errores': []}
    assert float(_posicion(wms, csv_cont)['StockTotal']) == 100


@requires_db
def test_importar_informa_cada_fila_invalida(logged_client, wms, datos):  # noqa: F811
    mat = _material(wms, datos)
    inactivo = _codigo()
    _alta(wms, "INSERT INTO materiales (codigo, nombre, activo, tenant_id) VALUES (%s, 'Inactivo', 0, %s)",
          (inactivo, datos['tenant']), 'materiales', 'id', 'codigo', inactivo)
    en_b = _poner(wms, datos, 'B', 1)
    A, cont = datos['codigo_A'], _codigo()[:10]
    filas = {
        f'{A},{mat},{cont},,Vendible,1,,':           'Tipo de stock: "Vendible" no es válido',
        f'{A},{mat},{cont},,,1,,31/12/2027':         'Fecha de vencimiento: "31/12/2027" no es una fecha válida',
        f'{A},{mat},{cont},,,,,':                    'StockTotal: es obligatorio.',
        f'{A},{mat},{cont},,,0,,':                   'StockTotal: tiene que ser mayor que cero.',
        f'{A},{mat},{cont},,,-3,,':                  'StockTotal: no puede ser negativo.',
        f'{A},{mat},{cont},,,abc,,':                 'StockTotal: "abc" no es un número válido.',
        f'{A},{mat},{cont},,,5,8,':                  'StockDisponible: no puede ser mayor que StockTotal.',
        f'{A},{mat},{PREFIJO}12345678,,,1,,':        'IDContenedor: admite hasta 10 caracteres.',
        f'{A},{mat},{cont},{"L" * 101},,1,,':        'Lote: admite hasta 100 caracteres.',
        f'NOEXISTE,{mat},{cont},,,1,,':              'La ubicación "NOEXISTE" no existe.',
        f"{datos['codigo_inactiva']},{mat},{cont},,,1,,": 'está inactiva.',
        f"{datos['codigo_ajena']},{mat},{cont},,,1,,":    'no existe.',
        f'{A},{inactivo},{cont},,,1,,':              'está inactivo.',
        f'{A},{mat},{en_b},,,1,,':                   f"El contenedor {en_b} ya está en la ubicación {datos['codigo_B']}.",
        f'{A},{mat},,,,1,,':                         'Falta IDContenedor: son obligatorios.',
    }
    r = _importar(logged_client, CABECERA + '\n'.join(filas) + f'\n{A},{mat},{cont},,,2,,\n')
    assert r['insertados'] == 1 and r['omitidos'] == []                      # la fila válida entra igual
    razones = [e['razon'] for e in r['errores']]
    assert len(razones) == len(filas)
    for razon, esperado in zip(razones, filas.values(), strict=True):
        assert esperado in razon
    assert float(_posicion(wms, cont)['StockTotal']) == 2


def _editar(client, id_posicion, cuerpo):
    r = client.post(f'/stockcontable/editar/{id_posicion}', json=cuerpo)
    return r.status_code, r.get_json()


@requires_db
def test_editar_una_posicion(logged_client, wms, datos):  # noqa: F811
    cont = _poner(wms, datos, 'A', 10)
    id_pos = _posicion(wms, cont)['ID']
    cambio = {'tipo_stock': 'Calidad', 'lote': 'LOTE-X', 'fecha_vencimiento': '2027-12-31'}

    estado, r = _editar(logged_client, id_pos, cambio)
    assert estado == 200 and r['ok'] and r['cambios'] == 3 and r['usuario'] == 'Usuario test conftest'
    p = _posicion(wms, cont)
    assert (p['TipoStock'], p['Lote'], str(p['FechaVencimiento'])) == ('Calidad', 'LOTE-X', '2027-12-31')
    movs = _movimientos(wms, cont)
    assert len(movs) == 1 and movs[0]['usuario'] == 'Usuario test conftest'   # el nombre, como el resto del sistema
    assert movs[0]['detalle'] == ('Edición de posición: tipo de stock Libre Venta → Calidad; lote UNICO → LOTE-X; '
                                  'vencimiento - → 31/12/2027')

    estado, r = _editar(logged_client, id_pos, cambio)                      # sin cambios: no ensucia el historial
    assert estado == 200 and r['cambios'] == 0 and len(_movimientos(wms, cont)) == 1


@requires_db
def test_editar_rechaza_lo_que_no_puede_guardar(logged_client, wms, datos):  # noqa: F811
    cont = _poner(wms, datos, 'A', 10)
    id_pos = _posicion(wms, cont)['ID']
    for cuerpo, mensaje in (
        ({'tipo_stock': 'Calidad', 'lote': 'L' * 101}, 'Lote: admite hasta 100 caracteres.'),
        ({'tipo_stock': 'Calidad', 'lote': ''}, 'El lote no puede estar vacío.'),
        ({'tipo_stock': 'Otro', 'lote': 'A'}, 'Tipo de stock: "Otro" no es válido'),
        ({'tipo_stock': 'Calidad', 'lote': 'A', 'fecha_vencimiento': '31/12/2027'}, 'Fecha de vencimiento'),
        ({'tipo_stock': 'Calidad', 'lote': 123, 'fecha_vencimiento': None}, None),   # antes: error 500
        ([], 'Sin datos'),
    ):
        estado, r = _editar(logged_client, id_pos, cuerpo)
        if mensaje is None:
            assert estado == 200 and _posicion(wms, cont)['Lote'] == '123'
        else:
            assert estado == 400 and mensaje in r['error'], (cuerpo, r)
    r = logged_client.post(f'/stockcontable/editar/{id_pos}', data='x')
    assert r.status_code == 400 and r.get_json()['error'] == 'Sin datos'

    # Una posición que no existe, o de otra empresa, ya no responde "ok"
    cur = wms.cursor()
    cur.execute("""INSERT INTO stockcontable (Ubicacion, Material, Lote, TipoStock, StockTotal, StockDisponible, IDContenedor, tenant_id)
                   VALUES (%s, %s, 'UNICO', 'Libre Venta', 1, 1, %s, %s)""",
                (datos['ajena'], datos['material'], PREFIJO + 'AJENO1', datos['tenant'] + 100000))
    wms.commit()
    for id_otra in (999999999, _posicion(wms, PREFIJO + 'AJENO1')['ID']):
        estado, r = _editar(logged_client, id_otra, {'tipo_stock': 'Calidad', 'lote': 'A'})
        assert estado == 404 and r['error'] == 'La posición de stock no existe.'
    assert _posicion(wms, PREFIJO + 'AJENO1')['TipoStock'] == 'Libre Venta'


@requires_db
def test_no_se_edita_con_una_omc_en_curso(logged_client, wms, datos):  # noqa: F811
    cont = _poner(wms, datos, 'A', 5)
    id_omc, mensajes = _crear(logged_client, cont, datos['A'], datos['B'])
    assert id_omc, mensajes
    wms.commit()
    cur = wms.cursor()
    cur.execute("SELECT ID FROM stockcontable WHERE IDContenedor = %s", (cont,))
    for fila in cur.fetchall():                                              # el origen (saliendo) y el destino (entrando)
        estado, r = _editar(logged_client, fila['ID'], {'tipo_stock': 'Bloqueado', 'lote': 'OTRO'})
        assert estado == 400 and r['error'] == (f'El contenedor {cont} tiene una OMC en curso: '
                                                'confirmala o anulala antes de editar la posición.')
    cur.execute("SELECT DISTINCT TipoStock, Lote FROM stockcontable WHERE IDContenedor = %s", (cont,))
    assert [tuple(f.values()) for f in cur.fetchall()] == [('Libre Venta', 'UNICO')]

    html = logged_client.get('/stockcontable').get_data(as_text=True)          # el saliente se ve y se puede filtrar
    assert 'data-saliendo="1"' in html and 'value="saliendo"' in html
