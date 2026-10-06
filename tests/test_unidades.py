"""Unidades de medida: alta, validaciones, inactivación e importación."""

import io
import uuid

import pytest

from tests.conftest import requires_db

PREFIJO = 'ZZU'   # los códigos de prueba empiezan así, para poder limpiarlos


def _codigo():
    # 9 caracteres: entra en unidad_base_referencia aun sin la migración que la amplía
    return PREFIJO + uuid.uuid4().hex[:6].upper()


@pytest.fixture
def wms(usuario_wms):
    """Conexión al WMS; al terminar borra lo que los tests hayan creado."""
    from modules.db_config import get_db_connection
    conn = get_db_connection()
    yield conn
    cur = conn.cursor()
    cur.execute("DELETE FROM materiales WHERE codigo LIKE %s", (PREFIJO + '%',))
    cur.execute("DELETE FROM unidades_medida WHERE codigo LIKE %s", (PREFIJO + '%',))
    conn.commit()
    conn.close()


def _flashes(client):
    with client.session_transaction() as s:
        # sin el saludo que deja el login
        mensajes = [m for _, m in s.get('_flashes', []) if not m.startswith('Bienvenido')]
        s['_flashes'] = []
    return mensajes


def _unidades(conn, codigo):
    conn.commit()  # refresca el snapshot de la transacción
    cur = conn.cursor()
    cur.execute("SELECT * FROM unidades_medida WHERE codigo = %s ORDER BY id_unidad", (codigo,))
    return cur.fetchall()


def _guardar(client, **datos):
    datos.setdefault('nombre', 'Unidad de prueba')
    datos.setdefault('simbolo', 'up')
    datos.setdefault('activo', 'on')
    client.post('/unidades/guardar', data=datos)
    return _flashes(client)


@requires_db
@pytest.mark.parametrize('id_enviado', ['0', '', None])
def test_alta_como_la_envia_la_pantalla(logged_client, wms, id_enviado):
    """La pantalla mandaba id_unidad=0 y el servidor lo tomaba como una modificación: no guardaba nada."""
    codigo = _codigo()
    datos = {} if id_enviado is None else {'id_unidad': id_enviado}
    assert _guardar(logged_client, codigo=codigo, tipo_magnitud='MASA', **datos) == ['Unidad guardada correctamente']
    (unidad,) = _unidades(wms, codigo)
    assert unidad['tipo_magnitud'] == 'MASA' and unidad['activo'] and float(unidad['conversion_a_base']) == 1
    assert codigo in logged_client.get('/unidades').get_data(as_text=True)


@requires_db
def test_codigo_repetido_se_rechaza(logged_client, wms):
    codigo = _codigo()
    _guardar(logged_client, codigo=codigo)
    assert _guardar(logged_client, codigo=codigo, nombre='Otra') == [f'Ya existe una unidad con el código "{codigo}".']
    (unidad,) = _unidades(wms, codigo)
    # Volver a guardar la misma unidad con su propio código sí se puede
    assert _guardar(logged_client, id_unidad=unidad['id_unidad'], codigo=codigo, nombre='Renombrada') == [
        'Unidad guardada correctamente']
    assert _unidades(wms, codigo)[0]['nombre'] == 'Renombrada'


@requires_db
@pytest.mark.parametrize('datos, mensaje', [
    ({'tipo_magnitud': 'INVENTADA'}, 'Tipo de magnitud "INVENTADA" no válido. Usar: CANTIDAD, MASA, VOLUMEN, LONGITUD, TIEMPO.'),
    ({'conversion_a_base': '0'}, 'Conversión a base: tiene que ser mayor que cero.'),
    ({'conversion_a_base': 'abc'}, 'Conversión a base: "abc" no es un número válido.'),
    ({'decimales_permitidos': '-1'}, 'Decimales permitidos: tiene que estar entre 0 y 4.'),
    ({'decimales_permitidos': '9'}, 'Decimales permitidos: tiene que estar entre 0 y 4.'),
    ({'nombre': 'x' * 101}, 'Nombre: admite hasta 100 caracteres.'),
    ({'nombre': '  '}, 'Nombre es obligatorio.'),
])
def test_datos_invalidos_no_se_guardan(logged_client, wms, datos, mensaje):
    codigo = _codigo()
    assert _guardar(logged_client, codigo=codigo, **datos) == [mensaje]
    assert _unidades(wms, codigo) == ()


