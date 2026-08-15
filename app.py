import datetime
import json
import logging
import os
import time
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

from modules.api import api_bp
from modules.bootstrap import (
    check_default_secrets,
    harden_session_config,
    register_error_handlers,
)
from modules.categorias import categorias_bp
from modules.clases_pedido import clases_pedido_bp
from modules.clientes import clientes_bp
from modules.context import (
    LOGIN_IDLE_TIMEOUT_SECONDS,
    SESSION_MAX_AGE_SECONDS,
    get_tenant_filter,
)
from modules.db_config import (
    _get_admin_connection,
    get_db_connection,
    get_db_engine,
    get_wms_runtime_config,
    test_connection,
)
from modules.despacho import despacho_bp
from modules.intercambio import intercambio_bp
from modules.inventario import inventario_bp
from modules.materiales import materiales_bp
from modules.movil import movil_bp
from modules.omc import omc_bp
from modules.parametros import parametros_bp
from modules.pedidos import pedidos_bp
from modules.permisos_cache import obtener_rutas_cached
from modules.proveedores import proveedores_bp
from modules.recepciones import recepciones_bp
from modules.reportes import reportes_bp
from modules.rutas import rutas_bp
from modules.schema_generator import ROUTE_CATALOG
from modules.sql_dialect import quote as sql_quote
from modules.stockcontable import stockcontable_bp
from modules.tipoubicacion import tipoubicacion_bp
from modules.transportes import transportes_bp
from modules.ubicaciones import ubicaciones_bp
from modules.unidades import unidades_bp
from modules.zonas import zonas_bp

app = Flask(__name__)
app.register_blueprint(materiales_bp)
app.register_blueprint(ubicaciones_bp)
app.register_blueprint(parametros_bp)
app.register_blueprint(unidades_bp)
app.register_blueprint(tipoubicacion_bp)
app.register_blueprint(categorias_bp)
app.register_blueprint(proveedores_bp)
app.register_blueprint(clientes_bp)
app.register_blueprint(transportes_bp)
app.register_blueprint(rutas_bp)
app.register_blueprint(pedidos_bp)
app.register_blueprint(clases_pedido_bp)
app.register_blueprint(stockcontable_bp)
app.register_blueprint(recepciones_bp)
app.register_blueprint(zonas_bp)
app.register_blueprint(omc_bp)
app.register_blueprint(inventario_bp)
app.register_blueprint(despacho_bp)
app.register_blueprint(intercambio_bp)
app.register_blueprint(movil_bp)
app.register_blueprint(api_bp)
app.register_blueprint(reportes_bp)

env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

APP_ENV = os.getenv('APP_ENV', 'development').strip().lower()

_SECRET_KEY = os.getenv('SECRET_KEY')
if not _SECRET_KEY:
    raise RuntimeError("Falta SECRET_KEY en .env (ver .env.example)")
app.secret_key = _SECRET_KEY

check_default_secrets(APP_ENV, [
    ('SECRET_KEY', os.getenv('SECRET_KEY')),
    ('ADMIN_SECRET_KEY', os.getenv('ADMIN_SECRET_KEY')),
    ('SECRET_SALT', os.getenv('SECRET_SALT')),
    ('DB_ADMIN_PASSWORD', os.getenv('DB_ADMIN_PASSWORD')),
    ('DB_PASSWORD', os.getenv('DB_PASSWORD')),
    ('DB_INTERCAMBIO_PASSWORD', os.getenv('DB_INTERCAMBIO_PASSWORD')),
], logger)

harden_session_config(app, APP_ENV)

csrf = CSRFProtect(app)
csrf.exempt(api_bp)

limiter = Limiter(key_func=get_remote_address, storage_uri="memory://", app=app)
limiter.limit("60 per minute")(api_bp)

register_error_handlers(app, logger)


