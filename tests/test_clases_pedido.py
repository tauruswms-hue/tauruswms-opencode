"""Clases de pedido: alta, validaciones, nombre único, inactivación, importación y exportación."""

import csv
import io
import uuid

import pytest

from tests.conftest import requires_db

PREFIJO = 'ZZK'   # los nombres de prueba empiezan así, para poder limpiarlos


def _nombre():
    return PREFIJO + uuid.uuid4().hex[:8].upper()


@pytest.fixture
def wms(usuario_wms):
    """Conexión al WMS; al terminar borra lo que los tests hayan creado."""
    from modules.db_config import get_db_connection
    conn = get_db_connection()
    yield conn
    conn.commit()
    cur = conn.cursor()
    cur.execute("DELETE FROM pedidos_cabecera WHERE nro_pedido LIKE %s", (PREFIJO + '%',))
    cur.execute("DELETE FROM clases_pedido WHERE nombre LIKE %s", (PREFIJO + '%',))
    cur.execute("DELETE FROM clientes WHERE codigo LIKE %s", (PREFIJO + '%',))
    conn.commit()
    conn.close()


def _flashes(client):
    with client.session_transaction() as s:
        # sin el saludo que deja el login
        mensajes = [m for _, m in s.get('_flashes', []) if not m.startswith('Bienvenido')]
        s['_flashes'] = []
    return mensajes


def _clases(conn, nombre):
    conn.commit()  # refresca el snapshot de la transacción
    cur = conn.cursor()
    cur.execute("SELECT * FROM clases_pedido WHERE nombre = %s", (nombre,))
    return list(cur.fetchall())


def _guardar(client, **datos):
    client.post('/clases-pedido/guardar', data=datos)
    return _flashes(client)


def _importar(client, contenido, archivo='clases.csv'):
    r = client.post('/clases-pedido/importar', data={'archivo': (io.BytesIO(contenido.encode('utf-8')), archivo)},
                    content_type='multipart/form-data')
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()


@requires_db
def test_alta_y_edicion(logged_client, wms, usuario_wms):
    nombre = _nombre()
    assert _guardar(logged_client, nombre=f'  {nombre}  ', activo='1') == ['Clase de pedido guardada con éxito']
    clase, = _clases(wms, nombre)                                  # sin los espacios de los extremos
    assert clase['activo'] and clase['tenant_id'] == usuario_wms['tenant_id']

    otro = _nombre()
    assert _guardar(logged_client, id_clase=clase['id_clase'], nombre=otro, activo='0') == ['Clase de pedido guardada con éxito']
    assert _clases(wms, nombre) == []
    editada, = _clases(wms, otro)
    assert editada['id_clase'] == clase['id_clase'] and not editada['activo']


@requires_db
def test_nombre_obligatorio_y_con_largo_maximo(logged_client, wms):
    assert _guardar(logged_client, nombre='   ', activo='1') == ['El nombre es obligatorio.']
    largo = PREFIJO + 'X' * 100
    assert _guardar(logged_client, nombre=largo, activo='1') == ['Nombre: admite hasta 100 caracteres.']
    assert _clases(wms, largo) == []


@requires_db
def test_nombre_unico_por_empresa(logged_client, wms):
    nombre, otro = _nombre(), _nombre()
    _guardar(logged_client, nombre=nombre, activo='1')
    _guardar(logged_client, nombre=otro, activo='1')
    assert _guardar(logged_client, nombre=nombre, activo='1') == [f'Ya existe una clase de pedido con el nombre "{nombre}".']
    assert len(_clases(wms, nombre)) == 1

    # Tampoco al renombrar otra; guardar la misma clase con su nombre sí se puede
    id_otro = _clases(wms, otro)[0]['id_clase']
    assert _guardar(logged_client, id_clase=id_otro, nombre=nombre, activo='1') == [f'Ya existe una clase de pedido con el nombre "{nombre}".']
    assert _guardar(logged_client, id_clase=id_otro, nombre=otro, activo='1') == ['Clase de pedido guardada con éxito']


