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
    # El formulario manda el Estado: 1 = Activo, 0 = Inactivo
    _guardar(logged_client, id=mid, codigo=codigo, activo='1')
    assert _material(wms, codigo)['activo']
    _guardar(logged_client, id=mid, codigo=codigo, activo='0')
    assert not _material(wms, codigo)['activo']


@requires_db
def test_estado_activo_o_inactivo(logged_client, wms):
    activo, inactivo, sin_estado = _codigo(), _codigo(), _codigo()
    _guardar(logged_client, codigo=activo, activo='1')
    _guardar(logged_client, codigo=inactivo, activo='0')    # se puede dar de alta ya inactivo
    _guardar(logged_client, codigo=sin_estado)               # sin indicarlo, nace activo
    assert _material(wms, activo)['activo'] and _material(wms, sin_estado)['activo']
    assert not _material(wms, inactivo)['activo']

    html = logged_client.get('/materiales').get_data(as_text=True)
    # El formulario tiene el campo Estado con las dos opciones, y el listado una columna
    lista = html[html.index('id="form_activo"'):]
    lista = lista[:lista.index('</select>')]
    assert '<option value="1">Activo</option>' in lista and '<option value="0">Inactivo</option>' in lista
    assert '>Estado</th>' in html
    for codigo, texto in ((activo, 'Activo</span>'), (inactivo, 'Inactivo</span>')):
        fila = html[html.index(f'<code>{codigo}</code>'):]
        assert texto in fila[:fila.index('</tr>')]


@requires_db
def test_estado_en_importacion_y_exportacion(logged_client, wms):
    a, b, c = _codigo(), _codigo(), _codigo()
    csv = f'codigo,nombre,activo\n{a},Activo,1\n{b},Inactivo,0\n{c},Sin indicar,\n'
    logged_client.post('/materiales/importar', data={
        'archivo': (io.BytesIO(csv.encode('utf-8')), 'materiales.csv')}, content_type='multipart/form-data')
    assert _material(wms, a)['activo'] and _material(wms, c)['activo'] and not _material(wms, b)['activo']
    exportado = logged_client.get('/materiales/exportar/csv').get_data(as_text=True)
    assert 'activo' in exportado.splitlines()[0].split(',')


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


# --- Métodos de picking: los habilitados para el tenant (parámetros del panel admin) ---

@pytest.fixture
def picking_del_tenant(usuario_wms):
    """Permite fijar los métodos habilitados del tenant de prueba; al final los restaura."""
    from modules.db_config import _get_admin_connection
    conn = _get_admin_connection()
    cur = conn.cursor()
    cur.execute("SELECT metodosdepicking, metodo_picking_default FROM tenants WHERE id = %s", (usuario_wms['tenant_id'],))
    original = cur.fetchone()

    def fijar(metodos, default):
        import json
        cur.execute("UPDATE tenants SET metodosdepicking = %s, metodo_picking_default = %s WHERE id = %s",
                    (json.dumps(metodos), default, usuario_wms['tenant_id']))
        conn.commit()

    yield fijar
    cur.execute("UPDATE tenants SET metodosdepicking = %s, metodo_picking_default = %s WHERE id = %s",
                (original['metodosdepicking'], original['metodo_picking_default'], usuario_wms['tenant_id']))
    conn.commit()
    conn.close()


def _opciones_de_picking(html):
    import re
    lista = html[html.index('id="form_metodo_picking"'):]
    return re.findall(r'<option value="([^"]*)"', lista[:lista.index('</select>')])


