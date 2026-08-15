from pathlib import Path

from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

from modules.db_config import get_db_connection
from modules.sql_dialect import insert_ignore_sql


def crear_usuario(usuario, clave, mail, nombre, rol):
    print("🧪 Creando Usuario " + usuario)
    print("=" * 50)
    env_path = Path('.') / '.env'
    load_dotenv(dotenv_path=env_path)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        print("✅ Conectado a BD")
        password_hash = generate_password_hash(clave)

        cols = ['username', 'email', 'password_hash', 'nombre_completo', 'rol']
        sql = insert_ignore_sql('usuarios', cols)
        cursor.execute(sql, (usuario, mail, password_hash, nombre, rol))

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