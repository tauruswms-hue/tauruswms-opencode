"""Zonas: alta, validaciones, código en mayúsculas, estado, baja, importación y permisos del OPERADOR."""

import csv
import io
import uuid

import pytest

from tests.conftest import requires_db

PREFIJO = 'ZZW'   # los códigos de prueba empiezan así, para poder limpiarlos


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
    cur.execute("DELETE FROM ubicaciones WHERE codigo LIKE %s", (PREFIJO + '%',))
    cur.execute("DELETE FROM zonas WHERE codigo LIKE %s OR (codigo = 'ZN-NORTE' AND nombre = 'Zona Norte')", (PREFIJO + '%',))
    conn.commit()
    conn.close()


def _flashes(client):
    with client.session_transaction() as s:
        # sin el saludo que deja el login
        mensajes = [m for _, m in s.get('_flashes', []) if not m.startswith('Bienvenido')]
        s['_flashes'] = []
    return mensajes


def _zona(conn, codigo):
    conn.commit()  # refresca el snapshot de la transacción
    cur = conn.cursor()
    cur.execute("SELECT * FROM zonas WHERE codigo = %s", (codigo,))
    return cur.fetchone()


def _guardar(client, **datos):
    datos.setdefault('nombre', 'Zona de prueba')
    client.post('/zonas/guardar', data=datos)
    return _flashes(client)


def _ubicacion(conn, tenant, id_zona):
    cur = conn.cursor()
    cur.execute("""INSERT INTO ubicaciones (codigo, id_zona, capacidad_maxima, ocupado, orden_picking, tenant_id)
                   VALUES (%s, %s, 0, 0, 0, %s)""", (_codigo(), id_zona, tenant))
    conn.commit()


def _importar(client, contenido):
    r = client.post('/zonas/importar', data={
        'archivo': (io.BytesIO(contenido.encode('utf-8')), 'zonas.csv')}, content_type='multipart/form-data')
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()


@requires_db
def test_alta_en_mayusculas_y_sin_espacios(logged_client, wms, usuario_wms):
    """La pantalla mostraba el código en mayúsculas pero lo guardaba como se había escrito."""
    codigo = _codigo()
    assert _guardar(logged_client, codigo=f'  {codigo.lower()}  ', nombre='  Norte  ', descripcion='  Sector norte  ',
                    activo='1') == ['Zona guardada correctamente.']
    z = _zona(wms, codigo)
    assert (z['codigo'], z['nombre'], z['descripcion']) == (codigo, 'Norte', 'Sector norte')   # comparación exacta: mayúsculas
    assert z['activo'] and z['tenant_id'] == usuario_wms['tenant_id']

    assert _guardar(logged_client, id=z['id'], codigo=codigo, nombre='Sur', descripcion='') == ['Zona guardada correctamente.']
    z = _zona(wms, codigo)
    assert (z['nombre'], z['descripcion']) == ('Sur', None) and z['activo']


@requires_db
@pytest.mark.parametrize('datos, mensaje', [
    ({'codigo': '   '}, 'Código: es obligatorio.'),
    ({'nombre': '   '}, 'Nombre: es obligatorio.'),
    ({'codigo': PREFIJO + 'X' * 20}, 'Código: admite hasta 20 caracteres.'),
    ({'nombre': 'n' * 101}, 'Nombre: admite hasta 100 caracteres.'),
    ({'id': 'abc'}, 'Zona inválida.'),
    ({'id': '999999999'}, 'La zona que se intenta modificar no existe.'),
])
def test_datos_invalidos_no_se_guardan(logged_client, wms, datos, mensaje):
    """Antes se guardaban tal cual o salía el error de la base."""
    codigo = _codigo()
    assert _guardar(logged_client, **{'codigo': codigo, **datos}) == [mensaje]
    assert _zona(wms, codigo) is None


@requires_db
def test_codigo_repetido_se_rechaza(logged_client, wms):
    codigo, otro = _codigo(), _codigo()
    _guardar(logged_client, codigo=codigo)
    _guardar(logged_client, codigo=otro)
    assert _guardar(logged_client, codigo=f' {codigo.lower()} ') == [f'Ya existe una zona con el código "{codigo}".']
    assert _guardar(logged_client, id=_zona(wms, otro)['id'], codigo=codigo) == [f'Ya existe una zona con el código "{codigo}".']
    # Guardar la misma zona con su código sí se puede; el nombre puede repetirse
    assert _guardar(logged_client, id=_zona(wms, codigo)['id'], codigo=codigo) == ['Zona guardada correctamente.']