@requires_db
def test_la_base_tambien_rechaza_el_nombre_repetido(wms, usuario_wms):
    from modules.sql_dialect import is_duplicate_key_error
    nombre = _nombre()
    cur = wms.cursor()
    cur.execute("INSERT INTO clases_pedido (nombre, activo, tenant_id) VALUES (%s, 1, %s)", (nombre, usuario_wms['tenant_id']))
    with pytest.raises(Exception) as error:
        cur.execute("INSERT INTO clases_pedido (nombre, activo, tenant_id) VALUES (%s, 1, %s)", (nombre, usuario_wms['tenant_id']))
    assert is_duplicate_key_error(error.value)
    wms.rollback()


@requires_db
def test_editar_una_clase_inexistente_o_de_otra_empresa(logged_client, wms):
    assert _guardar(logged_client, id_clase='99999999', nombre=_nombre(), activo='1') == ['La clase de pedido que se intenta modificar no existe.']
    assert _guardar(logged_client, id_clase='abc', nombre=_nombre(), activo='1') == ['Clase de pedido inválida.']

    # Una clase sugerida (sin empresa) no es de la empresa: no se puede tocar
    nombre = _nombre()
    cur = wms.cursor()
    cur.execute("INSERT INTO clases_pedido (nombre, activo, tenant_id) VALUES (%s, 1, NULL)", (nombre,))
    wms.commit()
    ajena = _clases(wms, nombre)[0]['id_clase']
    assert _guardar(logged_client, id_clase=ajena, nombre=_nombre(), activo='0') == ['La clase de pedido que se intenta modificar no existe.']
    logged_client.post(f'/clases-pedido/eliminar/{ajena}')
    assert _flashes(logged_client) == ['Clase de pedido no encontrada.']
    assert _clases(wms, nombre)[0]['activo']


@requires_db
def test_inactivar_y_reactivar(logged_client, wms):
    nombre = _nombre()
    _guardar(logged_client, nombre=nombre, activo='1')
    id_clase = _clases(wms, nombre)[0]['id_clase']

    logged_client.post(f'/clases-pedido/eliminar/{id_clase}')
    mensaje, = _flashes(logged_client)
    assert 'quedó inactiva' in mensaje and 'pedido' not in mensaje.replace('cargar pedidos', '')
    assert not _clases(wms, nombre)[0]['activo']

    logged_client.post(f'/clases-pedido/eliminar/{id_clase}')
    assert _flashes(logged_client) == [f'La clase "{nombre}" ya estaba inactiva.']

    # Sigue en el listado, marcada, y se reactiva desde la edición
    html = logged_client.get('/clases-pedido').get_data(as_text=True)
    fila = html[html.index(nombre):]
    assert 'Inactiva' in fila[:600] and f'/clases-pedido/eliminar/{id_clase}"' not in html
    _guardar(logged_client, id_clase=id_clase, nombre=nombre, activo='1')
    assert _clases(wms, nombre)[0]['activo']


@requires_db
def test_inactivar_una_clase_con_pedidos(logged_client, wms, usuario_wms):
    nombre = _nombre()
    _guardar(logged_client, nombre=nombre, activo='1')
    id_clase = _clases(wms, nombre)[0]['id_clase']
    cur = wms.cursor()
    cliente = _nombre()
    cur.execute("INSERT INTO clientes (codigo, razonsocial, tenant_id) VALUES (%s, 'Cliente de prueba', %s)", (cliente, usuario_wms['tenant_id']))
    wms.commit()
    cur.execute("SELECT id_cliente FROM clientes WHERE codigo = %s", (cliente,))
    cur.execute("INSERT INTO pedidos_cabecera (nro_pedido, id_cliente, id_clase, fecha_pedido, estado, tenant_id) VALUES (%s, %s, %s, '2026-01-15', 'Pendiente', %s)",
                (_nombre(), cur.fetchone()['id_cliente'], id_clase, usuario_wms['tenant_id']))
    wms.commit()

    logged_client.post(f'/clases-pedido/eliminar/{id_clase}')
    mensaje, = _flashes(logged_client)
    assert 'quedó inactiva' in mensaje and 'La tiene 1 pedido, que la conserva.' in mensaje
    assert not _clases(wms, nombre)[0]['activo']

    # El pedido la conserva: al editarlo se sigue ofreciendo su clase, aunque no las demás inactivas
    cur.execute("SELECT id_pedido FROM pedidos_cabecera WHERE id_clase = %s", (id_clase,))
    id_pedido = cur.fetchone()['id_pedido']
    html = logged_client.get(f'/pedidos/editar/{id_pedido}').get_data(as_text=True)
    assert f'<option value="{id_clase}" selected>' in html and f'{nombre} (inactiva)' in html
    assert nombre not in logged_client.get('/pedidos/nuevo').get_data(as_text=True)