# ============================================================================
# FUNCIONES GENERALES
# ============================================================================
def verificar_mysql():
    try:
        conn = get_db_connection()
        conn.close()
        return True, "✅ Motor BD Conectado"
    except Exception as e:
        parte1 = str(e)[:60]
        parte2 = str(e)[60:]
        todo = parte1 + "\n" + parte2
        return False, f"⚠️ Motor BD no disponible: {todo!s}"


def obtener_rutas_por_rol(rol):
    """Obtiene las rutas habilitadas para un rol específico.

    roles_rutas vive en taurus_admin, no en taurus_wms.
    El resultado se cachea por rol (TTL PERMISOS_CACHE_TTL, por defecto 30s)
    para no abrir una conexion admin en cada request; los cambios de rutas en
    el panel admin aplican sin re-login dentro del TTL.
    """

    def _consultar():
        conn = _get_admin_connection()
        cursor = conn.cursor()

        # Verificar si el rol tiene acceso a todas las rutas (*)
        sentencia = "SELECT ruta FROM roles_rutas WHERE rol = %s"
        cursor.execute(sentencia, (rol,))
        rutas = cursor.fetchall()

        cursor.close()
        conn.close()

        # Si hay una ruta con '*', significa acceso total
        for ruta in rutas:
            if ruta['ruta'] == '*':
                return ['*']  # Acceso total

        # Si no, devolver la lista de rutas específicas
        return [ruta['ruta'] for ruta in rutas]

    try:
        return obtener_rutas_cached(rol, _consultar)
    except Exception as e:
        logger.error("Error al obtener rutas por rol: %s", e)
        return []


def _match_permiso(permiso, path, ruta):
    """Evalúa si un patrón de permiso coincide con el path/endpoint actual."""
    if permiso == path or (ruta and permiso == ruta):
        return True
    if permiso.endswith('/*'):
        base = permiso[:-2]
        return path == base or path.startswith(base + '/')
    if permiso.endswith('*'):
        return path.startswith(permiso[:-1])
    return False


def _ruta_en_catalogo(path):
    """Indica si el path actual es una ruta gestionada por roles (ROUTE_CATALOG)."""
    for grupo in ROUTE_CATALOG:
        for permiso in grupo['rutas']:
            if _match_permiso(permiso, path, None):
                return True
    return False


def verificar_permiso_ruta(ruta, rol):
    """Verifica si un rol tiene permiso para acceder a la ruta actual.

    Los permisos se evalúan contra el path real (request.path) con soporte de
    comodines:
      - exacto:      "/materiales"
      - prefijo:     "/inventario/*" cubre "/inventario" y "/inventario/crear"
      - parcial:     "/recepciones/buscar_*" cubre cualquier subruta
      - acceso total: "*"

    Las rutas que no están en ROUTE_CATALOG no se controlan por roles: solo
    requieren autenticación (login, logout, index, helpers internos, etc.).
    """
    if not rol:
        return False

    # SUPERADMIN tiene acceso total (coherente con el middleware)
    if rol == 'SUPERADMIN':
        return True

    rutas_habilitadas = session.get('rutas_permitidas')
    if rutas_habilitadas is None:
        rutas_habilitadas = obtener_rutas_por_rol(rol)

    # Si tiene acceso total (*)
    if '*' in rutas_habilitadas:
        return True

    path = request.path

    # Rutas no gestionadas por roles: solo requieren autenticación
    if not _ruta_en_catalogo(path):
        return True

    return any(_match_permiso(permiso, path, ruta) for permiso in rutas_habilitadas)


def tiene_permiso_ruta(path_objetivo):
    """Indica si el usuario actual tiene permiso sobre una ruta (para la UI)."""
    rol = session.get('rol')
    if not rol:
        return False
    if rol == 'SUPERADMIN':
        return True
    rutas = session.get('rutas_permitidas')
    if not rutas:
        rutas = obtener_rutas_por_rol(rol)
    if '*' in rutas:
        return True
    return any(_match_permiso(permiso, path_objetivo, None) for permiso in rutas)


