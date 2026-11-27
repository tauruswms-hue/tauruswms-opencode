"""Contexto de request compartido: tenant actual y constantes de sesión.

Agrupa lo que antes estaba duplicado en cada blueprint (get_tenant_filter) y
los tiempos mágicos de sesión (28800 / 300) que aparecían en app.py.
"""

from flask import session, url_for

# Duración máxima de sesión (8 horas) y tope de inactividad del login (5 min).
SESSION_MAX_AGE_SECONDS = 8 * 60 * 60
LOGIN_IDLE_TIMEOUT_SECONDS = 5 * 60


# Destinos del enlace "Volver": ?desde=pedidos -> endpoint y rótulo. Se usa una
# lista cerrada para que el usuario no pueda inducir una URL ajena al WMS.
VOLVER_DESTINOS = {
    'pedidos': ('pedidos.listar', 'Volver a Pedidos'),
    'clientes': ('clientes.listar', 'Volver a Clientes'),
    'recepciones': ('recepciones.listar', 'Volver a Recepciones'),
    'omc': ('omc.listar', 'Volver a OMC'),
    'despacho': ('despacho.listar', 'Volver a Despacho'),
    'inventario': ('inventario.listar', 'Volver a Inventarios'),
}


def destino_volver(desde):
    """(endpoint, rótulo) para un valor conocido de ?desde=, o None."""
    return VOLVER_DESTINOS.get((desde or '').strip().lower())


def url_volver(desde, cliente=None):
    """URL de retorno, con el filtro de cliente cuando el origen lo pasó."""
    destino = destino_volver(desde)
    if not destino:
        return None
    extras = {}
    if cliente and destino[0] == 'pedidos.listar':
        extras['cliente'] = cliente
    return url_for(destino[0], **extras)


def get_tenant_filter():
    """Tenant desde el cual el usuario filtra sus datos operativos.

    Puede ser None (superadmin): las consultas usan el patrón
    `WHERE (%s IS NULL OR tenant_id = %s)` para devolver todas las filas.
    """
    return session.get('tenant_id')
