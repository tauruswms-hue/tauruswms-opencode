"""Regresiones de seguridad del panel admin: roles, tenant, sesión y permisos."""

import datetime
import uuid

import pytest

from modules.permisos_cache import (
    VERSION_CLAVE,
    incrementar_version_permisos,
    invalidar_permisos_cache,
    obtener_rutas_cached,
)
from modules.schema_generator import ROUTES_CONSULTA
from tests.conftest import requires_db


@pytest.fixture
def admin_conn():
    from modules.db_config import _get_admin_connection
    conn = _get_admin_connection()
    yield conn
    conn.close()


def _flashes(client):
    with client.session_transaction() as sesion:
        return [mensaje for _, mensaje in sesion.get('_flashes', [])]


def _id_usuario(admin_conn, username):
    cur = admin_conn.cursor()
    cur.execute("SELECT id, rol, activo FROM usuarios WHERE username = %s", (username,))
    return cur.fetchone()


@requires_db
def test_roles_reservados_no_se_crean(admin_logged_client, admin_conn):
    for rol in ('SUPERADMIN', 'ADMIN'):
        admin_logged_client.post('/admin/roles/guardar',
                                 data={'nombre': rol, 'descripcion': 'x', 'activo': '1'})
        assert any('reservado' in m for m in _flashes(admin_logged_client))

    cur = admin_conn.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM roles WHERE nombre = 'SUPERADMIN'")
    assert cur.fetchone()['n'] == 0


@requires_db
def test_rol_no_se_renombra_a_superadmin(admin_logged_client, admin_conn):
    nombre = 'ZZROL' + uuid.uuid4().hex[:6].upper()
    cur = admin_conn.cursor()
    cur.execute("INSERT INTO roles (nombre, activo) VALUES (%s, 1)", (nombre,))
    admin_conn.commit()
    cur.execute("SELECT id FROM roles WHERE nombre = %s", (nombre,))
    rol_id = cur.fetchone()['id']
    try:
        admin_logged_client.post('/admin/roles/guardar',
                                 data={'id': rol_id, 'nombre': 'SUPERADMIN', 'activo': '1'})
        assert any('reservado' in m for m in _flashes(admin_logged_client))
        cur.execute("SELECT nombre FROM roles WHERE id = %s", (rol_id,))
        assert cur.fetchone()['nombre'] == nombre
    finally:
        cur.execute("DELETE FROM roles WHERE id = %s", (rol_id,))
        admin_conn.commit()


@requires_db
def test_usuario_wms_no_acepta_rol_reservado(admin_logged_client, admin_conn, usuario_wms):
    usuario = _id_usuario(admin_conn, usuario_wms['username'])
    admin_logged_client.post('/admin/usuarios/guardar', data={
        'id': usuario['id'], 'tenant_id': usuario_wms['tenant_id'],
        'username': usuario_wms['username'], 'nombre': 'Cambio',
        'rol': 'SUPERADMIN', 'activo': '1',
    })
    assert any('no está disponible' in m for m in _flashes(admin_logged_client))
    assert _id_usuario(admin_conn, usuario_wms['username'])['rol'] == usuario['rol']


@requires_db
def test_usuario_legacy_con_rol_admin_puede_conservarlo(admin_logged_client, admin_conn, usuario_wms):
    usuario = _id_usuario(admin_conn, usuario_wms['username'])
    admin_logged_client.post('/admin/usuarios/guardar', data={
        'id': usuario['id'], 'tenant_id': usuario_wms['tenant_id'],
        'username': usuario_wms['username'], 'nombre': 'Nombre editado',
        'rol': 'ADMIN', 'activo': '1',
    })
    admin_conn.commit()  # refresca el snapshot de la transacción
    cur = admin_conn.cursor()
    cur.execute("SELECT nombre FROM usuarios WHERE id = %s", (usuario['id'],))
    assert cur.fetchone()['nombre'] == 'Nombre editado'


@requires_db
def test_usuario_no_se_desactiva_desde_otro_tenant(admin_logged_client, admin_conn, usuario_wms):
    codigo = 'ZZ' + uuid.uuid4().hex[:6].upper()
    cur = admin_conn.cursor()
    cur.execute("INSERT INTO tenants (codigo, nombre) VALUES (%s, %s)", (codigo, 'Otro tenant'))
    admin_conn.commit()
    cur.execute("SELECT id FROM tenants WHERE codigo = %s", (codigo,))
    otro_tenant = cur.fetchone()['id']
    from modules.admin import encode_id
    try:
        usuario = _id_usuario(admin_conn, usuario_wms['username'])
        admin_logged_client.post(
            f"/admin/usuarios/eliminar/{usuario['id']}/{encode_id(otro_tenant)}")
        assert _id_usuario(admin_conn, usuario_wms['username'])['activo'] == 1
    finally:
        cur.execute("DELETE FROM tenants WHERE id = %s", (otro_tenant,))
        admin_conn.commit()


