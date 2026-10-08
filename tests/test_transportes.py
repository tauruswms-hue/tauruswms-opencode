"""Transportes: alta, validaciones, rutas, muelle de salida, inactivación e importación."""

import io
import uuid

import pytest

from tests.conftest import requires_db

PREFIJO = 'ZZR'   # los códigos de prueba empiezan así, para poder limpiarlos


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
    cur.execute("DELETE FROM pedidos_cabecera WHERE nro_pedido LIKE %s", (PREFIJO + '%',))
    cur.execute("DELETE FROM clientes WHERE codigo LIKE %s", (PREFIJO + '%',))
    cur.execute("DELETE FROM transportes WHERE codigo LIKE %s", (PREFIJO + '%',))
    cur.execute("DELETE FROM rutas WHERE nombre_ruta LIKE %s", (PREFIJO + '%',))
    cur.execute("DELETE FROM ubicaciones WHERE codigo LIKE %s", (PREFIJO + '%',))
    cur.execute("DELETE FROM tipoubicacion WHERE descripcion LIKE %s", (PREFIJO + '%',))
    conn.commit()
    conn.close()


def _flashes(client):
    with client.session_transaction() as s:
        # sin el saludo que deja el login
        mensajes = [m for _, m in s.get('_flashes', []) if not m.startswith('Bienvenido')]
        s['_flashes'] = []
    return mensajes


def _transporte(conn, codigo):
    conn.commit()  # refresca el snapshot de la transacción
    cur = conn.cursor()
    cur.execute("SELECT * FROM transportes WHERE codigo = %s", (codigo,))
    return cur.fetchone()


def _rutas_de(conn, codigo):
    conn.commit()
    cur = conn.cursor()
    cur.execute("""SELECT r.nombre_ruta, tr.observaciones FROM transporte_rutas tr
                   JOIN rutas r ON r.id_ruta = tr.id_ruta
                   JOIN transportes t ON t.id_transporte = tr.id_transporte
                   WHERE t.codigo = %s ORDER BY r.nombre_ruta""", (codigo,))
    return [(r['nombre_ruta'], r['observaciones']) for r in cur.fetchall()]


def _guardar(client, **datos):
    datos.setdefault('razonsocial', 'Transporte de prueba S.A.')
    client.post('/transportes/guardar', data=datos)
    return _flashes(client)


def _ruta(conn, tenant, nombre=None):
    nombre = nombre or _codigo()
    cur = conn.cursor()
    cur.execute("INSERT INTO rutas (nombre_ruta, tenant_id) VALUES (%s, %s)", (nombre, tenant))
    conn.commit()
    cur.execute("SELECT id_ruta FROM rutas WHERE nombre_ruta = %s AND tenant_id = %s", (nombre, tenant))
    return cur.fetchone()['id_ruta'], nombre


def _ubicacion(conn, tenant, operacion):
    """Ubicación cuyo tipo tiene la operación dada ('S' = salida, 'R' = recepción)."""
    cur = conn.cursor()
    tipo, codigo = _codigo(), _codigo()
    cur.execute("INSERT INTO tipoubicacion (descripcion, operacion, tenant_id) VALUES (%s, %s, %s)", (tipo, operacion, tenant))
    conn.commit()
    cur.execute("SELECT id FROM tipoubicacion WHERE descripcion = %s", (tipo,))
    cur.execute("""INSERT INTO ubicaciones (codigo, descipcion, tipoubicacion, capacidad_maxima, ocupado, orden_picking, tenant_id)
                   VALUES (%s, 'Muelle de prueba', %s, 0, 0, 0, %s)""", (codigo, cur.fetchone()['id'], tenant))
    conn.commit()
    cur.execute("SELECT id FROM ubicaciones WHERE codigo = %s AND tenant_id = %s", (codigo, tenant))
    return cur.fetchone()['id'], codigo


# --- Alta y validaciones ---

