"""Rutas: alta, validaciones, nombre único, inactivación, uso en otros maestros, importación e Intercambio."""

import csv
import io
import uuid
from pathlib import Path

import pytest

from tests.conftest import requires_db

PREFIJO = 'ZZU'   # los nombres y códigos de prueba empiezan así, para poder limpiarlos


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
    cur.execute("DELETE FROM clientes WHERE codigo LIKE %s", (PREFIJO + '%',))
    cur.execute("DELETE FROM transportes WHERE codigo LIKE %s", (PREFIJO + '%',))
    cur.execute("DELETE FROM rutas WHERE nombre_ruta LIKE %s", (PREFIJO + '%',))
    conn.commit()
    conn.close()


def _flashes(client):
    with client.session_transaction() as s:
        # sin el saludo que deja el login
        mensajes = [m for _, m in s.get('_flashes', []) if not m.startswith('Bienvenido')]
        s['_flashes'] = []
    return mensajes


def _rutas(conn, nombre):
    conn.commit()  # refresca el snapshot de la transacción
    cur = conn.cursor()
    cur.execute("SELECT * FROM rutas WHERE nombre_ruta = %s", (nombre,))
    return list(cur.fetchall())


def _guardar(client, **datos):
    client.post('/rutas/guardar', data=datos)
    return _flashes(client)


def _ruta(client, conn, **datos):
    nombre = _nombre()
    assert _guardar(client, nombre_ruta=nombre, **datos) == ['Ruta guardada correctamente']
    return _rutas(conn, nombre)[0]['id_ruta'], nombre


def _importar(client, contenido):
    r = client.post('/rutas/importar', data={'archivo': (io.BytesIO(contenido.encode('utf-8')), 'rutas.csv')},
                    content_type='multipart/form-data')
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()


def _en_uso(conn, tenant, id_ruta):
    """Un transporte, un cliente y un pedido con la ruta. Devuelve (id_transporte, id_cliente, id_pedido)."""
    cur = conn.cursor()
    codigo = _nombre()
    cur.execute("INSERT INTO transportes (codigo, razonsocial, tenant_id) VALUES (%s, 'Transporte de prueba', %s)", (codigo, tenant))
    cur.execute("INSERT INTO clientes (codigo, razonsocial, id_ruta, tenant_id) VALUES (%s, 'Cliente de prueba', %s, %s)", (codigo, id_ruta, tenant))
    conn.commit()
    cur.execute("SELECT id_transporte FROM transportes WHERE codigo = %s", (codigo,))
    id_transporte = cur.fetchone()['id_transporte']
    cur.execute("SELECT id_cliente FROM clientes WHERE codigo = %s", (codigo,))
    id_cliente = cur.fetchone()['id_cliente']
    cur.execute("INSERT INTO transporte_rutas (id_transporte, id_ruta, tenant_id) VALUES (%s, %s, %s)", (id_transporte, id_ruta, tenant))
    cur.execute("""INSERT INTO pedidos_cabecera (nro_pedido, id_cliente, id_ruta, fecha_pedido, estado, tenant_id)
                   VALUES (%s, %s, %s, '2026-01-15', 'Pendiente', %s)""", (codigo, id_cliente, id_ruta, tenant))
    conn.commit()
    cur.execute("SELECT id_pedido FROM pedidos_cabecera WHERE nro_pedido = %s", (codigo,))
    return id_transporte, id_cliente, cur.fetchone()['id_pedido']


@requires_db
def test_alta_y_edicion(logged_client, wms, usuario_wms):
    nombre = _nombre()
    assert _guardar(logged_client, nombre_ruta=f'  {nombre}  ', descripcion='  Reparto  ', activo='1') == ['Ruta guardada correctamente']
    ruta, = _rutas(wms, nombre)                                   # sin los espacios de los extremos
    assert ruta['activo'] and ruta['descripcion'] == 'Reparto' and ruta['tenant_id'] == usuario_wms['tenant_id']

    otro = _nombre()
    assert _guardar(logged_client, id_ruta=ruta['id_ruta'], nombre_ruta=otro, descripcion='', activo='0') == ['Ruta guardada correctamente']
    assert _rutas(wms, nombre) == []
    editada, = _rutas(wms, otro)
    assert editada['id_ruta'] == ruta['id_ruta'] and not editada['activo'] and editada['descripcion'] is None


@requires_db
def test_nombre_obligatorio_y_con_largo_maximo(logged_client, wms):
    assert _guardar(logged_client, nombre_ruta='   ', activo='1') == ['El nombre de la ruta es obligatorio.']
    largo = PREFIJO + 'X' * 100
    assert _guardar(logged_client, nombre_ruta=largo, activo='1') == ['Nombre: admite hasta 100 caracteres.']
    assert _rutas(wms, largo) == []


