"""Proveedores: alta, validaciones, CUIT, estado, inactivación, uso en materiales e importación."""

import io
import uuid

import pytest

from modules.cuit import normalizar_cuit
from tests.conftest import requires_db

PREFIJO = 'ZZP'   # los códigos de prueba empiezan así, para poder limpiarlos


def _codigo():
    return PREFIJO + uuid.uuid4().hex[:8].upper()


@pytest.fixture
def wms(usuario_wms):
    """Conexión al WMS; al terminar borra los proveedores que los tests hayan creado."""
    from modules.db_config import get_db_connection
    conn = get_db_connection()
    yield conn
    cur = conn.cursor()
    cur.execute("DELETE FROM materiales WHERE codigo LIKE %s", (PREFIJO + '%',))   # arrastra material_proveedor
    cur.execute("DELETE FROM proveedores WHERE codigo LIKE %s", (PREFIJO + '%',))
    conn.commit()
    conn.close()


def _flashes(client):
    with client.session_transaction() as s:
        # sin el saludo que deja el login
        mensajes = [m for _, m in s.get('_flashes', []) if not m.startswith('Bienvenido')]
        s['_flashes'] = []
    return mensajes


def _proveedor(conn, codigo):
    conn.commit()  # refresca el snapshot de la transacción
    cur = conn.cursor()
    cur.execute("SELECT * FROM proveedores WHERE codigo = %s", (codigo,))
    return cur.fetchone()


def _guardar(client, **datos):
    datos.setdefault('razonsocial', 'Proveedor de prueba')
    client.post('/proveedores/guardar', data=datos)
    return _flashes(client)


@pytest.mark.parametrize('valor, esperado', [
    ('30-12345678-9', '30-12345678-9'),
    (' 30-12345678-9 ', '30-12345678-9'),
    ('30123456789', '30-12345678-9'),
    ('', ''),
    (None, ''),
    ('30-1234567-9', None),
    ('3012345678', None),
    ('30.12345678.9', None),
    ('AA-12345678-9', None),
])
def test_normalizar_cuit(valor, esperado):
    assert normalizar_cuit(valor) == esperado


@requires_db
@pytest.mark.parametrize('enviado, guardado', [
    ('30-12345678-9', '30-12345678-9'),
    ('30123456789', '30-12345678-9'),   # 11 dígitos sin guiones: se guarda formateado
    ('', None),                          # el CUIT es opcional
])
def test_cuit_valido_se_guarda_con_formato(logged_client, wms, enviado, guardado):
    codigo = _codigo()
    assert _guardar(logged_client, codigo=codigo, cuit=enviado) == ['Proveedor guardado correctamente']
    assert _proveedor(wms, codigo)['cuit'] == guardado


@requires_db
@pytest.mark.parametrize('cuit', ['30-1234-9', '3012345678', 'ABC', '30-12345678-99'])
def test_cuit_invalido_se_rechaza(logged_client, wms, cuit):
    codigo = _codigo()
    assert _guardar(logged_client, codigo=codigo, cuit=cuit) == ['CUIT inválido: debe tener el formato 99-99999999-9.']
    assert _proveedor(wms, codigo) is None


@requires_db
def test_cuit_cargado_antes_sin_guiones_se_muestra_formateado(logged_client, wms, usuario_wms):
    codigo = _codigo()
    cur = wms.cursor()
    cur.execute("INSERT INTO proveedores (codigo, razonsocial, cuit, tenant_id) VALUES (%s, 'Viejo', '20180039822', %s)",
                (codigo, usuario_wms['tenant_id']))
    wms.commit()
    html = logged_client.get('/proveedores').get_data(as_text=True)
    fila = html[html.index(f'<code>{codigo}</code>'):]
    fila = fila[:fila.index('</tr>')]
    assert '<td>20-18003982-2</td>' in fila and '"cuit": "20-18003982-2"' in fila
    # El campo del formulario exige el formato
    assert 'pattern="\\d{2}-\\d{8}-\\d"' in html and 'placeholder="99-99999999-9"' in html


@requires_db
def test_direccion_admite_500_caracteres(logged_client, wms):
    from modules.proveedores import DIRECCION_MAX
    assert DIRECCION_MAX == 500
    codigo, larga = _codigo(), 'Av. Siempre Viva 742, ' * 22   # 484 caracteres: antes el límite era 255
    assert len(larga.strip()) > 255
    assert _guardar(logged_client, codigo=codigo, direccion=larga) == ['Proveedor guardado correctamente']
    assert _proveedor(wms, codigo)['direccion'] == larga.strip()

    otro = _codigo()
    assert _guardar(logged_client, codigo=otro, direccion='x' * 501) == [
        'Dirección: admite hasta 500 caracteres (tiene 501).']
    assert _proveedor(wms, otro) is None
    assert f'maxlength="{DIRECCION_MAX}"' in logged_client.get('/proveedores').get_data(as_text=True)


