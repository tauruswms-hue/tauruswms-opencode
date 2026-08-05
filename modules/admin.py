from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from werkzeug.security import check_password_hash, generate_password_hash
import os
import datetime
import json
import base64
import hashlib
import logging
from dotenv import load_dotenv
from modules.db_config import _get_admin_connection, get_intercambio_connection, clear_config_cache
from modules.sql_dialect import date as date_func, is_duplicate_key_error, execute_insert, limit_sql
from modules.schema_generator import ROUTE_CATALOG
from modules.intercambio import (
    procesar_intercambio,
    reintentar_todo,
    MODULOS,
)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=env_path)

SECRET_SALT = os.getenv('SECRET_SALT', 'taurus-wms-salt-2024')


def encode_id(tenant_id):
    """Codifica el ID con base64 para ocultar el valor real"""
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
    except:
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


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_user_id' not in session:
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'admin_user_id' in session:
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
            
            if usuario:
                cursor.execute("""
                    UPDATE admin_usuarios SET ultimo_acceso = %s WHERE id = %s
                """, (datetime.datetime.now(), usuario['id']))
                conn.commit()
            
            cursor.close()
            conn.close()
            
            if usuario and check_password_hash(usuario['password_hash'], password):
                session['admin_user_id'] = usuario['id']
                session['admin_username'] = usuario['username']
                session['admin_nombre'] = usuario['nombre']
                session['admin_rol'] = usuario['rol']
                
                log_audit('LOGIN', 'auth', {'username': username})
                flash(f'Bienvenido, {usuario["nombre"]}', 'success')
                return redirect(url_for('admin.tenants'))
            else:
                flash('Credenciales inválidas', 'error')
                log_audit('LOGIN_FAILED', 'auth', {'username': username})
                
        except Exception as e:
            flash(f'Error de conexión: {str(e)}', 'error')
    
    return render_template('admin_login.html')


@admin_bp.route('/logout')
def logout():
    if 'admin_user_id' in session:
        log_audit('LOGOUT', 'auth', {'username': session.get('admin_username')})
    
    session.pop('admin_user_id', None)
    session.pop('admin_username', None)
    session.pop('admin_nombre', None)
    session.pop('admin_rol', None)
    
    flash('Sesión admin cerrada', 'info')
    return redirect(url_for('admin.login'))


@admin_bp.route('/')
@admin_required
def index():
    return redirect(url_for('admin.tenants'))