@requires_db
def test_el_formulario_ofrece_solo_los_metodos_habilitados(logged_client, wms, picking_del_tenant):
    picking_del_tenant(['fefo', 'libre'], 'fefo')
    html = logged_client.get('/materiales').get_data(as_text=True)
    assert _opciones_de_picking(html) == ['fefo', 'libre']
    assert 'const metodoPickingDefault = "fefo";' in html
    # La ayuda de la importación también lista solo los habilitados, y la plantilla usa el default
    ayuda = html[html.index('<code>metodo_picking</code>'):]
    ayuda = ayuda[:ayuda.index('</tr>')]
    assert '<code>fefo</code> / <code>libre</code>' in ayuda and 'fifo' not in ayuda and 'lifo' not in ayuda
    plantilla = logged_client.get('/materiales/plantilla/csv').get_data(as_text=True)
    assert ',ninguna,fefo,' in plantilla

    # Cambia la configuración en el panel: la pantalla lo refleja sin reiniciar
    picking_del_tenant(['lifo'], 'lifo')
    assert _opciones_de_picking(logged_client.get('/materiales').get_data(as_text=True)) == ['lifo']


@requires_db
def test_material_con_metodo_que_ya_no_esta_habilitado_se_marca(logged_client, wms, picking_del_tenant):
    codigo = _codigo()
    picking_del_tenant(['fifo', 'lifo'], 'fifo')
    _guardar(logged_client, codigo=codigo, metodo_picking='lifo')
    assert _material(wms, codigo)['metodo_picking'] == 'lifo'

    picking_del_tenant(['fifo'], 'fifo')   # se deshabilita LIFO para la empresa
    html = logged_client.get('/materiales').get_data(as_text=True)
    fila = html[html.index(f'<code>{codigo}</code>'):]
    fila = fila[:fila.index('</tr>')]
    assert 'no está habilitado para la empresa' in fila
    # Al guardarlo de nuevo con ese método, queda con uno habilitado
    _guardar(logged_client, id=_material(wms, codigo)['id'], codigo=codigo, metodo_picking='lifo')
    assert _material(wms, codigo)['metodo_picking'] == 'fifo'


def test_metodo_por_defecto_siempre_es_uno_habilitado(monkeypatch):
    """Un default que quedó fuera de los habilitados no se usa: se toma el primero habilitado."""
    from modules import materiales

    class _Cursor:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, *a): pass
        def fetchone(self): return {'metodosdepicking': '["fifo", "lifo"]', 'metodo_picking_default': 'libre'}

    class _Conn:
        def cursor(self): return _Cursor()
        def close(self): pass

    monkeypatch.setattr(materiales, '_get_admin_connection', lambda: _Conn())
    assert materiales._picking_del_tenant(1) == (['fifo', 'lifo'], 'fifo')
    assert materiales._picking_del_tenant(None) == (['fifo', 'lifo', 'fefo', 'libre'], 'libre')


# --- Código alternativo, código del proveedor y volumen con su unidad ---

@pytest.fixture
def unidades_prueba(wms, usuario_wms):
    """Una unidad de magnitud VOLUMEN y otra de MASA para el tenant de prueba."""
    cur = wms.cursor()
    ids = {}
    for clave, magnitud in (('litro', 'VOLUMEN'), ('kilo', 'MASA')):
        codigo = _codigo()
        cur.execute("INSERT INTO unidades_medida (codigo, nombre, simbolo, tipo_magnitud, tenant_id) "
                    "VALUES (%s, %s, %s, %s, %s)", (codigo, clave.capitalize(), clave[0], magnitud, usuario_wms['tenant_id']))
        wms.commit()
        cur.execute("SELECT id_unidad FROM unidades_medida WHERE codigo = %s", (codigo,))
        ids[clave] = cur.fetchone()['id_unidad']
    yield ids
    cur.execute("UPDATE materiales SET volumen_unidad_id = NULL WHERE volumen_unidad_id IN (%s, %s)", tuple(ids.values()))
    cur.execute("DELETE FROM unidades_medida WHERE id_unidad IN (%s, %s)", tuple(ids.values()))
    wms.commit()


