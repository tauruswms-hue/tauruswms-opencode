"""Ubicaciones: alta, validaciones, estado, inactivación, zona y tipo, importación y exportación, y uso en otras pantallas."""

import csv
import io
import uuid

import pytest

from tests.conftest import requires_db

PREFIJO = 'ZZB'   # los códigos y nombres de prueba empiezan así, para poder limpiarlos


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
    cur.execute("DELETE FROM stockcontable WHERE IDContenedor LIKE %s", (PREFIJO + '%',))
    cur.execute("DELETE FROM materiales WHERE codigo LIKE %s", (PREFIJO + '%',))
    cur.execute("DELETE FROM transportes WHERE codigo LIKE %s", (PREFIJO + '%',))
    cur.execute("DELETE FROM ubicaciones WHERE codigo LIKE %s OR codigo = 'UB-001'", (PREFIJO + '%',))
    cur.execute("DELETE FROM zonas WHERE codigo LIKE %s", (PREFIJO + '%',))
    cur.execute("DELETE FROM tipoubicacion WHERE descripcion LIKE %s", (PREFIJO + '%',))
    conn.commit()
    conn.close()


def _flashes(client):
    with client.session_transaction() as s:
        # sin el saludo que deja el login
        mensajes = [m for _, m in s.get('_flashes', []) if not m.startswith('Bienvenido')]
        s['_flashes'] = []
    return mensajes


def _ubicacion(conn, codigo):
    conn.commit()  # refresca el snapshot de la transacción
    cur = conn.cursor()
    cur.execute("SELECT * FROM ubicaciones WHERE codigo = %s", (codigo,))
    return cur.fetchone()


def _guardar(client, **datos):
    client.post('/ubicaciones/guardar', data=datos)
    return _flashes(client)


def _importar(client, contenido):
    r = client.post('/ubicaciones/importar', data={
        'archivo': (io.BytesIO(contenido.encode('utf-8')), 'ubicaciones.csv')}, content_type='multipart/form-data')
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()


def _fila(client, codigo):
    html = client.get('/ubicaciones').get_data(as_text=True)
    recorte = html[html.index(f'<strong>{codigo}</strong>'):]
    return recorte[:recorte.index('</tr>')]


@pytest.fixture
def maestros(wms, usuario_wms):
    """Un tipo de salida y una zona de la empresa de prueba, una zona inactiva, y un tipo y una zona de otra empresa."""
    tenant = usuario_wms['tenant_id']
    cur = wms.cursor()
    nombres = {clave: _codigo() for clave in ('tipo', 'tipo_ajeno', 'zona', 'zona_inactiva', 'zona_ajena')}
    # Los códigos de zona admiten 20 caracteres
    cur.execute("INSERT INTO tipoubicacion (descripcion, operacion, tenant_id) VALUES (%s, 'S', %s)", (nombres['tipo'], tenant))
    cur.execute("INSERT INTO tipoubicacion (descripcion, operacion, tenant_id) VALUES (%s, 'S', %s)", (nombres['tipo_ajeno'], tenant + 100000))
    cur.execute("INSERT INTO zonas (codigo, nombre, activo, tenant_id) VALUES (%s, 'Zona de prueba', 1, %s)", (nombres['zona'], tenant))
    cur.execute("INSERT INTO zonas (codigo, nombre, activo, tenant_id) VALUES (%s, 'Zona inactiva', 0, %s)", (nombres['zona_inactiva'], tenant))
    cur.execute("INSERT INTO zonas (codigo, nombre, activo, tenant_id) VALUES (%s, 'Zona ajena', 1, %s)", (nombres['zona_ajena'], tenant + 100000))
    wms.commit()
    ids = {}
    for clave in ('tipo', 'tipo_ajeno'):
        cur.execute("SELECT id FROM tipoubicacion WHERE descripcion = %s", (nombres[clave],))
        ids[clave] = cur.fetchone()['id']
    for clave in ('zona', 'zona_inactiva', 'zona_ajena'):
        cur.execute("SELECT id FROM zonas WHERE codigo = %s", (nombres[clave],))
        ids[clave] = cur.fetchone()['id']
    return {'ids': ids, 'nombres': nombres}


