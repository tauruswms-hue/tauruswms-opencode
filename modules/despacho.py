from datetime import datetime

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from modules.auditoria import registrar_movimiento
from modules.context import get_tenant_filter
from modules.db_config import get_db_connection

despacho_bp = Blueprint('despacho', __name__)


def _ids(valores):
    """Ids enteros de una lista recibida por JSON, sin repetir; los que no son ids se descartan."""
    ids = []
    for v in valores if isinstance(valores, (list, tuple)) else []:
        try:
            i = int(str(v).strip())
        except (TypeError, ValueError):
            continue
        if i > 0 and i not in ids:
            ids.append(i)
    return ids


def _contenedores_del_pedido(cursor, id_pedido):
    """Contenedores que las OMC confirmadas del pedido dejaron en el muelle: [(contenedor, id ubicación, código)]."""
    cursor.execute("""
        SELECT DISTINCT COALESCE(oc.id_contenedor_destino, oc.id_contenedor) AS contenedor,
               o.id_ubicacion_destino AS id_ubicacion, u.codigo AS ubicacion
        FROM omc o
        JOIN omc_contenedores oc ON oc.id_omc = o.id_omc
        JOIN ubicaciones u       ON u.id = o.id_ubicacion_destino
        WHERE o.id_pedido = %s AND o.estado = 'Confirmada'
        ORDER BY contenedor
    """, (id_pedido,))
    return [(r['contenedor'], r['id_ubicacion'], r['ubicacion']) for r in cursor.fetchall()]


def _despachar(conn, cursor, pedido, tenant_id, usuario, ahora):
    """Despacha un pedido Preparado: saca del muelle el stock de sus contenedores y lo marca Despachado.

    La mercadería deja el depósito: cada fila de stock que sale queda en el historial
    como DESPACHO (cantidad negativa). Devuelve los avisos de lo que no se pudo sacar.
    """
    avisos = []
    for contenedor, id_ubicacion, ubicacion in _contenedores_del_pedido(cursor, pedido['id_pedido']):
        cursor.execute("""
            SELECT Material, Lote, TipoStock, StockTotal, StockEntrando, StockSaliendo
            FROM stockcontable
            WHERE IDContenedor = %s AND Ubicacion = %s AND (%s IS NULL OR tenant_id = %s)
        """, (contenedor, id_ubicacion, tenant_id, tenant_id))
        filas = cursor.fetchall()
        if not any(f['StockTotal'] for f in filas):
            avisos.append(f'el contenedor {contenedor} ya no tiene stock en {ubicacion}')
            continue
        if any(f['StockEntrando'] or f['StockSaliendo'] for f in filas):
            # Hay una OMC en curso sobre ese contenedor: no se le saca el stock por debajo
            avisos.append(f'el contenedor {contenedor} tiene movimientos pendientes en {ubicacion} y no se descontó')
            continue
        cursor.execute("""
            DELETE FROM stockcontable
            WHERE IDContenedor = %s AND Ubicacion = %s AND (%s IS NULL OR tenant_id = %s)
        """, (contenedor, id_ubicacion, tenant_id, tenant_id))
        for f in filas:
            if f['StockTotal']:
                registrar_movimiento(
                    conn, tenant_id=tenant_id, accion='DESPACHO', usuario=usuario, modulo='despacho',
                    id_ubicacion=id_ubicacion, id_material=f['Material'], id_contenedor=contenedor,
                    lote=f['Lote'], tipo_stock=f['TipoStock'], cantidad=-f['StockTotal'],
                    detalle=f"Salida por despacho del pedido {pedido['nro_pedido']}")

    cursor.execute(
        "UPDATE pedidos_cabecera SET estado = 'Despachado', fecha_despacho = %s, usuario_despacho = %s WHERE id_pedido = %s",
        (ahora, usuario, pedido['id_pedido'])
    )
    return avisos