@requires_db
def test_magnitudes_con_nombre_anterior_se_normalizan(logged_client, wms, usuario_wms):
    """UNIDAD y PESO eran nombres anteriores de CANTIDAD y MASA: se aceptan y se muestran con el actual."""
    nueva, vieja = _codigo(), _codigo()
    _guardar(logged_client, codigo=nueva, tipo_magnitud='peso')
    assert _unidades(wms, nueva)[0]['tipo_magnitud'] == 'MASA'

    cur = wms.cursor()
    cur.execute("INSERT INTO unidades_medida (codigo, nombre, tipo_magnitud, tenant_id) VALUES (%s, 'Vieja', 'UNIDAD', %s)",
                (vieja, usuario_wms['tenant_id']))
    wms.commit()
    html = logged_client.get('/unidades').get_data(as_text=True)
    fila = html[html.index(f'<strong>{vieja}</strong>'):]
    fila = fila[:fila.index('</tr>')]
    assert '"tipo_magnitud": "CANTIDAD"' in fila and '<td>Cantidad</td>' in fila
    # El formulario ofrece exactamente las magnitudes admitidas
    from modules.unidades import MAGNITUDES
    for valor, rotulo in MAGNITUDES.items():
        assert f'<option value="{valor}">{rotulo}</option>' in html
    assert '<option value="UNIDAD">' not in html


@requires_db
def test_editar_una_unidad_inexistente_avisa(logged_client, wms):
    codigo = _codigo()
    assert _guardar(logged_client, id_unidad='999999999', codigo=codigo) == [
        'La unidad que se intenta modificar no existe.']
    assert _unidades(wms, codigo) == ()


@requires_db
def test_inactivar_y_reactivar(logged_client, wms, usuario_wms):
    codigo = _codigo()
    _guardar(logged_client, codigo=codigo)
    uid = _unidades(wms, codigo)[0]['id_unidad']
    cur = wms.cursor()
    cur.execute("INSERT INTO materiales (codigo, nombre, unidad_medida_id, tenant_id) VALUES (%s, 'Material', %s, %s)",
                (_codigo(), uid, usuario_wms['tenant_id']))
    wms.commit()

    logged_client.post(f'/unidades/eliminar/{uid}')
    (mensaje,) = _flashes(logged_client)
    assert 'quedó inactiva' in mensaje and 'La usa 1 material, que la conserva.' in mensaje
    assert not _unidades(wms, codigo)[0]['activo']

    # Sigue en el listado, marcada, y el formulario de materiales la sigue ofreciendo a quien ya la usa
    html = logged_client.get('/unidades').get_data(as_text=True)
    assert codigo in html and 'Inactiva</span>' in html
    assert '— inactiva</option>' in logged_client.get('/materiales').get_data(as_text=True)

    logged_client.post(f'/unidades/eliminar/{uid}')
    assert 'ya estaba inactiva' in _flashes(logged_client)[0]

    # Reactivar desde la edición (casilla "Unidad Activa" tildada); destildada, queda inactiva
    _guardar(logged_client, id_unidad=uid, codigo=codigo)
    assert _unidades(wms, codigo)[0]['activo']
    logged_client.post('/unidades/guardar', data={'id_unidad': uid, 'codigo': codigo, 'nombre': 'x'})
    assert not _unidades(wms, codigo)[0]['activo']


@requires_db
def test_inactivar_inexistente_avisa(logged_client, wms):
    logged_client.post('/unidades/eliminar/999999999')
    assert _flashes(logged_client) == ['Unidad no encontrada.']