# --- Alta y validaciones ---

@requires_db
def test_alta_y_edicion(logged_client, wms, usuario_wms, maestros):
    codigo, ids = _codigo(), maestros['ids']
    assert _guardar(logged_client, codigo=f'  {codigo}  ', descipcion='  Pasillo A  ', tipoubicacion=ids['tipo'],
                    id_zona=ids['zona'], orden_picking='5', coordenadaA=' A1 ', capacidad_maxima='100',
                    disponible_entrada='on') == ['Ubicación guardada']
    u = _ubicacion(wms, codigo)
    assert (u['descipcion'], u['coordenadaA'], u['orden_picking'], u['capacidad_maxima']) == ('Pasillo A', 'A1', 5, 100)
    assert (u['tipoubicacion'], u['id_zona'], u['tenant_id']) == (ids['tipo'], ids['zona'], usuario_wms['tenant_id'])
    assert u['activo'] and u['disponible_entrada'] and not u['disponible_salida']

    assert _guardar(logged_client, id=u['id'], codigo=codigo, descipcion='', capacidad_maxima='',
                    disponible_salida='on') == ['Ubicación guardada']
    u = _ubicacion(wms, codigo)
    assert u['descipcion'] is None and u['capacidad_maxima'] == 0 and u['tipoubicacion'] is None
    assert u['activo'] and u['disponible_salida'] and not u['disponible_entrada']


@requires_db
@pytest.mark.parametrize('datos, mensaje', [
    ({'codigo': '   '}, 'Código: es obligatorio.'),
    ({'codigo': PREFIJO + 'x' * 50}, 'Código: admite hasta 50 caracteres.'),
    ({'descipcion': 'x' * 201}, 'Descripción: admite hasta 200 caracteres.'),
    ({'coordenadaA': 'x' * 21}, 'Coordenada A: admite hasta 20 caracteres.'),
    ({'coordenadaD': 'x' * 21}, 'Coordenada D: admite hasta 20 caracteres.'),
    ({'capacidad_maxima': 'abc'}, 'Capacidad máxima: "abc" no es un número entero.'),
    ({'capacidad_maxima': '1.5'}, 'Capacidad máxima: "1.5" no es un número entero.'),
    ({'capacidad_maxima': '-5'}, 'Capacidad máxima: no puede ser negativo.'),
    ({'capacidad_maxima': 'nan'}, 'Capacidad máxima: "nan" no es un número entero.'),
    ({'orden_picking': '99999999999'}, 'Orden de picking: el valor es demasiado grande.'),
    ({'id_zona': '999999999'}, 'Zona: el valor elegido no existe.'),
    ({'tipoubicacion': '999999999'}, 'Tipo de ubicación: el valor elegido no existe.'),
    ({'tipoubicacion': 'abc'}, 'Tipo de ubicación: el valor elegido no existe.'),
    ({'id': 'abc'}, 'Ubicación inválida.'),
    ({'id': '999999999'}, 'La ubicación que se intenta modificar no existe.'),
])
def test_datos_invalidos_no_se_guardan(logged_client, wms, datos, mensaje):
    """Antes se guardaban tal cual o salía el error de la base o de Python."""
    codigo = _codigo()
    assert _guardar(logged_client, **{'codigo': codigo, **datos}) == [mensaje]
    assert _ubicacion(wms, codigo) is None


@requires_db
def test_tipo_y_zona_tienen_que_ser_de_la_empresa(logged_client, wms, maestros):
    codigo, ids = _codigo(), maestros['ids']
    assert _guardar(logged_client, codigo=codigo, id_zona=ids['zona_ajena']) == ['Zona: el valor elegido no existe.']
    assert _guardar(logged_client, codigo=codigo, tipoubicacion=ids['tipo_ajeno']) == [
        'Tipo de ubicación: el valor elegido no existe.']
    assert _ubicacion(wms, codigo) is None


