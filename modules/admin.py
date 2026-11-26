import base64
import binascii
import datetime
import hashlib
import json
import logging
import os
import re
import secrets
from functools import wraps

from dotenv import load_dotenv
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash, generate_password_hash

from modules.api import _hash_token
from modules.cuit import CUIT_INVALIDO, normalizar_cuit
from modules.db_config import (
    ConexionesError,
    _get_admin_connection,
    get_conexion,
    get_intercambio_connection,
)
from modules.intercambio import (
    MODULOS,
    procesar_intercambio,
    reintentar_todo,
)
from modules.passwords import validar_password
from modules.permisos_cache import (
    VERSION_CLAVE,
    incrementar_version_permisos,
    invalidar_permisos_cache,
)
from modules.schema_generator import ROUTE_CATALOG
from modules.sql_dialect import date as date_func
from modules.sql_dialect import execute_insert, is_duplicate_key_error, limit_sql

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

admin_limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")

env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=env_path)

SECRET_SALT = os.getenv('SECRET_SALT', 'taurus-wms-salt-2024')

# El WMS da acceso total al rol con este nombre (app.py), así que no se puede
# crear ni renombrar un rol a él desde el panel. ADMIN ya tiene '*' por seed.
ROLES_RESERVADOS = ('SUPERADMIN', 'ADMIN')

# Inactividad del panel: se cierra aunque la cookie siga vigente (8 h).
PANEL_IDLE_TIMEOUT_SECONDS = int(os.getenv('PANEL_IDLE_TIMEOUT_SECONDS', '900'))


def encode_id(tenant_id):
    """Ofusca el ID con base64; NO es un control de acceso (ver superadmin_required)."""
    if tenant_id is None:
        return ''
    data = f"{int(tenant_id)}:{SECRET_SALT}"
    return base64.urlsafe_b64encode(data.encode()).decode()


def decode_id(encoded):
    """Decodifica el ID"""
    if not encoded:
        return None
    try:
        data = base64.urlsafe_b64decode(encoded.encode()).decode()
        tenant_id, salt = data.split(':')
        if salt != SECRET_SALT:
            return None
        return int(tenant_id)
    except (ValueError, binascii.Error, UnicodeDecodeError):
        return None


def encode_codigo(codigo):
    """Encripta el código del tenant"""
    if not codigo:
        return None
    hash_obj = hashlib.sha256(f"{codigo}:{SECRET_SALT}".encode()).hexdigest()
    return hash_obj[:16]


def decode_codigo(encoded_codigo):
    """Retorna el código encriptado tal cual (para display)"""
    return encoded_codigo


@admin_bp.app_template_filter('datetime')
def format_datetime(value):
    if value is None:
        return '-'
    if isinstance(value, str):
        try:
            value = datetime.datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return value
    return value.strftime('%d/%m/%Y %H:%M')


@admin_bp.app_template_filter('encode_id')
def encode_id_filter(tenant_id):
    return encode_id(tenant_id)





def log_audit(accion, modulo, detalle=None):
    """Registra acciones en el log de auditoría"""
    try:
        conn = _get_admin_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_logs 
            (usuario_id, usuario_nombre, accion, modulo, detalle, ip_address, user_agent)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            session.get('admin_user_id'),
            session.get('admin_nombre'),
            accion,
            modulo,
            json.dumps(detalle) if detalle else None,
            request.remote_addr,
            request.user_agent.string[:255] if request.user_agent else None
        ))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logging.error("Error al registrar auditoría: %s", e)


def _sesion_panel_expirada():
    ingresado = session.get('admin_login_at')
    if not ingresado:
        return True
    try:
        inactivo = (datetime.datetime.now() - datetime.datetime.fromisoformat(ingresado)).total_seconds()
    except (TypeError, ValueError):
        return True
    return inactivo > PANEL_IDLE_TIMEOUT_SECONDS or inactivo < -60


def _validar_sesion_panel():
    """Cierra la sesión si expiró por inactividad o el usuario cambió/dejó de estar activo."""
    if 'admin_user_id' not in session:
        return redirect(url_for('admin.login'))
    if _sesion_panel_expirada():
        session.clear()
        flash('Sesión cerrada por inactividad', 'warning')
        return redirect(url_for('admin.login'))

    conn = _get_admin_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT activo, rol FROM admin_usuarios WHERE id = %s", (session['admin_user_id'],))
        usuario = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()
    if not usuario or not usuario['activo'] or usuario['rol'] != session.get('admin_rol'):
        session.clear()
        flash('Su usuario del panel fue dado de baja o cambió de rol', 'warning')
        return redirect(url_for('admin.login'))
    return None


def _roles_asignables(cursor):
    """Roles habilitados y asignables desde el panel (nunca los reservados del WMS)."""
    cursor.execute("SELECT nombre FROM roles WHERE activo")
    return {fila['nombre'] for fila in cursor.fetchall() if fila['nombre'] not in ROLES_RESERVADOS}


def _rutas_catalogadas():
    return {ruta for grupo in ROUTE_CATALOG for ruta in grupo['rutas']} | {'*'}


def _invalidar_permisos(conn):
    """Versión global (otros procesos) + caché local (este proceso)."""
    incrementar_version_permisos(conn)
    invalidar_permisos_cache()


def superadmin_required(f):
    """Todas las secciones del panel son globales: solo SUPERADMIN puede verlas o cambiarlas."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        respuesta = _validar_sesion_panel()
        if respuesta:
            return respuesta
        if session.get('admin_rol') != 'SUPERADMIN':
            abort(403)
        session['admin_login_at'] = datetime.datetime.now().isoformat()
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/login', methods=['GET', 'POST'])
@admin_limiter.limit("5 per 15 minutes", methods=['POST'])
def login():
    if 'admin_user_id' in session:
        if _sesion_panel_expirada():
            session.clear()
        else:
            return redirect(url_for('admin.tenants'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password')
        
        if not username or not password:
            flash('Debe ingresar usuario y contraseña', 'error')
            return render_template('admin_login.html')
        
        try:
            conn = _get_admin_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, username, password_hash, nombre, rol
                FROM admin_usuarios 
                WHERE username = %s AND activo = 1
            """, (username,))
            usuario = cursor.fetchone()
            valido = bool(usuario and check_password_hash(usuario['password_hash'], password))

            if valido:
                cursor.execute("""
                    UPDATE admin_usuarios SET ultimo_acceso = %s WHERE id = %s
                """, (datetime.datetime.now(), usuario['id']))
                conn.commit()

            cursor.close()
            conn.close()

            if valido:
                session['admin_user_id'] = usuario['id']
                session['admin_username'] = usuario['username']
                session['admin_nombre'] = usuario['nombre']
                session['admin_rol'] = usuario['rol']
                session['admin_login_at'] = datetime.datetime.now().isoformat()
                session.permanent = True
                
                log_audit('LOGIN', 'auth', {'username': username})
                flash(f'Bienvenido, {usuario["nombre"]}', 'success')
                return redirect(url_for('admin.tenants'))
            else:
                flash('Credenciales inválidas', 'error')
                log_audit('LOGIN_FAILED', 'auth', {'username': username})
                
        except Exception:
            logging.exception('Error al iniciar sesión en el panel')
            flash('No se pudo iniciar sesión. Intente nuevamente.', 'error')

    return render_template('admin_login.html')


