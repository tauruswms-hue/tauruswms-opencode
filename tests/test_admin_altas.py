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
