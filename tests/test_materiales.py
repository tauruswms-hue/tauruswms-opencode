"""Materiales: alta, validaciones, baja y plantillas de importación."""

import io
import uuid

import pytest
from werkzeug.datastructures import FileStorage

from modules.batch_utils import parse_file
from tests.conftest import requires_db

PREFIJO = 'ZZT'   # los códigos de prueba empiezan así, para poder limpiarlos


def _ean13(base12):
    """EAN-13 válido a partir de sus primeros 12 dígitos."""
    suma = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(base12))
    return base12 + str((10 - suma % 10) % 10)


def _gtin14(base13):
    suma = sum(int(d) * (1 if i % 2 else 3) for i, d in enumerate(base13))
    return base13 + str((10 - suma % 10) % 10)


def _codigo():
    return PREFIJO + uuid.uuid4().hex[:8].upper()


def _barras():
    """EAN-13 distinto en cada llamada."""
    return _ean13(str(uuid.uuid4().int)[:12])


@pytest.fixture
def wms(usuario_wms):
    """Conexión al WMS; al terminar borra lo que los tests hayan creado."""
    from modules.db_config import get_db_connection
    conn = get_db_connection()
    tenant = usuario_wms['tenant_id']
    yield conn
    cur = conn.cursor()
    cur.execute("SELECT id FROM materiales WHERE codigo LIKE %s AND tenant_id = %s", (PREFIJO + '%', tenant))
    ids = [r['id'] for r in cur.fetchall()]
    for mid in ids:
        cur.execute("DELETE FROM stock_movimientos WHERE id_material = %s", (mid,))
        cur.execute("DELETE FROM materiales WHERE id = %s", (mid,))
    cur.execute("DELETE FROM materiales WHERE codigo = 'MAT001' AND nombre = 'Ejemplo Material' AND tenant_id = %s",
                (tenant,))
    cur.execute("DELETE FROM proveedores WHERE codigo LIKE %s AND tenant_id = %s", (PREFIJO + '%', tenant))
    conn.commit()
    conn.close()


def _flashes(client):
    with client.session_transaction() as s:
        # sin el saludo que deja el login
        mensajes = [m for _, m in s.get('_flashes', []) if not m.startswith('Bienvenido')]
        s['_flashes'] = []
    return mensajes


def _material(conn, codigo):
    conn.commit()  # refresca el snapshot de la transacción
    cur = conn.cursor()
    cur.execute("SELECT * FROM materiales WHERE codigo = %s", (codigo,))
    return cur.fetchone()


def _guardar(client, **datos):
    datos.setdefault('nombre', 'Material de prueba')
    client.post('/materiales/guardar', data=datos)
    return _flashes(client)


def _proveedor(conn, tenant):
    cur = conn.cursor()
    cur.execute("INSERT INTO proveedores (codigo, razonsocial, tenant_id) VALUES (%s, %s, %s)",
                (_codigo(), 'Proveedor "de prueba"', tenant))
    conn.commit()
    cur.execute("SELECT MAX(id) AS id FROM proveedores WHERE tenant_id = %s", (tenant,))
    return cur.fetchone()['id']


# --- Alta y validaciones ---

@requires_db
def test_alta_sin_proveedores_y_listado(logged_client, wms):
    codigo = _codigo()
    assert _guardar(logged_client, codigo=codigo) == ['Material guardado correctamente']
    m = _material(wms, codigo)
    assert m and m['activo'] and m['trazabilidad'].lower() == 'ninguna'
    assert codigo in logged_client.get('/materiales').get_data(as_text=True)


@requires_db
def test_trazabilidad_se_muestra_aunque_la_base_la_guarde_en_mayusculas(logged_client, wms):
    """Hay instalaciones con el enum en mayúsculas ('LOTE'): el listado y la edición lo tienen que reconocer."""
    codigo = _codigo()
    _guardar(logged_client, codigo=codigo, trazabilidad='lote')
    assert _material(wms, codigo)['trazabilidad'].lower() == 'lote'
    html = logged_client.get('/materiales').get_data(as_text=True)
    fila = html[html.index(f'<code>{codigo}</code>'):]
    fila = fila[:fila.index('</tr>')]
    assert 'title="Por Lote"' in fila
    assert '"trazabilidad": "lote"' in fila


@requires_db
def test_codigo_repetido_da_mensaje_claro(logged_client, wms):
    codigo = _codigo()
    _guardar(logged_client, codigo=codigo)
    mensajes = _guardar(logged_client, codigo=codigo, nombre='Otro')
    assert mensajes == [f'Ya existe un material con el código "{codigo}".']
    assert _material(wms, codigo)['nombre'] == 'Material de prueba'


@requires_db
def test_codigo_de_barras_repetido_se_rechaza(logged_client, wms):
    barras, primero, segundo = _barras(), _codigo(), _codigo()
    _guardar(logged_client, codigo=primero, codigo_barras=barras)
    mensajes = _guardar(logged_client, codigo=segundo, codigo_barras=barras)
    assert mensajes == [f'El código de barras {barras} ya está asignado al material "{primero}".']
    assert _material(wms, segundo) is None
    # Volver a guardar el mismo material con su propio código de barras sí se puede
    mid = _material(wms, primero)['id']
    assert _guardar(logged_client, id=mid, codigo=primero, codigo_barras=barras) == ['Material guardado correctamente']