app.jinja_env.globals['tiene_permiso_ruta'] = tiene_permiso_ruta


def verificar_permiso_decorator(f):
    """Decorador para verificar permisos en rutas específicas"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Debe iniciar sesión para acceder a esta página', 'error')
            return redirect(url_for('login'))

        rol = session.get('rol')
        ruta_actual = request.endpoint

        if not verificar_permiso_ruta(ruta_actual, rol):
            flash('No tiene permisos para acceder a esta página', 'error')
            return redirect(url_for('index'))

        return f(*args, **kwargs)

    return decorated_function


# ============================================================================
# RUTAS PRINCIPALES
# ============================================================================
@app.route('/')
def index():
    if 'user_id' not in session or 'login_timestamp' not in session:
        return redirect(url_for('login'))

    tiempo_transcurrido = time.time() - session['login_timestamp']
    if tiempo_transcurrido > SESSION_MAX_AGE_SECONDS:
        session.clear()
        flash('La sesión ha expirado. Por favor, inicie sesión nuevamente.', 'info')
        return redirect(url_for('login'))

    # Renovar timestamp en cada visita al dashboard
    session['login_timestamp'] = time.time()

    estado_db = verificar_mysql()

    tenant_id = get_tenant_filter()
    pedidos_por_estado = {'Pendiente': 0, 'Preparado': 0, 'Despachado': 0}
    stock_por_tipo = {'Libre Venta': 0, 'Calidad': 0, 'Bloqueado': 0, 'Mal Estado': 0}
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT estado, COUNT(*) as total 
            FROM pedidos_cabecera 
            WHERE (%s IS NULL OR tenant_id = %s)
            GROUP BY estado
        """, (tenant_id, tenant_id))
        for row in cursor.fetchall():
            if row['estado'] in pedidos_por_estado:
                pedidos_por_estado[row['estado']] = row['total']

        cursor.execute("""
            SELECT TipoStock, SUM(StockTotal) AS total
            FROM stockcontable
            WHERE (%s IS NULL OR tenant_id = %s)
            GROUP BY TipoStock
        """, (tenant_id, tenant_id))
        for row in cursor.fetchall():
            clave = str(row['TipoStock']).upper()
            for k in stock_por_tipo:
                if k.upper() == clave:
                    stock_por_tipo[k] = int(row['total'])
                    break

        cursor.execute(f"""
            SELECT t.{sql_quote('descripcion')} AS tipo_ubi, SUM(sc.StockTotal) AS total
            FROM stockcontable sc
            JOIN ubicaciones u  ON sc.Ubicacion = u.id
            JOIN tipoubicacion t ON u.tipoubicacion = t.id
            WHERE (%s IS NULL OR sc.tenant_id = %s)
            GROUP BY t.id, t.{sql_quote('descripcion')}
            ORDER BY total DESC
        """, (tenant_id, tenant_id))
        stock_por_tipo_ubi = [
            {'tipo': row['tipo_ubi'], 'total': int(row['total'])}
            for row in cursor.fetchall()
        ]

        cursor.execute("""
            SELECT COUNT(*) as total 
            FROM recepciones_cabecera 
            WHERE estado = 'Abierta' AND (%s IS NULL OR tenant_id = %s)
        """, (tenant_id, tenant_id))
        row = cursor.fetchone()
        recepciones_abiertas = row['total'] if row else 0

        cursor.execute("""
            SELECT COUNT(*) as total 
            FROM omc 
            WHERE estado = 'Pendiente' AND (%s IS NULL OR tenant_id = %s)
        """, (tenant_id, tenant_id))
        row = cursor.fetchone()
        omc_pendientes = row['total'] if row else 0

        cursor.close()
        conn.close()
    except Exception:
        stock_por_tipo_ubi = []
        recepciones_abiertas = 0
        omc_pendientes = 0

    stock_total = sum(stock_por_tipo.values())

    return render_template('index.html',
                           estado_db=estado_db[1],
                           estado_db_ok=estado_db[0],
                           pedidos_por_estado=pedidos_por_estado,
                           stock_por_tipo=stock_por_tipo,
                           stock_total=stock_total,
                           stock_por_tipo_ubi=stock_por_tipo_ubi,
                           recepciones_abiertas=recepciones_abiertas,
                           omc_pendientes=omc_pendientes)