@requires_db
def test_codigos_alternativo_y_proveedor_y_volumen(logged_client, wms, unidades_prueba):
    codigo = _codigo()
    assert _guardar(logged_client, codigo=codigo, codigo_alternativo=' ALT-77 ', codigo_proveedor='PRV/123',
                    volumen='1.5', volumen_unidad_id=unidades_prueba['litro']) == ['Material guardado correctamente']
    m = _material(wms, codigo)
    assert m['codigo_alternativo'] == 'ALT-77' and m['codigo_proveedor'] == 'PRV/123'
    assert float(m['volumen']) == 1.5 and m['volumen_unidad_id'] == unidades_prueba['litro']

    # El listado muestra los códigos (se pueden buscar) y el formulario recibe los cuatro campos
    html = logged_client.get('/materiales').get_data(as_text=True)
    fila = html[html.index(f'<code>{codigo}</code>'):]
    fila = fila[:fila.index('</tr>')]
    assert 'Alt: ALT-77' in fila and 'Prov: PRV/123' in fila
    assert '"codigo_alternativo": "ALT-77"' in fila and f'"volumen_unidad_id": {unidades_prueba["litro"]}' in fila
    # La lista de unidades del volumen ofrece solo las de magnitud Volumen
    lista = html[html.index('id="form_volumen_unidad"'):]
    lista = lista[:lista.index('</select>')]
    assert f'value="{unidades_prueba["litro"]}"' in lista and f'value="{unidades_prueba["kilo"]}"' not in lista

    # Sin volumen, la unidad no se guarda; los códigos vacíos vuelven a valer el código del material
    _guardar(logged_client, id=m['id'], codigo=codigo, volumen='', volumen_unidad_id=unidades_prueba['litro'])
    m = _material(wms, codigo)
    assert m['volumen'] is None and m['volumen_unidad_id'] is None
    assert m['codigo_alternativo'] == codigo and m['codigo_proveedor'] == codigo


@requires_db
def test_codigos_alternativo_y_proveedor_valen_el_codigo_por_defecto(logged_client, wms):
    codigo, importado = _codigo(), _codigo()
    _guardar(logged_client, codigo=codigo)
    m = _material(wms, codigo)
    assert m['codigo_alternativo'] == codigo and m['codigo_proveedor'] == codigo
    # En el listado no se repiten debajo del código cuando son iguales
    html = logged_client.get('/materiales').get_data(as_text=True)
    fila = html[html.index(f'<code>{codigo}</code>'):]
    fila = fila[:fila.index('</tr>')]
    assert 'Alt:' not in fila and 'Prov:' not in fila

    # Uno solo distinto: el otro sigue valiendo el código
    _guardar(logged_client, id=m['id'], codigo=codigo, codigo_alternativo='OTRO')
    m = _material(wms, codigo)
    assert m['codigo_alternativo'] == 'OTRO' and m['codigo_proveedor'] == codigo

    # La importación aplica el mismo valor por defecto
    csv = f'codigo,nombre,codigo_alternativo,codigo_proveedor\n{importado},Importado,,\n'
    logged_client.post('/materiales/importar', data={
        'archivo': (io.BytesIO(csv.encode('utf-8')), 'materiales.csv')}, content_type='multipart/form-data')
    m = _material(wms, importado)
    assert m['codigo_alternativo'] == importado and m['codigo_proveedor'] == importado


@requires_db
@pytest.mark.parametrize('datos, mensaje', [
    ({'volumen': '2'}, 'Volumen: falta indicar la unidad de medida.'),
    ({'volumen': '2', 'volumen_unidad_id': '{kilo}'}, 'Volumen: la unidad de medida tiene que ser de magnitud Volumen.'),
    ({'volumen': '2', 'volumen_unidad_id': '999999999'}, 'Volumen: la unidad de medida elegida no existe.'),
    ({'volumen': '-1', 'volumen_unidad_id': '{litro}'}, 'Volumen no puede ser menor que 0.'),
    ({'codigo_alternativo': 'x' * 101}, 'Código alternativo: admite hasta 100 caracteres.'),
    ({'codigo_proveedor': 'x' * 101}, 'Código proveedor: admite hasta 100 caracteres.'),
])
def test_volumen_y_codigos_invalidos(logged_client, wms, unidades_prueba, datos, mensaje):
    codigo = _codigo()
    datos = {k: (v.format(**unidades_prueba) if isinstance(v, str) else v) for k, v in datos.items()}
    assert _guardar(logged_client, codigo=codigo, **datos) == [mensaje]
    assert _material(wms, codigo) is None


