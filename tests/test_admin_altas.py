"""Altas desde el panel admin: código de tenant y política de contraseñas."""

import uuid

import pytest

from tests.conftest import requires_db


@pytest.fixture
def admin_conn():
    from modules.db_config import _get_admin_connection
    conn = _get_admin_connection()
    yield conn
    conn.close()


def _flashes(client):
    with client.session_transaction() as s:
        return [m for _, m in s.get('_flashes', [])]


@requires_db
def test_alta_tenant_guarda_codigo_en_mayusculas(admin_logged_client, admin_conn):
    codigo = 'zz' + uuid.uuid4().hex[:6]
    try:
        admin_logged_client.post('/admin/tenants/guardar', data={'codigo': codigo, 'nombre': 'Tenant test'})
        cur = admin_conn.cursor()
        cur.execute("SELECT codigo FROM tenants WHERE codigo = %s", (codigo.upper(),))
        assert cur.fetchone(), _flashes(admin_logged_client)

        # Mismo código otra vez: mensaje claro, sin segundo registro
        admin_logged_client.post('/admin/tenants/guardar', data={'codigo': codigo, 'nombre': 'Otro'})
        assert any('Ya existe un tenant' in m for m in _flashes(admin_logged_client))
        cur.execute("SELECT COUNT(*) AS n FROM tenants WHERE codigo = %s", (codigo.upper(),))
        assert cur.fetchone()['n'] == 1
    finally:
        cur = admin_conn.cursor()
        cur.execute("DELETE FROM tenants WHERE codigo = %s", (codigo.upper(),))
        admin_conn.commit()


@pytest.mark.parametrize('valor, esperado', [
    ('20-12345678-9', '20-12345678-9'),
    (' 20-12345678-9 ', '20-12345678-9'),
    ('20123456789', '20-12345678-9'),
    ('', ''),
    (None, ''),
    ('20-1234567-9', None),
    ('2012345678', None),
    ('20.12345678.9', None),
    ('AA-12345678-9', None),
])
def test_normalizar_cuit(valor, esperado):
    from modules.admin import normalizar_cuit
    assert normalizar_cuit(valor) == esperado


@requires_db
def test_alta_tenant_valida_y_formatea_cuit(admin_logged_client, admin_conn):
    codigo = ('zz' + uuid.uuid4().hex[:6]).upper()
    cur = admin_conn.cursor()
    try:
        admin_logged_client.post('/admin/tenants/guardar',
                                 data={'codigo': codigo, 'nombre': 'Tenant test', 'cuit': '20-123-9'})
        assert any('CUIT inválido' in m for m in _flashes(admin_logged_client))
        admin_conn.commit()  # refresca el snapshot de la transacción
        cur.execute("SELECT COUNT(*) AS n FROM tenants WHERE codigo = %s", (codigo,))
        assert cur.fetchone()['n'] == 0

        admin_logged_client.post('/admin/tenants/guardar',
                                 data={'codigo': codigo, 'nombre': 'Tenant test', 'cuit': '20123456789'})
        admin_conn.commit()
        cur.execute("SELECT cuit FROM tenants WHERE codigo = %s", (codigo,))
        assert cur.fetchone()['cuit'] == '20-12345678-9', _flashes(admin_logged_client)
    finally:
        cur.execute("DELETE FROM tenants WHERE codigo = %s", (codigo,))
        admin_conn.commit()


@requires_db
@pytest.mark.parametrize('codigo', ['', 'con espacio', 'x' * 21])
def test_alta_tenant_rechaza_codigo_invalido(admin_logged_client, admin_conn, codigo):
    cur = admin_conn.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM tenants")
    antes = cur.fetchone()['n']
    admin_logged_client.post('/admin/tenants/guardar', data={'codigo': codigo, 'nombre': 'Tenant test'})
    assert any('Código inválido' in m for m in _flashes(admin_logged_client))
    admin_conn.commit()  # refresca el snapshot de la transacción
    cur.execute("SELECT COUNT(*) AS n FROM tenants")
    assert cur.fetchone()['n'] == antes