@admin_bp.route('/tenants')
@admin_required
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
@admin_required
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
@admin_required
def tenants_guardar():
    d = request.form
    tenant_id = d.get('id')
    nombre = d.get('nombre')
    
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
                d.get('cuit'), d.get('direccion'), d.get('telefono'), d.get('email'),
                1 if d.get('activo') else 0, tenant_id
            ))
            msg = 'Tenant actualizado correctamente'
            log_audit('UPDATE', 'tenants', {'id': tenant_id, 'nombre': nombre})
        else:
            tenant_id = execute_insert(cursor, """
                INSERT INTO tenants (nombre, razon_social, cuit, direccion, telefono, email)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                nombre, d.get('razon_social'),
                d.get('cuit'), d.get('direccion'), d.get('telefono'), d.get('email')
            ))
            msg = 'Tenant creado correctamente'
            log_audit('CREATE', 'tenants', {'id': tenant_id, 'nombre': nombre})
        
        conn.commit()
        flash(msg, 'success')
        cursor.close()
    except Exception as e:
        conn.rollback()
        flash(f'Error: {str(e)}', 'danger')
        log_audit('ERROR', 'tenants', {'error': str(e)})
    finally:
        conn.close()
    
    return redirect(url_for('admin.tenants'))


@admin_bp.route('/tenants/eliminar/<encoded_id>')
@admin_required
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
        flash('Tenant desactivado.', 'success')
        log_audit('DELETE', 'tenants', {'id': tenant_id})
        cursor.close()
    finally:
        conn.close()
    
    return redirect(url_for('admin.tenants'))


@admin_bp.route('/tenants/activar/<encoded_id>')
@admin_required
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
        flash('Tenant activado.', 'success')
        log_audit('UPDATE', 'tenants', {'id': tenant_id, 'action': 'activar'})
        cursor.close()
    finally:
        conn.close()
    
    return redirect(url_for('admin.tenants'))


@admin_bp.route('/usuarios/guardar', methods=['POST'])
@admin_required
def usuarios_guardar():
    d = request.form
    usuario_id = d.get('id')
    tenant_id = d.get('tenant_id')
    
    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        if usuario_id:
            if d.get('password'):
                cursor.execute("""
                    UPDATE usuarios SET 
                        nombre = %s, email = %s, rol = %s, activo = %s,
                        password_hash = %s
                    WHERE id = %s
                """, (
                    d.get('nombre'), d.get('email'), d.get('rol'),
                    1 if d.get('activo') else 0,
                    generate_password_hash(d.get('password')),
                    usuario_id
                ))
            else:
                cursor.execute("""
                    UPDATE usuarios SET 
                        nombre = %s, email = %s, rol = %s, activo = %s
                    WHERE id = %s
                """, (
                    d.get('nombre'), d.get('email'), d.get('rol'),
                    1 if d.get('activo') else 0, usuario_id
                ))
            msg = 'Usuario actualizado correctamente'
            log_audit('UPDATE', 'usuarios', {'id': usuario_id, 'username': d.get('username')})
        else:
            if not d.get('password'):
                flash('La contraseña es obligatoria para nuevos usuarios', 'danger')
                return redirect(url_for('admin.tenants_ver', encoded_id=encode_id(tenant_id)))
            
            cursor.execute("""
                INSERT INTO usuarios (username, password_hash, nombre, email, rol, tenant_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                d.get('username'),
                generate_password_hash(d.get('password')),
                d.get('nombre'),
                d.get('email'),
                d.get('rol'),
                tenant_id
            ))
            msg = 'Usuario creado correctamente'
            log_audit('CREATE', 'usuarios', {'username': d.get('username'), 'tenant_id': tenant_id})
        
        conn.commit()
        flash(msg, 'success')
        cursor.close()
    except Exception as e:
        conn.rollback()
        if is_duplicate_key_error(e):
            flash('El nombre de usuario ya existe. Elija otro.', 'danger')
        else:
            flash(f'Error: {str(e)}', 'danger')
        log_audit('ERROR', 'usuarios', {'error': str(e)})
    finally:
        conn.close()
    
    return redirect(url_for('admin.tenants_ver', encoded_id=encode_id(tenant_id)))


@admin_bp.route('/usuarios/eliminar/<int:usuario_id>/<encoded_tenant_id>')
@admin_required
def usuarios_eliminar(usuario_id, encoded_tenant_id):
    tenant_id = decode_id(encoded_tenant_id)
    if tenant_id is None:
        flash('ID inválido', 'danger')
        return redirect(url_for('admin.tenants'))
    
    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE usuarios SET activo = FALSE WHERE id = %s", (usuario_id,))
        conn.commit()
        filas_afectadas = cursor.rowcount
        cursor.close()
        
        if filas_afectadas > 0:
            flash('Usuario desactivado.', 'success')
            log_audit('DELETE', 'usuarios', {'id': usuario_id})
        else:
            flash('Usuario no encontrado.', 'warning')
    except Exception as e:
        conn.rollback()
        flash(f'Error: {str(e)}', 'danger')
        log_audit('ERROR', 'usuarios', {'error': str(e)})
    finally:
        conn.close()
    
    return redirect(url_for('admin.tenants_ver', encoded_id=encode_id(tenant_id)))


@admin_bp.route('/usuarios/activar/<int:usuario_id>/<encoded_tenant_id>')
@admin_required
def usuarios_activar(usuario_id, encoded_tenant_id):
    tenant_id = decode_id(encoded_tenant_id)
    if tenant_id is None:
        flash('ID inválido', 'danger')
        return redirect(url_for('admin.tenants'))
    
    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE usuarios SET activo = TRUE WHERE id = %s", (usuario_id,))
        conn.commit()
        filas_afectadas = cursor.rowcount
        cursor.close()
        
        if filas_afectadas > 0:
            flash('Usuario activado.', 'success')
            log_audit('UPDATE', 'usuarios', {'id': usuario_id, 'action': 'activar'})
        else:
            flash('Usuario no encontrado.', 'warning')
    except Exception as e:
        conn.rollback()
        flash(f'Error: {str(e)}', 'danger')
        log_audit('ERROR', 'usuarios', {'error': str(e)})
    finally:
        conn.close()
    
    return redirect(url_for('admin.tenants_ver', encoded_id=encode_id(tenant_id)))


