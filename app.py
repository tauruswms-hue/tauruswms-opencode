from flask import Flask, render_template, session, redirect, url_for, request, flash, jsonify, abort
from werkzeug.security import check_password_hash
import pymysql
import os
import time
import datetime
import json
from dotenv import load_dotenv
from pathlib import Path
from functools import wraps

from modules.materiales import materiales_bp
from modules.ubicaciones import ubicaciones_bp
from modules.parametros import parametros_bp
from modules.unidades import unidades_bp
from modules.tipoubicacion import tipoubicacion_bp
from modules.categorias import categorias_bp
from modules.proveedores import proveedores_bp
from modules.clientes import clientes_bp
from modules.transportes import transportes_bp
from modules.rutas import rutas_bp
from modules.pedidos import pedidos_bp
from modules.clases_pedido import clases_pedido_bp
from modules.stockcontable import stockcontable_bp
from modules.recepciones import recepciones_bp
from modules.zonas import zonas_bp
from modules.omc import omc_bp
from modules.inventario import inventario_bp
from modules.despacho import despacho_bp
from modules.db_config import get_db_config, clear_config_cache


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

app.secret_key = 'clave-secreta-simple-taurus'
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)


def get_db_config_from_table():
    config = get_db_config()
    return {
        'host': config.get('DB_HOST', 'localhost'),
        'user': config.get('DB_USER', 'taurus'),
        'password': config.get('DB_PASSWORD', ''),
        'database': config.get('DB_NAME', 'taurus_wms'),
        'charset': config.get('DB_CHAR_SET', 'utf8mb4'),
        'port': int(config.get('DB_PORT', 3306))
    }


try:
    DB_CONFIG = get_db_config_from_table()
except Exception as e:
    print(f"⚠️  No se pudo cargar config de BD desde tabla: {e}")
    print("⚠️  Usando valores por defecto del entorno (.env)")
    DB_CONFIG = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'user': os.getenv('DB_USER', 'taurus'),
        'password': os.getenv('DB_PASSWORD', ''),
        'database': os.getenv('DB_NAME', 'taurus_wms'),
        'charset': os.getenv('DB_CHAR_SET', 'utf8mb4'),
        'port': int(os.getenv('DB_PORT', 3306))
    }

ADMIN_DB_CONFIG = {
    'host': os.getenv('DB_ADMIN_HOST', 'localhost'),
    'user': os.getenv('DB_ADMIN_USER', 'taurus_admin'),
    'password': os.getenv('DB_ADMIN_PASSWORD', 'Taurus_2001'),
    'database': os.getenv('DB_ADMIN_NAME', 'taurus_admin'),
    'charset': os.getenv('DB_CHAR_SET', 'utf8mb4'),
    'port': int(os.getenv('DB_ADMIN_PORT', 3306))
}


# ============================================================================
# FUNCIONES GENERALES
# ============================================================================
def verificar_mysql():
    try:
        conn = pymysql.connect(**DB_CONFIG)
        conn.close()
        return True, "✅ Motor BD Conectado"
    except Exception as e:
        parte1 = str(e)[:60]
        parte2 = str(e)[60:]
        todo = parte1 + "\n" + parte2
        return False, f"⚠️ Motor BD no disponible: {str(todo)}"


def obtener_rutas_por_rol(rol):
    """Obtiene las rutas habilitadas para un rol específico"""
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor(pymysql.cursors.DictCursor)

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

    except Exception as e:
        print(f"Error al obtener rutas por rol: {str(e)}")
        return []


