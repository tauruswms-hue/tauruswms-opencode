"""Categorías: alta, validaciones, código y nombre únicos, inactivación, uso en materiales e importación."""

import csv
import io
import uuid

import pytest

from tests.conftest import requires_db

PREFIJO = 'ZZG'   # los códigos y nombres de prueba empiezan así, para poder limpiarlos


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
    cur.execute("DELETE FROM materiales WHERE codigo LIKE %s", (PREFIJO + '%',))
    cur.execute("DELETE FROM categorias WHERE codigo LIKE %s OR nombre LIKE %s", (PREFIJO + '%', PREFIJO + '%'))
    conn.commit()
    conn.close()


def _flashes(client):
    with client.session_transaction() as s:
        # sin el saludo que deja el login
        mensajes = [m for _, m in s.get('_flashes', []) if not m.startswith('Bienvenido')]
        s['_flashes'] = []
    return mensajes


def _categorias(conn, codigo):
    conn.commit()  # refresca el snapshot de la transacción
    cur = conn.cursor()
    cur.execute("SELECT * FROM categorias WHERE codigo = %s", (codigo,))
    return list(cur.fetchall())


def _guardar(client, **datos):
    client.post('/categorias/guardar', data=datos)
    return _flashes(client)


def _categoria(client, conn, **datos):
    codigo = _codigo()
    datos.setdefault('nombre', 'Nombre ' + codigo)
    assert _guardar(client, codigo=codigo, **datos) == ['Categoría guardada con éxito']
    return _categorias(conn, codigo)[0]['id_categoria'], codigo


def _importar(client, contenido):
    r = client.post('/categorias/importar', data={'archivo': (io.BytesIO(contenido.encode('utf-8')), 'categorias.csv')},
                    content_type='multipart/form-data')
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()


def _material(conn, tenant, id_categoria):
    cur = conn.cursor()
    codigo = _codigo()
    cur.execute("INSERT INTO materiales (codigo, nombre, categoria_id, tenant_id) VALUES (%s, 'Material de prueba', %s, %s)",
                (codigo, id_categoria, tenant))
    conn.commit()
    cur.execute("SELECT id FROM materiales WHERE codigo = %s", (codigo,))
    return cur.fetchone()['id']


@requires_db
def test_alta_y_edicion(logged_client, wms, usuario_wms):
    codigo = _codigo()
    assert _guardar(logged_client, codigo=f'  {codigo}  ', nombre=f'  Nombre {codigo}  ', descripcion='  Algo  ', activo='1') == ['Categoría guardada con éxito']
    cat, = _categorias(wms, codigo)                               # sin los espacios de los extremos
    assert (cat['nombre'], cat['descripcion']) == (f'Nombre {codigo}', 'Algo')
    assert cat['activo'] and cat['tenant_id'] == usuario_wms['tenant_id']

    otro = _codigo()
    assert _guardar(logged_client, id_categoria=cat['id_categoria'], codigo=otro, nombre='Nombre ' + otro, descripcion='', activo='0') == ['Categoría guardada con éxito']
    assert _categorias(wms, codigo) == []
    editada, = _categorias(wms, otro)
    assert editada['id_categoria'] == cat['id_categoria'] and not editada['activo'] and editada['descripcion'] is None


@requires_db
def test_codigo_y_nombre_obligatorios_y_con_largo_maximo(logged_client, wms):
    codigo = _codigo()
    assert _guardar(logged_client, codigo='  ', nombre='Nombre ' + codigo) == ['Código: es obligatorio.']
    assert _guardar(logged_client, codigo=codigo, nombre='   ') == ['Nombre: es obligatorio.']
    assert _guardar(logged_client, codigo=PREFIJO + 'X' * 50, nombre='Nombre ' + codigo) == ['Código: admite hasta 50 caracteres.']
    assert _guardar(logged_client, codigo=codigo, nombre=PREFIJO + 'X' * 100) == ['Nombre: admite hasta 100 caracteres.']
    assert _categorias(wms, codigo) == []


@requires_db
def test_codigo_y_nombre_no_se_repiten(logged_client, wms):
    id_cat, codigo = _categoria(logged_client, wms)
    id_otra, otra = _categoria(logged_client, wms)
    assert _guardar(logged_client, codigo=codigo, nombre='Nombre ' + _codigo()) == [f'Ya existe una categoría con el código "{codigo}".']
    assert _guardar(logged_client, codigo=_codigo(), nombre='Nombre ' + codigo) == [f'Ya existe una categoría con el nombre "Nombre {codigo}".']
    # Tampoco al editar otra; guardar la misma con sus datos sí se puede
    assert _guardar(logged_client, id_categoria=id_otra, codigo=codigo, nombre='Nombre ' + otra) == [f'Ya existe una categoría con el código "{codigo}".']
    assert _guardar(logged_client, id_categoria=id_otra, codigo=otra, nombre='Nombre ' + codigo) == [f'Ya existe una categoría con el nombre "Nombre {codigo}".']
    assert _guardar(logged_client, id_categoria=id_otra, codigo=otra, nombre='Nombre ' + otra) == ['Categoría guardada con éxito']

    # El código de una categoría inactiva sigue ocupado, y el mensaje lo dice (antes salía el error de la base)
    logged_client.post(f'/categorias/eliminar/{id_cat}')
    _flashes(logged_client)
    assert _guardar(logged_client, codigo=codigo, nombre='Nombre ' + _codigo()) == [f'Ya existe una categoría con el código "{codigo}".']