@requires_db
def test_nombre_unico_por_empresa(logged_client, wms, usuario_wms):
    _, nombre = _ruta(logged_client, wms)
    id_otra, otra = _ruta(logged_client, wms)
    assert _guardar(logged_client, nombre_ruta=nombre) == [f'Ya existe una ruta con el nombre "{nombre}".']
    assert _guardar(logged_client, id_ruta=id_otra, nombre_ruta=nombre) == [f'Ya existe una ruta con el nombre "{nombre}".']
    assert _guardar(logged_client, id_ruta=id_otra, nombre_ruta=otra) == ['Ruta guardada correctamente']
    assert len(_rutas(wms, nombre)) == 1

    # La base también lo rechaza
    from modules.sql_dialect import is_duplicate_key_error
    cur = wms.cursor()
    with pytest.raises(Exception) as error:
        cur.execute("INSERT INTO rutas (nombre_ruta, tenant_id) VALUES (%s, %s)", (nombre, usuario_wms['tenant_id']))
    assert is_duplicate_key_error(error.value)
    wms.rollback()


@requires_db
def test_editar_o_inactivar_una_ruta_inexistente(logged_client, wms):
    assert _guardar(logged_client, id_ruta='99999999', nombre_ruta=_nombre()) == ['La ruta que se intenta modificar no existe.']
    assert _guardar(logged_client, id_ruta='abc', nombre_ruta=_nombre()) == ['Ruta inválida.']
    logged_client.post('/rutas/eliminar/99999999')
    assert _flashes(logged_client) == ['Ruta no encontrada.']


@requires_db
def test_editar_sin_el_campo_estado_conserva_el_estado(logged_client, wms):
    id_ruta, nombre = _ruta(logged_client, wms, activo='0')
    _guardar(logged_client, id_ruta=id_ruta, nombre_ruta=nombre, descripcion='Otra')
    ruta, = _rutas(wms, nombre)
    assert not ruta['activo'] and ruta['descripcion'] == 'Otra'


@requires_db
def test_inactivar_no_borra_ni_quita_la_ruta_de_donde_se_usa(logged_client, wms, usuario_wms):
    id_ruta, nombre = _ruta(logged_client, wms)
    id_transporte, id_cliente, id_pedido = _en_uso(wms, usuario_wms['tenant_id'], id_ruta)

    logged_client.post(f'/rutas/eliminar/{id_ruta}')
    mensaje, = _flashes(logged_client)
    assert 'quedó inactiva' in mensaje
    assert 'La siguen teniendo: 1 transporte, 1 cliente, 1 pedido.' in mensaje

    ruta, = _rutas(wms, nombre)
    assert not ruta['activo']
    cur = wms.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM transporte_rutas WHERE id_transporte = %s AND id_ruta = %s", (id_transporte, id_ruta))
    assert cur.fetchone()['n'] == 1
    cur.execute("SELECT id_ruta FROM clientes WHERE id_cliente = %s", (id_cliente,))
    assert cur.fetchone()['id_ruta'] == id_ruta
    cur.execute("SELECT id_ruta FROM pedidos_cabecera WHERE id_pedido = %s", (id_pedido,))
    assert cur.fetchone()['id_ruta'] == id_ruta

    logged_client.post(f'/rutas/eliminar/{id_ruta}')
    assert _flashes(logged_client) == [f'La ruta "{nombre}" ya estaba inactiva.']

    # Sigue en el listado, marcada y con su uso; se reactiva desde la edición
    html = logged_client.get('/rutas').get_data(as_text=True)
    assert 'Inactiva' in html[html.index(nombre):][:900] and f'/rutas/eliminar/{id_ruta}"' not in html
    _guardar(logged_client, id_ruta=id_ruta, nombre_ruta=nombre, activo='1')
    assert _rutas(wms, nombre)[0]['activo']


@requires_db
def test_inactivar_una_ruta_sin_uso(logged_client, wms):
    id_ruta, _ = _ruta(logged_client, wms)
    logged_client.post(f'/rutas/eliminar/{id_ruta}')
    mensaje, = _flashes(logged_client)
    assert 'quedó inactiva' in mensaje and 'La siguen teniendo' not in mensaje