@requires_db
def test_importar_y_exportar_los_campos_nuevos(logged_client, wms, unidades_prueba):
    bueno, sin_unidad = _codigo(), _codigo()
    csv = '\n'.join([
        'codigo,nombre,codigo_alternativo,codigo_proveedor,volumen,volumen_unidad_id',
        f'{bueno},Importado,ALT-9,PRV-9,0.75,{unidades_prueba["litro"]}',
        f'{sin_unidad},Sin unidad,,,3,',
    ])
    r = logged_client.post('/materiales/importar', data={
        'archivo': (io.BytesIO(csv.encode('utf-8')), 'materiales.csv')}, content_type='multipart/form-data')
    resultado = r.get_json()
    assert resultado['insertados'] == 1
    assert [e['razon'] for e in resultado['errores']] == ['Volumen: falta indicar la unidad de medida.']
    m = _material(wms, bueno)
    assert (m['codigo_alternativo'], m['codigo_proveedor'], float(m['volumen'])) == ('ALT-9', 'PRV-9', 0.75)

    exportado = logged_client.get('/materiales/exportar/csv').get_data(as_text=True)
    encabezado = exportado.splitlines()[0]
    for campo in ('codigo_alternativo', 'codigo_proveedor', 'volumen', 'volumen_unidad_id', 'volumen_unidad_nombre'):
        assert campo in encabezado
    linea = next(x for x in exportado.splitlines() if x.startswith(bueno + ','))
    assert 'ALT-9' in linea and 'PRV-9' in linea and 'Litro' in linea


# --- Stock de reposición ---

@requires_db
def test_stock_de_reposicion(logged_client, wms):
    codigo = _codigo()
    assert _guardar(logged_client, codigo=codigo, stock_minimo='10', stock_reposicion='30', stock_maximo='100') == [
        'Material guardado correctamente']
    assert float(_material(wms, codigo)['stock_reposicion']) == 30
    html = logged_client.get('/materiales').get_data(as_text=True)
    fila = html[html.index(f'<code>{codigo}</code>'):]
    fila = fila[:fila.index('</tr>')]
    assert '10 / 30 / 100' in fila and 'id="form_stock_repo"' in html

    # Es opcional: sin indicarlo queda en 0
    otro = _codigo()
    _guardar(logged_client, codigo=otro, stock_minimo='10', stock_maximo='100')
    assert float(_material(wms, otro)['stock_reposicion']) == 0


@requires_db
@pytest.mark.parametrize('datos, mensaje', [
    ({'stock_minimo': '10', 'stock_reposicion': '5', 'stock_maximo': '100'},
     'El stock de reposición no puede ser menor que el stock mínimo.'),
    ({'stock_minimo': '10', 'stock_reposicion': '150', 'stock_maximo': '100'},
     'El stock de reposición no puede ser mayor que el stock máximo.'),
    ({'stock_reposicion': '-1'}, 'Stock de reposición no puede ser menor que 0.'),
    ({'stock_reposicion': 'abc'}, 'Stock de reposición: "abc" no es un número válido.'),
])
def test_stock_de_reposicion_invalido(logged_client, wms, datos, mensaje):
    codigo = _codigo()
    assert _guardar(logged_client, codigo=codigo, **datos) == [mensaje]
    assert _material(wms, codigo) is None


@requires_db
def test_importar_y_exportar_stock_de_reposicion(logged_client, wms):
    bueno, malo = _codigo(), _codigo()
    csv = '\n'.join([
        'codigo,nombre,stock_minimo,stock_reposicion,stock_maximo',
        f'{bueno},Importado,5,20,80',
        f'{malo},Fuera de rango,5,90,80',
    ])
    r = logged_client.post('/materiales/importar', data={
        'archivo': (io.BytesIO(csv.encode('utf-8')), 'materiales.csv')}, content_type='multipart/form-data')
    resultado = r.get_json()
    assert resultado['insertados'] == 1
    assert [e['razon'] for e in resultado['errores']] == ['El stock de reposición no puede ser mayor que el stock máximo.']
    assert float(_material(wms, bueno)['stock_reposicion']) == 20
    assert 'stock_reposicion' in logged_client.get('/materiales/exportar/csv').get_data(as_text=True).splitlines()[0]


