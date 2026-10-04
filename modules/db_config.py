import json
import logging
import os
import time
from contextlib import suppress
from pathlib import Path

from dotenv import load_dotenv

from modules.sql_dialect import set_engine

load_dotenv()

logger = logging.getLogger(__name__)

# Las conexiones a las tres bases (admin, wms, intercambio) viven en un único
# archivo JSON fuera de la BD: conexiones.json en la raíz del proyecto, o la
# ruta indicada en la variable de entorno TAURUS_CONEXIONES.
CONEXIONES_ARCHIVO = 'conexiones.json'
CONEXIONES_ENV = 'TAURUS_CONEXIONES'
BASES = ('admin', 'wms', 'intercambio')
_BASES_OBLIGATORIAS = ('admin', 'wms')
_CLAVES = ('engine', 'host', 'port', 'user', 'password', 'database', 'charset')
_CLAVES_OBLIGATORIAS = ('host', 'user', 'password', 'database')
_ENGINES = ('mysql', 'postgresql', 'sqlite', 'sqlserver')
_PUERTOS = {'mysql': 3306, 'postgresql': 5432, 'sqlserver': 1433}
_CHARSETS = {'mysql': 'utf8mb4', 'postgresql': 'UTF8'}

_conexiones = None
_conexiones_ts = 0.0
_conexiones_fijas = {}
_db_engine = None
_pools = {}

# El archivo se relee cada CONFIG_CACHE_TTL segundos; si cambió, se descartan
# engine y pools para reconectar con los valores nuevos sin reiniciar la app.
CONFIG_CACHE_TTL = float(os.getenv('CONFIG_CACHE_TTL', '30'))


class ConexionesError(Exception):
    """El archivo de conexiones falta, no se puede leer o está incompleto."""


def _cache_vigente(ts):
    return (time.monotonic() - ts) < CONFIG_CACHE_TTL


# ============================================================================
# ARCHIVO DE CONEXIONES
# ============================================================================

def ruta_conexiones():
    """Ruta del archivo de conexiones: TAURUS_CONEXIONES o conexiones.json en la raíz."""
    ruta = os.getenv(CONEXIONES_ENV, '').strip()
    if ruta:
        return Path(ruta)
    return Path(__file__).resolve().parent.parent / CONEXIONES_ARCHIVO


def normalizar_conexion(base, datos, origen):
    """Valida los datos de conexión de una base y completa los valores por defecto.

    Devuelve un dict con engine, host, port, user, password, database y charset.
    Lanza ConexionesError con un mensaje que indica qué corregir.
    """
    if not isinstance(datos, dict):
        raise ConexionesError(f"{origen}: la sección '{base}' debe ser un objeto {{...}}")
    desconocidas = sorted(set(datos) - set(_CLAVES))
    if desconocidas:
        raise ConexionesError(f"{origen}: claves desconocidas en '{base}': {', '.join(desconocidas)} "
                              f"(válidas: {', '.join(_CLAVES)})")

    engine = str(datos.get('engine') or 'mysql').strip().lower()
    if engine not in _ENGINES:
        raise ConexionesError(f"{origen}: engine '{engine}' no soportado en '{base}' "
                              f"(usar: {', '.join(_ENGINES)})")

    obligatorias = ('database',) if engine == 'sqlite' else _CLAVES_OBLIGATORIAS
    faltantes = [k for k in obligatorias if datos.get(k) in (None, '')]
    if faltantes:
        raise ConexionesError(f"{origen}: faltan claves obligatorias en '{base}': {', '.join(faltantes)}")

    port = datos.get('port')
    if port in (None, ''):
        port = _PUERTOS.get(engine, 0)
    elif not str(port).isdigit():
        raise ConexionesError(f"{origen}: port debe ser numérico en '{base}': {port!r}")

    return {
        'engine': engine,
        'host': str(datos.get('host') or ''),
        'port': int(port),
        'user': str(datos.get('user') or ''),
        'password': str(datos.get('password') or ''),
        'database': str(datos['database']),
        'charset': str(datos.get('charset') or _CHARSETS.get(engine, '')),
    }


def _leer_conexiones():
    """Lee y valida el archivo de conexiones. Devuelve {base: conexión normalizada}."""
    ruta = ruta_conexiones()
    try:
        with open(ruta, encoding='utf-8-sig') as fh:
            datos = json.load(fh)
    except FileNotFoundError:
        raise ConexionesError(
            f"No se encontró el archivo de conexiones ({ruta}). Cree {CONEXIONES_ARCHIVO} con las secciones "
            f"admin, wms e intercambio (ver docs/inicio/configuracion.html), o indique otra ruta con la "
            f"variable de entorno {CONEXIONES_ENV}."
        ) from None
    except json.JSONDecodeError as e:
        raise ConexionesError(f"{ruta} no es un JSON válido (línea {e.lineno}, columna {e.colno}): {e.msg}") from None
    except OSError as e:
        raise ConexionesError(f"No se pudo leer {ruta}: {e.strerror}") from None

    if not isinstance(datos, dict):
        raise ConexionesError(f"{ruta} debe contener un objeto JSON {{...}}")
    desconocidas = sorted(set(datos) - set(BASES))
    if desconocidas:
        raise ConexionesError(f"{ruta}: secciones desconocidas: {', '.join(desconocidas)} "
                              f"(válidas: {', '.join(BASES)})")
    faltantes = [b for b in _BASES_OBLIGATORIAS if b not in datos]
    if faltantes:
        raise ConexionesError(f"{ruta}: faltan las secciones: {', '.join(faltantes)}")

    return {base: normalizar_conexion(base, datos[base], str(ruta)) for base in BASES if base in datos}


