from flask import Flask, session
from werkzeug.security import check_password_hash, generate_password_hash
import pymysql
import os
import datetime
import base64
from dotenv import load_dotenv
from pathlib import Path

app = Flask(__name__)
app.secret_key = 'admin-secret-key-taurus-2024'
app.register_blueprint(__import__('modules.admin', fromlist=['admin_bp']).admin_bp)

env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

SECRET_SALT = os.getenv('SECRET_SALT', 'taurus-wms-salt-2024')

ADMIN_DB_CONFIG = {
    'host': os.getenv('DB_ADMIN_HOST', os.getenv('DB_HOST')),
    'user': os.getenv('DB_ADMIN_USER', os.getenv('DB_USER')),
    'password': os.getenv('DB_ADMIN_PASSWORD', os.getenv('DB_PASSWORD')),
    'database': os.getenv('DB_ADMIN_NAME', 'taurus_admin'),
    'charset': os.getenv('DB_CHARSET', 'utf8mb4'),
    'port': int(os.getenv('DB_ADMIN_PORT', os.getenv('DB_PORT', 3306)))
}


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
        conn = pymysql.connect(**ADMIN_DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT IGNORE INTO admin_usuarios (username, password_hash, nombre, email, rol)
            VALUES ('admin', %s, 'Administrador', 'admin@taurus.local', 'SUPERADMIN')
        """, (generate_password_hash('Admin@2024!'),))
        
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