@admin_bp.route('/logout')
def logout():
    if 'admin_user_id' in session:
        log_audit('LOGOUT', 'auth', {'username': session.get('admin_username')})
    
    session.pop('admin_user_id', None)
    session.pop('admin_username', None)
    session.pop('admin_nombre', None)
    session.pop('admin_rol', None)
    session.pop('admin_login_at', None)

    flash('Sesión admin cerrada', 'info')
    return redirect(url_for('admin.login'))


@admin_bp.route('/')
@superadmin_required
def index():
    return redirect(url_for('admin.tenants'))


@admin_bp.route('/tenants')
@superadmin_required
def tenants():
    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.*, 
                   (SELECT COUNT(*) FROM usuarios u WHERE u.tenant_id = t.id) as total_usuarios
            FROM tenants t 
            ORDER BY t.nombre
        """)
        tenants = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()
    
    log_audit('ACCESS', 'tenants')
    return render_template('admin_tenants.html', tenants=tenants)


@admin_bp.route('/tenants/ver/<encoded_id>')
@superadmin_required
def tenants_ver(encoded_id):
    tenant_id = decode_id(encoded_id)
    if tenant_id is None:
        flash('ID inválido', 'danger')
        return redirect(url_for('admin.tenants'))
    
    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tenants WHERE id = %s", (tenant_id,))
        tenant = cursor.fetchone()
        
        cursor.execute("""
            SELECT id, username, nombre, email, rol, activo, ultimo_acceso, created_at 
            FROM usuarios 
            WHERE tenant_id = %s 
            ORDER BY nombre
        """, (tenant_id,))
        usuarios = cursor.fetchall()

        cursor.execute("SELECT nombre FROM roles WHERE activo = 1 ORDER BY nombre")
        roles = cursor.fetchall()

        cursor.close()
    finally:
        conn.close()
    
    log_audit('ACCESS', 'tenants', {'id': tenant_id})
    return render_template('admin_tenant_detail.html', tenant=tenant, usuarios=usuarios, roles=roles)


@admin_bp.route('/tenants/guardar', methods=['POST'])
@superadmin_required
def tenants_guardar():
    d = request.form
    tenant_id = d.get('id')
    nombre = d.get('nombre')
    # codigo solo se carga en el alta: Intercambio lo usa como clave (tenant_codigo)
    codigo = (d.get('codigo') or '').strip().upper()
    if not tenant_id and not re.fullmatch(r'[A-Z0-9_-]{1,20}', codigo):
        flash('Código inválido: 1 a 20 caracteres entre letras, números, guion y guion bajo.', 'danger')
        return redirect(url_for('admin.tenants'))
    cuit = normalizar_cuit(d.get('cuit'))
    if cuit is None:
        flash(CUIT_INVALIDO, 'danger')
        return redirect(url_for('admin.tenants'))

    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        if tenant_id:
            cursor.execute("""
                UPDATE tenants SET 
                    nombre = %s, razon_social = %s, 
                    cuit = %s, direccion = %s, telefono = %s, email = %s, activo = %s
                WHERE id = %s
            """, (
                nombre, d.get('razon_social'),
                cuit, d.get('direccion'), d.get('telefono'), d.get('email'),
                1 if d.get('activo') else 0, tenant_id
            ))
            msg = 'Tenant actualizado correctamente'
            accion = 'UPDATE'
            datos_auditoria = {'id': tenant_id, 'nombre': nombre}
        else:
            tenant_id = execute_insert(cursor, """
                INSERT INTO tenants (codigo, nombre, razon_social, cuit, direccion, telefono, email)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                codigo, nombre, d.get('razon_social'),
                cuit, d.get('direccion'), d.get('telefono'), d.get('email')
            ))
            msg = 'Tenant creado correctamente'
            accion = 'CREATE'
            datos_auditoria = {'id': tenant_id, 'codigo': codigo, 'nombre': nombre}

        conn.commit()
        log_audit(accion, 'tenants', datos_auditoria)
        flash(msg, 'success')
        cursor.close()
    except Exception as e:
        conn.rollback()
        if is_duplicate_key_error(e):
            flash(f"Ya existe un tenant con el código '{codigo}'.", 'danger')
        else:
            logging.exception('Error al guardar tenant del panel')
            flash('No se pudo guardar el tenant. Intente nuevamente.', 'danger')
        log_audit('ERROR', 'tenants', {'accion': 'guardar'})
    finally:
        conn.close()
    
    return redirect(url_for('admin.tenants'))


@admin_bp.route('/tenants/eliminar/<encoded_id>', methods=['POST'])
@superadmin_required
def tenants_eliminar(encoded_id):
    tenant_id = decode_id(encoded_id)
    if tenant_id is None:
        flash('ID inválido', 'danger')
        return redirect(url_for('admin.tenants'))
    
    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE tenants SET activo = FALSE WHERE id = %s", (tenant_id,))
        conn.commit()
        log_audit('DELETE', 'tenants', {'id': tenant_id})
        flash('Tenant desactivado.', 'success')
        cursor.close()
    finally:
        conn.close()
    
    return redirect(url_for('admin.tenants'))


@admin_bp.route('/tenants/activar/<encoded_id>', methods=['POST'])
@superadmin_required
def tenants_activar(encoded_id):
    tenant_id = decode_id(encoded_id)
    if tenant_id is None:
        flash('ID inválido', 'danger')
        return redirect(url_for('admin.tenants'))
    
    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE tenants SET activo = TRUE WHERE id = %s", (tenant_id,))
        conn.commit()
        log_audit('UPDATE', 'tenants', {'id': tenant_id, 'action': 'activar'})
        flash('Tenant activado.', 'success')
        cursor.close()
    finally:
        conn.close()
    
    return redirect(url_for('admin.tenants'))