@admin_bp.route('/usuarios')
@admin_required
def usuarios():
    if session.get('admin_rol') != 'SUPERADMIN':
        flash('Solo SUPERADMIN puede gestionar todos los usuarios', 'danger')
        return redirect(url_for('admin.tenants'))
    
    tenant_id = request.args.get('tenant_id', type=int)
    
    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        
        if tenant_id:
            cursor.execute("""
                SELECT u.*, t.nombre as tenant_nombre
                FROM usuarios u
                JOIN tenants t ON u.tenant_id = t.id
                WHERE u.tenant_id = %s
                ORDER BY u.nombre
            """, (tenant_id,))
        else:
            cursor.execute("""
                SELECT u.*, t.nombre as tenant_nombre
                FROM usuarios u
                JOIN tenants t ON u.tenant_id = t.id
                ORDER BY t.nombre, u.nombre
            """)
        
        usuarios = cursor.fetchall()
        
        cursor.execute("SELECT id, nombre FROM tenants ORDER BY nombre")
        tenants = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()
    
    log_audit('ACCESS', 'usuarios')
    return render_template('admin_usuarios.html', usuarios=usuarios, tenants=tenants, tenant_id=tenant_id)


@admin_bp.route('/roles')
@admin_required
def roles():
    if session.get('admin_rol') != 'SUPERADMIN':
        flash('Solo SUPERADMIN puede gestionar roles', 'danger')
        return redirect(url_for('admin.tenants'))

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
@admin_required
def roles_guardar():
    if session.get('admin_rol') != 'SUPERADMIN':
        flash('Solo SUPERADMIN puede gestionar roles', 'danger')
        return redirect(url_for('admin.tenants'))

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
        if rol_id:
            cursor.execute("SELECT nombre FROM roles WHERE id = %s", (rol_id,))
            anterior = cursor.fetchone()
            cursor.execute("""
                UPDATE roles SET nombre = %s, descripcion = %s, activo = %s WHERE id = %s
            """, (nombre, descripcion, activo, rol_id))
            if anterior and anterior['nombre'] != nombre:
                cursor.execute("UPDATE roles_rutas SET rol = %s WHERE rol = %s", (nombre, anterior['nombre']))
                cursor.execute("UPDATE usuarios SET rol = %s WHERE rol = %s", (nombre, anterior['nombre']))
            msg = 'Rol actualizado correctamente'
            log_audit('UPDATE', 'roles', {'id': rol_id, 'nombre': nombre})
        else:
            cursor.execute("""
                INSERT INTO roles (nombre, descripcion, activo) VALUES (%s, %s, %s)
            """, (nombre, descripcion, activo))
            msg = 'Rol creado correctamente'
            log_audit('CREATE', 'roles', {'nombre': nombre})

        conn.commit()
        flash(msg, 'success')
        cursor.close()
    except Exception as e:
        conn.rollback()
        if is_duplicate_key_error(e):
            flash('Ya existe un rol con ese nombre', 'danger')
        else:
            flash(f'Error: {str(e)}', 'danger')
        log_audit('ERROR', 'roles', {'error': str(e)})
    finally:
        conn.close()

    return redirect(url_for('admin.roles'))


@admin_bp.route('/roles/eliminar/<int:rol_id>')
@admin_required
def roles_eliminar(rol_id):
    if session.get('admin_rol') != 'SUPERADMIN':
        flash('Solo SUPERADMIN puede gestionar roles', 'danger')
        return redirect(url_for('admin.tenants'))

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
        conn.commit()
        flash('Rol desactivado.', 'success')
        log_audit('DELETE', 'roles', {'id': rol_id, 'nombre': rol['nombre']})
        cursor.close()
    finally:
        conn.close()

    return redirect(url_for('admin.roles'))


@admin_bp.route('/roles/activar/<int:rol_id>')
@admin_required
def roles_activar(rol_id):
    if session.get('admin_rol') != 'SUPERADMIN':
        flash('Solo SUPERADMIN puede gestionar roles', 'danger')
        return redirect(url_for('admin.tenants'))

    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE roles SET activo = TRUE WHERE id = %s", (rol_id,))
        conn.commit()
        flash('Rol activado.', 'success')
        log_audit('UPDATE', 'roles', {'id': rol_id, 'action': 'activar'})
        cursor.close()
    finally:
        conn.close()

    return redirect(url_for('admin.roles'))