@requires_db
def test_alta_minima_sin_cuit_ni_rutas(logged_client, wms):
    """El CUIT es opcional y no hace falta cargar rutas."""
    codigo = _codigo()
    assert _guardar(logged_client, codigo=codigo) == ['Transporte guardado exitosamente.']
    t = _transporte(wms, codigo)
    assert t['activo'] and t['cuit'] is None and t['id_muelle_salida'] is None
    assert _rutas_de(wms, codigo) == []

    html = logged_client.get('/transportes').get_data(as_text=True)
    assert codigo in html
    campo = html[html.index('id="form_cuit"') - 80:html.index('id="form_cuit"') + 200]
    assert 'required' not in campo                       # el CUIT ya no es obligatorio en el formulario
    lista = html[html.index('id="form_activo"'):]
    lista = lista[:lista.index('</select>')]
    assert '<option value="1">Activo</option>' in lista and '<option value="0">Inactivo</option>' in lista


@requires_db
@pytest.mark.parametrize('datos, mensaje', [
    ({'codigo': '', 'razonsocial': 'x'}, 'Código es obligatorio.'),
    ({'razonsocial': '  '}, 'Razón social es obligatorio.'),
    ({'email': 'sin-arroba'}, 'Mail: no tiene formato de dirección de correo.'),
    ({'cuit': '30-123'}, 'CUIT inválido: debe tener el formato 99-99999999-9.'),
    ({'telefono': 'x' * 51}, 'Teléfono: admite hasta 50 caracteres.'),
    ({'id_muelle_salida': '999999999'}, 'Muelle de salida: la ubicación elegida no existe.'),
    ({'rutas_ids[]': '999999999'}, 'Rutas: la ruta elegida no existe.'),
])
def test_datos_invalidos_no_se_guardan(logged_client, wms, datos, mensaje):
    codigo = _codigo()
    datos = {'codigo': codigo, **datos}
    cur = wms.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM transportes")
    antes = cur.fetchone()['n']
    assert _guardar(logged_client, **datos) == [mensaje]
    wms.commit()
    cur.execute("SELECT COUNT(*) AS n FROM transportes")
    assert cur.fetchone()['n'] == antes


@requires_db
def test_codigo_repetido_da_mensaje_claro(logged_client, wms):
    codigo = _codigo()
    _guardar(logged_client, codigo=codigo)
    assert _guardar(logged_client, codigo=codigo, razonsocial='Otro') == [f'Ya existe un transporte con el código "{codigo}".']
    # Volver a guardar el mismo transporte con su propio código sí se puede
    t = _transporte(wms, codigo)
    assert _guardar(logged_client, id_transporte=t['id_transporte'], codigo=codigo, activo='1') == [
        'Transporte guardado exitosamente.']


@requires_db
def test_editar_un_transporte_de_otro_tenant_no_hace_nada(logged_client, wms, usuario_wms):
    ajeno = _codigo()
    cur = wms.cursor()
    cur.execute("INSERT INTO transportes (codigo, razonsocial, tenant_id) VALUES (%s, 'Ajeno', %s)",
                (ajeno, usuario_wms['tenant_id'] + 999999))
    wms.commit()
    id_ruta, _ = _ruta(wms, usuario_wms['tenant_id'])
    id_ajeno = _transporte(wms, ajeno)['id_transporte']
    assert _guardar(logged_client, id_transporte=id_ajeno, codigo=_codigo(), **{'rutas_ids[]': [id_ruta]}) == [
        'El transporte que se intenta modificar no existe.']
    assert _transporte(wms, ajeno)['razonsocial'] == 'Ajeno' and _rutas_de(wms, ajeno) == []


# --- Rutas y muelle ---

