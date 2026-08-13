from flask import Flask, session
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash
import os
import datetime
import base64
import logging
from dotenv import load_dotenv
from pathlib import Path
from modules.db_config import _get_admin_connection
from modules.sql_dialect import insert_ignore_sql
from modules.admin import admin_limiter

logger = logging.getLogger(__name__)

app = Flask(__name__)

env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

APP_ENV = os.getenv('APP_ENV', 'development').strip().lower()

_ADMIN_SECRET_KEY = os.getenv('ADMIN_SECRET_KEY')
if not _ADMIN_SECRET_KEY:
    raise RuntimeError("Falta ADMIN_SECRET_KEY en .env (ver .env.example)")
app.secret_key = _ADMIN_SECRET_KEY
app.register_blueprint(__import__('modules.admin', fromlist=['admin_bp']).admin_bp)

csrf = CSRFProtect(app)

admin_limiter.init_app(app)

_DEFAULT_SECRETOS = (
    'taurus-wms-secret-2024-dev', 'taurus-admin-secret-2024-dev',
    'taurus-wms-salt-2024', 'Admin@2024!', 'Taurus_2001', 'dev-fallback',
)


def _check_secretos():
    """Fuerza el cambio de secretos/passwords por defecto en production."""
    valores = [
        ('ADMIN_SECRET_KEY', os.getenv('ADMIN_SECRET_KEY')),
        ('SECRET_KEY', os.getenv('SECRET_KEY')),
        ('SECRET_SALT', os.getenv('SECRET_SALT')),
        ('DB_ADMIN_PASSWORD', os.getenv('DB_ADMIN_PASSWORD')),
        ('DB_PASSWORD', os.getenv('DB_PASSWORD')),
    ]
    encontrados = [f"{k}={v}" for k, v in valores if v and v in _DEFAULT_SECRETOS]
    if encontrados:
        mensaje = ("Se detectaron credenciales/secretos por defecto. Cambiarlos "
                   "antes de producción: " + ", ".join(encontrados))
        if APP_ENV == 'production':
            raise RuntimeError(mensaje)
        logger.warning("[SEGURIDAD] %s", mensaje)


_check_secretos()

# Hardening de sesión
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = (APP_ENV == 'production')
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(hours=8)

SECRET_SALT = os.getenv('SECRET_SALT', 'taurus-wms-salt-2024')


def encode_id(tenant_id):
    if tenant_id is None:
        return ''
    data = f"{int(tenant_id)}:{SECRET_SALT}"
    return base64.urlsafe_b64encode(data.encode()).decode()


@app.template_filter('datetime')
def format_datetime(value):
    if value is None:
        return '-'
    if isinstance(value, str):
        try:
            value = datetime.datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        except:
            return value
    return value.strftime('%d/%m/%Y %H:%M')


@app.template_filter('encode_id')
def encode_id_filter(tenant_id):
    return encode_id(tenant_id)


def init_admin_db():
    """Inicializa la BD admin con el usuario inicial si no existe"""
    try:
        conn = _get_admin_connection()
        cursor = conn.cursor()
        
        cols = ['username', 'password_hash', 'nombre', 'email', 'rol']
        sql = insert_ignore_sql('admin_usuarios', cols)
        cursor.execute(sql, (
            'admin', generate_password_hash('Admin@2024!'),
            'Administrador', 'admin@taurus.local', 'SUPERADMIN'
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Base de datos admin inicializada")
        return True
    except Exception as e:
        print(f"⚠️ Error al inicializar BD admin: {e}")
        return False


if __name__ == '__main__':
    init_admin_db()
    
    print("=" * 50)
    print("🔐 TAURUS WMS - PANEL DE ADMINISTRACIÓN")
    print("=" * 50)
    print("\n🌐 URL http://localhost:5001/admin")
    print("📧 Usuario: admin")
    print("🔑 Contraseña: Admin@2024!")
    print("\n⚠️ CAMBIE LA CONTRASEÑA TRAS EL PRIMER INGRESO")
    print("=" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=5001)