@admin_bp.route('/roles/rutas/<rol>', methods=['GET', 'POST'])
@admin_required
def roles_rutas_editar(rol):
    if session.get('admin_rol') != 'SUPERADMIN':
        flash('Solo SUPERADMIN puede gestionar roles', 'danger')
        return redirect(url_for('admin.tenants'))

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
            nuevas = request.form.getlist('rutas')
            cursor.execute("DELETE FROM roles_rutas WHERE rol = %s", (rol,))
            if '*' in nuevas:
                cursor.execute("INSERT INTO roles_rutas (rol, ruta) VALUES (%s, %s)", (rol, '*'))
            else:
                for ruta in nuevas:
                    cursor.execute("INSERT INTO roles_rutas (rol, ruta) VALUES (%s, %s)", (rol, ruta))
            conn.commit()
            flash('Rutas asignadas correctamente', 'success')
            log_audit('UPDATE', 'roles_rutas', {'rol': rol, 'rutas': nuevas})
            cursor.close()
            return redirect(url_for('admin.roles'))

        cursor.execute("SELECT ruta FROM roles_rutas WHERE rol = %s", (rol,))
        asignadas = [row['ruta'] for row in cursor.fetchall()]
        cursor.close()
    finally:
        conn.close()

    log_audit('ACCESS', 'roles_rutas', {'rol': rol})
    return render_template('admin_roles_rutas.html', role=role, catalogo=ROUTE_CATALOG, asignadas=asignadas)


@admin_bp.route('/audit')
@admin_required
def audit():
    if session.get('admin_rol') != 'SUPERADMIN':
        flash('Solo SUPERADMIN puede ver los logs', 'danger')
        return redirect(url_for('admin.tenants'))
    
    page = request.args.get('page', 1, type=int)
    por_pagina = 50
    offset = (page - 1) * por_pagina
    
    filtro_accion = request.args.get('accion', '')
    filtro_modulo = request.args.get('modulo', '')
    filtro_desde = request.args.get('desde', '')
    filtro_hasta = request.args.get('hasta', '')
    
    desde = None
    hasta = None
    
    if filtro_desde:
        try:
            desde = datetime.datetime.strptime(filtro_desde, '%Y-%m-%d')
        except ValueError:
            flash('Formato de fecha "desde" inválido', 'warning')
            filtro_desde = ''
    
    if filtro_hasta:
        try:
            hasta = datetime.datetime.strptime(filtro_hasta, '%Y-%m-%d')
        except ValueError:
            flash('Formato de fecha "hasta" inválido', 'warning')
            filtro_hasta = ''
    
    if desde and hasta:
        diff = (hasta - desde).days
        if diff < 7:
            flash('El rango de fechas no puede ser menor a 1 semana', 'warning')
            hasta = desde + datetime.timedelta(days=6)
            filtro_hasta = filtro_desde
    elif desde and not hasta:
        hasta = desde + datetime.timedelta(days=6)
        filtro_hasta = hasta.strftime('%Y-%m-%d')
    elif not desde and filtro_hasta:
        desde = hasta - datetime.timedelta(days=6)
        filtro_desde = desde.strftime('%Y-%m-%d')
    else:
        hasta = datetime.datetime.now()
        desde = hasta - datetime.timedelta(days=6)
        filtro_desde = desde.strftime('%Y-%m-%d')
        filtro_hasta = hasta.strftime('%Y-%m-%d')
    
    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        
        where = "1=1"
        params = []
        if filtro_accion:
            where += " AND accion = %s"
            params.append(filtro_accion)
        if filtro_modulo:
            where += " AND modulo = %s"
            params.append(filtro_modulo)
        if desde:
            where += f" AND {date_func('created_at')} >= %s"
            params.append(filtro_desde)
        if hasta:
            where += f" AND {date_func('created_at')} <= %s"
            params.append(filtro_hasta)
        
        cursor.execute(f"SELECT COUNT(*) as total FROM audit_logs WHERE {where}", params)
        total = cursor.fetchone()['total']
        
        cursor.execute(f"""
            SELECT * FROM audit_logs 
            WHERE {where}
            ORDER BY created_at DESC
            {limit_sql(por_pagina, offset)}
        """, params)
        logs = cursor.fetchall()
        
        cursor.close()
    finally:
        conn.close()
    
    total_paginas = (total + por_pagina - 1) // por_pagina if total > 0 else 1
    
    log_audit('ACCESS', 'audit')
    return render_template('admin_audit.html', 
                         logs=logs, 
                         page=page, 
                         total_paginas=total_paginas,
                         filtro_accion=filtro_accion,
                         filtro_modulo=filtro_modulo,
                         filtro_desde=filtro_desde,
                         filtro_hasta=filtro_hasta)