@despacho_bp.route('/despacho')
def listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT p.*, c.razonsocial AS cliente_nombre, c.codigo AS cliente_codigo,
                       r.nombre_ruta, t.razonsocial AS transporte_nombre,
                       cp.nombre AS clase_nombre,
                       (SELECT COUNT(*) FROM pedidos_detalle d
                        WHERE d.id_pedido = p.id_pedido AND d.Cantidad_preparada < d.cantidad) AS renglones_incompletos
                FROM pedidos_cabecera p
                JOIN clientes c ON p.id_cliente = c.id_cliente
                LEFT JOIN rutas r ON p.id_ruta = r.id_ruta
                LEFT JOIN transportes t ON p.id_transporte = t.id_transporte
                LEFT JOIN clases_pedido cp ON p.id_clase = cp.id_clase
                WHERE p.estado = 'Preparado' AND (%s IS NULL OR p.tenant_id = %s)
                ORDER BY p.fecha_pedido ASC, p.id_pedido ASC
            """, (tenant_id, tenant_id))
            pedidos = [dict(p) for p in cursor.fetchall()]
            for p in pedidos:
                # Qué se despacha: los contenedores que sus OMC dejaron en el muelle
                contenedores = _contenedores_del_pedido(cursor, p['id_pedido'])
                p['contenedores'] = len(contenedores)
                p['muelles'] = ', '.join(sorted({ubicacion for _, _, ubicacion in contenedores}))
        return render_template('despacho.html', pedidos=pedidos)
    finally:
        conn.close()


@despacho_bp.route('/despacho/despachar/<int:id_pedido>', methods=['POST'])
def despachar(id_pedido):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id_pedido, estado, nro_pedido FROM pedidos_cabecera WHERE id_pedido = %s AND (%s IS NULL OR tenant_id = %s)", (id_pedido, tenant_id, tenant_id))
            p = cursor.fetchone()
            if not p:
                flash("El pedido no existe.", "warning")
                return redirect(url_for('despacho.listar'))
            if p['estado'] != 'Preparado':
                flash(f"El pedido {p['nro_pedido']} no está en estado Preparado (está {p['estado']}).", "warning")
                return redirect(url_for('despacho.listar'))

            avisos = _despachar(conn, cursor, p, tenant_id, session.get('nombre', 'sistema'), datetime.now())
            conn.commit()
            flash(f"Pedido {p['nro_pedido']} despachado.", "success")
            if avisos:
                flash(f"Pedido {p['nro_pedido']}: {'; '.join(avisos)}.", "warning")
    except Exception as e:
        conn.rollback()
        flash(f"No se pudo despachar el pedido: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('despacho.listar'))


@despacho_bp.route('/despacho/despachar_masivo', methods=['POST'])
def despachar_masivo():
    ids = _ids((request.get_json(silent=True) or {}).get('ids'))
    if not ids:
        return jsonify({"status": "error", "message": "No hay pedidos seleccionados"}), 400

    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            usuario, ahora = session.get('nombre', 'sistema'), datetime.now()
            despachados, omitidos, avisos = 0, 0, []
            for id_pedido in ids:
                cursor.execute("SELECT id_pedido, estado, nro_pedido FROM pedidos_cabecera WHERE id_pedido = %s AND (%s IS NULL OR tenant_id = %s)", (id_pedido, tenant_id, tenant_id))
                p = cursor.fetchone()
                if not p or p['estado'] != 'Preparado':
                    omitidos += 1
                    continue
                avisos += [f"{p['nro_pedido']}: {a}" for a in _despachar(conn, cursor, p, tenant_id, usuario, ahora)]
                despachados += 1
            conn.commit()
            mensaje = f"{despachados} pedido(s) despachado(s)."
            if omitidos:
                mensaje += f" {omitidos} no se despacharon porque ya no estaban Preparados."
            if avisos:
                mensaje += " Avisos: " + '; '.join(avisos) + '.'
            return jsonify({"status": "success", "message": mensaje, "despachados": despachados, "omitidos": omitidos})
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": f"No se pudo despachar: {e!s}"}), 500
    finally:
        conn.close()