@admin_bp.route('/usuarios/guardar', methods=['POST'])
@superadmin_required
def usuarios_guardar():
    d = request.form
    usuario_id = d.get('id')
    tenant_id = d.get('tenant_id')
    destino = url_for('admin.tenants_ver', encoded_id=encode_id(tenant_id))
    rol = (d.get('rol') or '').strip()

    # Alta: contraseña obligatoria. Edición: solo se valida si se cambia.
    if d.get('password') or not usuario_id:
        error_password = validar_password(d.get('password'))
        if error_password:
            flash(error_password, 'danger')
            return redirect(destino)

    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        actual = None
        if usuario_id:
            cursor.execute("SELECT id, rol FROM usuarios WHERE id = %s AND tenant_id = %s",
                           (usuario_id, tenant_id))
            actual = cursor.fetchone()
            if not actual:
                flash('Usuario no encontrado en este tenant.', 'danger')
                cursor.close()
                return redirect(destino)

        roles_validos = _roles_asignables(cursor)
        # Un usuario legacy con rol ADMIN puede conservarlo al editarse; lo que
        # se prohíbe es asignarlo (o SUPERADMIN) a un usuario nuevo.
        conserva_actual = bool(actual and rol == actual['rol'] and rol != 'SUPERADMIN')
        if rol not in roles_validos and not conserva_actual:
            flash('El rol indicado no está disponible. Elija un rol activo.', 'danger')
            cursor.close()
            return redirect(destino)

        if usuario_id:
            params = [d.get('nombre'), d.get('email'), rol, 1 if d.get('activo') else 0]
            if d.get('password'):
                params.append(generate_password_hash(d.get('password')))
                sentencia = """
                    UPDATE usuarios SET nombre = %s, email = %s, rol = %s, activo = %s,
                        password_hash = %s
                    WHERE id = %s AND tenant_id = %s
                """
            else:
                sentencia = """
                    UPDATE usuarios SET nombre = %s, email = %s, rol = %s, activo = %s
                    WHERE id = %s AND tenant_id = %s
                """
            params.extend([usuario_id, tenant_id])
            cursor.execute(sentencia, params)
            msg = 'Usuario actualizado correctamente'
            accion = 'UPDATE'
        else:
            cursor.execute("""
                INSERT INTO usuarios (username, password_hash, nombre, email, rol, tenant_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                d.get('username'),
                generate_password_hash(d.get('password')),
                d.get('nombre'),
                d.get('email'),
                rol,
                tenant_id
            ))
            msg = 'Usuario creado correctamente'
            accion = 'CREATE'

        conn.commit()
        log_audit(accion, 'usuarios', {'id': usuario_id or None,
                                      'username': d.get('username'), 'tenant_id': tenant_id,
                                      'rol': rol})
        flash(msg, 'success')
        cursor.close()
    except Exception as e:
        conn.rollback()
        if is_duplicate_key_error(e):
            flash('El nombre de usuario ya existe. Elija otro.', 'danger')
        else:
            logging.exception('Error al guardar usuario del panel')
            flash('No se pudo guardar el usuario. Intente nuevamente.', 'danger')
        log_audit('ERROR', 'usuarios', {'accion': 'guardar'})
    finally:
        conn.close()

    return redirect(destino)


@admin_bp.route('/usuarios/eliminar/<int:usuario_id>/<encoded_tenant_id>', methods=['POST'])
@superadmin_required
def usuarios_eliminar(usuario_id, encoded_tenant_id):
    tenant_id = decode_id(encoded_tenant_id)
    if tenant_id is None:
        flash('ID inválido', 'danger')
        return redirect(url_for('admin.tenants'))
    
    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE usuarios SET activo = FALSE WHERE id = %s AND tenant_id = %s",
                       (usuario_id, tenant_id))
        conn.commit()
        filas_afectadas = cursor.rowcount
        cursor.close()

        if filas_afectadas > 0:
            log_audit('DELETE', 'usuarios', {'id': usuario_id, 'tenant_id': tenant_id})
            flash('Usuario desactivado.', 'success')
        else:
            flash('Usuario no encontrado para este tenant.', 'warning')
    except Exception:
        conn.rollback()
        logging.exception('Error al desactivar usuario del panel')
        flash('No se pudo desactivar el usuario. Intente nuevamente.', 'danger')
        log_audit('ERROR', 'usuarios', {'accion': 'eliminar'})
    finally:
        conn.close()
    
    return redirect(url_for('admin.tenants_ver', encoded_id=encode_id(tenant_id)))


@admin_bp.route('/usuarios/borrar/<int:usuario_id>/<encoded_tenant_id>', methods=['POST'])
@superadmin_required
def usuarios_borrar(usuario_id, encoded_tenant_id):
    """Elimina el usuario definitivamente de la BD (solo dentro de su tenant)."""
    tenant_id = decode_id(encoded_tenant_id)
    if tenant_id is None:
        flash('ID inválido', 'danger')
        return redirect(url_for('admin.tenants'))

    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM usuarios WHERE id = %s AND tenant_id = %s", (usuario_id, tenant_id))
        usuario = cursor.fetchone()
        cursor.execute(
            "DELETE FROM usuarios WHERE id = %s AND tenant_id = %s",
            (usuario_id, tenant_id)
        )
        conn.commit()
        filas_afectadas = cursor.rowcount
        cursor.close()

        if filas_afectadas > 0:
            log_audit('DELETE', 'usuarios', {
                'id': usuario_id, 'username': usuario['username'] if usuario else None,
                'tenant_id': tenant_id, 'action': 'borrado_fisico',
            })
            flash('Usuario eliminado definitivamente de la base de datos.', 'success')
        else:
            flash('Usuario no encontrado para este tenant.', 'warning')
    except Exception:
        conn.rollback()
        logging.exception('Error al borrar usuario del panel')
        flash('No se pudo eliminar el usuario. Intente nuevamente.', 'danger')
        log_audit('ERROR', 'usuarios', {'accion': 'borrar'})
    finally:
        conn.close()

    return redirect(url_for('admin.tenants_ver', encoded_id=encode_id(tenant_id)))


@admin_bp.route('/usuarios/activar/<int:usuario_id>/<encoded_tenant_id>', methods=['POST'])
@superadmin_required
def usuarios_activar(usuario_id, encoded_tenant_id):
    tenant_id = decode_id(encoded_tenant_id)
    if tenant_id is None:
        flash('ID inválido', 'danger')
        return redirect(url_for('admin.tenants'))
    
    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE usuarios SET activo = TRUE WHERE id = %s AND tenant_id = %s",
                       (usuario_id, tenant_id))
        conn.commit()
        filas_afectadas = cursor.rowcount
        cursor.close()

        if filas_afectadas > 0:
            log_audit('UPDATE', 'usuarios', {'id': usuario_id, 'tenant_id': tenant_id,
                                             'action': 'activar'})
            flash('Usuario activado.', 'success')
        else:
            flash('Usuario no encontrado para este tenant.', 'warning')
    except Exception:
        conn.rollback()
        logging.exception('Error al activar usuario del panel')
        flash('No se pudo activar el usuario. Intente nuevamente.', 'danger')
        log_audit('ERROR', 'usuarios', {'accion': 'activar'})
    finally:
        conn.close()
    
    return redirect(url_for('admin.tenants_ver', encoded_id=encode_id(tenant_id)))


@admin_bp.route('/usuarios')
@superadmin_required
def usuarios():
    tenant_id = request.args.get('tenant_id', type=int)
    
    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        
        if tenant_id:
            cursor.execute("""
                SELECT u.*, t.codigo as tenant_codigo, t.nombre as tenant_nombre
                FROM usuarios u
                JOIN tenants t ON u.tenant_id = t.id
                WHERE u.tenant_id = %s
                ORDER BY u.nombre
            """, (tenant_id,))
        else:
            cursor.execute("""
                SELECT u.*, t.codigo as tenant_codigo, t.nombre as tenant_nombre
                FROM usuarios u
                JOIN tenants t ON u.tenant_id = t.id
                ORDER BY t.nombre, u.nombre
            """)
        
        usuarios = cursor.fetchall()
        
        cursor.execute("SELECT id, codigo, nombre FROM tenants ORDER BY nombre")
        tenants = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()
    
    log_audit('ACCESS', 'usuarios')
    return render_template('admin_usuarios.html', usuarios=usuarios, tenants=tenants, tenant_id=tenant_id)


@admin_bp.route('/roles')
@superadmin_required
def roles():
    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.id, r.nombre, r.descripcion, r.activo,
                   (SELECT COUNT(*) FROM usuarios u WHERE u.rol = r.nombre) as total_usuarios,
                   (SELECT COUNT(*) FROM roles_rutas rr WHERE rr.rol = r.nombre) as total_rutas
            FROM roles r
            ORDER BY r.nombre
        """)
        roles = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()

    log_audit('ACCESS', 'roles')
    return render_template('admin_roles.html', roles=roles)