@requires_db
def test_alta_usuario_wms_rechaza_password_corta(admin_logged_client, admin_conn):
    username = 'zzcorta' + uuid.uuid4().hex[:6]
    cur = admin_conn.cursor()
    cur.execute("SELECT id FROM tenants WHERE activo = 1 ORDER BY id LIMIT 1")
    tid = cur.fetchone()['id']
    try:
        admin_logged_client.post('/admin/usuarios/guardar', data={
            'username': username, 'password': 'corta', 'nombre': 'x', 'rol': 'OPERADOR', 'tenant_id': tid,
        })
        assert any('al menos' in m for m in _flashes(admin_logged_client))
        cur.execute("SELECT 1 FROM usuarios WHERE username = %s", (username,))
        assert cur.fetchone() is None
    finally:
        cur.execute("DELETE FROM usuarios WHERE username = %s", (username,))
        admin_conn.commit()


@requires_db
def test_listado_usuarios_muestra_codigo_y_nombre_del_tenant(admin_logged_client, admin_conn, usuario_wms):
    cur = admin_conn.cursor()
    cur.execute("SELECT codigo, nombre FROM tenants WHERE id = %s", (usuario_wms['tenant_id'],))
    tenant = cur.fetchone()
    html = admin_logged_client.get(f"/admin/usuarios?tenant_id={usuario_wms['tenant_id']}").get_data(as_text=True)
    assert usuario_wms['username'] in html
    assert f"<code>{tenant['codigo']}</code> {tenant['nombre']}" in html


@pytest.fixture
def config_temporal(admin_conn):
    """Crea claves en `configuracion` y las borra al final."""
    claves = []

    def crear(clave, valor):
        cur = admin_conn.cursor()
        cur.execute("INSERT INTO configuracion (clave, valor, descripcion) VALUES (%s, %s, 'test')", (clave, valor))
        admin_conn.commit()
        claves.append(clave)
        cur.execute("SELECT id FROM configuracion WHERE clave = %s", (clave,))
        return cur.fetchone()['id']

    yield crear
    cur = admin_conn.cursor()
    for clave in claves:
        cur.execute("DELETE FROM configuracion WHERE clave = %s", (clave,))
    admin_conn.commit()


def _valor_config(admin_conn, config_id):
    admin_conn.commit()  # refresca el snapshot de la transacción
    cur = admin_conn.cursor()
    cur.execute("SELECT clave, valor FROM configuracion WHERE id = %s", (config_id,))
    return cur.fetchone()


@requires_db
def test_configuracion_no_envia_valores_sensibles_al_navegador(admin_logged_client, admin_conn, config_temporal):
    sufijo = uuid.uuid4().hex[:6].upper()
    secreto = 'secreto-' + sufijo
    config_id = config_temporal(f'ZZ_PASSWORD_{sufijo}', secreto)
    html = admin_logged_client.get('/admin/configuracion').get_data(as_text=True)
    assert f'ZZ_PASSWORD_{sufijo}' in html
    assert secreto not in html

    # Editar con el valor en blanco conserva el actual; con valor, lo reemplaza
    admin_logged_client.post('/admin/configuracion/guardar', data={'id': config_id, 'valor': '', 'descripcion': 'x'})
    assert _valor_config(admin_conn, config_id)['valor'] == secreto
    admin_logged_client.post('/admin/configuracion/guardar', data={'id': config_id, 'valor': 'nuevo', 'descripcion': 'x'})
    assert _valor_config(admin_conn, config_id)['valor'] == 'nuevo'