# --- Imagen del producto: ruta del servidor, ruta de red o URL ---

PNG_1X1 = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
           b'\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\xc9\xfe\x92\xef\x00\x00\x00\x00IEND\xaeB`\x82')


@requires_db
def test_imagen_por_ruta_del_servidor(logged_client, wms, tmp_path):
    archivo = tmp_path / 'producto.png'
    archivo.write_bytes(PNG_1X1)
    codigo = _codigo()
    assert _guardar(logged_client, codigo=codigo, imagen_ruta=f'  "{archivo}"  ') == ['Material guardado correctamente']
    m = _material(wms, codigo)
    assert m['imagen_ruta'] == str(archivo)   # sin espacios ni comillas (al copiar "como ruta" en Windows)

    r = logged_client.get(f"/materiales/imagen/{m['id']}")
    assert r.status_code == 200 and r.mimetype == 'image/png' and r.data == PNG_1X1
    assert r.headers['X-Content-Type-Options'] == 'nosniff'
    r.close()
    # El listado enlaza a la imagen a través del servidor
    assert f'href="/materiales/imagen/{m["id"]}"' in logged_client.get('/materiales').get_data(as_text=True)


@requires_db
def test_imagen_por_url(logged_client, wms):
    codigo, url = _codigo(), 'https://ejemplo.com/fotos/producto.jpg?v=2'
    _guardar(logged_client, codigo=codigo, imagen_ruta=url)
    m = _material(wms, codigo)
    assert m['imagen_ruta'] == url
    r = logged_client.get(f"/materiales/imagen/{m['id']}")
    assert r.status_code == 302 and r.headers['Location'] == url
    # El listado enlaza directo a la dirección web
    assert 'href="https://ejemplo.com/fotos/producto.jpg?v=2"' in logged_client.get('/materiales').get_data(as_text=True)


@requires_db
def test_imagen_de_red_que_el_servidor_no_encuentra_avisa(logged_client, wms):
    codigo, ruta = _codigo(), r'\servidor-inexistente\fotos\producto.jpg'
    mensajes = _guardar(logged_client, codigo=codigo, imagen_ruta=ruta)
    assert mensajes[0] == 'Material guardado correctamente' and 'no encuentra la imagen' in mensajes[1]
    m = _material(wms, codigo)
    assert m['imagen_ruta'] == ruta
    assert logged_client.get(f"/materiales/imagen/{m['id']}").status_code == 404


@requires_db
@pytest.mark.parametrize('ruta, mensaje', [
    (r'C:\taurus\conexiones.json', 'Imagen: el archivo tiene que ser una imagen'),
    ('/etc/passwd', 'Imagen: el archivo tiene que ser una imagen'),
    ('javascript:alert(1)', 'Imagen: como dirección web solo se admiten URL http o https.'),
    ('ftp://servidor/foto.jpg', 'Imagen: como dirección web solo se admiten URL http o https.'),
    ('file:///C:/foto.jpg', 'Imagen: como dirección web solo se admiten URL http o https.'),
    ('x' * 497 + '.jpg', 'Imagen: la ruta admite hasta 500 caracteres.'),
])
def test_imagen_con_ruta_no_admitida(logged_client, wms, ruta, mensaje):
    codigo = _codigo()
    (recibido,) = _guardar(logged_client, codigo=codigo, imagen_ruta=ruta)
    assert recibido.startswith(mensaje)
    assert _material(wms, codigo) is None


