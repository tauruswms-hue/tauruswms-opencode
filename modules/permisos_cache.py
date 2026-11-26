"""Cache de permisos por rol, invalidable entre procesos (FASE 2.7).

La clave de cache incluye una "version global" guardada en
taurus_admin.configuracion (clave ``permisos_version``). Cada cambio del panel
en roles/roles_rutas incrementa esa version: los procesos WMS la ven en el
siguiente request y descartan su entrada aunque no compartan memoria.

La version se consulta en cada request (una query pequena al pool admin); el
TTL sigue siendo el limite superior por si la BD no esta disponible.
"""

import os
import time

TTL = float(os.getenv('PERMISOS_CACHE_TTL', '30'))

VERSION_CLAVE = 'permisos_version'

_cache = {}  # (rol, version) -> (timestamp, [rutas])


def obtener_rutas_cached(rol, loader, usar_cache=True, version='0'):
    """Devuelve las rutas del rol usando la cache si esta fresca.

    loader() es un callable sin argumentos que consulta la BD y devuelve la
    lista de rutas (se invoca solo en miss). Un rol sin cache previa SIEMPRE
    consulta la BD (primer request tras cambios = coherente).
    """
    if not usar_cache:
        return loader()

    ahora = time.time()
    clave = (rol, version)
    entrada = _cache.get(clave)
    if entrada is not None and (ahora - entrada[0]) < TTL:
        return entrada[1]

    rutas = loader()
    _cache[clave] = (ahora, rutas)
    return rutas


def invalidar_permisos_cache():
    """Limpia la cache local (llamar tras modificar roles o roles_rutas)."""
    _cache.clear()


def incrementar_version_permisos(conn):
    """Incrementa la version global de permisos en la misma transaccion del panel."""
    from modules.sql_dialect import execute_insert

    cursor = conn.cursor()
    try:
        cursor.execute("SELECT valor FROM configuracion WHERE clave = %s", (VERSION_CLAVE,))
        fila = cursor.fetchone()
        if fila:
            try:
                nueva = str(int(fila['valor']) + 1)
            except (TypeError, ValueError):
                nueva = '1'
            cursor.execute("UPDATE configuracion SET valor = %s WHERE clave = %s",
                           (nueva, VERSION_CLAVE))
        else:
            execute_insert(cursor, """
                INSERT INTO configuracion (clave, valor, descripcion)
                VALUES (%s, %s, %s)
            """, (VERSION_CLAVE, '1', 'Versión global de permisos (uso interno)'))
    finally:
        cursor.close()
