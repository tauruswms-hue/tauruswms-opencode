import os
from contextlib import suppress

from dotenv import load_dotenv

from modules.sql_dialect import set_engine

load_dotenv()

_cached_config = None
_db_engine = None
_intercambio_config_cache = None
_pools = {}

_ENGINES = ('mysql', 'postgresql', 'sqlite', 'sqlserver')


def _get_env(key, default=''):
    return os.getenv(key, default)


def _get_pooled(pool_key, connect_kwargs):
    """Devuelve una conexion desde un pool DBUtils (reusada, nunca cerrada de verdad).

    La primera llamada crea el pool con maxconnections=20; conn.close() en los
    callers devuelve la conexion al pool en vez de cerrarla (reset=True hace
    rollback al devolverla, manteniendo las transacciones aisladas).
    """
    pool = _pools.get(pool_key)
    if pool is None:
        try:
            from dbutils.pooled_db import PooledDB
        except ImportError:
            from DBUtils.PooledDB import PooledDB
        engine = pool_key[0]
        pool = PooledDB(
            creator=lambda: _create_pool_connection(engine, connect_kwargs),
            mincached=1,
            maxcached=5,
            maxconnections=20,
            blocking=True,
            reset=True,
            ping=1,
        )
        _pools[pool_key] = pool
    return pool.connection()


def _pool_key_for(engine, connect_kwargs):
    import hashlib
    canon = dict(connect_kwargs)
    for k, v in list(canon.items()):
        canon[k] = str(v)
    digest = hashlib.md5(repr(sorted(canon.items())).encode('utf-8')).hexdigest()
    return (engine, digest)


def _create_pool_connection(engine, connect_kwargs):
    driver = _get_driver_for_engine(engine)
    if engine == 'sqlite':
        conn = driver.connect(connect_kwargs['database'])
        conn.row_factory = driver.Row
        return conn
    return driver.connect(**connect_kwargs)


def _get_admin_connection():
    engine = _get_env('DB_ADMIN_ENGINE', 'mysql').strip().lower()
    connect_kwargs = _admin_connect_kwargs(engine)

    if engine == 'sqlite':
        return _create_pool_connection(engine, connect_kwargs)

    return _get_pooled(_pool_key_for(engine, connect_kwargs), connect_kwargs)


def _admin_connect_kwargs(engine):
    connect_kwargs = dict(
        host=_get_env('DB_ADMIN_HOST', 'localhost'),
        user=_get_env('DB_ADMIN_USER', 'taurus_admin'),
        password=_get_env('DB_ADMIN_PASSWORD', 'Taurus_2001'),
        database=_get_env('DB_ADMIN_NAME', 'taurus_admin'),
    )

    if engine == 'sqlite':
        connect_kwargs = {'database': connect_kwargs['database']}
        return connect_kwargs

    port = int(_get_env('DB_ADMIN_PORT', '3306'))

    if engine == 'mysql':
        connect_kwargs['charset'] = _get_env('DB_CHAR_SET', 'utf8mb4')
        connect_kwargs['port'] = port
        connect_kwargs['cursorclass'] = _get_driver_for_engine(engine).cursors.DictCursor
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

    return connect_kwargs


def get_db_engine():
    global _db_engine
    if _db_engine is not None:
        return _db_engine
    env_engine = _get_env('DB_ENGINE', '').strip().lower()
    if env_engine in _ENGINES:
        _db_engine = env_engine
        set_engine(env_engine)
        return _db_engine
    try:
        config = get_db_config()
        engine_val = config.get('DB_ENGINE', 'mysql').strip().lower()
        if engine_val not in _ENGINES:
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
            raise ImportError("psycopg2 no está instalado. Ejecute: pip install psycopg2-binary") from None
    if engine == 'sqlite':
        import sqlite3
        return sqlite3
    if engine == 'sqlserver':
        try:
            import pymssql
            return pymssql
        except ImportError:
            raise ImportError("pymssql no está instalado. Ejecute: pip install pymssql") from None
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
    global _cached_config, _db_engine, _intercambio_config_cache, _pools
    _cached_config = None
    _db_engine = None
    _intercambio_config_cache = None
    for pool in _pools.values():
        with suppress(Exception):
            pool.close()
    _pools = {}
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
    config = get_intercambio_config()

    connect_kwargs = _intercambio_connect_kwargs(engine, config)

    if engine == 'sqlite':
        return _create_pool_connection(engine, connect_kwargs)

    return _get_pooled(_pool_key_for(engine, connect_kwargs), connect_kwargs)