@requires_db
def test_configuracion_escapa_valores_y_no_cambia_la_clave(admin_logged_client, admin_conn, config_temporal):
    clave = 'ZZ_COMILLA_' + uuid.uuid4().hex[:6].upper()
    valor = "O'Brien \"x\" <b>"
    config_id = config_temporal(clave, valor)
    html = admin_logged_client.get('/admin/configuracion').get_data(as_text=True)
    assert 'data-valor="O&#39;Brien &#34;x&#34; &lt;b&gt;"' in html
    assert "editarConfig(this)" in html and "O'Brien" not in html

    admin_logged_client.post('/admin/configuracion/guardar',
                             data={'id': config_id, 'clave': 'OTRA_CLAVE', 'valor': 'v', 'descripcion': ''})
    assert _valor_config(admin_conn, config_id) == {'clave': clave, 'valor': 'v'}


@pytest.mark.parametrize('modulo, detalle, esperado', [
    ('tenants', '{"id": 1}', [('Tenant', 'T1 — Uno')]),
    ('tenants', '{"id": 1, "action": "activar"}', [('Tenant', 'T1 — Uno'), ('Operación', 'Reactivación')]),
    ('tenants', '{"id": 1, "nombre": "Nuevo"}', [('Nombre', 'Nuevo')]),
    ('usuarios', '{"id": 99}', [('Usuario', 'ID 99')]),
    ('usuarios', '{"username": "ana", "tenant_id": 1}', [('Usuario', 'ana'), ('Tenant', 'T1 — Uno')]),
    ('roles_rutas', '{"rol": "ADMIN", "rutas": ["*"]}', [('Rol', 'ADMIN'), ('Rutas', 'Acceso total')]),
    ('roles_rutas', '{"rol": "X", "rutas": ["/a", "/b"]}', [('Rol', 'X'), ('Rutas', '/a, /b')]),
    ('intercambio', '{"procesados": 3, "errores": 0}', [('Aplicados', 3), ('Con error', 0)]),
    ('auth', 'texto suelto', [('Detalle', 'texto suelto')]),
    ('auth', None, []),
])
def test_detalle_audit_legible(modulo, detalle, esperado):
    from modules.admin import _detalle_audit
    assert _detalle_audit(modulo, detalle, {'tenants': {1: 'T1 — Uno'}}) == esperado


@requires_db
def test_auditoria_muestra_textos_y_oculta_consultas(admin_logged_client, admin_conn):
    # Un ingreso fallido reconocible y una consulta de pantalla
    intento = 'zzaudit' + uuid.uuid4().hex[:6]
    admin_logged_client.application.test_client().post('/admin/login', data={'username': intento, 'password': 'x'})
    admin_logged_client.get('/admin/tenants')

    html = admin_logged_client.get('/admin/audit').get_data(as_text=True)
    assert 'Ingreso fallido' in html and intento in html
    assert 'LOGIN_FAILED</span>' not in html and '{&#34;username&#34;' not in html
    # La insignia aparece una sola vez: en la ayuda, no en la tabla
    assert html.count('Consulta de pantalla</span>') == 1
    assert 'sin contar las consultas de pantalla' in html
    # Ayuda de la pantalla: explica cada acción y cada sección
    from modules import admin as panel
    assert 'id="ayudaAuditoria"' in html
    assert set(panel.AUDIT_AYUDA_ACCIONES) == set(panel.AUDIT_ACCIONES)
    assert set(panel.AUDIT_AYUDA_MODULOS) == set(panel.AUDIT_MODULOS)
    assert 'Intento de ingreso con usuario o contraseña incorrectos' in html

    html = admin_logged_client.get('/admin/audit?consultas=1').get_data(as_text=True)
    assert html.count('Consulta de pantalla</span>') > 1

    # Un solo día es un rango válido (antes se forzaba una semana)
    hoy = __import__('datetime').date.today()
    html = admin_logged_client.get(f'/admin/audit?desde={hoy}&hasta={hoy}').get_data(as_text=True)
    assert f"del <strong>{hoy:%d/%m/%Y}</strong> al <strong>{hoy:%d/%m/%Y}</strong>" in html

    # El intento fallido no tiene usuario: el fixture no lo limpia
    cur = admin_conn.cursor()
    cur.execute("DELETE FROM audit_logs WHERE accion = 'LOGIN_FAILED' AND detalle LIKE %s", (f'%{intento}%',))
    admin_conn.commit()
