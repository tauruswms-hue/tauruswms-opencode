import os
from dotenv import load_dotenv

from modules.sql_dialect import set_engine

load_dotenv()

_cached_config = None
_db_engine = None
_intercambio_config_cache = None


def _get_env(key, default=''):
    return os.getenv(key, default)


def _get_admin_connection():
    engine = _get_env('DB_ADMIN_ENGINE', 'mysql').strip().lower()
    driver = _get_driver_for_engine(engine)

    connect_kwargs = dict(
        host=_get_env('DB_ADMIN_HOST', 'localhost'),
        user=_get_env('DB_ADMIN_USER', 'taurus_admin'),
        password=_get_env('DB_ADMIN_PASSWORD', 'Taurus_2001'),
        database=_get_env('DB_ADMIN_NAME', 'taurus_admin'),
    )

    if engine == 'sqlite':
        return driver.connect(connect_kwargs['database'])

    port = int(_get_env('DB_ADMIN_PORT', '3306'))

    if engine == 'mysql':
        connect_kwargs['charset'] = _get_env('DB_CHAR_SET', 'utf8mb4')
        connect_kwargs['port'] = port
        connect_kwargs['cursorclass'] = driver.cursors.DictCursor
    elif engine == 'postgresql':
        connect_kwargs['port'] = port
        connect_kwargs['options'] = f"-c client_encoding={_get_env('DB_CHAR_SET', 'UTF8')}"
        from psycopg2.extras import RealDictCursor
        connect_kwargs['cursor_factory'] = RealDictCursor
    elif engine == 'sqlserver':
        connect_kwargs = dict(
            server=_get_env('DB_ADMIN_HOST', 'localhost'),
            user=_get_env('DB_ADMIN_USER', 'taurus_admin'),
            password=_get_env('DB_ADMIN_PASSWORD', 'Taurus_2001'),
            database=_get_env('DB_ADMIN_NAME', 'taurus_admin'),
            port=port,
        )

    return driver.connect(**connect_kwargs)


def get_db_engine():
    global _db_engine
    if _db_engine is not None:
        return _db_engine
    env_engine = _get_env('DB_ENGINE', '').strip().lower()
    if env_engine in ('mysql', 'postgresql', 'sqlite', 'sqlserver'):
        _db_engine = env_engine
        set_engine(env_engine)
        return _db_engine
    try:
        config = get_db_config()
        engine_val = config.get('DB_ENGINE', 'mysql').strip().lower()
        if engine_val not in ('mysql', 'postgresql', 'sqlite', 'sqlserver'):
            engine_val = 'mysql'
        _db_engine = engine_val
        set_engine(engine_val)
        return _db_engine
    except Exception:
        _db_engine = 'mysql'
        set_engine('mysql')
        return _db_engine


def _get_driver_for_engine(engine):
    if engine == 'postgresql':
        try:
            import psycopg2
            return psycopg2
        except ImportError:
            raise ImportError("psycopg2 no está instalado. Ejecute: pip install psycopg2-binary")
    if engine == 'sqlite':
        import sqlite3
        return sqlite3
    if engine == 'sqlserver':
        try:
            import pymssql
            return pymssql
        except ImportError:
            raise ImportError("pymssql no está instalado. Ejecute: pip install pymssql")
    import pymysql
    return pymysql


