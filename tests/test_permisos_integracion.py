"""Tests de integración de permisos por rol (Fase 2.5).

Requisito: MySQL con taurus_admin + taurus_wms. Crea un rol y usuario
temporales en taurus_admin (prefijo TEST-PERM-) y los elimina al final.
"""

import uuid

import pytest
from conftest import DB_OK, requires_db
from werkzeug.security import generate_password_hash

from app import _match_permiso, _ruta_en_catalogo
from modules.db_config import _get_admin_connection


# --------------------------------------------------------------------------
# Unit tests de la logica (sin DB)
# --------------------------------------------------------------------------
@pytest.mark.parametrize('permiso,path,esperado', [
    ('/materiales', '/materiales', True),
    ('/materiales', '/materiales/guardar', False),
    ('/inventario/*', '/inventario', True),
    ('/inventario/*', '/inventario/crear', True),
    ('/inventario/*', '/inventario/crear/1', True),
    ('/inventario/*', '/inventario_otro', False),
    ('/pedidos/buscar_*', '/pedidos/buscar_x', True),
    ('/pedidos/buscar_*', '/pedidos/listar', False),
    ('*', '/cualquier/cosa', True),
])
def test_match_permiso(permiso, path, esperado):
    assert _match_permiso(permiso, path, None) is esperado


def test_ruta_en_catalogo_materiales():
    assert _ruta_en_catalogo('/materiales')


def test_ruta_en_catalogo_no_catalogadas():
    assert not _ruta_en_catalogo('/login')
    assert not _ruta_en_catalogo('/acerca')


def test_rutas_publicas_no_requieren_permiso():
    """Las rutas fuera del catalogo son auth-only (no por rol)."""
    # '/clases-pedido' SI esta en el catalogo (grupo Clases de pedido)
    assert _ruta_en_catalogo('/clases-pedido')


@pytest.fixture(scope='module')
def rol_prueba():
    """Crea un rol temporal con rutas limitadas y un usuario con ese rol."""
    if not DB_OK:
        pytest.skip('MySQL no disponible')
    uid = uuid.uuid4().hex[:8]
    rol = f'TEST-PERM-{uid}'
    username = f'testperm{uid}'
    conn = _get_admin_connection()
    try:
        cur = conn.cursor()
        # rol con SOLO /materiales (y wildcard para /materiales/*)
        cur.execute("INSERT INTO roles (nombre, activo) VALUES (%s, 1)", (rol,))
        cur.execute("INSERT INTO roles_rutas (rol, ruta) VALUES (%s, %s)", (rol, '/materiales/*'))
        # usuario con ese rol, tenant = primer tenant activo
        cur.execute("SELECT id FROM tenants WHERE activo = 1 ORDER BY id LIMIT 1")
        tid = cur.fetchone()['id']
        cur.execute("""
            INSERT INTO usuarios (username, password_hash, nombre, rol, tenant_id, activo)
            VALUES (%s, %s, %s, %s, %s, 1)
        """, (username, generate_password_hash('Test@2024!'), 'Usuario test permisos',
              rol, tid))
        conn.commit()
        yield {'rol': rol, 'username': username, 'password': 'Test@2024!'}
    finally:
        cur = conn.cursor()
        cur.execute("DELETE FROM usuarios WHERE username = %s", (username,))
        cur.execute("DELETE FROM roles_rutas WHERE rol = %s", (rol,))
        cur.execute("DELETE FROM roles WHERE nombre = %s", (rol,))
        conn.commit()
        conn.close()


@pytest.mark.usefixtures('rol_prueba')
@requires_db
def test_login_rol_limited_accede_ruta_permitida(client, rol_prueba):
    resp = client.post('/login', data={
        'username': rol_prueba['username'], 'password': rol_prueba['password'],
    })
    assert resp.status_code in (302, 200)
    # /materiales esta habilitado (wildcard /materiales/*)
    resp2 = client.get('/materiales')
    assert resp2.status_code == 200


@pytest.mark.usefixtures('rol_prueba')
@requires_db
def test_login_rol_limited_bloqueado_en_ruta_sin_permiso(client, rol_prueba):
    client.post('/login', data={
        'username': rol_prueba['username'], 'password': rol_prueba['password'],
    })
    # /clases-pedido NO esta habilitado para este rol
    resp = client.get('/clases-pedido')
    # el middleware redirige a index con flash de permisos
    assert resp.status_code == 302
    assert '/clases-pedido' not in resp.headers.get('Location', '')


@requires_db
def test_superadmin_bypass(client, rol_prueba):
    """Un rol SUPERADMIN puede acceder a cualquier ruta catalogada."""
    from app import app as wms_app
    from app import verificar_permiso_ruta
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'x'
        sess['rol'] = 'SUPERADMIN'
        sess['rutas_permitidas'] = []
        sess['login_timestamp'] = __import__('time').time()
    with wms_app.test_request_context('/clases-pedido'):
        assert verificar_permiso_ruta('/clases-pedido', 'SUPERADMIN') is True


@requires_db
def test_acceso_global_wildcard(client, rol_prueba):
    """Rol con acceso '*' puede acceder a cualquier ruta catalogada."""
    from app import app as wms_app
    from app import verificar_permiso_ruta
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'x'
        sess['rol'] = 'CONSULTA'
        sess['rutas_permitidas'] = ['*']
        sess['login_timestamp'] = __import__('time').time()
    with wms_app.test_request_context('/clases-pedido'):
        assert verificar_permiso_ruta('/clases-pedido', 'CONSULTA') is True