@requires_db
def test_codigo_repetido_se_rechaza(logged_client, wms):
    codigo, otro = _codigo(), _codigo()
    _guardar(logged_client, codigo=codigo)
    _guardar(logged_client, codigo=otro)
    assert _guardar(logged_client, codigo=f' {codigo} ') == [f'Ya existe una ubicación con el código "{codigo}".']
    assert _guardar(logged_client, id=_ubicacion(wms, otro)['id'], codigo=codigo) == [
        f'Ya existe una ubicación con el código "{codigo}".']
    assert _guardar(logged_client, id=_ubicacion(wms, codigo)['id'], codigo=codigo, descipcion='x') == ['Ubicación guardada']


# --- Estado e inactivación ---

@requires_db
def test_inactivar_y_reactivar(logged_client, wms):
    """El botón marcaba la ubicación como inactiva, pero el listado mostraba otra cosa y no se podía reactivar."""
    codigo = _codigo()
    _guardar(logged_client, codigo=codigo, disponible_entrada='on', disponible_salida='on')
    uid = _ubicacion(wms, codigo)['id']
    fila = _fila(logged_client, codigo)
    assert '>Activa</span>' in fila and 'Entrada / Salida' in fila and f'/ubicaciones/eliminar/{uid}"' in fila

    logged_client.post(f'/ubicaciones/eliminar/{uid}')
    (mensaje,) = _flashes(logged_client)
    assert 'quedó inactiva' in mensaje and 'Se puede reactivar' in mensaje
    u = _ubicacion(wms, codigo)
    assert not u['activo'] and u['disponible_entrada']            # Entrada / Salida no cambian
    fila = _fila(logged_client, codigo)
    assert 'Inactiva</span>' in fila and '>Activa</span>' not in fila and '/ubicaciones/eliminar/' not in fila

    logged_client.post(f'/ubicaciones/eliminar/{uid}')
    assert _flashes(logged_client) == [f'La ubicación "{codigo}" ya estaba inactiva.']
    logged_client.post('/ubicaciones/eliminar/999999999')
    assert _flashes(logged_client) == ['Ubicación no encontrada.']

    # Editar sin el dato del estado lo conserva; Estado: Activa la reactiva
    _guardar(logged_client, id=uid, codigo=codigo)
    assert not _ubicacion(wms, codigo)['activo']
    _guardar(logged_client, id=uid, codigo=codigo, activo='1')
    assert _ubicacion(wms, codigo)['activo']
    html = logged_client.get('/ubicaciones').get_data(as_text=True)
    assert '<select name="activo" id="form_activo"' in html


@requires_db
def test_no_se_inactiva_una_ubicacion_con_stock(logged_client, wms, usuario_wms):
    tenant = usuario_wms['tenant_id']
    codigo, material = _codigo(), _codigo()
    _guardar(logged_client, codigo=codigo)
    uid = _ubicacion(wms, codigo)['id']
    cur = wms.cursor()
    cur.execute("INSERT INTO materiales (codigo, nombre, tenant_id) VALUES (%s, 'Material de prueba', %s)", (material, tenant))
    cur.execute("SELECT id FROM materiales WHERE codigo = %s AND tenant_id = %s", (material, tenant))
    cur.execute("""INSERT INTO stockcontable (Ubicacion, Material, StockTotal, StockDisponible, IDContenedor, tenant_id)
                   VALUES (%s, %s, 5, 5, %s, %s)""", (uid, cur.fetchone()['id'], PREFIJO + 'C1', tenant))
    wms.commit()

    logged_client.post(f'/ubicaciones/eliminar/{uid}')
    assert _flashes(logged_client) == [f'No se puede inactivar la ubicación "{codigo}": tiene stock.']
    assert _guardar(logged_client, id=uid, codigo=codigo, activo='0') == ['No se puede inactivar la ubicación: tiene stock.']
    assert _ubicacion(wms, codigo)['activo']

    cur.execute("UPDATE stockcontable SET StockTotal = 0, StockDisponible = 0 WHERE Ubicacion = %s", (uid,))
    wms.commit()
    assert _guardar(logged_client, id=uid, codigo=codigo, activo='0') == ['Ubicación guardada']   # vacía, se puede
    assert not _ubicacion(wms, codigo)['activo']