@requires_db
def test_rutas_que_cubre(logged_client, wms, usuario_wms):
    codigo = _codigo()
    r1, n1 = _ruta(wms, usuario_wms['tenant_id'], _codigo() + ' "Norte"')
    r2, n2 = _ruta(wms, usuario_wms['tenant_id'])
    assert _guardar(logged_client, codigo=codigo, **{'rutas_ids[]': [r1, '', r2],
                                                     'rutas_obs[]': ['Lunes y jueves', '', '']}) == [
        'Transporte guardado exitosamente.']
    assert _rutas_de(wms, codigo) == sorted([(n1, 'Lunes y jueves'), (n2, None)])

    # La misma ruta dos veces se rechaza con un mensaje claro
    otro = _codigo()
    assert _guardar(logged_client, codigo=otro, **{'rutas_ids[]': [r1, r1]}) == ['Rutas: hay una ruta repetida.']
    assert _transporte(wms, otro) is None

    # El listado muestra las rutas de cada transporte; los nombres van escapados
    html = logged_client.get('/transportes').get_data(as_text=True)
    fila = html[html.index(f'<code>{codigo}</code>'):]
    fila = fila[:fila.index('</tr>')]
    assert n2 in fila and '&#34;Norte&#34;' in fila

    # Editar reemplaza las rutas, y se pueden quitar todas
    t = _transporte(wms, codigo)
    _guardar(logged_client, id_transporte=t['id_transporte'], codigo=codigo, activo='1', **{'rutas_ids[]': [r2]})
    assert _rutas_de(wms, codigo) == [(n2, None)]
    _guardar(logged_client, id_transporte=t['id_transporte'], codigo=codigo, activo='1')
    assert _rutas_de(wms, codigo) == []


@requires_db
def test_muelle_de_salida_tiene_que_ser_una_ubicacion_de_salida(logged_client, wms, usuario_wms):
    salida, cod_salida = _ubicacion(wms, usuario_wms['tenant_id'], 'S')
    recepcion, _ = _ubicacion(wms, usuario_wms['tenant_id'], 'R')
    codigo, otro = _codigo(), _codigo()
    assert _guardar(logged_client, codigo=codigo, id_muelle_salida=salida) == ['Transporte guardado exitosamente.']
    assert _transporte(wms, codigo)['id_muelle_salida'] == salida
    assert _guardar(logged_client, codigo=otro, id_muelle_salida=recepcion) == [
        'Muelle de salida: la ubicación tiene que ser de un tipo de salida.']
    assert _transporte(wms, otro) is None

    html = logged_client.get('/transportes').get_data(as_text=True)
    fila = html[html.index(f'<code>{codigo}</code>'):]
    assert f'<code>{cod_salida}</code>' in fila[:fila.index('</tr>')]


def test_el_formulario_escapa_los_valores_que_inserta():
    """transportes.js arma filas y opciones con texto del usuario: tiene que escaparlo."""
    from pathlib import Path
    js = (Path(__file__).resolve().parent.parent / 'static' / 'js' / 'transportes.js').read_text(encoding='utf-8')
    assert 'escTra(r.nombre_ruta)' in js and 'escTra(obs)' in js
    assert '${r.nombre_ruta}' not in js and '${obs}' not in js and '${m.descipcion}' not in js


# --- Estado ---

@requires_db
def test_inactivar_y_reactivar(logged_client, wms, usuario_wms):
    codigo, cliente = _codigo(), _codigo()
    _guardar(logged_client, codigo=codigo)
    tid = _transporte(wms, codigo)['id_transporte']
    cur = wms.cursor()
    cur.execute("INSERT INTO clientes (codigo, razonsocial, id_transporte_predeterminado, tenant_id) VALUES (%s, 'Cliente', %s, %s)",
                (cliente, tid, usuario_wms['tenant_id']))
    wms.commit()

    logged_client.post(f'/transportes/eliminar/{tid}')
    (mensaje,) = _flashes(logged_client)
    assert 'quedó inactivo' in mensaje and 'Lo tiene como transporte habitual 1 cliente, que lo conserva.' in mensaje
    assert not _transporte(wms, codigo)['activo']

    # Sigue en el listado, marcado, y la ficha de clientes lo sigue ofreciendo a quien ya lo tiene
    html = logged_client.get('/transportes').get_data(as_text=True)
    fila = html[html.index(f'<code>{codigo}</code>'):]
    assert 'Inactivo</span>' in fila[:fila.index('</tr>')]
    html = logged_client.get('/clientes').get_data(as_text=True)
    datos = html[html.index('const transportesDB = '):]
    assert f'"id_transporte": {tid}' in datos[:datos.index('</script>')]

    logged_client.post(f'/transportes/eliminar/{tid}')
    assert 'ya estaba inactivo' in _flashes(logged_client)[0]
    # Reactivar y volver a inactivar desde la edición, con el campo Estado
    _guardar(logged_client, id_transporte=tid, codigo=codigo, activo='1')
    assert _transporte(wms, codigo)['activo']
    _guardar(logged_client, id_transporte=tid, codigo=codigo, activo='0')
    assert not _transporte(wms, codigo)['activo']
    logged_client.post('/transportes/eliminar/999999999')
    assert _flashes(logged_client) == ['Transporte no encontrado.']


