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
    'pedido': ('pedidos.ver_detalle', 'Volver al Pedido'),
    'clientes': ('clientes.listar', 'Volver a Clientes'),
    'materiales': ('materiales.listar', 'Volver a Materiales'),
    'recepciones': ('recepciones.listar', 'Volver a Recepciones'),
    'omc': ('omc.listar', 'Volver a OMC'),
    'despacho': ('despacho.listar', 'Volver a Despacho'),
    'inventario': ('inventario.listar', 'Volver a Inventarios'),
}


def destino_volver(desde):
    """(endpoint, rótulo) para un valor conocido de ?desde=, o None."""
    return VOLVER_DESTINOS.get((desde or '').strip().lower())


def url_volver(desde, cliente=None, id_pedido=None):
    """URL de retorno, con el contexto del origen (filtro de cliente o pedido)."""
    destino = destino_volver(desde)
    if not destino:
        return None
    if destino[0] == 'pedidos.ver_detalle':
        # Sólo un id numérico: nunca se construye una URL con dato arbitrario.
        if not str(id_pedido or '').isdigit():
            return None
        return url_for(destino[0], id_pedido=int(id_pedido))
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