@requires_db
def test_la_ruta_de_imagen_no_sirve_para_leer_otros_archivos(logged_client, wms, tmp_path, usuario_wms):
    """Aunque la base tenga otra cosa en imagen_ruta, solo se entregan imágenes de verdad."""
    secreto = tmp_path / 'secreto.txt'
    secreto.write_text('clave: 1234', encoding='utf-8')
    disfrazado = tmp_path / 'disfrazado.png'       # extensión de imagen, contenido de texto
    disfrazado.write_text('clave: 1234', encoding='utf-8')
    cur = wms.cursor()
    for ruta in (secreto, disfrazado):
        codigo = _codigo()
        cur.execute("INSERT INTO materiales (codigo, nombre, imagen_ruta, tenant_id) VALUES (%s, 'x', %s, %s)",
                    (codigo, str(ruta), usuario_wms['tenant_id']))
        wms.commit()
        r = logged_client.get(f"/materiales/imagen/{_material(wms, codigo)['id']}")
        assert r.status_code == 404 and b'1234' not in r.data
    assert logged_client.get('/materiales/imagen/999999999').status_code == 404


@requires_db
def test_imagen_en_importacion_y_exportacion(logged_client, wms):
    codigo, url = _codigo(), 'https://ejemplo.com/a.png'
    csv = f'codigo,nombre,imagen_ruta\n{codigo},Importado,{url}\n{_codigo()},Mala,C:\\datos\\clave.txt\n'
    r = logged_client.post('/materiales/importar', data={
        'archivo': (io.BytesIO(csv.encode('utf-8')), 'materiales.csv')}, content_type='multipart/form-data')
    resultado = r.get_json()
    assert resultado['insertados'] == 1 and len(resultado['errores']) == 1
    assert _material(wms, codigo)['imagen_ruta'] == url
    exportado = logged_client.get('/materiales/exportar/csv').get_data(as_text=True)
    assert 'imagen_ruta' in exportado.splitlines()[0] and url in exportado


def test_la_ruta_de_imagen_esta_en_el_catalogo_de_permisos():
    from modules.schema_generator import ROUTE_CATALOG, ROUTES_CONSULTA, ROUTES_OPERADOR
    assert any('/materiales/imagen/*' in g['rutas'] for g in ROUTE_CATALOG)
    assert '/materiales/imagen/*' in ROUTES_OPERADOR and '/materiales/imagen/*' in ROUTES_CONSULTA


# --- Distribución: stock del material en cada posición ---

@pytest.fixture
def stock_de_prueba(wms, usuario_wms):
    """Crea ubicaciones y stock para un material; al final los borra."""
    cur = wms.cursor()
    tenant = usuario_wms['tenant_id']
    creados = {'ubicaciones': []}

    def ubicacion(codigo):
        cur.execute("INSERT INTO ubicaciones (codigo, descipcion, capacidad_maxima, ocupado, orden_picking, tenant_id) "
                    "VALUES (%s, %s, 0, 0, 0, %s)", (codigo, 'Estantería de prueba', tenant))
        wms.commit()
        cur.execute("SELECT id FROM ubicaciones WHERE codigo = %s AND tenant_id = %s", (codigo, tenant))
        creados['ubicaciones'].append(cur.fetchone()['id'])
        return creados['ubicaciones'][-1]

    def stock(id_material, id_ubicacion, contenedor, total, disponible, entrando=0, saliendo=0, lote='UNICO',
              tenant_id=tenant):
        cur.execute("""INSERT INTO stockcontable (Ubicacion, Material, Lote, TipoStock, StockTotal, StockDisponible,
                           StockEntrando, StockSaliendo, IDContenedor, tenant_id)
                       VALUES (%s, %s, %s, 'Libre Venta', %s, %s, %s, %s, %s, %s)""",
                    (id_ubicacion, id_material, lote, total, disponible, entrando, saliendo, contenedor, tenant_id))
        wms.commit()

    yield ubicacion, stock
    for uid in creados['ubicaciones']:
        cur.execute("DELETE FROM stockcontable WHERE Ubicacion = %s", (uid,))
        cur.execute("DELETE FROM ubicaciones WHERE id = %s", (uid,))
    wms.commit()


