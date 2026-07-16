import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

_cached_config = None


def _get_env(key, default=''):
    return os.getenv(key, default)


def _get_admin_connection():
    return pymysql.connect(
        host=_get_env('DB_ADMIN_HOST', 'localhost'),
        user=_get_env('DB_ADMIN_USER', 'taurus_admin'),
        password=_get_env('DB_ADMIN_PASSWORD', 'Taurus_2001'),
        database=_get_env('DB_ADMIN_NAME', 'taurus_admin'),
        charset=_get_env('DB_CHAR_SET', 'utf8mb4'),
        port=int(_get_env('DB_ADMIN_PORT', '3306')),
        cursorclass=pymysql.cursors.DictCursor
    )


def get_db_config():
    global _cached_config
    if _cached_config is not None:
        return _cached_config.copy()
    
    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT clave, valor FROM configuracion WHERE clave IN ('DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DB_CHAR_SET')")
        rows = cursor.fetchall()
        cursor.close()
        
        config = {}
        for row in rows:
            clave = row['clave']
            valor = row['valor'] if row['valor'] is not None else ''
            config[clave] = str(valor)
        
        if len(config) < 6:
            raise Exception(f"Configuración incompleta en BD. Se encontraron {len(config)} de 6 parámetros requeridos.")
        
        _cached_config = config
        return config.copy()
    finally:
        conn.close()


def clear_config_cache():
    global _cached_config
    _cached_config = None


def get_db_connection():
    config = get_db_config()
    return pymysql.connect(
        host=config['DB_HOST'],
        user=config['DB_USER'],
        password=config['DB_PASSWORD'],
        database=config['DB_NAME'],
        charset=config['DB_CHAR_SET'],
        port=int(config['DB_PORT']),
        cursorclass=pymysql.cursors.DictCursor
    )