@requires_db
def test_inactivar_avisa_si_es_el_muelle_de_un_transporte(logged_client, wms, usuario_wms, maestros):
    codigo = _codigo()
    _guardar(logged_client, codigo=codigo, tipoubicacion=maestros['ids']['tipo'])
    uid = _ubicacion(wms, codigo)['id']
    cur = wms.cursor()
    cur.execute("INSERT INTO transportes (codigo, razonsocial, id_muelle_salida, tenant_id) VALUES (%s, 'Transporte', %s, %s)",
                (_codigo(), uid, usuario_wms['tenant_id']))
    wms.commit()
    logged_client.post(f'/ubicaciones/eliminar/{uid}')
    (mensaje,) = _flashes(logged_client)
    assert 'Es el muelle de salida de 1 transporte, que la conserva; conviene asignarle otro.' in mensaje
    assert not _ubicacion(wms, codigo)['activo']


@requires_db
def test_la_ubicacion_conserva_su_zona_inactiva(logged_client, wms, maestros):
    """La ficha cargaba solo las zonas activas: al editar, la ubicación perdía la suya."""
    ids, nombres = maestros['ids'], maestros['nombres']
    html = logged_client.get('/ubicaciones').get_data(as_text=True)
    assert f'<option value="{ids["zona_inactiva"]}" data-inactiva="1">{nombres["zona_inactiva"]} — Zona inactiva (inactiva)</option>' in html
    assert f'<option value="{ids["zona"]}">{nombres["zona"]} — Zona de prueba</option>' in html
    assert 'function mostrarZonasInactivas' in logged_client.get('/static/js/ubicaciones.js').get_data(as_text=True)


# --- Importación y exportación ---

@requires_db
def test_importar_por_nombre_de_tipo_y_codigo_de_zona(logged_client, wms, maestros):
    ids, nombres = maestros['ids'], maestros['nombres']
    buena, por_id, inactiva, mala_zona, mal_tipo, ajena, numero, larga = (_codigo() for _ in range(8))
    resultado = _importar(logged_client, '\n'.join([
        'codigo,descipcion,tipoubicacion,id_zona,orden_picking,capacidad_maxima,disponible_entrada,disponible_salida,activo',
        f'  {buena}  ,  Estante 1  ,{nombres["tipo"]},{nombres["zona"]},3,50,1,0,',
        f'{por_id},,{ids["tipo"]},{ids["zona"]},,,,,',
        f'{inactiva},,,,,,,,0',
        f'{mala_zona},,,NOEXISTE,,,,,',
        f'{mal_tipo},,Inventado,,,,,,',
        f'{ajena},,,{ids["zona_ajena"]},,,,,',
        f'{numero},,,,,abc,,,',
        f'{larga},{"x" * 201},,,,,,,',
        f'{buena},Repetida,,,,,,,',
        ',Sin código,,,,,,,',
    ]))
    assert resultado['insertados'] == 3 and resultado['omitidos'] == [buena]
    assert [(e['fila'], e['razon']) for e in resultado['errores']] == [
        (4, 'Zona: no existe "NOEXISTE".'),
        (5, 'Tipo de ubicación: no existe "Inventado".'),
        (6, f'Zona: no existe "{ids["zona_ajena"]}".'),              # el ID de una zona de otra empresa
        (7, 'Capacidad máxima: "abc" no es un número entero.'),
        (8, 'Descripción: admite hasta 200 caracteres.'),
        (10, 'Código es obligatorio')]
    u = _ubicacion(wms, buena)
    assert (u['descipcion'], u['tipoubicacion'], u['id_zona'], u['orden_picking'], u['capacidad_maxima']) == (
        'Estante 1', ids['tipo'], ids['zona'], 3, 50)
    assert u['disponible_entrada'] and not u['disponible_salida'] and u['activo']
    u = _ubicacion(wms, por_id)
    assert (u['tipoubicacion'], u['id_zona']) == (ids['tipo'], ids['zona']) and u['disponible_entrada'] and u['disponible_salida']
    assert not _ubicacion(wms, inactiva)['activo']