# --- Importación y exportación ---

@requires_db
def test_importar_con_muelle_y_rutas(logged_client, wms, usuario_wms):
    _, ruta_a = _ruta(wms, usuario_wms['tenant_id'])
    _, ruta_b = _ruta(wms, usuario_wms['tenant_id'])
    _, muelle = _ubicacion(wms, usuario_wms['tenant_id'], 'S')
    completo, sin_estado, inactivo = _codigo(), _codigo(), _codigo()
    malos = [_codigo() for _ in range(4)]
    csv = '\n'.join([
        'codigo,razonsocial,cuit,email,muelle_salida,rutas,activo',
        f'{completo},Completo S.A.,30123456789,a@b.com,{muelle},{ruta_a}; {ruta_b},1',
        f'{sin_estado},Sin estado,,,,,',                     # activo vacío: nace activo
        f'{inactivo},Inactivo,,,,,0',
        f'{malos[0]},Ruta inexistente,,,,NOEXISTE,1',
        f'{malos[1]},Muelle inexistente,,,NOEXISTE,,1',
        f'{malos[2]},Mail malo,,sin-arroba,,,1',
        f'{malos[3]},CUIT malo,30-1,,,,1',
        f'{completo},Repetido,,,,,1',
    ])
    r = logged_client.post('/transportes/importar', data={
        'archivo': (io.BytesIO(csv.encode('utf-8')), 'transportes.csv')}, content_type='multipart/form-data')
    resultado = r.get_json()
    assert resultado['insertados'] == 3 and resultado['omitidos'] == [completo]
    assert [e['razon'] for e in resultado['errores']] == [
        'Rutas: no existe la ruta "NOEXISTE".', 'Muelle de salida: no existe la ubicación "NOEXISTE".',
        'Mail: no tiene formato de dirección de correo.', 'CUIT inválido: debe tener el formato 99-99999999-9.']
    t = _transporte(wms, completo)
    assert t['cuit'] == '30-12345678-9' and t['id_muelle_salida'] is not None and t['activo']
    assert _rutas_de(wms, completo) == sorted([(ruta_a, None), (ruta_b, None)])
    assert _transporte(wms, sin_estado)['activo'] and not _transporte(wms, inactivo)['activo']
    assert all(_transporte(wms, m) is None for m in malos)

    # Lo exportado tiene el mismo formato que acepta la importación
    exportado = logged_client.get('/transportes/exportar/csv').get_data(as_text=True)
    assert exportado.splitlines()[0].lstrip('﻿').split(',')[-3:] == ['muelle_salida', 'rutas', 'activo']
    linea = next(x for x in exportado.splitlines() if x.startswith(completo + ','))
    assert muelle in linea and '; '.join(sorted([ruta_a, ruta_b])) in linea