@requires_db
def test_importar(logged_client, wms):
    buena, legado, mala = _codigo(), _codigo(), _codigo()
    csv = ('codigo,nombre,simbolo,tipo_magnitud,conversion_a_base,decimales_permitidos,activo\n'
           f'{buena},Kilogramo,kg,MASA,1,3,1\n'
           f'{legado},Unidad,u,UNIDAD,,,\n'
           f'{mala},Mala,m,INVENTADA,1,0,1\n'
           f'{buena},Repetida,kg,MASA,1,0,1\n'
           f'{_codigo()},Conversión mala,x,MASA,0,0,1\n')
    r = logged_client.post('/unidades/importar', data={
        'archivo': (io.BytesIO(csv.encode('utf-8')), 'unidades.csv')}, content_type='multipart/form-data')
    resultado = r.get_json()
    assert resultado['insertados'] == 2 and resultado['omitidos'] == [buena]
    assert sorted(e['razon'] for e in resultado['errores']) == [
        'Conversión a base: tiene que ser mayor que cero.',
        'Tipo de magnitud "INVENTADA" no válido. Usar: CANTIDAD, MASA, VOLUMEN, LONGITUD, TIEMPO.']
    assert _unidades(wms, buena)[0]['decimales_permitidos'] == 3
    assert _unidades(wms, legado)[0]['tipo_magnitud'] == 'CANTIDAD' and _unidades(wms, legado)[0]['activo']
    assert _unidades(wms, mala) == ()


@requires_db
def test_la_plantilla_se_puede_importar_y_exportar(logged_client, wms):
    from werkzeug.datastructures import FileStorage

    from modules.batch_utils import parse_file
    for formato in ('csv', 'json', 'xlsx'):
        plantilla = logged_client.get(f'/unidades/plantilla/{formato}')
        filas = parse_file(FileStorage(io.BytesIO(plantilla.data), filename=f'p.{formato}'))
        assert [(f['codigo'], f['tipo_magnitud']) for f in filas] == [('UND', 'CANTIDAD')]
    # La exportación incluye las inactivas, con su estado
    codigo = _codigo()
    logged_client.post('/unidades/guardar', data={'codigo': codigo, 'nombre': 'Inactiva'})
    exportado = logged_client.get('/unidades/exportar/csv').get_data(as_text=True)
    assert codigo in exportado


# --- Unidad base: la unidad sobre la que se calculan múltiplos y submúltiplos ---

@requires_db
def test_unidad_base_y_submultiplo(logged_client, wms):
    """1000 mm = 1 m: la base del milímetro es el metro y su conversión 0,001."""
    metro, mm = _codigo(), _codigo()
    # Una unidad sin base es una unidad base: su conversión queda en 1 aunque se mande otra
    _guardar(logged_client, codigo=metro, simbolo='m', tipo_magnitud='LONGITUD', conversion_a_base='5')
    (u,) = _unidades(wms, metro)
    assert u['unidad_base_referencia'] is None and float(u['conversion_a_base']) == 1

    assert _guardar(logged_client, codigo=mm, simbolo='mm', tipo_magnitud='LONGITUD',
                    unidad_base_referencia=metro, conversion_a_base='0.001') == ['Unidad guardada correctamente']
    (u,) = _unidades(wms, mm)
    assert u['unidad_base_referencia'] == metro and float(u['conversion_a_base']) == 0.001

    html = logged_client.get('/unidades').get_data(as_text=True)
    assert '1 mm = 0.001 m' in html and '— (es base)' in html
    # El formulario es una lista desplegable; las opciones las arma el script con las unidades cargadas
    assert '<select name="unidad_base_referencia" id="unidad_base_referencia">' in html
    assert 'const unidadesCargadas = ' in html and f'"codigo": "{metro}"' in html


@requires_db
def test_unidad_base_tiene_que_existir_y_ser_de_la_misma_magnitud(logged_client, wms):
    kilo, otra = _codigo(), _codigo()
    _guardar(logged_client, codigo=kilo, simbolo='kg', tipo_magnitud='MASA')
    assert _guardar(logged_client, codigo=otra, tipo_magnitud='LONGITUD', unidad_base_referencia=kilo) == [
        f'Unidad base: "{kilo}" es de otra magnitud (Masa).']
    assert _guardar(logged_client, codigo=otra, tipo_magnitud='MASA', unidad_base_referencia='NOEXISTE') == [
        'Unidad base: no existe una unidad con el código "NOEXISTE".']
    assert _unidades(wms, otra) == ()


