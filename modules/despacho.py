from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from datetime import datetime
from modules.db_config import get_db_connection

despacho_bp = Blueprint('despacho', __name__)


def get_tenant_filter():
    return session.get('tenant_id')


@despacho_bp.route('/despacho')
def listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT p.*, c.razonsocial AS cliente_nombre, c.codigo AS cliente_codigo,
                       r.nombre_ruta, t.razonsocial AS transporte_nombre,
                       cp.nombre AS clase_nombre
                FROM pedidos_cabecera p
                JOIN clientes c ON p.id_cliente = c.id_cliente
                LEFT JOIN rutas r ON p.id_ruta = r.id_ruta
                LEFT JOIN transportes t ON p.id_transporte = t.id_transporte
                LEFT JOIN clases_pedido cp ON p.id_clase = cp.id_clase
                WHERE p.estado = 'Preparado' AND (%s IS NULL OR p.tenant_id = %s)
                ORDER BY p.fecha_pedido ASC, p.id_pedido ASC
            """, (tenant_id, tenant_id))
            pedidos = cursor.fetchall()
        return render_template('despacho.html', pedidos=pedidos)
    finally:
        conn.close()


@despacho_bp.route('/despacho/despachar/<int:id_pedido>', methods=['POST'])
def despachar(id_pedido):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT estado, nro_pedido FROM pedidos_cabecera WHERE id_pedido = %s AND (%s IS NULL OR tenant_id = %s)", (id_pedido, tenant_id, tenant_id))
            p = cursor.fetchone()
            if not p or p['estado'] != 'Preparado':
                flash("El pedido no está en estado Preparado.", "warning")
                return redirect(url_for('despacho.listar'))

            cursor.execute(
                "UPDATE pedidos_cabecera SET estado = 'Despachado', fecha_despacho = %s WHERE id_pedido = %s",
                (datetime.now(), id_pedido)
            )
            conn.commit()
            flash(f"Pedido {p['nro_pedido']} despachado.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {str(e)}", "danger")
    finally:
        conn.close()
    return redirect(url_for('despacho.listar'))


@despacho_bp.route('/despacho/despachar_masivo', methods=['POST'])
def despachar_masivo():
    ids = request.json.get('ids', [])
    if not ids:
        return jsonify({"status": "error", "message": "No hay pedidos seleccionados"}), 400

    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            ph = ','.join(['%s'] * len(ids))
            cursor.execute(
                f"UPDATE pedidos_cabecera SET estado = 'Despachado', fecha_despacho = %s "
                f"WHERE id_pedido IN ({ph}) AND estado = 'Preparado' AND (%s IS NULL OR tenant_id = %s)",
                tuple([datetime.now()] + list(ids) + [tenant_id, tenant_id])
            )
            conn.commit()
            return jsonify({"status": "success", "message": f"{cursor.rowcount} pedido(s) despachado(s)."})
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()