@admin_bp.route('/roles/guardar', methods=['POST'])
@superadmin_required
def roles_guardar():
    d = request.form
    rol_id = d.get('id')
    nombre = (d.get('nombre') or '').strip().upper()
    descripcion = (d.get('descripcion') or '').strip()
    activo = 1 if d.get('activo') else 0

    if not nombre:
        flash('El nombre del rol es obligatorio', 'danger')
        return redirect(url_for('admin.roles'))

    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        anterior = None
        if rol_id:
            cursor.execute("SELECT nombre FROM roles WHERE id = %s", (rol_id,))
            anterior = cursor.fetchone()
        if nombre in ROLES_RESERVADOS and (not anterior or anterior['nombre'] != nombre):
            flash(f'El rol {nombre} está reservado y no puede crearse ni asignarse desde el panel.', 'danger')
            cursor.close()
            return redirect(url_for('admin.roles'))

        if rol_id:
            cursor.execute("""
                UPDATE roles SET nombre = %s, descripcion = %s, activo = %s WHERE id = %s
            """, (nombre, descripcion, activo, rol_id))
            if anterior and anterior['nombre'] != nombre:
                cursor.execute("UPDATE roles_rutas SET rol = %s WHERE rol = %s", (nombre, anterior['nombre']))
                cursor.execute("UPDATE usuarios SET rol = %s WHERE rol = %s", (nombre, anterior['nombre']))
            _invalidar_permisos(conn)
            msg = 'Rol actualizado correctamente'
            accion = 'UPDATE'
        else:
            cursor.execute("""
                INSERT INTO roles (nombre, descripcion, activo) VALUES (%s, %s, %s)
            """, (nombre, descripcion, activo))
            msg = 'Rol creado correctamente'
            accion = 'CREATE'

        conn.commit()
        log_audit(accion, 'roles', {'id': rol_id, 'nombre': nombre})
        flash(msg, 'success')
        cursor.close()
    except Exception as e:
        conn.rollback()
        if is_duplicate_key_error(e):
            flash('Ya existe un rol con ese nombre', 'danger')
        else:
            logging.exception('Error al guardar rol del panel')
            flash('No se pudo guardar el rol. Intente nuevamente.', 'danger')
        log_audit('ERROR', 'roles', {'accion': 'guardar'})
    finally:
        conn.close()

    return redirect(url_for('admin.roles'))


@admin_bp.route('/roles/eliminar/<int:rol_id>', methods=['POST'])
@superadmin_required
def roles_eliminar(rol_id):
    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT nombre FROM roles WHERE id = %s", (rol_id,))
        rol = cursor.fetchone()
        if not rol:
            flash('Rol no encontrado.', 'warning')
            cursor.close()
            return redirect(url_for('admin.roles'))

        cursor.execute("SELECT COUNT(*) as total FROM usuarios WHERE rol = %s AND activo = 1", (rol['nombre'],))
        if cursor.fetchone()['total'] > 0:
            flash('No se puede desactivar el rol porque tiene usuarios asignados', 'danger')
            cursor.close()
            return redirect(url_for('admin.roles'))

        cursor.execute("UPDATE roles SET activo = FALSE WHERE id = %s", (rol_id,))
        _invalidar_permisos(conn)
        conn.commit()
        log_audit('DELETE', 'roles', {'id': rol_id, 'nombre': rol['nombre']})
        flash('Rol desactivado.', 'success')
        cursor.close()
    finally:
        conn.close()

    return redirect(url_for('admin.roles'))


@admin_bp.route('/roles/activar/<int:rol_id>', methods=['POST'])
@superadmin_required
def roles_activar(rol_id):
    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE roles SET activo = TRUE WHERE id = %s", (rol_id,))
        _invalidar_permisos(conn)
        conn.commit()
        log_audit('UPDATE', 'roles', {'id': rol_id, 'action': 'activar'})
        flash('Rol activado.', 'success')
        cursor.close()
    finally:
        conn.close()

    return redirect(url_for('admin.roles'))