@requires_db
def test_unidad_base_sin_referencias_circulares_ni_cambio_de_magnitud(logged_client, wms):
    a, b = _codigo(), _codigo()
    _guardar(logged_client, codigo=a, simbolo='a', tipo_magnitud='VOLUMEN')
    _guardar(logged_client, codigo=b, simbolo='b', tipo_magnitud='VOLUMEN', unidad_base_referencia=a,
             conversion_a_base='10')
    id_a = _unidades(wms, a)[0]['id_unidad']

    # A no puede pasar a calcularse sobre B, que ya se calcula sobre A
    assert _guardar(logged_client, id_unidad=id_a, codigo=a, tipo_magnitud='VOLUMEN', unidad_base_referencia=b) == [
        f'Unidad base: "{b}" ya se calcula a partir de esta unidad (referencia circular).']
    # Ni cambiar de magnitud mientras otras la usan como base
    assert _guardar(logged_client, id_unidad=id_a, codigo=a, tipo_magnitud='MASA') == [
        'No se puede cambiar la magnitud: 1 unidad(es) usan esta como unidad base.']
    # Elegirse a sí misma equivale a no tener base
    assert _guardar(logged_client, id_unidad=id_a, codigo=a, tipo_magnitud='VOLUMEN', unidad_base_referencia=a) == [
        'Unidad guardada correctamente']
    assert _unidades(wms, a)[0]['unidad_base_referencia'] is None


@requires_db
def test_renombrar_la_unidad_base_actualiza_las_que_la_usan(logged_client, wms):
    base, derivada, nuevo = _codigo(), _codigo(), _codigo()
    _guardar(logged_client, codigo=base, tipo_magnitud='TIEMPO')
    _guardar(logged_client, codigo=derivada, tipo_magnitud='TIEMPO', unidad_base_referencia=base, conversion_a_base='60')
    _guardar(logged_client, id_unidad=_unidades(wms, base)[0]['id_unidad'], codigo=nuevo, tipo_magnitud='TIEMPO')
    assert _unidades(wms, derivada)[0]['unidad_base_referencia'] == nuevo


@requires_db
def test_importar_con_unidad_base(logged_client, wms):
    litro, ml, mala = _codigo(), _codigo(), _codigo()
    encabezado = 'codigo,nombre,simbolo,tipo_magnitud,conversion_a_base,unidad_base_referencia'
    csv = '\n'.join([
        encabezado,
        f'{litro},Litro,zzl,VOLUMEN,1,',               # unidad base
        f'{ml},Mililitro,zzml,VOLUMEN,0.001,{litro}',  # base por código, definida antes en el archivo
        f'{mala},Mala,x,VOLUMEN,2,NOEXISTE',
    ])
    r = logged_client.post('/unidades/importar', data={
        'archivo': (io.BytesIO(csv.encode('utf-8')), 'unidades.csv')}, content_type='multipart/form-data')
    resultado = r.get_json()
    assert resultado['insertados'] == 2
    assert [e['razon'] for e in resultado['errores']] == ['Unidad base: no existe una unidad con el código "NOEXISTE".']
    assert _unidades(wms, litro)[0]['unidad_base_referencia'] is None
    assert _unidades(wms, ml)[0]['unidad_base_referencia'] == litro

    # Archivos anteriores indicaban la base por su símbolo, o repetían el símbolo propio en una unidad base
    por_simbolo, propia = _codigo(), _codigo()
    csv = '\n'.join([
        encabezado,
        f'{por_simbolo},Centilitro,zzcl,VOLUMEN,0.01,zzl',
        f'{propia},Otra base,zzq,VOLUMEN,1,zzq',
    ])
    r = logged_client.post('/unidades/importar', data={
        'archivo': (io.BytesIO(csv.encode('utf-8')), 'unidades.csv')}, content_type='multipart/form-data')
    assert r.get_json()['insertados'] == 2
    assert _unidades(wms, por_simbolo)[0]['unidad_base_referencia'] == litro
    assert _unidades(wms, propia)[0]['unidad_base_referencia'] is None
