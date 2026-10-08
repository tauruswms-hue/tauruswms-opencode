"""Tipos de ubicación: alta, validaciones, operación (recepción / salida), baja, importación y uso en otras pantallas."""

import csv
import io
import re
import uuid
from pathlib import Path

import pytest

from tests.conftest import requires_db

PREFIJO = 'ZZY'   # las descripciones y códigos de prueba empiezan así, para poder limpiarlos


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
    cur.execute("DELETE FROM recepciones_cabecera WHERE numero LIKE %s", (PREFIJO + '%',))
    cur.execute("DELETE FROM proveedores WHERE codigo LIKE %s", (PREFIJO + '%',))
    cur.execute("DELETE FROM ubicaciones WHERE codigo LIKE %s", (PREFIJO + '%',))
    cur.execute("DELETE FROM tipoubicacion WHERE descripcion LIKE %s OR descripcion = 'Estantería'", (PREFIJO + '%',))
    conn.commit()
    conn.close()


def _flashes(client):
    with client.session_transaction() as s:
        # sin el saludo que deja el login
        mensajes = [m for _, m in s.get('_flashes', []) if not m.startswith('Bienvenido')]
        s['_flashes'] = []
    return mensajes


def _tipo(conn, descripcion):
    conn.commit()  # refresca el snapshot de la transacción
    cur = conn.cursor()
    cur.execute("SELECT * FROM tipoubicacion WHERE descripcion = %s", (descripcion,))
    return cur.fetchone()


def _guardar(client, **datos):
    client.post('/tipoubicacion/guardar', data=datos)
    return _flashes(client)


def _ubicacion(conn, tenant, id_tipo, activo=1):
    codigo = _nombre()
    cur = conn.cursor()
    cur.execute("""INSERT INTO ubicaciones (codigo, descipcion, tipoubicacion, capacidad_maxima, ocupado, orden_picking, activo, tenant_id)
                   VALUES (%s, 'Ubicación de prueba', %s, 0, 0, 0, %s, %s)""", (codigo, id_tipo, activo, tenant))
    conn.commit()
    cur.execute("SELECT id FROM ubicaciones WHERE codigo = %s AND tenant_id = %s", (codigo, tenant))
    return cur.fetchone()['id'], codigo


def _importar(client, contenido):
    r = client.post('/tipoubicacion/importar', data={
        'archivo': (io.BytesIO(contenido.encode('utf-8')), 'tipos.csv')}, content_type='multipart/form-data')
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()


# --- Alta, operación y validaciones ---

@requires_db
def test_alta_con_operacion_y_edicion(logged_client, wms, usuario_wms):
    """La operación (recepción / salida) estaba en la base pero no se podía cargar desde ninguna pantalla."""
    nombre = _nombre()
    assert _guardar(logged_client, descripcion=f'  {nombre}  ', operacion='S', soporte_picking='1') == ['Tipo de ubicación guardado']
    t = _tipo(wms, nombre)
    assert (t['operacion'], t['tenant_id']) == ('S', usuario_wms['tenant_id']) and t['soporte_picking']

    html = logged_client.get('/tipoubicacion').get_data(as_text=True)
    fila = html[html.index(f'<strong>{nombre}</strong>'):]
    assert 'Salida (despacho)</span>' in fila[:fila.index('</tr>')]
    for valor, rotulo in (('', 'Almacenamiento'), ('R', 'Recepción'), ('S', 'Salida (despacho)')):
        assert f'<option value="{valor}">{rotulo}</option>' in html

    # Almacenamiento se guarda sin operación; el nombre anterior del campo del formulario se sigue aceptando
    otro = _nombre()
    assert _guardar(logged_client, id=t['id'], descipcion=otro, operacion='') == ['Tipo de ubicación guardado']
    t = _tipo(wms, otro)
    assert t['operacion'] is None and not t['soporte_picking'] and _tipo(wms, nombre) is None
    # Una edición que no manda la operación conserva la que tenía
    _guardar(logged_client, id=t['id'], descripcion=otro, operacion='R')
    _guardar(logged_client, id=t['id'], descripcion=otro)
    assert _tipo(wms, otro)['operacion'] == 'R'


@requires_db
@pytest.mark.parametrize('datos, mensaje', [
    ({'descripcion': '   '}, 'Descripción: es obligatoria.'),
    ({}, 'Descripción: es obligatoria.'),
    ({'descripcion': PREFIJO + 'x' * 100}, 'Descripción: admite hasta 100 caracteres.'),
    ({'operacion': 'X'}, 'Operación: "X" no es válida. Usar: R (recepción), S (salida) o vacío.'),
    ({'id': 'abc'}, 'Tipo de ubicación inválido.'),
    ({'id': '999999999'}, 'El tipo de ubicación que se intenta modificar no existe.'),
])
def test_datos_invalidos_no_se_guardan(logged_client, wms, datos, mensaje):
    """Antes se guardaban tal cual o salía el error de la base."""
    nombre = _nombre()
    assert _guardar(logged_client, **{'descripcion': nombre, **datos} if datos else {}) == [mensaje]
    assert _tipo(wms, nombre) is None