@requires_db
def test_importar_valida_cuit_y_direccion(logged_client, wms):
    bueno, sin_guiones, malo, largo = _codigo(), _codigo(), _codigo(), _codigo()
    csv = '\n'.join([
        'codigo,razonsocial,cuit,direccion',
        f'{bueno},Uno,30-12345678-9,Calle 1',
        f'{sin_guiones},Dos,30123456789,',
        f'{malo},Tres,30-123,',
        f'{largo},Cuatro,,{"x" * 501}',
    ])
    r = logged_client.post('/proveedores/importar', data={
        'archivo': (io.BytesIO(csv.encode('utf-8')), 'proveedores.csv')}, content_type='multipart/form-data')
    resultado = r.get_json()
    assert resultado['insertados'] == 2
    assert sorted(e['razon'] for e in resultado['errores']) == [
        'CUIT inválido: debe tener el formato 99-99999999-9.',
        'Dirección: admite hasta 500 caracteres (tiene 501).']
    assert _proveedor(wms, sin_guiones)['cuit'] == '30-12345678-9'
    assert _proveedor(wms, malo) is None and _proveedor(wms, largo) is None


# --- Validaciones, estado e inactivación ---

@requires_db
def test_alta_sin_espacios_en_los_extremos(logged_client, wms, usuario_wms):
    codigo = _codigo()
    assert _guardar(logged_client, codigo=f'  {codigo}  ', razonsocial='  Uno S.A.  ', telefono='  11 4444  ',
                    email='  a@b.com  ') == ['Proveedor guardado correctamente']
    p = _proveedor(wms, codigo)
    assert (p['codigo'], p['razonsocial'], p['telefono'], p['email']) == (codigo, 'Uno S.A.', '11 4444', 'a@b.com')
    assert p['activo'] and p['tenant_id'] == usuario_wms['tenant_id']


@requires_db
@pytest.mark.parametrize('datos, mensaje', [
    ({'codigo': '   '}, 'Código: es obligatorio.'),
    ({'razonsocial': '   '}, 'Razón Social: es obligatorio.'),
    ({'codigo': PREFIJO + 'x' * 50}, 'Código: admite hasta 50 caracteres.'),
    ({'razonsocial': 'x' * 201}, 'Razón Social: admite hasta 200 caracteres.'),
    ({'telefono': '1' * 51}, 'Teléfono: admite hasta 50 caracteres.'),
    ({'email': 'a@' + 'b' * 100}, 'Email: admite hasta 100 caracteres.'),
    ({'email': 'no-es-mail'}, 'Email: "no-es-mail" no es una dirección válida.'),
    ({'id': 'abc'}, 'Proveedor inválido.'),
    ({'id': '999999999'}, 'El proveedor que se intenta modificar no existe.'),
])
def test_datos_invalidos_no_se_guardan(logged_client, wms, datos, mensaje):
    """Antes se guardaban tal cual o salía el error de la base (Data too long, Duplicate entry)."""
    codigo = _codigo()
    assert _guardar(logged_client, **{'codigo': codigo, **datos}) == [mensaje]
    assert _proveedor(wms, codigo) is None


@requires_db
def test_largos_del_formulario_son_los_de_la_base(logged_client, wms):
    codigo = _codigo()
    assert _guardar(logged_client, codigo=codigo, razonsocial='R' * 200) == ['Proveedor guardado correctamente']
    html = logged_client.get('/proveedores').get_data(as_text=True)
    assert 'id="form_codigo" required maxlength="50"' in html and 'id="form_razon" required maxlength="200"' in html


@requires_db
def test_codigo_repetido_se_rechaza(logged_client, wms):
    codigo, otro = _codigo(), _codigo()
    _guardar(logged_client, codigo=codigo)
    _guardar(logged_client, codigo=otro)
    assert _guardar(logged_client, codigo=f' {codigo} ', razonsocial='Otro') == [f'Ya existe un proveedor con el código "{codigo}".']
    assert _guardar(logged_client, id=_proveedor(wms, otro)['id'], codigo=codigo) == [
        f'Ya existe un proveedor con el código "{codigo}".']
    # Guardar el mismo proveedor con su propio código sí se puede; CUIT y razón social pueden repetirse
    assert _guardar(logged_client, id=_proveedor(wms, codigo)['id'], codigo=codigo, razonsocial='Renombrado',
                    cuit='30-12345678-9') == ['Proveedor guardado correctamente']
    assert _guardar(logged_client, id=_proveedor(wms, otro)['id'], codigo=otro, razonsocial='Renombrado',
                    cuit='30-12345678-9') == ['Proveedor guardado correctamente']
    # El código de un proveedor inactivo sigue ocupado, y el mensaje lo dice
    logged_client.post(f'/proveedores/eliminar/{_proveedor(wms, codigo)["id"]}')
    _flashes(logged_client)
    assert _guardar(logged_client, codigo=codigo) == [f'Ya existe un proveedor con el código "{codigo}".']