@requires_db
@pytest.mark.parametrize('formato', ['csv', 'json', 'xlsx'])
def test_la_plantilla_se_puede_importar(logged_client, wms, formato):
    from werkzeug.datastructures import FileStorage

    from modules.batch_utils import parse_file
    plantilla = logged_client.get(f'/transportes/plantilla/{formato}')
    filas = parse_file(FileStorage(io.BytesIO(plantilla.data), filename=f'p.{formato}'))
    assert [f['codigo'] for f in filas] == ['TRA001'] and 'rutas' in filas[0] and 'muelle_salida' in filas[0]


# --- Estado, uso en clientes y pedidos, muelle que deja de servir ---

def _pedido(conn, tenant, id_transporte, estado='Pendiente'):
    """Un cliente y un pedido suyo con el transporte dado. Devuelve el id del pedido."""
    cur = conn.cursor()
    cliente, nro = _codigo(), _codigo()
    cur.execute("INSERT INTO clientes (codigo, razonsocial, tenant_id) VALUES (%s, 'Cliente de prueba', %s)", (cliente, tenant))
    cur.execute("SELECT id_cliente FROM clientes WHERE codigo = %s", (cliente,))
    cur.execute("""INSERT INTO pedidos_cabecera (nro_pedido, id_cliente, id_transporte, fecha_pedido, estado, tenant_id)
                   VALUES (%s, %s, %s, CURRENT_DATE, %s, %s)""", (nro, cur.fetchone()['id_cliente'], id_transporte, estado, tenant))
    conn.commit()
    cur.execute("SELECT id_pedido FROM pedidos_cabecera WHERE nro_pedido = %s", (nro,))
    return cur.fetchone()['id_pedido']


@requires_db
def test_editar_sin_el_estado_lo_conserva(logged_client, wms):
    codigo = _codigo()
    _guardar(logged_client, codigo=codigo, activo='0')
    tid = _transporte(wms, codigo)['id_transporte']
    _guardar(logged_client, id_transporte=tid, codigo=codigo)
    assert not _transporte(wms, codigo)['activo']
    _guardar(logged_client, id_transporte=tid, codigo=codigo, activo='1')
    _guardar(logged_client, id_transporte=tid, codigo=codigo)       # antes, sin el dato, quedaba inactivo
    assert _transporte(wms, codigo)['activo']


@requires_db
def test_inactivar_avisa_los_pedidos_sin_despachar_y_el_listado_cuenta_el_uso(logged_client, wms, usuario_wms):
    tenant = usuario_wms['tenant_id']
    codigo = _codigo()
    id_ruta, nombre_ruta = _ruta(wms, tenant)
    _guardar(logged_client, codigo=codigo, **{'rutas_ids[]': [str(id_ruta)], 'rutas_obs[]': ['']})
    tid = _transporte(wms, codigo)['id_transporte']
    _pedido(wms, tenant, tid, 'Pendiente')
    _pedido(wms, tenant, tid, 'Preparado')
    _pedido(wms, tenant, tid, 'Despachado')
    cur = wms.cursor()
    cur.execute("UPDATE rutas SET activo = 0 WHERE id_ruta = %s", (id_ruta,))
    wms.commit()

    def fila():
        html = logged_client.get('/transportes').get_data(as_text=True)
        recorte = html[html.index(f'<code>{codigo}</code>'):]
        return recorte[:recorte.index('</tr>')]

    antes = fila()
    assert '>0</td>' in antes and '>3</td>' in antes                 # 0 clientes y 3 pedidos
    assert f'{nombre_ruta} (inactiva)</span>' in antes and f'/transportes/eliminar/{tid}"' in antes

    logged_client.post(f'/transportes/eliminar/{tid}')
    (mensaje,) = _flashes(logged_client)
    assert 'Lo usan 2 pedidos sin despachar, que lo conservan.' in mensaje
    assert '/transportes/eliminar/' not in fila()                    # un inactivo no tiene el botón de inactivar