def verificar_permiso_ruta(ruta, rol):
    """Verifica si un rol tiene permiso para acceder a una ruta específica"""
    if not rol:
        return False

    rutas_habilitadas = obtener_rutas_por_rol(rol)

    # Si tiene acceso total (*)
    if '*' in rutas_habilitadas:
        return True

    # Verificar si la ruta está en la lista de rutas habilitadas
    return ruta in rutas_habilitadas


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
    if tiempo_transcurrido > 28800:
        session.clear()
        flash('La sesión ha expirado. Por favor, inicie sesión nuevamente.', 'info')
        return redirect(url_for('login'))

    # Renovar timestamp en cada visita al dashboard
    session['login_timestamp'] = time.time()

    estado_db = verificar_mysql()

    tenant_id = session.get('tenant_id')
    pedidos_por_estado = {'Pendiente': 0, 'Preparado': 0, 'Despachado': 0}
    stock_por_tipo = {'Libre Venta': 0, 'Calidad': 0, 'Bloqueado': 0, 'Mal Estado': 0}
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor(pymysql.cursors.DictCursor)

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
            if row['TipoStock'] in stock_por_tipo:
                stock_por_tipo[row['TipoStock']] = int(row['total'])

        cursor.execute("""
            SELECT t.`descipción` AS tipo_ubi, SUM(sc.StockTotal) AS total
            FROM stockcontable sc
            JOIN ubicaciones u  ON sc.Ubicacion = u.id
            JOIN tipoubicacion t ON u.tipoubicacion = t.id
            WHERE (%s IS NULL OR sc.tenant_id = %s)
            GROUP BY t.id, t.`descipción`
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
def login():
    if 'user_id' in session and 'login_timestamp' in session:
        tiempo_transcurrido = time.time() - session['login_timestamp']
        if tiempo_transcurrido <= 300:  # 5 minutos en segundos
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
            conn = pymysql.connect(**ADMIN_DB_CONFIG)
            cursor = conn.cursor(pymysql.cursors.DictCursor)
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

        except pymysql.Error as e:
            flash(f'Error al conectar con la base de datos: {str(e)}', 'error')
        except Exception as e:
            flash(f'Error inesperado: {str(e)}', 'error')

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
    print(f"📋 Configuración DB cargada: {db_config['DB_HOST']}:{db_config['DB_PORT']}/{db_config['DB_NAME']}")
    return render_template('configuracion_db.html', db_config=db_config)


# ============================================================================
# FUNCIONES AUXILIARES PARA CONFIGURACIÓN
# ============================================================================
def get_db_config_from_env():
    """Obtiene la configuración de BD desde la tabla configuracion en taurus_admin"""
    config = get_db_config()
    return {
        'DB_HOST': config.get('DB_HOST', 'localhost'),
        'DB_PORT': config.get('DB_PORT', '3306'),
        'DB_NAME': config.get('DB_NAME', 'taurus_wms'),
        'DB_USER': config.get('DB_USER', 'taurus'),
        'DB_PASSWORD': config.get('DB_PASSWORD', ''),
        'DB_CHARSET': config.get('DB_CHAR_SET', 'utf8mb4')
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
        print(f"🔐 Verificando conexión a BD...")
        print(f"📋 Host: {data.get('host', os.getenv('DB_HOST'))}")
        print(f"📋 Usuario: {data.get('username', os.getenv('DB_USER'))}")
        print(f"📋 Base de datos: {data.get('database', os.getenv('DB_NAME'))}")

        # Determinar qué contraseña usar
        password_input = data.get('password', '')
        if password_input and password_input != '********':
            # Usar la contraseña ingresada en el formulario (si no es el placeholder)
            password = password_input
            print("🔑 Usando contraseña del formulario")
        else:
            # Usar la contraseña del .env
            password = os.getenv('DB_PASSWORD', '')
            print("🔑 Usando contraseña del archivo .env")

        # Configuración de prueba
        test_config = {
            'host': data.get('host', os.getenv('DB_HOST', 'localhost')),
            'port': int(data.get('port', os.getenv('DB_PORT', 3306))),
            'user': data.get('username', os.getenv('DB_USER', 'taurus')),
            'password': password,
            'database': data.get('database', os.getenv('DB_NAME', 'taurus_wms')),
            'charset': data.get('charset', os.getenv('DB_CHARSET', 'utf8')),
            'connect_timeout': 5
        }

        # Intentar conexión
        connection = pymysql.connect(**test_config)
        connection.close()

        return jsonify({
            'success': True,
            'message': f'✅ Conexión exitosa a {test_config["database"]} en {test_config["host"]}:{test_config["port"]}'
        })

    except pymysql.Error as e:
        error_msg = str(e)
        print(f"❌ Error MySQL: {error_msg}")  # Para depuración

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
    except Exception as e:
        print(f"❌ Error inesperado: {str(e)}")  # Para depuración
        return jsonify({
            'success': False,
            'message': f'❌ Error inesperado: {str(e)}'
        })


# ============================================================================
# RUTAS DE GESTIÓN (TODAS PROTEGIDAS CON EL DECORADOR)
# ============================================================================

@app.route('/ubicaciones')
@verificar_permiso_decorator
def ubicaciones():
    """Gestión de ubicaciones"""
    return render_template('ubicaciones.html')


@app.route('/stock')
@verificar_permiso_decorator
def stock():
    """Consulta de stock"""
    return render_template('stock.html')


@app.route('/entradas')
@verificar_permiso_decorator
def entradas():
    """Registro de entradas"""
    return render_template('entradas.html')


@app.route('/salidas')
@verificar_permiso_decorator
def salidas():
    """Registro de salidas"""
    return render_template('salidas.html')


@app.route('/movimientos')
def movimientos():
    """Redirige al listado de OMC"""
    return redirect(url_for('omc.listar'))


@app.route('/rentradas')
@verificar_permiso_decorator
def rentradas():
    """Registro de entradas"""
    return render_template('entradas.html')


@app.route('/rsalidas')
@verificar_permiso_decorator
def rsalidas():
    """Registro de salidas"""
    return render_template('salidas.html')


@app.route('/reportes')
@verificar_permiso_decorator
def reportes():
    """Reportes y consultas"""
    return render_template('reportes.html')


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
        
        conn = pymysql.connect(**ADMIN_DB_CONFIG)
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


@app.route('/parametros')
@verificar_permiso_decorator
def parametros():
    """Parámetros del sistema"""
    return render_template('parametros.html')


# ============================================================================
# RUTAS ADICIONALES
# ============================================================================
@app.route('/dashboard')
def dashboard():
    return redirect(url_for('index'))


@app.route('/estado')
@verificar_permiso_decorator
def estado():
    mysql_ok, mysql_msg = verificar_mysql()
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


@app.route('/acerca')
def acerca():
    """Página acerca de - Pública"""
    return render_template('acerca.html')


# ============================================================================
# MIDDLEWARE PARA VERIFICAR AUTENTICACIÓN Y PERMISOS
# ============================================================================
@app.before_request
def verificar_autenticacion_y_permisos():
    """Verificar autenticación y permisos para rutas protegidas"""

    # Lista de rutas públicas (no requieren autenticación)
    rutas_publicas = ['login', 'acerca', 'static']

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
        if tiempo_transcurrido > 28800:  # 8 horas
            session.clear()
            flash('La sesión ha expirado. Por favor, inicie sesión nuevamente.', 'info')
            return redirect(url_for('login'))

    # Para rutas que no tienen el decorador pero requieren verificación
    # Nota: La mayoría de las rutas ya tienen @verificar_permiso_decorator
    # Este middleware asegura que todas las rutas (excepto públicas) al menos requieran autenticación


# ============================================================================
# INICIO DE LA APLICACIÓN
# ============================================================================
if __name__ == '__main__':
    mysql_ok, mysql_msg = verificar_mysql()
    print(f"\n📦 Estado MySQL: {mysql_msg}")
    print("=" * 50)
    print("🚀 TAURUS WMS")
    print("=" * 50)
    print("\n🌐 URL http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)