def _material_con_proveedor(conn, tenant, id_proveedor):
    cur = conn.cursor()
    codigo = _codigo()
    cur.execute("INSERT INTO materiales (codigo, nombre, tenant_id) VALUES (%s, 'Material de prueba', %s)", (codigo, tenant))
    cur.execute("SELECT id FROM materiales WHERE codigo = %s", (codigo,))
    id_material = cur.fetchone()['id']
    cur.execute("INSERT INTO material_proveedor (id_material, id_proveedor, es_habitual, tenant_id) VALUES (%s, %s, 1, %s)",
                (id_material, id_proveedor, tenant))
    conn.commit()
    return id_material


@requires_db
def test_inactivar_y_reactivar(logged_client, wms, usuario_wms):
    codigo = _codigo()
    _guardar(logged_client, codigo=codigo, razonsocial=f'Razon {codigo}')
    pid = _proveedor(wms, codigo)['id']
    _material_con_proveedor(wms, usuario_wms['tenant_id'], pid)

    logged_client.post(f'/proveedores/eliminar/{pid}')
    (mensaje,) = _flashes(logged_client)
    assert 'quedó inactivo' in mensaje and 'Lo tiene asignado 1 material, que lo conserva.' in mensaje
    assert not _proveedor(wms, codigo)['activo']
    logged_client.post(f'/proveedores/eliminar/{pid}')
    assert _flashes(logged_client) == [f'El proveedor "Razon {codigo}" ya estaba inactivo.']
    logged_client.post('/proveedores/eliminar/999999999')
    assert _flashes(logged_client) == ['Proveedor no encontrado.']

    # Sigue en el listado, marcado, con sus materiales y sin el botón de inactivar
    html = logged_client.get('/proveedores').get_data(as_text=True)
    fila = html[html.index(f'<code>{codigo}</code>'):]
    fila = fila[:fila.index('</tr>')]
    assert 'Inactivo</span>' in fila and '>1</td>' in fila and '/proveedores/eliminar/' not in fila
    # Materiales lo recibe marcado: lo ofrece solo en la fila del material que ya lo tiene
    assert f'"activo": 0, "id": {pid}' in logged_client.get('/materiales').get_data(as_text=True)

    # Editar sin el dato del estado lo conserva; Estado: Activo lo reactiva
    _guardar(logged_client, id=pid, codigo=codigo)
    assert not _proveedor(wms, codigo)['activo']
    _guardar(logged_client, id=pid, codigo=codigo, activo='1')
    assert _proveedor(wms, codigo)['activo']
    _guardar(logged_client, id=pid, codigo=codigo, activo='0')
    assert not _proveedor(wms, codigo)['activo']


@requires_db
def test_importar_y_exportar_con_estado(logged_client, wms):
    import csv as modulo_csv
    activo, inactivo, sin_estado, mail_malo, largo = _codigo(), _codigo(), _codigo(), _codigo(), _codigo()
    contenido = '\n'.join([
        'codigo,razonsocial,email,activo',
        f'  {activo}  ,  Uno  ,a@b.com,1',
        f'{inactivo},Dos,,0',
        f'{sin_estado},Tres,,',
        f'{mail_malo},Cuatro,no-es-mail,1',
        f'{largo},{"x" * 201},,1',
        f'{activo},Repetido,,1',
    ])
    r = logged_client.post('/proveedores/importar', data={
        'archivo': (io.BytesIO(contenido.encode('utf-8')), 'proveedores.csv')}, content_type='multipart/form-data')
    resultado = r.get_json()
    assert resultado['insertados'] == 3 and resultado['omitidos'] == [activo]
    assert [(e['fila'], e['razon']) for e in resultado['errores']] == [
        (4, 'Email: "no-es-mail" no es una dirección válida.'),
        (5, 'Razón Social: admite hasta 200 caracteres.')]
    assert _proveedor(wms, activo)['razonsocial'] == 'Uno' and _proveedor(wms, activo)['activo']
    assert _proveedor(wms, sin_estado)['activo'] and not _proveedor(wms, inactivo)['activo']

    # La exportación trae los inactivos con su estado, y se puede volver a importar
    exportado = logged_client.get('/proveedores/exportar/csv').get_data(as_text=True)
    filas = {f['codigo']: f['activo'] for f in modulo_csv.DictReader(io.StringIO(exportado.lstrip('\ufeff')))}
    assert (filas[activo], filas[inactivo]) == ('1', '0')
    r = logged_client.post('/proveedores/importar', data={
        'archivo': (io.BytesIO(exportado.encode('utf-8')), 'proveedores.csv')}, content_type='multipart/form-data')
    assert r.get_json()['insertados'] == 0 and r.get_json()['errores'] == []


def test_el_filtro_datetime_del_panel_formatea_fechas():
    """El filtro 'datetime' había quedado asociado por error a la función del CUIT."""
    import datetime

    import admin
    filtro = admin.app.jinja_env.filters['datetime']
    assert filtro(datetime.datetime(2026, 1, 2, 3, 4)) == '02/01/2026 03:04'
    assert filtro(None) == '-'