@requires_db
def test_estado_e_inactivacion(logged_client, wms, usuario_wms):
    codigo = _codigo()
    _guardar(logged_client, codigo=codigo, activo='1')
    zid = _zona(wms, codigo)['id']
    _ubicacion(wms, usuario_wms['tenant_id'], zid)
    _ubicacion(wms, usuario_wms['tenant_id'], zid)

    mensajes = _guardar(logged_client, id=zid, codigo=codigo, activo='0')
    assert mensajes[0] == 'Zona guardada correctamente.'
    assert 'quedó inactiva' in mensajes[1] and 'La tiene 2 ubicaciones, que la conservan.' in mensajes[1]
    assert not _zona(wms, codigo)['activo']
    # Editar sin el dato del estado lo conserva (antes la dejaba inactiva); Estado: Activa la reactiva
    assert _guardar(logged_client, id=zid, codigo=codigo) == ['Zona guardada correctamente.']
    assert not _zona(wms, codigo)['activo']
    _guardar(logged_client, id=zid, codigo=codigo, activo='1')
    _guardar(logged_client, id=zid, codigo=codigo)
    assert _zona(wms, codigo)['activo']

    html = logged_client.get('/zonas').get_data(as_text=True)
    lista = html[html.index('id="form_activo"'):]
    lista = lista[:lista.index('</select>')]
    assert '<option value="1">Activa</option>' in lista and '<option value="0">Inactiva</option>' in lista


@requires_db
def test_eliminar(logged_client, wms, usuario_wms):
    libre, en_uso = _codigo(), _codigo()
    _guardar(logged_client, codigo=libre)
    _guardar(logged_client, codigo=en_uso)
    _ubicacion(wms, usuario_wms['tenant_id'], _zona(wms, en_uso)['id'])

    logged_client.post(f'/zonas/eliminar/{_zona(wms, en_uso)["id"]}')
    assert _flashes(logged_client) == [
        f'No se puede eliminar la zona "{en_uso}": tiene 1 ubicación asignada. Se puede inactivar desde su edición.']
    logged_client.post(f'/zonas/eliminar/{_zona(wms, libre)["id"]}')
    assert _flashes(logged_client) == ['Zona eliminada.'] and _zona(wms, libre) is None
    logged_client.post('/zonas/eliminar/999999999')
    assert _flashes(logged_client) == ['Zona no encontrada.']


@requires_db
def test_importar_y_exportar(logged_client, wms):
    """Con la columna activo vacía la zona nacía inactiva, aunque la ayuda decía "default 1"."""
    sin_estado, activa, inactiva, larga = (_codigo() for _ in range(4))
    resultado = _importar(logged_client, '\n'.join([
        'codigo,nombre,descripcion,activo',
        f'  {sin_estado.lower()}  ,  Sin estado  ,,',
        f'{activa},Activa,Algo,1',
        f'{inactiva},Inactiva,,0',
        f'{larga},{"n" * 101},,1',
        f'{activa},Repetida,,1',
        ',Sin código,,1',
    ]))
    assert resultado['insertados'] == 3 and resultado['omitidos'] == [activa]
    assert [(e['fila'], e['razon']) for e in resultado['errores']] == [
        (4, 'Nombre: admite hasta 100 caracteres.'), (6, 'Código y Nombre son obligatorios')]
    assert _zona(wms, sin_estado)['activo'] and _zona(wms, sin_estado)['nombre'] == 'Sin estado'
    assert _zona(wms, activa)['activo'] and not _zona(wms, inactiva)['activo']

    exportado = logged_client.get('/zonas/exportar/csv').get_data(as_text=True).lstrip('﻿')
    filas = {f['codigo']: f['activo'] for f in csv.DictReader(io.StringIO(exportado))}
    assert (filas[sin_estado], filas[inactiva]) == ('1', '0')
    resultado = _importar(logged_client, exportado)                  # y se puede volver a importar
    assert resultado['insertados'] == 0 and resultado['errores'] == []


@requires_db
@pytest.mark.parametrize('formato', ['csv', 'json', 'xlsx'])
def test_la_plantilla_se_puede_importar(logged_client, wms, formato):
    plantilla = logged_client.get(f'/zonas/plantilla/{formato}')
    r = logged_client.post('/zonas/importar', data={
        'archivo': (io.BytesIO(plantilla.data), f'plantilla.{formato}')}, content_type='multipart/form-data')
    resultado = r.get_json()
    assert resultado['insertados'] + len(resultado['omitidos']) == 1 and resultado['errores'] == []


def test_operador_administra_zonas_y_clases_de_pedido():
    """El OPERADOR tenía todas las rutas de Ubicaciones pero ninguna de Zonas, ni de Clases de Pedido."""
    from modules.schema_generator import ROUTES_OPERADOR
    for base in ('/zonas', '/clases-pedido'):
        for ruta in ('', '/guardar', '/eliminar/*', '/importar', '/exportar/*', '/plantilla/*'):
            assert base + ruta in ROUTES_OPERADOR
    assert '/clases-pedido/plantilla-datos/*' in ROUTES_OPERADOR
