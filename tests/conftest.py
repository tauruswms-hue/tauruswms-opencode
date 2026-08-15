"""Fixtures compartidos para los tests de Taurus WMS.

Se importan las apps reales (app.py / admin.py). Para tests que no tocan la
BD se desactiva CSRF y rate limiting; los tests de integración que requieren
MySQL se marcan con `requires_db` (salto automático si no hay conexión).
"""

import os
import sys
import uuid

import pytest
from werkzeug.security import generate_password_hash

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('APP_ENV', 'development')

import admin as admin_app_module
import app as wms_app_module


# --------------------------------------------------------------------------
# Disponibilidad de la BD (para tests de integración)
# --------------------------------------------------------------------------
def _mysql_disponible():
    try:
        from modules.db_config import _get_admin_connection
        conn = _get_admin_connection()
        conn.close()
        return True
    except Exception:
        return False


DB_OK = _mysql_disponible()

requires_db = pytest.mark.skipif(
    not DB_OK,
    reason='MySQL no disponible: se omiten tests de integración',
)


@pytest.fixture(autouse=True)
def _desactivar_limiter_y_csrf():
    """Por defecto: sin rate limiting y sin CSRF para poder testear flujos.

    flask-limiter fija `limiter.enabled` al inicializarse (init_app), así que
    cambiar RATELIMIT_ENABLED en config después no surte efecto: se toca el
    atributo directamente. Los tests de rate-limiting lo re-habilitan y usan
    reset() para partir de cero.
    """
    wms_app_module.app.config['WTF_CSRF_ENABLED'] = False
    admin_app_module.app.config['WTF_CSRF_ENABLED'] = False
    if getattr(wms_app_module.limiter, 'initialized', False):
        wms_app_module.limiter.enabled = False
    if getattr(admin_app_module.admin_limiter, 'initialized', False):
        admin_app_module.admin_limiter.enabled = False
    yield


@pytest.fixture
def client():
    wms_app_module.app.config.update(TESTING=True)
    with wms_app_module.app.test_client() as c:
        yield c


@pytest.fixture
def admin_client():
    admin_app_module.app.config.update(TESTING=True)
    with admin_app_module.app.test_client() as c:
        yield c


@pytest.fixture
def usuario_wms():
    """Usuario WMS temporal en taurus_admin (credenciales propias, no seed).

    Se crea con rol ADMIN en el primer tenant activo y se elimina al final,
    de modo que los tests no dependen de los passwords de los seeds.
    """
    if not DB_OK:
        pytest.skip('MySQL no disponible')
    from modules.db_config import _get_admin_connection
    username = 'testwms' + uuid.uuid4().hex[:8]
    conn = _get_admin_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM tenants WHERE activo = 1 ORDER BY id LIMIT 1")
        tid = cur.fetchone()['id']
        cur.execute("""
            INSERT INTO usuarios (username, password_hash, nombre, rol, tenant_id, activo)
            VALUES (%s, %s, %s, 'ADMIN', %s, 1)
        """, (username, generate_password_hash('Test@2024!'),
              'Usuario test conftest', tid))
        conn.commit()
        yield {'username': username, 'password': 'Test@2024!', 'tenant_id': tid}
    finally:
        cur = conn.cursor()
        cur.execute("DELETE FROM usuarios WHERE username = %s", (username,))
        conn.commit()
        conn.close()


@pytest.fixture
def usuario_panel():
    """Usuario del panel admin temporal (admin_usuarios, credenciales propias).

    Se crea con rol SUPERADMIN y se elimina al final, sin depender de los
    passwords de los seeds.
    """
    if not DB_OK:
        pytest.skip('MySQL no disponible')
    from modules.db_config import _get_admin_connection
    username = 'testpanel' + uuid.uuid4().hex[:8]
    conn = _get_admin_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO admin_usuarios (username, password_hash, nombre, rol, activo)
            VALUES (%s, %s, %s, 'SUPERADMIN', 1)
        """, (username, generate_password_hash('Test@2024!'),
              'Usuario panel test'))
        conn.commit()
        yield {'username': username, 'password': 'Test@2024!'}
    finally:
        cur = conn.cursor()
        cur.execute("DELETE FROM admin_usuarios WHERE username = %s", (username,))
        conn.commit()
        conn.close()


@pytest.fixture
def logged_client(client, usuario_wms):
    """Cliente WMS autenticado con un usuario temporal propio (no seed)."""
    resp = client.post('/login', data={
        'username': usuario_wms['username'], 'password': usuario_wms['password'],
    })
    assert resp.status_code in (302, 200)
    return client


@pytest.fixture
def admin_logged_client(admin_client, usuario_panel):
    """Cliente del panel admin autenticado con un usuario temporal propio."""
    resp = admin_client.post('/admin/login', data={
        'username': usuario_panel['username'], 'password': usuario_panel['password'],
    })
    assert resp.status_code in (302, 200)
    return admin_client
