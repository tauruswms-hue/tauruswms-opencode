from flask import Flask, session
from werkzeug.security import check_password_hash, generate_password_hash
import os
import datetime
import base64
from dotenv import load_dotenv
from pathlib import Path
from modules.db_config import _get_admin_connection
from modules.sql_dialect import insert_ignore_sql

app = Flask(__name__)

env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

app.secret_key = os.getenv('ADMIN_SECRET_KEY', 'dev-fallback')
app.register_blueprint(__import__('modules.admin', fromlist=['admin_bp']).admin_bp)

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