@requires_db
def test_distribucion_muestra_el_stock_por_posicion(logged_client, wms, stock_de_prueba):
    ubicacion, stock = stock_de_prueba
    codigo, otro = _codigo(), _codigo()
    _guardar(logged_client, codigo=codigo, nombre='Con stock')
    _guardar(logged_client, codigo=otro, nombre='Otro material')
    mid, otro_id = _material(wms, codigo)['id'], _material(wms, otro)['id']
    base = _codigo()   # mismo prefijo: la grilla ordena por código de ubicación
    a, b = ubicacion(base + '-A'), ubicacion(base + '-B')
    stock(mid, a, 'C1', 100, 80, saliendo=20, lote='L-01')
    stock(mid, a, 'C2', 50.5, 50.5)
    stock(mid, b, 'C3', 0, 0, entrando=30)      # todavía no llegó: se muestra, tiene cantidad en camino
    stock(mid, b, 'C4', 0, 0)                   # posición en cero: no se lista
    stock(otro_id, b, 'C5', 999, 999)           # de otro material: no se mezcla

    r = logged_client.get(f'/materiales/distribucion/{mid}')
    assert r.status_code == 200
    datos = r.get_json()
    assert datos['material']['codigo'] == codigo and datos['material']['nombre'] == 'Con stock'
    assert [(p['contenedor'], p['total'], p['disponible'], p['entrando'], p['saliendo']) for p in datos['posiciones']] == [
        ('C1', 100.0, 80.0, 0.0, 20.0), ('C2', 50.5, 50.5, 0.0, 0.0), ('C3', 0.0, 0.0, 30.0, 0.0)]
    assert datos['posiciones'][0]['lote'] == 'L-01' and datos['posiciones'][0]['ubicacion'].endswith('-A')
    assert datos['posiciones'][0]['ubicacion_descripcion'] == 'Estantería de prueba'
    assert datos['totales'] == {'total': 150.5, 'disponible': 130.5, 'entrando': 30.0, 'saliendo': 20.0}
    assert datos['ubicaciones'] == 2

    # El listado tiene el botón de Distribución para cada material
    html = logged_client.get('/materiales').get_data(as_text=True)
    assert f'onclick="verDistribucion({mid})"' in html and 'id="modalDistribucion"' in html


@requires_db
def test_distribucion_sin_stock_o_de_otro_tenant(logged_client, wms, stock_de_prueba, usuario_wms):
    ubicacion, stock = stock_de_prueba
    codigo = _codigo()
    _guardar(logged_client, codigo=codigo)
    mid = _material(wms, codigo)['id']
    datos = logged_client.get(f'/materiales/distribucion/{mid}').get_json()
    assert datos['posiciones'] == [] and datos['totales']['total'] == 0

    # Stock cargado a nombre de otro tenant para el mismo material: no se ve
    stock(mid, ubicacion(_codigo() + '-X'), 'C9', 10, 10, tenant_id=usuario_wms['tenant_id'] + 999999)
    assert logged_client.get(f'/materiales/distribucion/{mid}').get_json()['posiciones'] == []

    # Un material que no es del tenant (o no existe) no se puede consultar
    cur = wms.cursor()
    ajeno = _codigo()
    cur.execute("INSERT INTO materiales (codigo, nombre, tenant_id) VALUES (%s, 'Ajeno', %s)",
                (ajeno, usuario_wms['tenant_id'] + 999999))
    wms.commit()
    try:
        cur.execute("SELECT id FROM materiales WHERE codigo = %s", (ajeno,))
        r = logged_client.get(f"/materiales/distribucion/{cur.fetchone()['id']}")
        assert r.status_code == 404 and r.get_json() == {'error': 'Material no encontrado'}
    finally:
        cur.execute("DELETE FROM materiales WHERE codigo = %s", (ajeno,))
        wms.commit()
    assert logged_client.get('/materiales/distribucion/999999999').status_code == 404


def test_la_ruta_de_distribucion_esta_en_el_catalogo_de_permisos():
    from modules.schema_generator import ROUTE_CATALOG, ROUTES_CONSULTA, ROUTES_OPERADOR
    assert any('/materiales/distribucion/*' in g['rutas'] for g in ROUTE_CATALOG)
    assert '/materiales/distribucion/*' in ROUTES_OPERADOR and '/materiales/distribucion/*' in ROUTES_CONSULTA
