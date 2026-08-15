"""Contexto de request compartido: tenant actual y constantes de sesión.

Agrupa lo que antes estaba duplicado en cada blueprint (get_tenant_filter) y
los tiempos mágicos de sesión (28800 / 300) que aparecían en app.py.
"""

from flask import session

# Duración máxima de sesión (8 horas) y tope de inactividad del login (5 min).
SESSION_MAX_AGE_SECONDS = 8 * 60 * 60
LOGIN_IDLE_TIMEOUT_SECONDS = 5 * 60


def get_tenant_filter():
    """Tenant desde el cual el usuario filtra sus datos operativos.

    Puede ser None (superadmin): las consultas usan el patrón
    `WHERE (%s IS NULL OR tenant_id = %s)` para devolver todas las filas.
    """
    return session.get('tenant_id')