@requires_db
def test_el_pedido_conserva_su_transporte_inactivo_al_editarlo(logged_client, wms, usuario_wms):
    """El formulario de edición cargaba solo los activos: el del pedido se perdía al guardar."""
    tenant = usuario_wms['tenant_id']
    codigo, otro = _codigo(), _codigo()
    _guardar(logged_client, codigo=codigo, razonsocial=f'Tra <{codigo}>')
    _guardar(logged_client, codigo=otro, razonsocial=f'Otro {otro}', activo='0')
    tid = _transporte(wms, codigo)['id_transporte']
    id_pedido = _pedido(wms, tenant, tid)
    logged_client.post(f'/transportes/eliminar/{tid}')
    _flashes(logged_client)

    html = logged_client.get(f'/pedidos/editar/{id_pedido}').get_data(as_text=True)
    datos = html[html.index('const transportesDB = '):]
    datos = datos[:datos.index('</script>')]
    assert f'"id_transporte": {tid}' in datos and '"activo": 0' in datos
    assert f'Otro {otro}' not in datos                               # otro inactivo no se ofrece
    # El nombre se inserta como texto, no como HTML
    assert ".text(t.razonsocial" in html and '>${t.razonsocial}<' not in html
    # En un pedido nuevo, el inactivo no aparece
    assert f'"id_transporte": {tid}' not in logged_client.get('/pedidos/nuevo').get_data(as_text=True)


@requires_db
def test_muelle_que_dejo_de_servir_se_conserva_y_se_avisa(logged_client, wms, usuario_wms):
    tenant = usuario_wms['tenant_id']
    muelle, cod_muelle = _ubicacion(wms, tenant, 'S')
    inactivo, _ = _ubicacion(wms, tenant, 'S')
    codigo, otro = _codigo(), _codigo()
    _guardar(logged_client, codigo=codigo, id_muelle_salida=muelle)
    tid = _transporte(wms, codigo)['id_transporte']
    cur = wms.cursor()
    cur.execute("UPDATE ubicaciones SET activo = 0 WHERE id IN (%s, %s)", (muelle, inactivo))
    wms.commit()

    # Una ubicación inactiva no se puede asignar de nuevo, pero el transporte que ya la tiene la conserva
    assert _guardar(logged_client, codigo=otro, id_muelle_salida=inactivo) == ['Muelle de salida: la ubicación está inactiva.']
    assert _guardar(logged_client, id_transporte=tid, codigo=codigo, id_muelle_salida=inactivo) == [
        'Muelle de salida: la ubicación está inactiva.']
    assert _guardar(logged_client, id_transporte=tid, codigo=codigo, razonsocial='Renombrado',
                    id_muelle_salida=muelle) == ['Transporte guardado exitosamente.']
    assert _transporte(wms, codigo)['id_muelle_salida'] == muelle

    html = logged_client.get('/transportes').get_data(as_text=True)
    fila = html[html.index(f'<code>{codigo}</code>'):]
    fila = fila[:fila.index('</tr>')]
    assert 'ubicación inactiva' in fila and '"muelle_aviso": "ubicaci' in fila
    # La lista de muelles que se ofrecen ya no la trae
    ofrecidos = html[html.index('const muelles = '):]
    assert f'"codigo": "{cod_muelle}"' not in ofrecidos[:ofrecidos.index('</script>')]

    # Si la ubicación deja de ser de salida, también se conserva y se avisa
    cur.execute("UPDATE ubicaciones SET activo = 1 WHERE id = %s", (muelle,))
    cur.execute("UPDATE tipoubicacion SET operacion = 'R' WHERE id = (SELECT tipoubicacion FROM ubicaciones WHERE id = %s)", (muelle,))
    wms.commit()
    assert _guardar(logged_client, id_transporte=tid, codigo=codigo, id_muelle_salida=muelle) == ['Transporte guardado exitosamente.']
    assert 'ya no es una ubicación de salida' in logged_client.get('/transportes').get_data(as_text=True)
    # Y se le puede quitar
    _guardar(logged_client, id_transporte=tid, codigo=codigo, id_muelle_salida='')
    assert _transporte(wms, codigo)['id_muelle_salida'] is None