@admin_bp.route('/roles/rutas/<rol>', methods=['GET', 'POST'])
@superadmin_required
def roles_rutas_editar(rol):
    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM roles WHERE nombre = %s", (rol,))
        role = cursor.fetchone()
        if not role:
            flash('Rol no encontrado.', 'warning')
            cursor.close()
            return redirect(url_for('admin.roles'))

        if request.method == 'POST':
            permitidas = _rutas_catalogadas()
            nuevas = list(dict.fromkeys(r for r in request.form.getlist('rutas') if r in permitidas))
            if '*' in nuevas:
                nuevas = ['*']
            try:
                cursor.execute("DELETE FROM roles_rutas WHERE rol = %s", (rol,))
                for ruta in nuevas:
                    cursor.execute("INSERT INTO roles_rutas (rol, ruta) VALUES (%s, %s)", (rol, ruta))
                _invalidar_permisos(conn)
                conn.commit()
                log_audit('UPDATE', 'roles_rutas', {'rol': rol, 'rutas': nuevas})
                flash('Rutas asignadas correctamente', 'success')
            except Exception:
                conn.rollback()
                logging.exception('Error al guardar las rutas del rol %s', rol)
                flash('No se pudieron guardar las rutas. Intente nuevamente.', 'danger')
                log_audit('ERROR', 'roles_rutas', {'rol': rol})
            cursor.close()
            return redirect(url_for('admin.roles'))

        cursor.execute("SELECT ruta FROM roles_rutas WHERE rol = %s", (rol,))
        asignadas = [row['ruta'] for row in cursor.fetchall()]
        cursor.close()
    finally:
        conn.close()

    log_audit('ACCESS', 'roles_rutas', {'rol': rol})
    return render_template('admin_roles_rutas.html', role=role, catalogo=ROUTE_CATALOG, asignadas=asignadas)


# Rótulos de la pantalla de auditoría. En audit_logs se siguen guardando los
# códigos (accion, modulo y el detalle en JSON); acá solo se traducen al mostrarlos.
AUDIT_ACCIONES = {
    'LOGIN': 'Ingreso',
    'LOGIN_FAILED': 'Ingreso fallido',
    'LOGOUT': 'Salida',
    'CREATE': 'Alta',
    'UPDATE': 'Modificación',
    'DELETE': 'Baja',
    'PROCESS': 'Proceso',
    'ERROR': 'Error',
    'ACCESS': 'Consulta de pantalla',
}
AUDIT_MODULOS = {
    'auth': 'Acceso al panel',
    'tenants': 'Tenants',
    'usuarios': 'Usuarios',
    'roles': 'Roles',
    'roles_rutas': 'Permisos por rol',
    'parametros': 'Parámetros del tenant',
    'api_token': 'Token de API',
    'configuracion': 'Configuración',
    'intercambio': 'Intercambio',
    'audit': 'Auditoría',
}
# Ayuda de la pantalla: qué significa cada acción y qué abarca cada sección
AUDIT_AYUDA_ACCIONES = {
    'LOGIN': 'Alguien ingresó al panel con usuario y contraseña correctos.',
    'LOGIN_FAILED': 'Intento de ingreso con usuario o contraseña incorrectos. La columna Usuario queda vacía '
                    'porque nadie llegó a ingresar; el detalle muestra el usuario que se escribió. '
                    'Muchos seguidos desde un mismo equipo pueden ser un intento de adivinar la contraseña.',
    'LOGOUT': 'El usuario cerró su sesión.',
    'CREATE': 'Se creó un registro nuevo (un tenant, un usuario, un rol, una clave de configuración).',
    'UPDATE': 'Se cambió un registro que ya existía. Incluye reactivar algo que estaba dado de baja.',
    'DELETE': 'Se dio de baja un registro. Los tenants, usuarios y roles quedan inactivos y se pueden '
              'reactivar, salvo que el detalle diga "Borrado definitivo". Las claves de configuración se '
              'eliminan del todo.',
    'PROCESS': 'Se ejecutó un proceso; hoy, el procesamiento del Intercambio.',
    'ERROR': 'Una operación falló y no se guardó. El detalle trae el mensaje del error.',
    'ACCESS': 'Alguien abrió una sección del panel, sin cambiar nada.',
}
AUDIT_AYUDA_MODULOS = {
    'auth': 'Ingresos y salidas del panel.',
    'tenants': 'Alta, modificación, baja y reactivación de tenants.',
    'usuarios': 'Usuarios del WMS de cada tenant.',
    'roles': 'Catálogo de roles.',
    'roles_rutas': 'Pantallas del WMS habilitadas para cada rol.',
    'parametros': 'Datos y parámetros de operación de un tenant.',
    'api_token': 'Generación del token de la API de un tenant (el anterior deja de servir).',
    'configuracion': 'Claves de la pantalla Configuración.',
    'intercambio': 'Procesamiento y reintento de registros del Intercambio.',
    'audit': 'Consultas a esta pantalla y limpieza de registros antiguos, que se hace con superusuario.exe.',
}
_AUDIT_CAMPOS = {
    'username': 'Usuario', 'nombre': 'Nombre', 'codigo': 'Código', 'clave': 'Clave', 'rol': 'Rol',
    'rutas': 'Rutas', 'error': 'Error', 'action': 'Operación', 'procesados': 'Aplicados',
    'errores': 'Con error', 'reintentados': 'Reintentados', 'hasta': 'Registros hasta el',
    'eliminados': 'Registros eliminados', 'origen': 'Hecho desde',
}
_AUDIT_OPERACIONES = {'activar': 'Reactivación', 'borrado_fisico': 'Borrado definitivo'}
# Módulos cuyo detalle trae el `id` de un registro: rótulo y catálogo donde buscar su nombre
_AUDIT_ID = {'tenants': 'Tenant', 'usuarios': 'Usuario', 'roles': 'Rol'}