@requires_db
@pytest.mark.parametrize('datos, mensaje', [
    ({'stock_minimo': '10', 'stock_maximo': '5'}, 'El stock mínimo no puede ser mayor que el stock máximo.'),
    ({'stock_minimo': '-1'}, 'Stock mínimo no puede ser menor que 0.'),
    ({'peso_neto': 'abc'}, 'Peso neto: "abc" no es un número válido.'),
    ({'trazabilidad': 'otra'}, 'Trazabilidad inválida.'),
    ({'categoria_id': '999999999'}, 'Categoría: el valor elegido no existe.'),
    ({'codigo_barras': '1234567890123'}, 'El código de barras tiene un dígito verificador inválido.'),
    ({'prov_ids[]': '999999999'}, 'Proveedor: el valor elegido no existe.'),
])
def test_datos_invalidos_no_se_guardan(logged_client, wms, datos, mensaje):
    codigo = _codigo()
    assert _guardar(logged_client, codigo=codigo, **datos) == [mensaje]
    assert _material(wms, codigo) is None


@requires_db
def test_metodo_de_picking_no_habilitado_usa_uno_valido(logged_client, wms, usuario_wms):
    from modules.materiales import _get_picking_metodos
    codigo = _codigo()
    _guardar(logged_client, codigo=codigo, metodo_picking='inventado')
    assert _material(wms, codigo)['metodo_picking'] in _get_picking_metodos(usuario_wms['tenant_id'])


@requires_db
def test_proveedores_y_presentaciones_con_comillas(logged_client, wms, usuario_wms):
    codigo, prov = _codigo(), _proveedor(wms, usuario_wms['tenant_id'])
    gtin = _gtin14(str(uuid.uuid4().int)[:13])
    assert _guardar(logged_client, codigo=codigo, **{
        'prov_ids[]': [str(prov)], 'prov_codigos[]': ['REF "A"'], 'prov_habitual': '0',
        'pres_nombres[]': ['Tubo 2"'], 'pres_barcodes[]': [gtin], 'pres_cantidades[]': ['12'],
        'pres_pesos_brutos[]': [''], 'pres_pesos_netos[]': ['1.5'],
    }) == ['Material guardado correctamente']
    mid = _material(wms, codigo)['id']
    cur = wms.cursor()
    cur.execute("SELECT * FROM material_proveedor WHERE id_material = %s", (mid,))
    relacion = cur.fetchone()
    assert relacion['codigo_referencia_prov'] == 'REF "A"' and relacion['es_habitual']
    cur.execute("SELECT * FROM material_presentaciones WHERE id_material = %s", (mid,))
    pres = cur.fetchone()
    assert pres['nombre'] == 'Tubo 2"' and float(pres['cantidad_unidades']) == 12 and pres['codigo_barras'] == gtin

    # La pantalla manda esos valores al navegador como datos, no dentro del HTML del formulario
    html = logged_client.get('/materiales').get_data(as_text=True)
    assert 'Tubo 2\\"' in html and 'value="Tubo 2"' not in html

    # El mismo GTIN-14 en otro material se rechaza; el mismo proveedor dos veces, también
    otro = _codigo()
    assert _guardar(logged_client, codigo=otro, **{
        'pres_nombres[]': ['Caja'], 'pres_barcodes[]': [gtin], 'pres_cantidades[]': ['1'],
    }) == [f'Presentación "Caja": el GTIN-14 {gtin} ya lo usa el material "{codigo}".']
    assert _guardar(logged_client, codigo=otro, **{'prov_ids[]': [str(prov), str(prov)]}) == [
        'Hay un proveedor repetido en la lista de proveedores.']
    assert _material(wms, otro) is None


def test_el_formulario_escapa_los_valores_que_inserta():
    """materiales.js arma filas con texto del usuario: tiene que pasar por esc()."""
    from pathlib import Path
    js = (Path(__file__).resolve().parent.parent / 'static' / 'js' / 'materiales.js').read_text(encoding='utf-8')
    for campo in ('p.razonsocial', 'codigoProv', 'nombre', 'codigoBarras'):
        assert '${esc(' + campo + ')}' in js
        assert '${' + campo + '}' not in js


@requires_db
def test_editar_un_material_inexistente_no_crea_nada(logged_client, wms):
    codigo = _codigo()
    mensajes = _guardar(logged_client, id='999999999', codigo=codigo, **{'pres_nombres[]': ['Caja']})
    assert mensajes == ['El material que se intenta modificar no existe.']
    cur = wms.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM material_presentaciones WHERE id_material = 999999999")
    assert cur.fetchone()['n'] == 0


# --- Baja ---

@requires_db
def test_eliminar_sin_movimientos_borra(logged_client, wms):
    codigo = _codigo()
    _guardar(logged_client, codigo=codigo)
    logged_client.post(f"/materiales/eliminar/{_material(wms, codigo)['id']}")
    assert _flashes(logged_client) == ['Material eliminado']
    assert _material(wms, codigo) is None