@requires_db
def test_una_ruta_inactiva_solo_se_ofrece_a_quien_ya_la_tiene(logged_client, wms, usuario_wms):
    id_ruta, nombre = _ruta(logged_client, wms)
    _, _, id_pedido = _en_uso(wms, usuario_wms['tenant_id'], id_ruta)
    logged_client.post(f'/rutas/eliminar/{id_ruta}')
    _flashes(logged_client)   # el aviso de inactivación nombra la ruta: que no se cuele en la página siguiente

    # Pedido nuevo: no se ofrece. El pedido que ya la tiene la conserva al editarlo.
    assert nombre not in logged_client.get('/pedidos/nuevo').get_data(as_text=True)
    html = logged_client.get(f'/pedidos/editar/{id_pedido}').get_data(as_text=True)
    assert f'<option value="{id_ruta}" selected>' in html and f'{nombre} (inactiva)' in html

    # Clientes y transportes la reciben marcada: sus formularios la ocultan salvo para quien ya la tiene
    html = logged_client.get('/clientes').get_data(as_text=True)
    assert f'<option value="{id_ruta}" data-inactiva="1">{nombre} (inactiva)</option>' in html
    html = logged_client.get('/transportes').get_data(as_text=True)
    assert nombre in html


@requires_db
def test_importar_y_exportar(logged_client, wms):
    _, existente = _ruta(logged_client, wms)
    nueva, inactiva, sin_estado = _nombre(), _nombre(), _nombre()
    largo = PREFIJO + 'X' * 100
    resultado = _importar(logged_client, 'nombre_ruta,descripcion,activo\n'
                          f'{existente},,1\n{nueva},Reparto,1\n{inactiva},,0\n{sin_estado},,\n,,1\n{nueva},,1\n{largo},,1\n')
    assert resultado['insertados'] == 3
    assert resultado['omitidos'] == [existente, nueva]            # la que ya estaba y la repetida en el archivo
    assert [(e['fila'], e['razon']) for e in resultado['errores']] == [
        (5, 'El campo nombre_ruta es obligatorio'), (7, 'Nombre: admite hasta 100 caracteres.')]
    assert _rutas(wms, nueva)[0]['activo'] and _rutas(wms, sin_estado)[0]['activo']
    assert not _rutas(wms, inactiva)[0]['activo']

    # Un archivo sin la columna activo (el formato anterior) se sigue importando: nacen activas
    vieja = _nombre()
    assert _importar(logged_client, f'nombre_ruta,descripcion\n{vieja},Reparto\n')['insertados'] == 1
    assert _rutas(wms, vieja)[0]['activo']

    r = logged_client.get('/rutas/exportar/csv')
    filas = {f['nombre_ruta']: f['activo'] for f in csv.DictReader(io.StringIO(r.get_data(as_text=True).lstrip('\ufeff')))}
    assert (filas[nueva], filas[inactiva]) == ('1', '0')
    resultado = _importar(logged_client, r.get_data(as_text=True))  # lo exportado se puede volver a importar
    assert resultado['insertados'] == 0 and resultado['errores'] == []


def test_el_nombre_se_escapa_al_editar():
    js = (Path(__file__).resolve().parent.parent / 'static' / 'js' / 'rutas.js').read_text(encoding='utf-8')
    assert "escRuta(data.nombre_ruta)" in js and "' + data.nombre_ruta)" not in js


@requires_db
def test_la_baja_por_intercambio_inactiva_y_el_alta_reactiva(logged_client, wms, usuario_wms):
    from modules.db_config import _get_admin_connection, get_intercambio_connection
    from modules.intercambio import procesar_intercambio_rutas
    tenant = usuario_wms['tenant_id']
    id_ruta, nombre = _ruta(logged_client, wms)
    _, id_cliente, _ = _en_uso(wms, tenant, id_ruta)

    conn_admin, conn_int = _get_admin_connection(), get_intercambio_connection()
    try:
        cur = conn_admin.cursor()
        cur.execute("SELECT codigo FROM tenants WHERE id = %s", (tenant,))
        tenant_codigo = cur.fetchone()['codigo']
        cur_int = conn_int.cursor()
        for accion in ('baja', 'alta'):
            cur_int.execute("""INSERT INTO intercambio_rutas (tenant_codigo, nombre_ruta, descripcion, accion, estado)
                               VALUES (%s, %s, 'por intercambio', %s, 'pendiente')""", (tenant_codigo, nombre, accion))
            conn_int.commit()
            res = procesar_intercambio_rutas(tenant_id=tenant, conn_int=conn_int, conn_admin=conn_admin)
            assert res['procesados'] == 1, res['errores_detalle']
            ruta, = _rutas(wms, nombre)
            assert bool(ruta['activo']) == (accion == 'alta') and ruta['id_ruta'] == id_ruta
            cur_wms = wms.cursor()
            cur_wms.execute("SELECT id_ruta FROM clientes WHERE id_cliente = %s", (id_cliente,))
            assert cur_wms.fetchone()['id_ruta'] == id_ruta      # el cliente conserva la ruta
    finally:
        cur_int = conn_int.cursor()
        cur_int.execute("DELETE FROM intercambio_rutas WHERE nombre_ruta = %s", (nombre,))
        conn_int.commit()
        conn_int.close()
        conn_admin.close()