def get_conexiones():
    """Conexiones del archivo, cacheadas CONFIG_CACHE_TTL segundos."""
    global _conexiones, _conexiones_ts
    if _conexiones is not None and _cache_vigente(_conexiones_ts):
        return _conexiones

    try:
        conexiones = _leer_conexiones()
    except Exception:
        if _conexiones is None:
            raise
        # El archivo no se pudo leer al refrescar: seguir con las conexiones conocidas.
        logger.warning('No se pudo refrescar el archivo de conexiones; se usan las cacheadas', exc_info=True)
        _conexiones_ts = time.monotonic()
        return _conexiones

    if _conexiones is not None and conexiones != _conexiones:
        logger.info('Archivo de conexiones modificado; se reinician engine y pools')
        clear_config_cache()
    _conexiones = conexiones
    _conexiones_ts = time.monotonic()
    return _conexiones


def get_conexion(base):
    """Datos de conexión de una base ('admin', 'wms' o 'intercambio')."""
    if base in _conexiones_fijas:
        return _conexiones_fijas[base].copy()
    conexiones = get_conexiones()
    if base not in conexiones:
        raise ConexionesError(f"{ruta_conexiones()}: falta la sección '{base}'")
    return conexiones[base].copy()


def set_conexion(base, datos, origen='configuración'):
    """Fija la conexión de una base sin leer el archivo.

    Lo usa superusuario.exe, que trae sus propias credenciales de taurus_admin.
    """
    _conexiones_fijas[base] = normalizar_conexion(base, datos, origen)
    return _conexiones_fijas[base].copy()


def passwords_conexiones():
    """Pares (nombre, password) de cada base, para check_default_secrets."""
    return [(f'{CONEXIONES_ARCHIVO} {base}.password', c['password'])
            for base, c in get_conexiones().items()]


def clear_config_cache():
    global _conexiones, _db_engine, _pools
    _conexiones = None
    _db_engine = None
    for pool in _pools.values():
        with suppress(Exception):
            pool.close()
    _pools = {}
    set_engine('mysql')


# ============================================================================
# POOL Y DRIVERS
# ============================================================================

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


def _connect_kwargs(conexion):
    """Argumentos del driver para una conexión normalizada."""
    engine = conexion['engine']
    if engine == 'sqlite':
        return {'database': conexion['database']}
    if engine == 'sqlserver':
        return dict(
            server=conexion['host'],
            user=conexion['user'],
            password=conexion['password'],
            database=conexion['database'],
            port=conexion['port'],
        )

    connect_kwargs = dict(
        host=conexion['host'],
        user=conexion['user'],
        password=conexion['password'],
        database=conexion['database'],
        port=conexion['port'],
    )
    if engine == 'mysql':
        connect_kwargs['charset'] = conexion['charset'] or 'utf8mb4'
        connect_kwargs['cursorclass'] = _get_driver_for_engine(engine).cursors.DictCursor
    elif engine == 'postgresql':
        connect_kwargs['options'] = f"-c client_encoding={conexion['charset'] or 'UTF8'}"
        from psycopg2.extras import RealDictCursor
        connect_kwargs['cursor_factory'] = RealDictCursor
    return connect_kwargs


def _abrir(conexion):
    engine = conexion['engine']
    connect_kwargs = _connect_kwargs(conexion)
    if engine == 'sqlite':
        return _create_pool_connection(engine, connect_kwargs)
    return _get_pooled(_pool_key_for(engine, connect_kwargs), connect_kwargs)


# ============================================================================
# CONEXIONES
# ============================================================================

def _get_admin_connection():
    return _abrir(get_conexion('admin'))


def get_intercambio_connection():
    return _abrir(get_conexion('intercambio'))


def get_db_connection():
    # Primero la conexión: si el archivo cambió, resetea el engine cacheado.
    conexion = get_conexion('wms')
    get_db_engine()
    return _abrir(conexion)


def get_db_engine():
    """Engine de la base WMS; lo deja activo en sql_dialect."""
    global _db_engine
    if _db_engine is not None:
        return _db_engine
    try:
        engine = get_conexion('wms')['engine']
    except Exception:
        engine = 'mysql'
    _db_engine = engine
    set_engine(engine)
    return _db_engine


def get_db_config():
    """Conexión WMS con las claves DB_* (compatibilidad con migrate.py y generar_schema.py)."""
    c = get_conexion('wms')
    return {
        'DB_ENGINE': c['engine'],
        'DB_HOST': c['host'],
        'DB_PORT': str(c['port']),
        'DB_NAME': c['database'],
        'DB_USER': c['user'],
        'DB_PASSWORD': c['password'],
        'DB_CHAR_SET': c['charset'],
    }


def get_intercambio_config():
    """Conexión de intercambio con las claves INTERCAMBIO_* (compatibilidad)."""
    c = get_conexion('intercambio')
    return {
        'INTERCAMBIO_ENGINE': c['engine'],
        'INTERCAMBIO_HOST': c['host'],
        'INTERCAMBIO_PORT': str(c['port']),
        'INTERCAMBIO_NAME': c['database'],
        'INTERCAMBIO_USER': c['user'],
        'INTERCAMBIO_PASSWORD': c['password'],
        'INTERCAMBIO_CHAR_SET': c['charset'],
    }


def get_wms_runtime_config():
    """Conexión efectiva de la BD WMS como dict plano (host/user/password/database/charset/port/engine)."""
    return get_conexion('wms')


def probar_conexion(engine, host=None, port=None, user=None, password=None,
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
