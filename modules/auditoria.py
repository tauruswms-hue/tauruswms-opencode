"""Auditoría de movimientos de stock (historial por posición).

Cada movimiento de stock (recepción, OMC, pedido, ajuste, API) registra un
evento en `stock_movimientos` con signo: `cantidad` positivo = ingreso a la
posición (ubicación/material/contenedor), negativo = egreso. Los cambios de
estado sin cantidad (p. ej. cambio de lote) se registran con cantidad NULL.

`registrar_movimiento` es best-effort: si falla, loguea y no rompe el flujo
de negocio.
"""
import datetime
import logging

from modules.sql_dialect import quote

logger = logging.getLogger(__name__)

COLUMNAS = [
    'tenant_id', 'fecha', 'usuario', 'accion', 'modulo', 'id_ubicacion',
    'id_material', 'id_contenedor', 'lote', 'tipo_stock', 'cantidad', 'detalle',
]


def registrar_movimiento(conn, *, tenant_id, accion, usuario='sistema', modulo=None,
                         id_ubicacion=None, id_material=None, id_contenedor=None,
                         lote=None, tipo_stock=None, cantidad=None, fecha=None,
                         detalle=None):
    """Registra un movimiento de stock. No lanza excepciones."""
    try:
        if cantidad is not None:
            try:
                cantidad = float(cantidad)
            except (TypeError, ValueError):
                cantidad = None
        if cantidad is not None and abs(cantidad) < 0.0001:
            cantidad = None
        valores = (
            tenant_id,
            fecha or datetime.datetime.now(),
            usuario,
            accion,
            modulo,
            id_ubicacion,
            id_material,
            id_contenedor,
            lote,
            tipo_stock,
            cantidad,
            (detalle or accion)[:500],
        )
        with conn.cursor() as cursor:
            cursor.execute(f"""
                INSERT INTO {quote('stock_movimientos')}
                    ({', '.join(quote(c) for c in COLUMNAS)})
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, valores)
    except Exception as e:
        logger.error("No se pudo registrar movimiento de stock (%s): %s", accion, e)