def _intercambio_connect_kwargs(engine, config):
    if engine == 'sqlite':
        return {'database': config['INTERCAMBIO_NAME']}

    connect_kwargs = dict(
        host=config['INTERCAMBIO_HOST'],
        user=config['INTERCAMBIO_USER'],
        password=config['INTERCAMBIO_PASSWORD'],
        database=config['INTERCAMBIO_NAME'],
        port=int(config.get('INTERCAMBIO_PORT', 3306)),
    )
    if engine == 'mysql':
        connect_kwargs['charset'] = config.get('INTERCAMBIO_CHAR_SET', 'utf8mb4')
        connect_kwargs['cursorclass'] = _get_driver_for_engine(engine).cursors.DictCursor
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

    return connect_kwargs


def get_db_connection():
    engine = get_db_engine()
    config = get_db_config()

    connect_kwargs = _wms_connect_kwargs(engine, config)

    if engine == 'sqlite':
        return _create_pool_connection(engine, connect_kwargs)

    return _get_pooled(_pool_key_for(engine, connect_kwargs), connect_kwargs)


def get_wms_runtime_config():
    """Configuracion efectiva de la BD WMS con fallback a variables de entorno.

    Devuelve un dict plano (host/user/password/database/charset/port/engine).
    Si la tabla `configuracion` no esta disponible (o esta incompleta) se usa
    el entorno (.env) como fallback, igual que en el bootstrap de app.py.
    """
    try:
        config = get_db_config()
    except Exception:
        config = {}

    engine = (config.get('DB_ENGINE') or _get_env('DB_ENGINE', 'mysql')).strip().lower()
    if engine not in _ENGINES:
        engine = 'mysql'

    return {
        'host': config.get('DB_HOST') or _get_env('DB_HOST', 'localhost'),
        'user': config.get('DB_USER') or _get_env('DB_USER', 'taurus'),
        'password': config.get('DB_PASSWORD') or _get_env('DB_PASSWORD', ''),
        'database': config.get('DB_NAME') or _get_env('DB_NAME', 'taurus_wms'),
        'charset': config.get('DB_CHAR_SET') or _get_env('DB_CHAR_SET', 'utf8mb4'),
        'port': int(config.get('DB_PORT') or _get_env('DB_PORT', '3306')),
        'engine': engine,
    }


def test_connection(engine, host=None, port=None, user=None, password=None,
                    database=None, charset=None):
    """Prueba una conexion contra un engine con los datos dados.

    Reutiliza el mismo armado de kwargs por engine que las conexiones reales,
    para que la prueba refleje lo que realmente usaria la app. Lanza la
    excepcion del driver si la conexion falla.
    """
    kwargs = _test_connect_kwargs(engine, host, port, user, password, database, charset)
    conn = _create_pool_connection(engine, kwargs)
    with suppress(Exception):
        conn.close()
    return True


def _test_connect_kwargs(engine, host, port, user, password, database, charset):
    if engine == 'sqlite':
        return {'database': database}

    kwargs = dict(host=host, user=user, password=password, database=database)

    if engine == 'mysql':
        kwargs['port'] = int(port or 3306)
        kwargs['charset'] = charset or 'utf8mb4'
        kwargs['connect_timeout'] = 5
        kwargs['cursorclass'] = _get_driver_for_engine(engine).cursors.DictCursor
    elif engine == 'postgresql':
        kwargs['port'] = int(port or 5432)
        from psycopg2.extras import RealDictCursor
        kwargs['cursor_factory'] = RealDictCursor
    elif engine == 'sqlserver':
        kwargs = dict(
            server=host, user=user, password=password,
            database=database, port=int(port or 1433),
        )

    return kwargs


def _wms_connect_kwargs(engine, config):
    if engine == 'sqlite':
        return {'database': config['DB_NAME']}

    connect_kwargs = dict(
        host=config['DB_HOST'],
        user=config['DB_USER'],
        password=config['DB_PASSWORD'],
        database=config['DB_NAME'],
        port=int(config['DB_PORT']),
    )
    if engine == 'mysql':
        connect_kwargs['charset'] = config.get('DB_CHAR_SET', 'utf8mb4')
        connect_kwargs['cursorclass'] = _get_driver_for_engine(engine).cursors.DictCursor
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

    return connect_kwargs