@admin_bp.route('/configuracion')
@admin_required
def configuracion():
    if session.get('admin_rol') != 'SUPERADMIN':
        flash('Solo SUPERADMIN puede gestionar la configuración', 'danger')
        return redirect(url_for('admin.tenants'))
    
    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM configuracion ORDER BY clave")
        configs = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()
    
    log_audit('ACCESS', 'configuracion')
    return render_template('admin_configuracion.html', configs=configs)


@admin_bp.route('/configuracion/guardar', methods=['POST'])
@admin_required
def configuracion_guardar():
    if session.get('admin_rol') != 'SUPERADMIN':
        flash('Solo SUPERADMIN puede gestionar la configuración', 'danger')
        return redirect(url_for('admin.tenants'))
    
    d = request.form
    config_id = d.get('id')
    clave = d.get('clave', '').strip().upper()
    valor = d.get('valor', '')
    descripcion = d.get('descripcion', '').strip()
    
    if not clave:
        flash('La clave es obligatoria', 'danger')
        return redirect(url_for('admin.configuracion'))
    
    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        
        if config_id:
            cursor.execute("""
                UPDATE configuracion SET 
                    clave = %s, valor = %s, descripcion = %s
                WHERE id = %s
            """, (clave, valor, descripcion, config_id))
            msg = 'Configuración actualizada correctamente'
            log_audit('UPDATE', 'configuracion', {'clave': clave})
        else:
            cursor.execute("""
                INSERT INTO configuracion (clave, valor, descripcion)
                VALUES (%s, %s, %s)
            """, (clave, valor, descripcion))
            msg = 'Configuración creada correctamente'
            log_audit('CREATE', 'configuracion', {'clave': clave})
        
        conn.commit()
        clear_config_cache()
        flash(msg, 'success')
        cursor.close()
    except Exception as e:
        conn.rollback()
        if is_duplicate_key_error(e):
            flash('La clave ya existe. Elija otra.', 'danger')
            log_audit('ERROR', 'configuracion', {'error': 'clave duplicada'})
        else:
            flash(f'Error: {str(e)}', 'danger')
            log_audit('ERROR', 'configuracion', {'error': str(e)})
    finally:
        conn.close()
    
    return redirect(url_for('admin.configuracion'))


@admin_bp.route('/configuracion/eliminar/<int:config_id>')
@admin_required
def configuracion_eliminar(config_id):
    if session.get('admin_rol') != 'SUPERADMIN':
        flash('Solo SUPERADMIN puede gestionar la configuración', 'danger')
        return redirect(url_for('admin.tenants'))
    
    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM configuracion WHERE id = %s", (config_id,))
        conn.commit()
        clear_config_cache()
        filas = cursor.rowcount
        cursor.close()
        
        if filas > 0:
            flash('Configuración eliminada.', 'success')
            log_audit('DELETE', 'configuracion', {'id': config_id})
        else:
            flash('Configuración no encontrada.', 'warning')
    except Exception as e:
        conn.rollback()
        flash(f'Error: {str(e)}', 'danger')
        log_audit('ERROR', 'configuracion', {'error': str(e)})
    finally:
        conn.close()
    
    return redirect(url_for('admin.configuracion'))