@requires_db
def test_descripcion_repetida_se_rechaza(logged_client, wms):
    nombre, otro = _nombre(), _nombre()
    _guardar(logged_client, descripcion=nombre)
    _guardar(logged_client, descripcion=otro)
    assert _guardar(logged_client, descripcion=f' {nombre} ') == [f'Ya existe un tipo de ubicación con la descripción "{nombre}".']
    assert _guardar(logged_client, id=_tipo(wms, otro)['id'], descripcion=nombre) == [
        f'Ya existe un tipo de ubicación con la descripción "{nombre}".']
    assert _guardar(logged_client, id=_tipo(wms, nombre)['id'], descripcion=nombre, soporte_picking='1') == [
        'Tipo de ubicación guardado']


@requires_db
def test_eliminar(logged_client, wms, usuario_wms):
    libre, en_uso = _nombre(), _nombre()
    _guardar(logged_client, descripcion=libre)
    _guardar(logged_client, descripcion=en_uso)
    _ubicacion(wms, usuario_wms['tenant_id'], _tipo(wms, en_uso)['id'])

    logged_client.post(f'/tipoubicacion/eliminar/{_tipo(wms, en_uso)["id"]}')
    assert _flashes(logged_client) == [f'No se puede eliminar el tipo "{en_uso}": lo usa 1 ubicación.']
    html = logged_client.get('/tipoubicacion').get_data(as_text=True)
    fila = html[html.index(f'<strong>{en_uso}</strong>'):]
    assert '>1</td>' in fila[:fila.index('</tr>')]                  # el listado cuenta sus ubicaciones

    logged_client.post(f'/tipoubicacion/eliminar/{_tipo(wms, libre)["id"]}')
    assert _flashes(logged_client) == ['Tipo de ubicación eliminado'] and _tipo(wms, libre) is None
    logged_client.post('/tipoubicacion/eliminar/999999999')
    assert _flashes(logged_client) == ['Tipo de ubicación no encontrado.']


# --- La operación la usan otras pantallas ---

@requires_db
def test_recepciones_ofrece_las_ubicaciones_de_tipos_de_recepcion(logged_client, wms, usuario_wms):
    """Antes dependía de que la descripción del tipo tuviera el texto "Recepci"."""
    tenant = usuario_wms['tenant_id']
    de_recepcion, con_el_nombre = _nombre(), _nombre() + ' Recepción'
    _guardar(logged_client, descripcion=de_recepcion, operacion='R')
    _guardar(logged_client, descripcion=con_el_nombre)               # se llama "Recepción" pero es de almacenamiento
    _, cod_ok = _ubicacion(wms, tenant, _tipo(wms, de_recepcion)['id'])
    _, cod_no = _ubicacion(wms, tenant, _tipo(wms, con_el_nombre)['id'])

    encontradas = [u['codigo'] for u in logged_client.get('/recepciones/buscar_ubicaciones',
                                                          query_string={'q': PREFIJO, 'tipo': 'recep'}).get_json()]
    assert cod_ok in encontradas and cod_no not in encontradas
    html = logged_client.get('/recepciones/nueva').get_data(as_text=True)
    assert cod_ok in html and cod_no not in html


@requires_db
def test_transportes_ofrece_como_muelle_las_ubicaciones_de_tipos_de_salida(logged_client, wms, usuario_wms):
    tenant = usuario_wms['tenant_id']
    de_salida, otro = _nombre(), _nombre()
    _guardar(logged_client, descripcion=de_salida, operacion='S')
    _guardar(logged_client, descripcion=otro)
    _, cod_muelle = _ubicacion(wms, tenant, _tipo(wms, de_salida)['id'])
    _, cod_no = _ubicacion(wms, tenant, _tipo(wms, otro)['id'])
    html = logged_client.get('/transportes').get_data(as_text=True)
    muelles = html[html.index('const muelles = '):]
    muelles = muelles[:muelles.index('</script>')]
    assert f'"codigo": "{cod_muelle}"' in muelles and f'"codigo": "{cod_no}"' not in muelles