def _detalle_audit(modulo, detalle, nombres):
    """Convierte el detalle de un registro de auditoría (JSON) en pares (rótulo, valor) legibles.

    `nombres` es {'tenants': {id: texto}, 'usuarios': {...}, 'roles': {...}} para mostrar
    a quién corresponde un id en vez del número.
    """
    if not detalle:
        return []
    try:
        datos = json.loads(detalle)
    except (TypeError, ValueError):
        return [('Detalle', str(detalle))]
    if not isinstance(datos, dict):
        return [('Detalle', str(datos))]

    def nombre_de(catalogo, valor):
        try:
            return nombres.get(catalogo, {}).get(int(valor)) or f'ID {valor}'
        except (TypeError, ValueError):
            return f'ID {valor}'

    # El id solo se muestra si el registro no trae ya un nombre que lo identifique
    identificado = any(datos.get(k) for k in ('nombre', 'username', 'codigo', 'clave'))
    pares = []
    for clave, valor in datos.items():
        if clave == 'id':
            if not identificado:
                pares.append((_AUDIT_ID.get(modulo, 'ID'), nombre_de(modulo, valor) if modulo in _AUDIT_ID else valor))
        elif clave == 'tenant_id':
            pares.append(('Tenant', nombre_de('tenants', valor)))
        elif clave == 'action':
            pares.append(('Operación', _AUDIT_OPERACIONES.get(valor, valor)))
        elif isinstance(valor, list):
            texto = 'Acceso total' if valor == ['*'] else ', '.join(str(v) for v in valor) or 'ninguna'
            pares.append((_AUDIT_CAMPOS.get(clave, clave), texto))
        else:
            pares.append((_AUDIT_CAMPOS.get(clave, clave), valor))
    return pares


def _fecha_filtro(valor, rotulo):
    """Fecha de un filtro (AAAA-MM-DD) o None si está vacía o es inválida."""
    if not valor:
        return None
    try:
        return datetime.datetime.strptime(valor, '%Y-%m-%d').date()
    except ValueError:
        flash(f'Fecha "{rotulo}" inválida', 'warning')
        return None


@admin_bp.route('/audit')
@superadmin_required
def audit():
    page = max(request.args.get('page', 1, type=int), 1)
    por_pagina = 50
    offset = (page - 1) * por_pagina

    filtro_accion = request.args.get('accion', '')
    filtro_modulo = request.args.get('modulo', '')
    # Las consultas de pantalla (ACCESS) son la mayoría de los registros y tapan
    # los cambios: se muestran solo si se piden.
    incluir_consultas = bool(request.args.get('consultas')) or filtro_accion == 'ACCESS'

    # Rango de fechas: sin filtro, los últimos 7 días
    desde = _fecha_filtro(request.args.get('desde', ''), 'desde')
    hasta = _fecha_filtro(request.args.get('hasta', ''), 'hasta')
    if not hasta:
        hasta = desde + datetime.timedelta(days=6) if desde else datetime.date.today()
    if not desde:
        desde = hasta - datetime.timedelta(days=6)
    if desde > hasta:
        desde, hasta = hasta, desde
    filtro_desde = desde.strftime('%Y-%m-%d')
    filtro_hasta = hasta.strftime('%Y-%m-%d')

    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()

        where = f"{date_func('created_at')} >= %s AND {date_func('created_at')} <= %s"
        params = [filtro_desde, filtro_hasta]
        if filtro_accion:
            where += " AND accion = %s"
            params.append(filtro_accion)
        elif not incluir_consultas:
            where += " AND accion <> 'ACCESS'"
        if filtro_modulo:
            where += " AND modulo = %s"
            params.append(filtro_modulo)

        cursor.execute(f"SELECT COUNT(*) as total FROM audit_logs WHERE {where}", params)
        total = cursor.fetchone()['total']

        cursor.execute(f"""
            SELECT * FROM audit_logs
            WHERE {where}
            ORDER BY created_at DESC, id DESC
            {limit_sql(por_pagina, offset)}
        """, params)
        logs = [dict(r) for r in cursor.fetchall()]

        # Nombres para mostrar a qué tenant, usuario o rol corresponde cada id del detalle
        nombres = {}
        cursor.execute("SELECT id, codigo, nombre FROM tenants")
        nombres['tenants'] = {t['id']: f"{t['codigo']} — {t['nombre']}" for t in cursor.fetchall()}
        cursor.execute("SELECT id, username FROM usuarios")
        nombres['usuarios'] = {u['id']: u['username'] for u in cursor.fetchall()}
        cursor.execute("SELECT id, nombre FROM roles")
        nombres['roles'] = {r['id']: r['nombre'] for r in cursor.fetchall()}

        cursor.close()
    finally:
        conn.close()

    for log in logs:
        log['accion_txt'] = AUDIT_ACCIONES.get(log['accion'], log['accion'])
        log['modulo_txt'] = AUDIT_MODULOS.get(log['modulo'], log['modulo'])
        log['detalle_pares'] = _detalle_audit(log['modulo'], log['detalle'], nombres)

    total_paginas = (total + por_pagina - 1) // por_pagina if total > 0 else 1

    log_audit('ACCESS', 'audit')
    return render_template('admin_audit.html',
                         logs=logs,
                         total=total,
                         page=page,
                         total_paginas=total_paginas,
                         acciones=AUDIT_ACCIONES,
                         modulos=AUDIT_MODULOS,
                         ayuda_acciones=AUDIT_AYUDA_ACCIONES,
                         ayuda_modulos=AUDIT_AYUDA_MODULOS,
                         filtro_accion=filtro_accion,
                         filtro_modulo=filtro_modulo,
                         incluir_consultas=incluir_consultas,
                         desde=desde,
                         hasta=hasta,
                         filtro_desde=filtro_desde,
                         filtro_hasta=filtro_hasta)


def _clave_sensible(clave):
    """Claves de configuracion cuyo valor no se muestra en el panel."""
    return any(p in (clave or '').upper() for p in ('PASSWORD', 'SECRET', 'TOKEN'))


@admin_bp.route('/configuracion')
@superadmin_required
def configuracion():
    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM configuracion WHERE clave <> %s ORDER BY clave", (VERSION_CLAVE,))
        configs = [dict(c) for c in cursor.fetchall()]
        cursor.close()
    finally:
        conn.close()

    # Los valores sensibles no viajan al navegador: se editan en blanco
    for c in configs:
        c['sensible'] = _clave_sensible(c['clave'])
        if c['sensible']:
            c['valor'] = ''
    
    log_audit('ACCESS', 'configuracion')
    return render_template('admin_configuracion.html', configs=configs)