@requires_db
def test_eliminar_con_movimientos_desactiva_y_se_puede_reactivar(logged_client, wms, usuario_wms):
    codigo = _codigo()
    _guardar(logged_client, codigo=codigo)
    mid = _material(wms, codigo)['id']
    cur = wms.cursor()
    cur.execute("""INSERT INTO stock_movimientos (tenant_id, fecha, accion, id_material, cantidad)
                   VALUES (%s, '2000-01-01 00:00:00', 'TEST', %s, 1)""", (usuario_wms['tenant_id'], mid))
    wms.commit()

    logged_client.post(f'/materiales/eliminar/{mid}')
    assert 'quedó inactivo' in _flashes(logged_client)[0]
    assert not _material(wms, codigo)['activo']
    assert 'Inactivo</span>' in logged_client.get('/materiales').get_data(as_text=True)

    # Guardar desde otro origen, sin el campo "activo", no cambia el estado
    _guardar(logged_client, id=mid, codigo=codigo)
    assert not _material(wms, codigo)['activo']
    # El formulario manda 0 y, tildado, 1
    _guardar(logged_client, id=mid, codigo=codigo, activo=['0', '1'])
    assert _material(wms, codigo)['activo']
    _guardar(logged_client, id=mid, codigo=codigo, activo=['0'])
    assert not _material(wms, codigo)['activo']


@requires_db
def test_eliminar_inexistente_avisa(logged_client, wms):
    logged_client.post('/materiales/eliminar/999999999')
    assert _flashes(logged_client) == ['Material no encontrado.']


# --- Importación ---

@requires_db
@pytest.mark.parametrize('formato', ['csv', 'json', 'xlsx'])
def test_la_plantilla_descargada_se_puede_importar(logged_client, wms, formato):
    """Cada plantilla tiene que poder leerse tal cual se descarga: una fila, la de ejemplo."""
    plantilla = logged_client.get(f'/materiales/plantilla/{formato}')
    assert plantilla.status_code == 200
    filas = parse_file(FileStorage(io.BytesIO(plantilla.data), filename=f'plantilla.{formato}'))
    assert [(f['codigo'], f['nombre']) for f in filas] == [('MAT001', 'Ejemplo Material')]

    # E importarse: el ejemplo referencia categoría, unidad y proveedor 1, que pueden no existir
    r = logged_client.post('/materiales/importar', data={
        'archivo': (io.BytesIO(plantilla.data), f'plantilla.{formato}')}, content_type='multipart/form-data')
    resultado = r.get_json()
    assert r.status_code == 200 and 'error' not in resultado
    assert resultado['insertados'] + len(resultado['omitidos']) + len(resultado['errores']) == 1
    assert all('obligatorios' not in e['razon'] for e in resultado['errores'])


@requires_db
def test_importar_csv(logged_client, wms):
    bueno, sin_categoria = _codigo(), _codigo()
    csv = ('codigo,nombre,categoria_id,metodo_picking\n'
           f'{bueno},Importado,,inventado\n'
           f'{sin_categoria},Con categoría inexistente,999999999,\n'
           f'{bueno},Repetido en el archivo,,\n'
           ',Sin código,,\n')
    r = logged_client.post('/materiales/importar', data={
        'archivo': (io.BytesIO(csv.encode('utf-8')), 'materiales.csv')}, content_type='multipart/form-data')
    resultado = r.get_json()
    assert resultado['insertados'] == 1 and resultado['omitidos'] == [bueno]
    assert sorted(e['razon'] for e in resultado['errores']) == [
        'Código y Nombre son obligatorios', 'categoria_id: el valor elegido no existe.']
    assert _material(wms, bueno)['nombre'] == 'Importado'
    assert _material(wms, sin_categoria) is None


# --- Lector de archivos (compartido por todas las importaciones) ---

def _leer(contenido, nombre):
    return parse_file(FileStorage(io.BytesIO(contenido.encode('utf-8')), filename=nombre))


def test_csv_ignora_comentarios_y_tablas_de_referencia():
    filas = _leer('# TITULO\n\nCodigo,Nombre\nA,Uno\n\nB,Dos\n\n# REFERENCIAS\nid,nombre\n1,Categoría\n', 'x.csv')
    assert filas == [{'codigo': 'A', 'nombre': 'Uno'}, {'codigo': 'B', 'nombre': 'Dos'}]


def test_csv_simple_sigue_funcionando():
    assert _leer('codigo,nombre\nA,Uno\n', 'x.csv') == [{'codigo': 'A', 'nombre': 'Uno'}]


def test_json_acepta_array_u_objeto_con_listas():
    assert _leer('[{"Codigo": "A"}]', 'x.json') == [{'codigo': 'A'}]
    assert _leer('{"materiales": [{"codigo": "A"}], "categorias": [{"id": 1}]}', 'x.json') == [{'codigo': 'A'}]
    for malo in ('{"a": 1}', '"texto"', '[1, 2]'):
        with pytest.raises(ValueError, match='array de objetos'):
            _leer(malo, 'x.json')
