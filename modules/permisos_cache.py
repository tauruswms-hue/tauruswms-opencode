"""Cache de permisos por rol (FASE 2.7).

obtener_rutas_por_rol() en app.py abria una conexion admin en cada request.
Este modulo cachea el resultado por rol con TTL (por defecto 30s,
configurable con PERMISOS_CACHE_TTL) para no golpear la BD en cada request.

Garantia de consistencia:
  - TTL corto: los cambios de roles_rutas en el panel admin aplican sin
    re-login dentro del TTL (mismo proceso o no).
  - invalidar_permisos_cache(): los procesos que modifiquen roles_rutas
    (admin.py) la llaman para limpiar de inmediato SI comparten proceso;
    entre procesos separados el TTL es la garantia.
"""

import os
import time

TTL = float(os.getenv('PERMISOS_CACHE_TTL', '30'))

_cache = {}  # rol -> (timestamp, [rutas])


def obtener_rutas_cached(rol, loader, usar_cache=True):
    """Devuelve las rutas del rol usando la cache si esta fresca.

    loader() es un callable sin argumentos que consulta la BD y devuelve la
    lista de rutas (se invoca solo en miss). Un rol sin cache previa SIEMPRE
    consulta la BD (primer request tras cambios = coherente).
    """
    if not usar_cache:
        return loader()

    ahora = time.time()
    entrada = _cache.get(rol)
    if entrada is not None and (ahora - entrada[0]) < TTL:
        return entrada[1]

    rutas = loader()
    _cache[rol] = (ahora, rutas)
    return rutas


def invalidar_permisos_cache():
    """Limpia la cache completa (llamar tras modificar roles_rutas)."""
    _cache.clear()