@requires_db
def test_editar_o_inactivar_una_categoria_inexistente(logged_client, wms):
    codigo = _codigo()
    assert _guardar(logged_client, id_categoria='99999999', codigo=codigo, nombre='Nombre ' + codigo) == ['La categoría que se intenta modificar no existe.']
    assert _guardar(logged_client, id_categoria='abc', codigo=codigo, nombre='Nombre ' + codigo) == ['Categoría inválida.']
    logged_client.post('/categorias/eliminar/99999999')
    assert _flashes(logged_client) == ['Categoría no encontrada.']


@requires_db
def test_inactivar_y_reactivar(logged_client, wms, usuario_wms):
    id_cat, codigo = _categoria(logged_client, wms)
    _material(wms, usuario_wms['tenant_id'], id_cat)

    logged_client.post(f'/categorias/eliminar/{id_cat}')
    mensaje, = _flashes(logged_client)
    assert 'quedó inactiva' in mensaje and 'La tiene 1 material, que la conserva.' in mensaje
    assert not _categorias(wms, codigo)[0]['activo']

    logged_client.post(f'/categorias/eliminar/{id_cat}')
    assert _flashes(logged_client) == [f'La categoría "Nombre {codigo}" ya estaba inactiva.']

    # Sigue en el listado, marcada y con sus materiales; se reactiva desde la edición
    html = logged_client.get('/categorias').get_data(as_text=True)
    assert 'Inactiva' in html[html.index(codigo):][:900] and f'/categorias/eliminar/{id_cat}"' not in html
    _guardar(logged_client, id_categoria=id_cat, codigo=codigo, nombre='Nombre ' + codigo, activo='1')
    assert _categorias(wms, codigo)[0]['activo']


@requires_db
def test_inactivar_una_categoria_sin_materiales(logged_client, wms):
    id_cat, _ = _categoria(logged_client, wms)
    logged_client.post(f'/categorias/eliminar/{id_cat}')
    mensaje, = _flashes(logged_client)
    assert 'quedó inactiva' in mensaje and 'La tiene' not in mensaje


@requires_db
def test_el_material_conserva_su_categoria_inactiva(logged_client, wms, usuario_wms):
    """El formulario de materiales recibe la categoría inactiva marcada: la oculta salvo para el material que la tiene."""
    id_cat, codigo = _categoria(logged_client, wms)
    _material(wms, usuario_wms['tenant_id'], id_cat)
    logged_client.post(f'/categorias/eliminar/{id_cat}')
    _flashes(logged_client)

    html = logged_client.get('/materiales').get_data(as_text=True)
    assert f'<option value="{id_cat}" data-inactiva="1">Nombre {codigo} (inactiva)</option>' in html


@requires_db
def test_importar_y_exportar(logged_client, wms):
    _, existente = _categoria(logged_client, wms)
    nueva, inactiva, sin_estado, repite_nombre = _codigo(), _codigo(), _codigo(), _codigo()
    largo = PREFIJO + 'X' * 50
    resultado = _importar(logged_client, 'codigo,nombre,descripcion,activo\n'
                          f'{existente},Otro nombre,,1\n{nueva},Nombre {nueva},Algo,1\n{inactiva},Nombre {inactiva},,0\n'
                          f'{sin_estado},Nombre {sin_estado},,\n,Sin código,,1\n{nueva},Repetida,,1\n'
                          f'{repite_nombre},Nombre {nueva},,1\n{largo},Nombre largo,,1\n')
    assert resultado['insertados'] == 3
    assert resultado['omitidos'] == [existente, nueva]            # la que ya estaba y la repetida en el archivo
    assert [(e['fila'], e['razon']) for e in resultado['errores']] == [
        (5, 'Código y Nombre son obligatorios'),
        (7, f'Ya existe una categoría con el nombre "Nombre {nueva}".'),
        (8, 'Código: admite hasta 50 caracteres.')]
    assert _categorias(wms, nueva)[0]['activo']
    assert _categorias(wms, sin_estado)[0]['activo']              # sin dato en activo, nace activa
    assert not _categorias(wms, inactiva)[0]['activo']

    r = logged_client.get('/categorias/exportar/csv')
    filas = {f['codigo']: f['activo'] for f in csv.DictReader(io.StringIO(r.get_data(as_text=True).lstrip('﻿')))}
    assert (filas[nueva], filas[inactiva]) == ('1', '0')           # la exportación trae las inactivas
    resultado = _importar(logged_client, r.get_data(as_text=True))  # y se puede volver a importar
    assert resultado['insertados'] == 0 and resultado['errores'] == []


def test_operador_puede_importar_y_exportar_categorias():
    from modules.schema_generator import ROUTES_OPERADOR
    for ruta in ('/categorias/importar', '/categorias/exportar/*', '/categorias/plantilla/*'):
        assert ruta in ROUTES_OPERADOR
