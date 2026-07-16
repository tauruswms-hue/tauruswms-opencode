import pymysql
import os
from pathlib import Path
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash


def crear_usuario(usuario, clave, mail, nombre, rol):
    print("🧪 Creando Usuario " + usuario)
    print("=" * 50)
    env_path = Path('.') / '.env'
    load_dotenv(dotenv_path=env_path)

    DB_CONFIG = {
        'host': os.getenv('DB_HOST'),
        'user': os.getenv('DB_USER'),
        'password': os.getenv('DB_PASSWORD'),
        'database': os.getenv('DB_NAME'),
        'charset': os.getenv('DB_CHARSET'),
        'port': int(os.getenv('DB_PORT'))
    }

    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        print("✅ Conectado a MySQL")
        password_hash = generate_password_hash(clave)

        cursor.execute("""
            INSERT IGNORE INTO usuarios 
            (username, email, password_hash, nombre_completo, rol) 
            VALUES (%s, %s, %s, %s, %s)
        """, (usuario, mail, password_hash, nombre, rol))

        print("   ✅ Usuario creado: " + usuario)
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    usuario = "prueba"
    clave = "prueba"
    mail = "prueba@tauros.com"
    nombre = "prueba"
    rol = "ADMIN"
    crear_usuario(usuario, clave, mail, nombre, rol)