@admin_bp.route('/configuracion/guardar', methods=['POST'])
@superadmin_required
def configuracion_guardar():
    d = request.form
    config_id = d.get('id')
    clave = d.get('clave', '').strip().upper()
    valor = d.get('valor', '')
    descripcion = d.get('descripcion', '').strip()
    
    if not config_id and not clave:
        flash('La clave es obligatoria', 'danger')
        return redirect(url_for('admin.configuracion'))
    
    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        
        if config_id:
            # La clave no se cambia al editar; un valor sensible en blanco conserva el actual
            cursor.execute("SELECT clave FROM configuracion WHERE id = %s", (config_id,))
            actual = cursor.fetchone()
            if not actual:
                flash('Configuración no encontrada.', 'warning')
                return redirect(url_for('admin.configuracion'))
            clave = actual['clave']
            if _clave_sensible(clave) and not valor:
                cursor.execute("UPDATE configuracion SET descripcion = %s WHERE id = %s",
                               (descripcion, config_id))
            else:
                cursor.execute("UPDATE configuracion SET valor = %s, descripcion = %s WHERE id = %s",
                               (valor, descripcion, config_id))
            msg = 'Configuración actualizada correctamente'
            accion = 'UPDATE'
        else:
            cursor.execute("""
                INSERT INTO configuracion (clave, valor, descripcion)
                VALUES (%s, %s, %s)
            """, (clave, valor, descripcion))
            msg = 'Configuración creada correctamente'
            accion = 'CREATE'

        conn.commit()
        log_audit(accion, 'configuracion', {'clave': clave})
        flash(msg, 'success')
        cursor.close()
    except Exception as e:
        conn.rollback()
        if is_duplicate_key_error(e):
            flash('La clave ya existe. Elija otra.', 'danger')
            log_audit('ERROR', 'configuracion', {'motivo': 'clave duplicada'})
        else:
            logging.exception('Error al guardar configuración del panel')
            flash('No se pudo guardar la configuración. Intente nuevamente.', 'danger')
            log_audit('ERROR', 'configuracion', {'accion': 'guardar'})
    finally:
        conn.close()
    
    return redirect(url_for('admin.configuracion'))


@admin_bp.route('/configuracion/eliminar/<int:config_id>', methods=['POST'])
@superadmin_required
def configuracion_eliminar(config_id):
    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT clave FROM configuracion WHERE id = %s", (config_id,))
        config = cursor.fetchone()
        cursor.execute("DELETE FROM configuracion WHERE id = %s", (config_id,))
        conn.commit()
        filas = cursor.rowcount
        cursor.close()
        
        if filas > 0:
            log_audit('DELETE', 'configuracion', {'id': config_id, 'clave': config['clave'] if config else None})
            flash('Configuración eliminada.', 'success')
        else:
            flash('Configuración no encontrada.', 'warning')
    except Exception:
        conn.rollback()
        logging.exception('Error al eliminar configuración del panel')
        flash('No se pudo eliminar la configuración. Intente nuevamente.', 'danger')
        log_audit('ERROR', 'configuracion', {'accion': 'eliminar'})
    finally:
        conn.close()
    
    return redirect(url_for('admin.configuracion'))


@admin_bp.route('/intercambio')
@superadmin_required
def intercambio():
    # Conexión de intercambio (sin la contraseña), tal como está en el archivo de conexiones
    descripciones = {'engine': 'Motor de BD', 'host': 'Servidor', 'port': 'Puerto',
                     'database': 'Base de datos', 'user': 'Usuario'}
    try:
        conexion = get_conexion('intercambio')
        config_intercambio = [{'clave': k, 'valor': conexion[k], 'descripcion': d}
                              for k, d in descripciones.items()]
    except ConexionesError:
        config_intercambio = []

    conn_int = get_intercambio_connection()
    try:
        cursor_int = conn_int.cursor()
        conteo = {'pendiente': 0, 'procesado': 0, 'error': 0}
        errores = []
        for m, conf in MODULOS.items():
            cursor_int.execute(
                f"SELECT estado, COUNT(*) AS total FROM {conf['tabla']} GROUP BY estado")
            for r in cursor_int.fetchall():
                clave = str(r['estado']).lower()
                conteo[clave] = conteo.get(clave, 0) + r['total']

            cursor_int.execute(
                f"SELECT * FROM {conf['tabla']} WHERE estado = 'error' "
                f"ORDER BY id DESC {limit_sql(100)}")
            for row in cursor_int.fetchall():
                row = dict(row)
                if m == 'transporte_rutas':
                    referencia = (row.get('transporte_codigo') or '') + ' -> ' + (row.get('ruta_nombre') or '')
                    nombre = row.get('observaciones') or ''
                elif m == 'rutas':
                    referencia = row.get('nombre_ruta')
                    nombre = row.get('descripcion') or ''
                else:
                    referencia = row.get('codigo')
                    nombre = row.get('nombre') or row.get('razonsocial') or ''
                errores.append({
                    'modulo': m,
                    'modulo_nombre': conf['nombre'],
                    'id': row.get('id'),
                    'tenant_codigo': row.get('tenant_codigo'),
                    'referencia': referencia,
                    'nombre': nombre,
                    'intentos': row.get('intentos'),
                    'error_mensaje': row.get('error_mensaje'),
                })
        errores.sort(key=lambda r: (r.get('id') or 0), reverse=True)
        errores = errores[:100]

        cursor_int.execute(
            f"SELECT * FROM intercambio_log ORDER BY id DESC {limit_sql(20)}")
        logs = cursor_int.fetchall()
    finally:
        conn_int.close()

    log_audit('ACCESS', 'intercambio')
    return render_template('admin_intercambio.html',
                           config_intercambio=config_intercambio,
                           conteo=conteo,
                           errores=errores,
                           logs=logs)


@admin_bp.route('/intercambio/procesar', methods=['POST'])
@superadmin_required
def intercambio_procesar():
    try:
        resultado = procesar_intercambio(usuario=session.get('admin_username'))
        if resultado.get('aviso'):
            flash(resultado['aviso'], 'warning')
        elif resultado['errores'] == 0:
            flash(f"Intercambio procesado: {resultado['procesados']} registro(s) aplicados.", 'success')
        else:
            flash(f"Intercambio procesado: {resultado['procesados']} aplicados, "
                  f"{resultado['errores']} con error.", 'warning')
        log_audit('PROCESS', 'intercambio',
                  {'procesados': resultado['procesados'], 'errores': resultado['errores']})
    except Exception:
        logging.exception('Error al procesar el intercambio desde el panel')
        flash('No se pudo procesar el intercambio. Revise los logs.', 'danger')
        log_audit('ERROR', 'intercambio', {'accion': 'procesar'})
    return redirect(url_for('admin.intercambio'))