def get_db_config():
    global _cached_config
    if _cached_config is not None:
        return _cached_config.copy()

    conn = _get_admin_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT clave, valor FROM configuracion WHERE clave IN ('DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DB_CHAR_SET', 'DB_ENGINE')")
        rows = cursor.fetchall()
        cursor.close()

        config = {}
        for row in rows:
            clave = row['clave']
            valor = row['valor'] if row['valor'] is not None else ''
            config[clave] = str(valor)

        required = ['DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
        missing = [k for k in required if k not in config]
        if missing:
            raise Exception(f"Configuración incompleta en BD. Faltan: {', '.join(missing)}")

        if 'DB_ENGINE' not in config:
            config['DB_ENGINE'] = 'mysql'

        _cached_config = config
        return config.copy()
    finally:
        conn.close()


def clear_config_cache():
    global _cached_config, _db_engine, _intercambio_config_cache
    _cached_config = None
    _db_engine = None
    _intercambio_config_cache = None
    set_engine('mysql')


def get_intercambio_config():
    """Configuracion de la base de intercambio (taurus_intercambio).

    Lee las claves INTERCAMBIO_* de la tabla configuracion de taurus_admin;
    si faltan, usa el fallback de variables de entorno DB_INTERCAMBIO_*.
    """
    global _intercambio_config_cache
    if _intercambio_config_cache is not None:
        return _intercambio_config_cache.copy()

    config = {
        'INTERCAMBIO_HOST':      _get_env('DB_INTERCAMBIO_HOST', 'localhost'),
        'INTERCAMBIO_PORT':      _get_env('DB_INTERCAMBIO_PORT', '3306'),
        'INTERCAMBIO_NAME':      _get_env('DB_INTERCAMBIO_NAME', 'taurus_intercambio'),
        'INTERCAMBIO_USER':      _get_env('DB_INTERCAMBIO_USER', 'taurus'),
        'INTERCAMBIO_PASSWORD':  _get_env('DB_INTERCAMBIO_PASSWORD', 'Taurus_2001'),
        'INTERCAMBIO_CHAR_SET':  _get_env('DB_INTERCAMBIO_CHAR_SET', 'utf8mb4'),
        'INTERCAMBIO_ENGINE':    _get_env('DB_INTERCAMBIO_ENGINE', 'mysql'),
    }

    try:
        conn = _get_admin_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT clave, valor FROM configuracion WHERE clave LIKE 'INTERCAMBIO%'")
            rows = cursor.fetchall()
            cursor.close()
        finally:
            conn.close()
        for row in rows:
            clave = row['clave']
            valor = row['valor']
            if clave in config and valor is not None:
                config[clave] = str(valor)
    except Exception:
        pass

    _intercambio_config_cache = config
    return config.copy()


def get_intercambio_connection():
    engine = get_intercambio_config().get('INTERCAMBIO_ENGINE', 'mysql').strip().lower()
    driver = _get_driver_for_engine(engine)
    config = get_intercambio_config()

    if engine == 'sqlite':
        conn = driver.connect(config['INTERCAMBIO_NAME'])
        conn.row_factory = driver.Row
        return conn

    connect_kwargs = dict(
        host=config['INTERCAMBIO_HOST'],
        user=config['INTERCAMBIO_USER'],
        password=config['INTERCAMBIO_PASSWORD'],
        database=config['INTERCAMBIO_NAME'],
        port=int(config.get('INTERCAMBIO_PORT', 3306)),
    )
    if engine == 'mysql':
        connect_kwargs['charset'] = config.get('INTERCAMBIO_CHAR_SET', 'utf8mb4')
        connect_kwargs['cursorclass'] = driver.cursors.DictCursor
    elif engine == 'postgresql':
        connect_kwargs['options'] = f"-c client_encoding={config.get('INTERCAMBIO_CHAR_SET', 'UTF8')}"
        from psycopg2.extras import RealDictCursor
        connect_kwargs['cursor_factory'] = RealDictCursor
    elif engine == 'sqlserver':
        connect_kwargs = dict(
            server=config['INTERCAMBIO_HOST'],
            user=config['INTERCAMBIO_USER'],
            password=config['INTERCAMBIO_PASSWORD'],
            database=config['INTERCAMBIO_NAME'],
        )
        port = config.get('INTERCAMBIO_PORT', '1433')
        if port:
            connect_kwargs['port'] = int(port)

    return driver.connect(**connect_kwargs)


def get_db_connection():
    engine = get_db_engine()
    driver = _get_driver_for_engine(engine)
    config = get_db_config()

    if engine == 'sqlite':
        conn = driver.connect(config['DB_NAME'])
        conn.row_factory = driver.Row
        return conn

    connect_kwargs = dict(
        host=config['DB_HOST'],
        user=config['DB_USER'],
        password=config['DB_PASSWORD'],
        database=config['DB_NAME'],
        port=int(config['DB_PORT']),
    )
    if engine == 'mysql':
        connect_kwargs['charset'] = config.get('DB_CHAR_SET', 'utf8mb4')
        connect_kwargs['cursorclass'] = driver.cursors.DictCursor
    elif engine == 'postgresql':
        connect_kwargs['options'] = f"-c client_encoding={config.get('DB_CHAR_SET', 'UTF8')}"
        from psycopg2.extras import RealDictCursor
        connect_kwargs['cursor_factory'] = RealDictCursor
    elif engine == 'sqlserver':
        connect_kwargs = dict(
            server=config['DB_HOST'],
            user=config['DB_USER'],
            password=config['DB_PASSWORD'],
            database=config['DB_NAME'],
        )
        port = config.get('DB_PORT', '1433')
        if port:
            connect_kwargs['port'] = int(port)

    return driver.connect(**connect_kwargs)