# ============================================================================
@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per 15 minutes", methods=['POST'])
def login():
    if 'user_id' in session and 'login_timestamp' in session:
        tiempo_transcurrido = time.time() - session['login_timestamp']
        if tiempo_transcurrido <= LOGIN_IDLE_TIMEOUT_SECONDS:  # 5 minutos
            return redirect(url_for('index'))
        else:
            session.clear()
            flash('La sesión ha expirado. Por favor, inicie sesión nuevamente.', 'info')

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password')
        if not username or not password:
            flash('Debe ingresar usuario y contraseña', 'error')
            return render_template('login.html')
        try:
            conn = _get_admin_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.id, u.username, u.password_hash, u.nombre, u.rol, u.tenant_id, u.activo as usuario_activo,
                       t.nombre as tenant_nombre, t.activo as tenant_activo,
                       u.sidebar_preferences
                FROM usuarios u 
                JOIN tenants t ON u.tenant_id = t.id 
                WHERE u.username = %s
            """, (username,))
            usuario = cursor.fetchone()
            cursor.close()
            conn.close()

            if not usuario:
                flash('Usuario o contraseña incorrectos', 'error')
            elif not usuario['usuario_activo']:
                flash('El usuario está desactivado. Contacte al administrador.', 'error')
            elif not usuario['tenant_activo']:
                flash('La empresa está desactivada. Contacte al administrador.', 'error')
            elif check_password_hash(usuario['password_hash'], password):
                if not usuario['tenant_id']:
                    flash('Error: El usuario no tiene un tenant asignado. Contacte al administrador.', 'error')
                    return render_template('login.html')
                
                session['user_id'] = usuario['id']
                session['username'] = usuario['username']
                session['nombre'] = usuario['nombre']
                session['rol'] = usuario['rol']
                session['login_timestamp'] = time.time()
                session.permanent = True
                session['tenant_id'] = usuario['tenant_id']
                session['tenant_nombre'] = usuario['tenant_nombre']

                rutas_permitidas = obtener_rutas_por_rol(usuario['rol'])
                session['rutas_permitidas'] = rutas_permitidas

                sidebar_prefs = usuario.get('sidebar_preferences')
                if sidebar_prefs:
                    session['sidebar_collapsed'] = json.loads(sidebar_prefs) if isinstance(sidebar_prefs, str) else sidebar_prefs
                else:
                    session['sidebar_collapsed'] = {}

                flash(f'Bienvenido al sistema {usuario["nombre"]}', 'success')
                
                return redirect(url_for('index'))
            else:
                flash('Usuario o contraseña incorrectos', 'error')

        except Exception as e:
            logger.error("Error en login: %s", e, exc_info=True)
            flash(f'Error al iniciar sesión: {e!s}', 'error')

    return render_template('login.html')


# ============================================================================
@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada exitosamente', 'info')
    return redirect(url_for('login'))


# ============================================================================
# RUTA: CONFIGURACIÓN DE BASE DE DATOS
# ============================================================================
@app.route('/configuracion-db')
@verificar_permiso_decorator
def configuracion_db():
    db_config = get_db_config_from_env()
    db_config['LAST_MODIFIED'] = get_env_file_modification_time()
    logger.info("Configuración DB cargada: %s:%s/%s", db_config['DB_HOST'], db_config['DB_PORT'], db_config['DB_NAME'])
    return render_template('configuracion_db.html', db_config=db_config)


# ============================================================================
# FUNCIONES AUXILIARES PARA CONFIGURACIÓN
# ============================================================================
def get_db_config_from_env():
    """Obtiene la configuración de BD desde la tabla configuracion en taurus_admin."""
    config = get_wms_runtime_config()
    return {
        'DB_HOST': config['host'],
        'DB_PORT': str(config['port']),
        'DB_NAME': config['database'],
        'DB_USER': config['user'],
        'DB_PASSWORD': config['password'],
        'DB_CHARSET': config['charset'],
    }


def get_env_file_modification_time():
    """Obtiene la fecha de última modificación del archivo .env"""
    env_path = Path('.') / '.env'
    if env_path.exists():
        timestamp = env_path.stat().st_mtime
        return datetime.datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y %H:%M:%S')
    return None


# ============================================================================
# RUTA: PROBAR CONEXIÓN A BASE DE DATOS
# ============================================================================
@app.route('/test_db_connection', methods=['POST'])
@verificar_permiso_decorator
def test_db_connection():
    """Prueba la conexión a la base de datos con la configuración proporcionada"""
    try:
        data = request.get_json()

        # Recargar .env para asegurar valores actuales
        load_dotenv(dotenv_path=env_path, override=True)

        # Para depuración (puedes borrar esto después)
        logger.info("Verificando conexión a BD...")
        logger.debug("Host: %s", data.get('host', os.getenv('DB_HOST')))
        logger.debug("Usuario: %s", data.get('username', os.getenv('DB_USER')))
        logger.debug("Base de datos: %s", data.get('database', os.getenv('DB_NAME')))

        # Determinar qué contraseña usar
        password_input = data.get('password', '')
        if password_input and password_input != '********':
            # Usar la contraseña ingresada en el formulario (si no es el placeholder)
            password = password_input
            logger.debug("Usando contraseña del formulario")
        else:
            # Usar la contraseña del .env
            password = os.getenv('DB_PASSWORD', '')
            logger.debug("Usando contraseña del archivo .env")

        # Configuración de prueba
        test_config = {
            'host': data.get('host', os.getenv('DB_HOST', 'localhost')),
            'port': int(data.get('port', os.getenv('DB_PORT', 3306))),
            'user': data.get('username', os.getenv('DB_USER', 'taurus')),
            'password': password,
            'database': data.get('database', os.getenv('DB_NAME', 'taurus_wms')),
            'charset': data.get('charset', os.getenv('DB_CHARSET', 'utf8mb4')),
        }

        # Intentar conexión con el engine efectivo (la app decide el engine;
        # los datos del formulario solo aportan host/puerto/usuario/password).
        engine = get_db_engine()
        test_connection(engine, **test_config)

        return jsonify({
            'success': True,
            'message': f'✅ Conexión exitosa a {test_config["database"]} en {test_config["host"]}:{test_config["port"]}'
        })

    except Exception as e:
        error_msg = str(e)
        logger.error("Error de conexión a BD: %s", error_msg)

        if "Access denied" in error_msg:
            error_msg = "Acceso denegado: Usuario o contraseña incorrectos"
        elif "Unknown database" in error_msg:
            error_msg = f"Base de datos '{test_config.get('database', '')}' no existe"
        elif "Can't connect" in error_msg:
            error_msg = f"No se puede conectar al servidor {test_config.get('host', '')}:{test_config.get('port', '')}"
        elif "Connection refused" in error_msg:
            error_msg = f"Conexión rechazada. Verifica que MySQL esté corriendo en {test_config.get('host', '')}:{test_config.get('port', '')}"

        return jsonify({
            'success': False,
            'message': f'❌ {error_msg}'
        })


# ============================================================================
# RUTAS DE GESTIÓN (TODAS PROTEGIDAS CON EL DECORADOR)
# ============================================================================

@app.route('/api/xlsx_sheetnames', methods=['POST'])
def api_xlsx_sheetnames():
    """Lista las pestañas de un archivo XLSX para que el importador permita elegir."""
    from modules.batch_utils import xlsx_sheetnames
    file = request.files.get('archivo')
    if not file or file.filename == '':
        return jsonify({'error': 'No se proporcionó archivo'}), 400
    if not file.filename.lower().endswith('.xlsx'):
        return jsonify({'error': 'El archivo no es XLSX'}), 400
    try:
        return jsonify({'hojas': xlsx_sheetnames(file)})
    except Exception as e:
        return jsonify({'error': f'Error al leer el archivo: {e!s}'}), 400


@app.route('/sidebar-preferences', methods=['POST'])
def guardar_sidebar_preferences():
    """Guarda las preferencias de sidebar del usuario"""
    if 'user_id' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    
    try:
        data = request.get_json()
        section = data.get('section')
        value = data.get('value')
        
        collapsed = session.get('sidebar_collapsed', {})
        if isinstance(collapsed, str):
            collapsed = json.loads(collapsed)
        
        if section is not None:
            collapsed[section] = value
        
        conn = _get_admin_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE usuarios SET sidebar_preferences = %s WHERE id = %s",
                    (json.dumps(collapsed), session['user_id'])
                )
            conn.commit()
            session['sidebar_collapsed'] = collapsed
        finally:
            conn.close()
        
        return jsonify({'success': True, 'collapsed': collapsed})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# RUTAS ADICIONALES
# ============================================================================
@app.route('/estado')
@verificar_permiso_decorator
def estado():
    _mysql_ok, mysql_msg = verificar_mysql()
    fecha_hora = datetime.datetime.fromtimestamp(session.get('login_timestamp', time.time()))
    fecha_formateada = fecha_hora.strftime('%d/%m/%Y %H:%M:%S')
    info = {
        'mysql': mysql_msg,
        'sesion_activa': 'user_id' in session,
        'usuario': session.get('username', 'NA'),
        'rol': session.get('rol', 'NA'),
        'inicio': fecha_formateada
    }

    return render_template('estado.html', info=info)


# ============================================================================
# MIDDLEWARE PARA VERIFICAR AUTENTICACIÓN Y PERMISOS
# ============================================================================
@app.before_request
def verificar_autenticacion_y_permisos():
    """Verificar autenticación y permisos para rutas protegidas"""

    # Lista de rutas públicas (no requieren autenticación)
    rutas_publicas = ['login', 'static']

    # La API REST /api/v1 se autentica por token Bearer (no usa sesión).
    if request.path.startswith('/api/v1/'):
        return

    # Si la ruta es pública, permitir acceso
    if request.endpoint in rutas_publicas:
        return

    # Verificar si el usuario está autenticado
    if 'user_id' not in session:
        flash('Debe iniciar sesión para acceder a esta página', 'error')
        return redirect(url_for('login'))

    # Verificar expiración de sesión
    if 'login_timestamp' in session:
        tiempo_transcurrido = time.time() - session['login_timestamp']
        if tiempo_transcurrido > SESSION_MAX_AGE_SECONDS:  # 8 horas
            session.clear()
            flash('La sesión ha expirado. Por favor, inicie sesión nuevamente.', 'info')
            return redirect(url_for('login'))

    # Verificar permisos por rol (aplica a todos los tenants, de forma global).
    # Se recalculan las rutas permitidas en cada request para que los cambios
    # hechos en el panel admin (roles_rutas) apliquen sin esperar re-login.
    rol = session.get('rol')
    if rol:
        session['rutas_permitidas'] = obtener_rutas_por_rol(rol)
        if rol != 'SUPERADMIN' and not verificar_permiso_ruta(request.endpoint, rol):
            flash('No tiene permisos para acceder a esta página', 'error')
            return redirect(url_for('index'))


# ============================================================================
# INICIO DE LA APLICACIÓN
# ============================================================================
if __name__ == '__main__':
    mysql_ok, mysql_msg = verificar_mysql()
    logger.info("Estado BD (%s): %s", get_db_engine(), mysql_msg)
    logger.info("=" * 50)
    logger.info("TAURUS WMS")
    logger.info("=" * 50)
    logger.info("URL http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)