@admin_bp.route('/intercambio/reintentar', methods=['POST'])
@superadmin_required
def intercambio_reintentar():
    try:
        n = reintentar_todo()
        flash(f"{n} registro(s) en error devuelto(s) a pendiente.", 'info')
        log_audit('UPDATE', 'intercambio', {'reintentados': n})
    except Exception:
        logging.exception('Error al reintentar el intercambio desde el panel')
        flash('No se pudieron reintentar los registros. Revise los logs.', 'danger')
        log_audit('ERROR', 'intercambio', {'accion': 'reintentar'})
    return redirect(url_for('admin.intercambio'))


@admin_bp.route('/parametros/editar/<int:tenant_id>', methods=['GET', 'POST'])
@superadmin_required
def parametros_editar(tenant_id):
    conn_admin = _get_admin_connection()
    
    try:
        cursor_admin = conn_admin.cursor()
        cursor_admin.execute("SELECT id, nombre FROM tenants WHERE activo = 1 ORDER BY nombre")
        tenants_list = cursor_admin.fetchall()
        
        cursor_admin.execute("""
            SELECT id, nombre, razon_social, cuit, direccion, telefono, email,
                   nombredelalmacen, metodosdepicking, metodo_picking_default,
                   bajostock, dias_filtro_fechas, proveedor_api_ia, api_key, modelo_api_ia,
                   contexto, prompt, api_token
            FROM tenants WHERE id = %s
        """, (tenant_id,))
        tenant_actual = cursor_admin.fetchone()
        if not tenant_actual:
            flash('Tenant no encontrado', 'danger')
            return redirect(url_for('admin.tenants'))

        if request.method == 'POST':
            d = request.form
            cuit = normalizar_cuit(d.get('cuit'))
            if cuit is None:
                flash(CUIT_INVALIDO, 'danger')
                return redirect(url_for('admin.parametros_editar', tenant_id=tenant_id))
            try:
                bajostock = float(d.get('bajostock') or 0)
                dias_filtro = int(d.get('dias_filtro_fechas') or 30)
            except (TypeError, ValueError):
                flash('Los valores numéricos de los parámetros no son válidos.', 'danger')
                return redirect(url_for('admin.parametros_editar', tenant_id=tenant_id))
            metodos = request.form.getlist('metodosdepicking')
            if not metodos:
                metodos = ['fifo']
            picking_json = json.dumps(metodos)

            metodo_default = (d.get('metodo_picking_default') or '').strip().lower()
            if metodo_default not in metodos:
                metodo_default = metodos[0]
            
            cursor_admin.execute("""
                UPDATE tenants SET
                    nombre = %s,
                    razon_social = %s,
                    cuit = %s,
                    direccion = %s,
                    telefono = %s,
                    email = %s,
                    nombredelalmacen = %s,
                    metodosdepicking = %s,
                    metodo_picking_default = %s,
                    bajostock = %s,
                    dias_filtro_fechas = %s,
                    proveedor_api_ia = %s,
                    api_key = %s,
                    modelo_api_ia = %s,
                    contexto = %s,
                    prompt = %s
                WHERE id = %s
            """, (
                d.get('nombre', ''),
                d.get('razon_social', ''),
                cuit,
                d.get('direccion', ''),
                d.get('telefono', ''),
                d.get('email', ''),
                d.get('nombredelalmacen', ''),
                picking_json,
                metodo_default,
                bajostock,
                dias_filtro,
                d.get('proveedor_api_ia', ''),
                d.get('api_key') or tenant_actual['api_key'] or '',
                d.get('modelo_api_ia', ''),
                d.get('contexto', ''),
                d.get('prompt', ''),
                tenant_id
            ))
            conn_admin.commit()
            
            flash('Parámetros actualizados correctamente', 'success')
            log_audit('UPDATE', 'parametros', {'tenant_id': tenant_id})
            
            return redirect(url_for('admin.tenants'))
        
        param = {
            'tenant_id': tenant_actual['id'],
            'tenant_nombre': tenant_actual['nombre'],
            'razon_social': tenant_actual.get('razon_social') or '',
            'cuit': tenant_actual.get('cuit') or '',
            'direccion': tenant_actual.get('direccion') or '',
            'telefono': tenant_actual.get('telefono') or '',
            'email': tenant_actual.get('email') or '',
            'nombredelalmacen': tenant_actual.get('nombredelalmacen') or '',
            'metodosdepicking': tenant_actual.get('metodosdepicking') or '"fifo"',
            'metodo_picking_default': tenant_actual.get('metodo_picking_default') or 'libre',
            'bajostock': tenant_actual.get('bajostock') or 0,
            'dias_filtro_fechas': tenant_actual.get('dias_filtro_fechas') or 30,
            'proveedor_api_ia': tenant_actual.get('proveedor_api_ia') or '',
            'api_key': '',
            'api_key_configurada': bool(tenant_actual.get('api_key')),
            'modelo_api_ia': tenant_actual.get('modelo_api_ia') or '',
            'contexto': tenant_actual.get('contexto') or '',
            'prompt': tenant_actual.get('prompt') or '',
            'api_token_activo': bool(tenant_actual.get('api_token')),
        }
        log_audit('ACCESS', 'parametros', {'tenant_id': tenant_id})
        return render_template('admin_parametros_editar.html', param=param, tenants=tenants_list, tenant_id=tenant_id)
    finally:
        conn_admin.close()


@admin_bp.route('/parametros/<int:tenant_id>/api-token', methods=['POST'])
@superadmin_required
def api_token_generar(tenant_id):
    token = secrets.token_urlsafe(32)
    conn_admin = _get_admin_connection()
    try:
        cursor_admin = conn_admin.cursor()
        cursor_admin.execute(
            "UPDATE tenants SET api_token = %s WHERE id = %s",
            (_hash_token(token), tenant_id)
        )
        if cursor_admin.rowcount == 0:
            flash('Tenant no encontrado', 'danger')
            return redirect(url_for('admin.tenants'))
        conn_admin.commit()
        log_audit('UPDATE', 'api_token', {'tenant_id': tenant_id})
    except Exception:
        conn_admin.rollback()
        logging.exception('Error al generar el token API del tenant %s', tenant_id)
        flash('No se pudo generar el token. Intente nuevamente.', 'danger')
        return redirect(url_for('admin.parametros_editar', tenant_id=tenant_id))
    finally:
        conn_admin.close()

    flash(
        "Token API generado. Copialo ahora: ya no se volverá a mostrar. "
        "Usalo como Authorization: Bearer <token> contra /api/v1/. "
        f"Token: {token}",
        'info'
    )
    return redirect(url_for('admin.parametros_editar', tenant_id=tenant_id))