@requires_db
def test_la_exportacion_se_puede_importar_en_otro_servidor(logged_client, wms, maestros):
    """El tipo sale por su nombre y la zona por su código: los ID internos cambian de un servidor a otro."""
    ids, nombres = maestros['ids'], maestros['nombres']
    codigo = _codigo()
    _guardar(logged_client, codigo=codigo, tipoubicacion=ids['tipo'], id_zona=ids['zona'], capacidad_maxima='7',
             disponible_entrada='on', activo='0')
    exportado = logged_client.get('/ubicaciones/exportar/csv').get_data(as_text=True).lstrip('﻿')
    fila = next(f for f in csv.DictReader(io.StringIO(exportado)) if f['codigo'] == codigo)
    assert (fila['tipoubicacion'], fila['id_zona'], fila['activo']) == (nombres['tipo'], nombres['zona'], '0')

    # Como si fuera otro servidor: se borra la ubicación y se la vuelve a cargar desde esa fila
    cur = wms.cursor()
    cur.execute("DELETE FROM ubicaciones WHERE codigo = %s", (codigo,))
    wms.commit()
    linea = next(x for x in exportado.splitlines() if x.startswith(codigo + ','))
    resultado = _importar(logged_client, exportado.splitlines()[0] + '\n' + linea + '\n')
    assert resultado['insertados'] == 1 and resultado['errores'] == []
    u = _ubicacion(wms, codigo)
    assert (u['tipoubicacion'], u['id_zona'], u['capacidad_maxima']) == (ids['tipo'], ids['zona'], 7)
    assert not u['activo'] and u['disponible_entrada'] and not u['disponible_salida']


@requires_db
@pytest.mark.parametrize('formato', ['csv', 'json', 'xlsx'])
def test_la_plantilla_se_puede_importar(logged_client, wms, formato):
    plantilla = logged_client.get(f'/ubicaciones/plantilla/{formato}')
    r = logged_client.post('/ubicaciones/importar', data={
        'archivo': (io.BytesIO(plantilla.data), f'plantilla.{formato}')}, content_type='multipart/form-data')
    resultado = r.get_json()
    assert resultado['insertados'] == 1 and resultado['errores'] == []
    u = _ubicacion(wms, 'UB-001')
    assert u['capacidad_maxima'] == 100 and u['activo']
    cur = wms.cursor()
    cur.execute("DELETE FROM ubicaciones WHERE codigo = 'UB-001' AND descipcion = 'Pasillo A - Estante 1'")
    wms.commit()


# --- Las otras pantallas no ofrecen una ubicación inactiva ---

@requires_db
def test_una_ubicacion_inactiva_no_se_ofrece_en_otras_pantallas(logged_client, wms, maestros):
    activa, inactiva = _codigo(), _codigo()
    tipo = maestros['ids']['tipo']
    _guardar(logged_client, codigo=activa, tipoubicacion=tipo)
    _guardar(logged_client, codigo=inactiva, tipoubicacion=tipo, activo='0')
    for ruta in ('/recepciones/buscar_ubicaciones', '/omc/buscar_ubicaciones'):
        codigos = [u['codigo'] for u in logged_client.get(ruta, query_string={'q': PREFIJO}).get_json()]
        assert activa in codigos and inactiva not in codigos, ruta