@requires_db
def test_no_deja_de_ser_de_recepcion_con_recepciones_sin_confirmar(logged_client, wms, usuario_wms):
    tenant = usuario_wms['tenant_id']
    nombre = _nombre()
    _guardar(logged_client, descripcion=nombre, operacion='R')
    tid = _tipo(wms, nombre)['id']
    id_ubicacion, _ = _ubicacion(wms, tenant, tid)
    cur = wms.cursor()
    cur.execute("INSERT INTO proveedores (codigo, razonsocial, tenant_id) VALUES (%s, 'Proveedor de prueba', %s)", (_nombre(), tenant))
    cur.execute("SELECT MAX(id) AS id FROM proveedores WHERE tenant_id = %s AND codigo LIKE %s", (tenant, PREFIJO + '%'))
    numero = _nombre()
    cur.execute("""INSERT INTO recepciones_cabecera
                       (numero, id_proveedor, estado, id_contenedor, id_ubicacion_recep, usuario_creacion, tenant_id)
                   VALUES (%s, %s, 'Abierta', '', %s, 'test', %s)""", (numero, cur.fetchone()['id'], id_ubicacion, tenant))
    wms.commit()

    assert _guardar(logged_client, id=tid, descripcion=nombre, operacion='') == [
        'No se puede cambiar la operación: hay 1 recepción sin confirmar en ubicaciones de este tipo.']
    assert _tipo(wms, nombre)['operacion'] == 'R'
    cur.execute("UPDATE recepciones_cabecera SET estado = 'Confirmada' WHERE numero = %s", (numero,))
    wms.commit()
    assert _guardar(logged_client, id=tid, descripcion=nombre, operacion='') == ['Tipo de ubicación guardado']


# --- Importación y exportación ---

@requires_db
def test_importar_y_exportar_con_operacion(logged_client, wms):
    recepcion, salida, por_nombre, almacen, mala, larga = (_nombre() for _ in range(6))
    resultado = _importar(logged_client, '\n'.join([
        'descripcion,operacion,soporte_picking',
        f'  {recepcion}  ,R,0',
        f'{salida},s,',
        f'{por_nombre},Recepción,',
        f'{almacen},,1',
        f'{mala},X,',
        f'{larga}{"x" * 100},,',
        f'{recepcion},S,',
        ',R,',
    ]))
    assert resultado['insertados'] == 4 and resultado['omitidos'] == [recepcion]
    assert [(e['fila'], e['razon']) for e in resultado['errores']] == [
        (5, 'Operación: "X" no es válida. Usar: R (recepción), S (salida) o vacío.'),
        (6, 'Descripción: admite hasta 100 caracteres.'),
        (8, 'El campo descripcion es obligatorio')]
    assert [_tipo(wms, n)['operacion'] for n in (recepcion, salida, por_nombre, almacen)] == ['R', 'S', 'R', None]
    assert _tipo(wms, almacen)['soporte_picking'] and not _tipo(wms, recepcion)['soporte_picking']

    exportado = logged_client.get('/tipoubicacion/exportar/csv').get_data(as_text=True).lstrip('﻿')
    filas = {f['descripcion']: f for f in csv.DictReader(io.StringIO(exportado))}
    assert (filas[recepcion]['operacion'], filas[salida]['operacion'], filas[almacen]['operacion']) == ('R', 'S', '')
    resultado = _importar(logged_client, exportado)                  # y se puede volver a importar
    assert resultado['insertados'] == 0 and resultado['errores'] == []


@requires_db
@pytest.mark.parametrize('formato', ['csv', 'json', 'xlsx'])
def test_la_plantilla_se_puede_importar(logged_client, wms, formato):
    plantilla = logged_client.get(f'/tipoubicacion/plantilla/{formato}')
    r = logged_client.post('/tipoubicacion/importar', data={
        'archivo': (io.BytesIO(plantilla.data), f'plantilla.{formato}')}, content_type='multipart/form-data')
    resultado = r.get_json()
    assert resultado['insertados'] + len(resultado['omitidos']) == 1 and resultado['errores'] == []
    cur = wms.cursor()
    cur.execute("DELETE FROM tipoubicacion WHERE descripcion = 'Estantería' AND id NOT IN (SELECT tipoubicacion FROM ubicaciones WHERE tipoubicacion IS NOT NULL)")
    wms.commit()


def test_ninguna_pantalla_reconoce_la_recepcion_por_el_nombre_del_tipo():
    """La operación del tipo es la única regla: no tiene que volver la búsqueda por el texto "Recepci"."""
    modulos = Path(__file__).resolve().parent.parent / 'modules'
    con_el_texto = [p.name for p in modulos.glob('*.py') if re.search(r"Recepci%", p.read_text(encoding='utf-8'))]
    assert con_el_texto == []