@admin_bp.route('/intercambio')
@admin_required
def intercambio():
    if session.get('admin_rol') != 'SUPERADMIN':
        flash('Solo SUPERADMIN puede monitorear el intercambio', 'danger')
        return redirect(url_for('admin.tenants'))

    conn_admin = _get_admin_connection()
    try:
        cursor = conn_admin.cursor()
        cursor.execute("SELECT clave, valor, descripcion FROM configuracion WHERE clave LIKE 'INTERCAMBIO%' ORDER BY clave")
        config_intercambio = cursor.fetchall()
        cursor.close()
    finally:
        conn_admin.close()

    conn_int = get_intercambio_connection()
    try:
        cursor_int = conn_int.cursor()
        conteo = {'pendiente': 0, 'procesado': 0, 'error': 0}
        errores = []
        for m, conf in MODULOS.items():
            cursor_int.execute(
                f"SELECT estado, COUNT(*) AS total FROM {conf['tabla']} GROUP BY estado")
            for r in cursor_int.fetchall():
                conteo[r['estado']] = conteo.get(r['estado'], 0) + r['total']

            cursor_int.execute(
                f"SELECT * FROM {conf['tabla']} WHERE estado = 'error' "
                f"ORDER BY id DESC LIMIT 100")
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
            "SELECT * FROM intercambio_log ORDER BY id DESC LIMIT 20")
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
@admin_required
def intercambio_procesar():
    if session.get('admin_rol') != 'SUPERADMIN':
        flash('Solo SUPERADMIN puede procesar el intercambio', 'danger')
        return redirect(url_for('admin.tenants'))

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
    except Exception as e:
        flash(f"Error al procesar el intercambio: {str(e)}", 'danger')
        log_audit('ERROR', 'intercambio', {'error': str(e)})
    return redirect(url_for('admin.intercambio'))


@admin_bp.route('/intercambio/reintentar', methods=['POST'])
@admin_required
def intercambio_reintentar():
    if session.get('admin_rol') != 'SUPERADMIN':
        flash('Solo SUPERADMIN puede reintentar registros', 'danger')
        return redirect(url_for('admin.tenants'))

    try:
        n = reintentar_todo()
        flash(f"{n} registro(s) en error devuelto(s) a pendiente.", 'info')
        log_audit('UPDATE', 'intercambio', {'reintentados': n})
    except Exception as e:
        flash(f"Error: {str(e)}", 'danger')
        log_audit('ERROR', 'intercambio', {'error': str(e)})
    return redirect(url_for('admin.intercambio'))


@admin_bp.route('/parametros/editar/<int:tenant_id>', methods=['GET', 'POST'])
@admin_required
def parametros_editar(tenant_id):
    if session.get('admin_rol') != 'SUPERADMIN':
        flash('Solo SUPERADMIN puede gestionar parámetros', 'danger')
        return redirect(url_for('admin.tenants'))
    
    conn_admin = _get_admin_connection()
    
    try:
        cursor_admin = conn_admin.cursor()
        cursor_admin.execute("SELECT id, nombre FROM tenants WHERE activo = 1 ORDER BY nombre")
        tenants_list = cursor_admin.fetchall()
        
        cursor_admin.execute("""
            SELECT id, nombre, razon_social, cuit, direccion, telefono, email,
                   nombredelalmacen, metodosdepicking, metodo_picking_default,
                   bajostock, dias_filtro_fechas, proveedor_api_ia, api_key, modelo_api_ia,
                   contexto, prompt
            FROM tenants WHERE id = %s
        """, (tenant_id,))
        tenant_actual = cursor_admin.fetchone()
        
        if request.method == 'POST':
            d = request.form
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
                d.get('cuit', ''),
                d.get('direccion', ''),
                d.get('telefono', ''),
                d.get('email', ''),
                d.get('nombredelalmacen', ''),
                picking_json,
                metodo_default,
                float(d.get('bajostock') or 0),
                int(d.get('dias_filtro_fechas') or 30),
                d.get('proveedor_api_ia', ''),
                d.get('api_key', ''),
                d.get('modelo_api_ia', ''),
                d.get('contexto', ''),
                d.get('prompt', ''),
                tenant_id
            ))
            conn_admin.commit()
            
            flash('Parámetros actualizados correctamente', 'success')
            log_audit('UPDATE', 'parametros', {'tenant_id': tenant_id})
            
            return redirect(url_for('admin.tenants'))
        
        if tenant_actual:
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
                'api_key': tenant_actual.get('api_key') or '',
                'modelo_api_ia': tenant_actual.get('modelo_api_ia') or '',
                'contexto': tenant_actual.get('contexto') or '',
                'prompt': tenant_actual.get('prompt') or '',
            }
            log_audit('ACCESS', 'parametros', {'tenant_id': tenant_id})
            return render_template('admin_parametros_editar.html', param=param, tenants=tenants_list, tenant_id=tenant_id)
        else:
            flash('Tenant no encontrado', 'danger')
            return redirect(url_for('admin.tenants'))
    finally:
        conn_admin.close()