@requires_db
def test_el_estado_por_defecto(logged_client, wms):
    # Alta sin el campo Estado: nace activa. Casilla de formularios anteriores: on = activa.
    nombre, otro = _nombre(), _nombre()
    _guardar(logged_client, nombre=nombre)
    _guardar(logged_client, nombre=otro, activo='on')
    assert _clases(wms, nombre)[0]['activo'] and _clases(wms, otro)[0]['activo']


@requires_db
def test_importar(logged_client, wms):
    existente, nueva, inactiva, sin_estado = _nombre(), _nombre(), _nombre(), _nombre()
    _guardar(logged_client, nombre=existente, activo='1')
    largo = PREFIJO + 'X' * 100
    resultado = _importar(logged_client, 'nombre,activo\n'
                          f'{existente},1\n{nueva},1\n{inactiva},0\n{sin_estado},\n,1\n{nueva},1\n{largo},1\n')
    assert resultado['insertados'] == 3
    assert resultado['omitidos'] == [existente, nueva]            # la que ya estaba y la repetida en el archivo
    assert [(e['fila'], e['razon']) for e in resultado['errores']] == [
        (5, 'El campo nombre es obligatorio'), (7, 'Nombre: admite hasta 100 caracteres.')]
    assert _clases(wms, nueva)[0]['activo'] and _clases(wms, sin_estado)[0]['activo']
    assert not _clases(wms, inactiva)[0]['activo']
    assert len(_clases(wms, nueva)) == 1


@requires_db
def test_exportar_incluye_las_inactivas(logged_client, wms):
    activa, inactiva = _nombre(), _nombre()
    _guardar(logged_client, nombre=activa, activo='1')
    _guardar(logged_client, nombre=inactiva, activo='0')
    r = logged_client.get('/clases-pedido/exportar/csv')
    filas = {f['nombre']: f['activo'] for f in csv.DictReader(io.StringIO(r.get_data(as_text=True).lstrip('\ufeff')))}
    assert (filas[activa], filas[inactiva]) == ('1', '0')

    # Lo exportado se puede volver a importar: todo existe, nada se duplica
    resultado = _importar(logged_client, r.get_data(as_text=True))
    assert resultado['insertados'] == 0 and resultado['errores'] == []


@requires_db
def test_clases_sugeridas(logged_client, wms):
    """La descarga trae las clases sin empresa y las propias; la pantalla solo lista las propias."""
    sugerida, propia = _nombre(), _nombre()
    cur = wms.cursor()
    cur.execute("INSERT INTO clases_pedido (nombre, activo, tenant_id) VALUES (%s, 1, NULL)", (sugerida,))
    wms.commit()
    _guardar(logged_client, nombre=propia, activo='1')

    html = logged_client.get('/clases-pedido').get_data(as_text=True)
    assert propia in html and sugerida not in html
    assert 'Clases sugeridas' in html

    r = logged_client.get('/clases-pedido/plantilla-datos/csv')
    assert r.status_code == 200
    descarga = r.get_data(as_text=True)
    assert sugerida in descarga and propia in descarga

    # Importar la descarga incorpora la sugerida a la empresa
    resultado = _importar(logged_client, descarga)
    assert resultado['errores'] == [] and propia in resultado['omitidos']
    assert len(_clases(wms, sugerida)) == 2


def test_la_descarga_de_sugeridas_esta_en_el_catalogo_de_rutas():
    from modules.schema_generator import ROUTE_CATALOG
    rutas = [ruta for grupo in ROUTE_CATALOG for ruta in grupo['rutas']]
    assert '/clases-pedido/plantilla-datos/*' in rutas