@requires_db
def test_rol_desactivado_no_devuelve_permisos(admin_logged_client, admin_conn):
    nombre = 'ZZPERM' + uuid.uuid4().hex[:6].upper()
    cur = admin_conn.cursor()
    cur.execute("INSERT INTO roles (nombre, activo) VALUES (%s, 1)", (nombre,))
    cur.execute("INSERT INTO roles_rutas (rol, ruta) VALUES (%s, '/materiales')", (nombre,))
    admin_conn.commit()
    cur.execute("SELECT id FROM roles WHERE nombre = %s", (nombre,))
    rol_id = cur.fetchone()['id']
    try:
        assert '/materiales' in _rutas_del_rol(nombre)
        admin_logged_client.post(f'/admin/roles/eliminar/{rol_id}')
        assert _rutas_del_rol(nombre) == []
    finally:
        cur.execute("DELETE FROM roles_rutas WHERE rol = %s", (nombre,))
        cur.execute("DELETE FROM roles WHERE id = %s", (rol_id,))
        admin_conn.commit()


def _rutas_del_rol(rol):
    from app import obtener_rutas_por_rol
    return obtener_rutas_por_rol(rol)


@requires_db
def test_version_permisos_invalida_cache_entre_procesos(admin_conn):
    invalidar_permisos_cache()
    cur = admin_conn.cursor()
    cur.execute("SELECT valor FROM configuracion WHERE clave = %s", (VERSION_CLAVE,))
    fila = cur.fetchone()
    anterior = fila['valor'] if fila else '0'

    llamadas = []
    assert obtener_rutas_cached('ROL-CACHE', lambda: ['/a'], version=anterior) == ['/a']
    assert obtener_rutas_cached('ROL-CACHE', lambda: llamadas.append(1) or ['/a'], version=anterior) == ['/a']
    assert llamadas == []

    incrementar_version_permisos(admin_conn)
    admin_conn.commit()
    cur.execute("SELECT valor FROM configuracion WHERE clave = %s", (VERSION_CLAVE,))
    nueva = cur.fetchone()['valor']
    assert nueva != anterior
    assert obtener_rutas_cached('ROL-CACHE', lambda: ['/b'], version=nueva) == ['/b']
    invalidar_permisos_cache()


@requires_db
def test_sesion_panel_expira_por_inactividad(admin_logged_client, admin_conn, usuario_panel):
    cur = admin_conn.cursor()
    cur.execute("SELECT id FROM admin_usuarios WHERE username = %s", (usuario_panel['username'],))
    user_id = cur.fetchone()['id']
    inactivo = (datetime.datetime.now() - datetime.timedelta(hours=1)).isoformat()
    with admin_logged_client.session_transaction() as sesion:
        sesion['admin_user_id'] = user_id
        sesion['admin_username'] = usuario_panel['username']
        sesion['admin_rol'] = 'SUPERADMIN'
        sesion['admin_login_at'] = inactivo
    respuesta = admin_logged_client.get('/admin/tenants')
    assert respuesta.status_code == 302 and '/admin/login' in respuesta.headers['Location']
    assert any('inactividad' in m for m in _flashes(admin_logged_client))


@requires_db
def test_sesion_panel_se_cierra_si_usuario_se_da_de_baja(admin_logged_client, admin_conn, usuario_panel):
    cur = admin_conn.cursor()
    cur.execute("SELECT id FROM admin_usuarios WHERE username = %s", (usuario_panel['username'],))
    user_id = cur.fetchone()['id']
    cur.execute("UPDATE admin_usuarios SET activo = 0 WHERE id = %s", (user_id,))
    admin_conn.commit()
    respuesta = admin_logged_client.get('/admin/tenants')
    assert respuesta.status_code == 302 and '/admin/login' in respuesta.headers['Location']


@requires_db
def test_datos_de_usuario_no_van_en_onclick(admin_logged_client, admin_conn, usuario_wms):
    from modules.admin import encode_id
    username = "O'Brien';alert(1);//"
    cur = admin_conn.cursor()
    cur.execute("UPDATE usuarios SET username = %s WHERE username = %s",
                (username, usuario_wms['username']))
    admin_conn.commit()
    try:
        html = admin_logged_client.get(
            f"/admin/tenants/ver/{encode_id(usuario_wms['tenant_id'])}").get_data(as_text=True)
        assert 'onclick="editarUsuario' not in html
        assert 'data-username="O&#39;Brien&#39;;alert(1);//"' in html
    finally:
        cur.execute("UPDATE usuarios SET username = %s WHERE username = %s",
                    (usuario_wms['username'], username))
        admin_conn.commit()


def test_consulta_no_tiene_acceso_de_escritura_a_inventario():
    from flask import url_for

    from app import app as wms_app

    assert '/inventario/*' not in ROUTES_CONSULTA
    assert '/inventario/ver/*' in ROUTES_CONSULTA
    with wms_app.test_request_context('/'):
        assert url_for('inventario.detalle', id_inventario=7) == '/inventario/ver/7'

