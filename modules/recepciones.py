from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from datetime import datetime
from collections import OrderedDict
from modules.batch_utils import parse_file, float_or_zero, plantilla_csv, plantilla_json, plantilla_xlsx
from modules.db_config import get_db_connection, _get_admin_connection
from modules.sql_dialect import upsert_incremental_sql, cast_as_int, substring_index, year as year_func, quote, execute_insert, limit_sql

recepciones_bp = Blueprint('recepciones', __name__)


def get_tenant_filter():
    return session.get('tenant_id')


# ============================================================================
# LISTADO
# ============================================================================
@recepciones_bp.route('/recepciones')
def listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT r.*, p.razonsocial AS proveedor_nombre, p.codigo AS proveedor_codigo,
                       ur.codigo AS ubicacion_recep_codigo,
                       ud.codigo AS ubicacion_dest_codigo,
                       (SELECT COUNT(*) FROM recepciones_detalle d
                       WHERE d.id_recepcion = r.id_recepcion) AS total_items,
                       (SELECT COALESCE(SUM(d.cantidad_recibida), 0) FROM recepciones_detalle d
                       WHERE d.id_recepcion = r.id_recepcion) AS total_unidades
                FROM recepciones_cabecera r
                JOIN proveedores p ON r.id_proveedor = p.id
                JOIN ubicaciones ur ON r.id_ubicacion_recep = ur.id
                LEFT JOIN ubicaciones ud ON r.id_ubicacion_destino = ud.id
                WHERE (%s IS NULL OR r.tenant_id = %s)
                ORDER BY r.id_recepcion DESC
            """, (tenant_id, tenant_id))
            recepciones = cursor.fetchall()

        conn_admin = _get_admin_connection()
        try:
            with conn_admin.cursor() as cursor_admin:
                cursor_admin.execute("SELECT dias_filtro_fechas FROM tenants WHERE id = %s", (tenant_id,))
                param = cursor_admin.fetchone()
                dias_filtro = param['dias_filtro_fechas'] if param else 30
        finally:
            conn_admin.close()

        return render_template('recepciones.html', recepciones=recepciones, dias_filtro=dias_filtro)
    finally:
        conn.close()


# ============================================================================
# NUEVA RECEPCIÓN — formulario de cabecera
# ============================================================================
@recepciones_bp.route('/recepciones/nueva')
def nueva():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, codigo, razonsocial FROM proveedores WHERE activo = 1 AND (%s IS NULL OR proveedores.tenant_id = %s) ORDER BY razonsocial",
                (tenant_id, tenant_id)
            )
            proveedores = cursor.fetchall()

            cursor.execute(f"""
                SELECT u.id, u.codigo, u.descipcion AS nombre, t.{quote('descripcion')} AS tipo
                FROM ubicaciones u
                JOIN tipoubicacion t ON u.tipoubicacion = t.id
                WHERE t.{quote('descripcion')} LIKE '%Recepci%' AND (%s IS NULL OR u.tenant_id = %s)
                ORDER BY u.codigo
            """, (tenant_id, tenant_id))
            ubicaciones_recep = cursor.fetchall()

        ultima_ubicacion = session.get('ultima_ubicacion_recepcion')

        return render_template('recepciones_nueva.html',
                               proveedores=proveedores,
                               ubicaciones_recep=ubicaciones_recep,
                               ubicacion_default=ultima_ubicacion,
                               hoy=datetime.now().strftime('%Y-%m-%d'))
    finally:
        conn.close()


# ============================================================================
# GUARDAR CABECERA
# ============================================================================
@recepciones_bp.route('/recepciones/guardar', methods=['POST'])
def guardar():
    d = request.form
    tenant_id = get_tenant_filter()
    
    if not d.get('id_ubicacion_recep'):
        flash("Debe seleccionar una ubicación de recepción.", "danger")
        return redirect(url_for('recepciones.nueva'))
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            anio = datetime.now().year
            expr = cast_as_int(substring_index("numero", "-", -1))
            cursor.execute(
                f"SELECT MAX({expr}) AS max_seq "
                f"FROM recepciones_cabecera WHERE {year_func('fecha_recepcion')} = %s AND (%s IS NULL OR tenant_id = %s)",
                (anio, tenant_id, tenant_id)
            )
            seq = (cursor.fetchone()['max_seq'] or 0) + 1
            numero = f"REC-{anio}-{seq:05d}"
            usuario = session.get('nombre', 'sistema')

            id_recepcion = execute_insert(cursor, """
                INSERT INTO recepciones_cabecera
                    (numero, id_proveedor, id_ubicacion_recep, id_ubicacion_destino,
                     observaciones, usuario_creacion, tenant_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                numero,
                d.get('id_proveedor'),
                d.get('id_ubicacion_recep'),
                d.get('id_ubicacion_destino') or None,
                d.get('observaciones') or None,
                usuario,
                tenant_id
            ))

            # El contenedor se genera con el ID definitivo
            contenedor = f"RC{id_recepcion:05d}"
            cursor.execute(
                "UPDATE recepciones_cabecera SET id_contenedor = %s WHERE id_recepcion = %s AND (%s IS NULL OR tenant_id = %s)",
                (contenedor, id_recepcion, tenant_id, tenant_id)
            )
            conn.commit()
            session['ultima_ubicacion_recepcion'] = d.get('id_ubicacion_recep')
            if d.get('redirect_to') == 'listar':
                flash(f"Recepción {numero} creada — contenedor {contenedor}.", "success")
                return redirect(url_for('recepciones.listar'))
            flash(f"Recepción {numero} creada — contenedor {contenedor}. Agregue los materiales.", "success")
            return redirect(url_for('recepciones.ver', id_recepcion=id_recepcion))

    except Exception as e:
        conn.rollback()
        flash(f"Error al crear la recepción: {str(e)}", "danger")
        return redirect(url_for('recepciones.nueva'))
    finally:
        conn.close()


# ============================================================================
# VER / GESTIONAR RECEPCIÓN
# ============================================================================
@recepciones_bp.route('/recepciones/ver/<int:id_recepcion>')
def ver(id_recepcion):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT r.*, p.razonsocial AS proveedor_nombre, p.codigo AS proveedor_codigo,
                       ur.codigo AS ubicacion_recep_codigo, ur.descipcion AS ubicacion_recep_nombre,
                       ud.id AS ubicacion_dest_id,
                       ud.codigo AS ubicacion_dest_codigo, ud.descipcion AS ubicacion_dest_nombre
                FROM recepciones_cabecera r
                JOIN proveedores p ON r.id_proveedor = p.id
                JOIN ubicaciones ur ON r.id_ubicacion_recep = ur.id
                LEFT JOIN ubicaciones ud ON r.id_ubicacion_destino = ud.id
                WHERE r.id_recepcion = %s AND (%s IS NULL OR r.tenant_id = %s)
            """, (id_recepcion, tenant_id, tenant_id))
            recepcion = cursor.fetchone()

            if not recepcion:
                flash("Recepción no encontrada.", "danger")
                return redirect(url_for('recepciones.listar'))

            cursor.execute("""
                SELECT d.*, m.codigo AS material_codigo, m.nombre AS material_nombre,
                       mp.codigo_referencia_prov,
                       un.nombre AS unidad_nombre
                FROM recepciones_detalle d
                JOIN materiales m ON d.id_material = m.id
                LEFT JOIN material_proveedor mp
                       ON mp.id_material = m.id AND mp.id_proveedor = %s
                LEFT JOIN unidades_medida un ON m.unidad_medida_id = un.id_unidad
                WHERE d.id_recepcion = %s
                  AND (%s IS NULL OR d.tenant_id = %s)
                ORDER BY d.id_detalle
            """, (recepcion['id_proveedor'], id_recepcion, tenant_id, tenant_id))
            detalle = cursor.fetchall()

            # Materiales disponibles del proveedor para el selector
            cursor.execute("""
                SELECT m.id, m.codigo, m.nombre,
                       COALESCE(m.codigo_barras, '') AS codigo_barras,
                       mp.codigo_referencia_prov,
                       un.nombre AS unidad_nombre
                FROM materiales m
                JOIN material_proveedor mp ON m.id = mp.id_material
                LEFT JOIN unidades_medida un ON m.unidad_medida_id = un.id_unidad
                WHERE mp.id_proveedor = %s AND m.activo = 1 AND (%s IS NULL OR m.tenant_id = %s)
                ORDER BY m.nombre
            """, (recepcion['id_proveedor'], tenant_id, tenant_id))
            materiales = cursor.fetchall()

            # Ubicaciones para el modal de cierre
            cursor.execute(f"""
                SELECT u.id, u.codigo, u.descipcion AS nombre, t.{quote('descripcion')} AS tipo
                FROM ubicaciones u
                JOIN tipoubicacion t ON u.tipoubicacion = t.id
                WHERE (%s IS NULL OR u.tenant_id = %s)
                ORDER BY u.codigo
            """, (tenant_id, tenant_id))
            ubicaciones_destino = cursor.fetchall()

            # OMC relacionada (si existe)
            cursor.execute(f"""
                SELECT id_omc, numero, estado
                FROM omc
                WHERE id_recepcion = %s AND (%s IS NULL OR tenant_id = %s)
                ORDER BY id_omc DESC {limit_sql(1)}
            """, (id_recepcion, tenant_id, tenant_id))
            omc_relacionada = cursor.fetchone()

        return render_template('recepciones_ver.html',
                               recepcion=recepcion,
                               detalle=detalle,
                               materiales=materiales,
                               ubicaciones_destino=ubicaciones_destino,
                               omc_relacionada=omc_relacionada)
    finally:
        conn.close()


# ============================================================================
# BÚSQUEDA DE MATERIALES (AJAX)
# ============================================================================
@recepciones_bp.route('/recepciones/buscar_materiales/<int:id_proveedor>')
def buscar_materiales(id_proveedor):
    q = request.args.get('q', '').strip()
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            like = f'%{q}%'
            cursor.execute(f"""
                SELECT m.id, m.codigo, m.nombre,
                       COALESCE(m.codigo_barras, '') AS codigo_barras,
                       mp.codigo_referencia_prov,
                       un.nombre AS unidad_nombre
                FROM materiales m
                JOIN material_proveedor mp ON m.id = mp.id_material
                LEFT JOIN unidades_medida un ON m.unidad_medida_id = un.id_unidad
                WHERE mp.id_proveedor = %s AND m.activo = 1 AND (%s IS NULL OR m.tenant_id = %s)
                  AND (m.nombre LIKE %s OR m.codigo LIKE %s
                       OR m.codigo_barras LIKE %s OR mp.codigo_referencia_prov LIKE %s)
                ORDER BY m.nombre
                {limit_sql(20)}
            """, (id_proveedor, tenant_id, tenant_id, like, like, like, like))
            return jsonify(cursor.fetchall())
    finally:
        conn.close()


@recepciones_bp.route('/recepciones/buscar_barcode/<int:id_proveedor>')
def buscar_barcode(id_proveedor):
    """Búsqueda exacta por código de barras (usado por lector)."""
    barcode = request.args.get('barcode', '').strip()
    if not barcode:
        return jsonify({})
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT m.id, m.codigo, m.nombre,
                       COALESCE(m.codigo_barras, '') AS codigo_barras,
                       mp.codigo_referencia_prov,
                       un.nombre AS unidad_nombre
                FROM materiales m
                JOIN material_proveedor mp ON m.id = mp.id_material
                LEFT JOIN unidades_medida un ON m.unidad_medida_id = un.id_unidad
                WHERE mp.id_proveedor = %s AND m.activo = 1 AND (%s IS NULL OR m.tenant_id = %s)
                  AND (m.codigo_barras = %s OR m.codigo = %s
                       OR mp.codigo_referencia_prov = %s)
                {limit_sql(1)}
            """, (id_proveedor, tenant_id, tenant_id, barcode, barcode, barcode))
            mat = cursor.fetchone()
            return jsonify(mat or {})
    finally:
        conn.close()


# ============================================================================
# BÚSQUEDA DE UBICACIONES (AJAX)
# ============================================================================
@recepciones_bp.route('/recepciones/buscar_ubicaciones')
def buscar_ubicaciones():
    q = request.args.get('q', '').strip()
    tipo = request.args.get('tipo', '')  # 'recep' filtra solo tipo Recepcion
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            like = f'%{q}%'
            if tipo == 'recep':
                cursor.execute(f"""
                    SELECT u.id, u.codigo, u.descipcion AS nombre, t.{quote('descripcion')} AS tipo
                    FROM ubicaciones u
                    JOIN tipoubicacion t ON u.tipoubicacion = t.id
                    WHERE t.{quote('descripcion')} LIKE '%Recepci%'
                      AND (u.codigo LIKE %s OR u.descipcion LIKE %s)
                      AND (%s IS NULL OR u.tenant_id = %s)
                    ORDER BY u.codigo
                    {limit_sql(20)}
                """, (like, like, tenant_id, tenant_id))
            else:
                cursor.execute(f"""
                    SELECT u.id, u.codigo, u.descipcion AS nombre, t.{quote('descripcion')} AS tipo
                    FROM ubicaciones u
                    JOIN tipoubicacion t ON u.tipoubicacion = t.id
                    WHERE (u.codigo LIKE %s OR u.descipcion LIKE %s)
                      AND (%s IS NULL OR u.tenant_id = %s)
                    ORDER BY u.codigo
                    {limit_sql(20)}
                """, (like, like, tenant_id, tenant_id))
            return jsonify(cursor.fetchall())
    finally:
        conn.close()


# ============================================================================
# GUARDAR ÍTEM (AJAX)
# ============================================================================
@recepciones_bp.route('/recepciones/guardar_item', methods=['POST'])
def guardar_item():
    d = request.json or {}
    id_recepcion  = d.get('id_recepcion')
    id_material   = d.get('id_material')
    lote          = (d.get('lote') or 'UNICO').strip() or 'UNICO'
    fecha_venc    = d.get('fecha_vencimiento') or None
    cant_esp      = float(d.get('cantidad_esperada') or 0)
    cant_rec      = float(d.get('cantidad_recibida') or 0)
    tipo_stock    = d.get('tipo_stock') or 'Libre Venta'
    observaciones = d.get('observaciones') or None
    id_detalle    = d.get('id_detalle')
    tenant_id = get_tenant_filter()

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT estado FROM recepciones_cabecera WHERE id_recepcion = %s AND (%s IS NULL OR tenant_id = %s)",
                (id_recepcion, tenant_id, tenant_id)
            )
            rec = cursor.fetchone()
            if not rec or rec['estado'] != 'Abierta':
                return jsonify({"ok": False, "msg": "La recepción no está Abierta."})

            if id_detalle:
                cursor.execute("""
                    UPDATE recepciones_detalle
                    SET cantidad_esperada=%s, cantidad_recibida=%s, lote=%s,
                        fecha_vencimiento=%s, tipo_stock=%s, observaciones=%s
                    WHERE id_detalle=%s AND id_recepcion=%s
                      AND (%s IS NULL OR tenant_id = %s)
                """, (cant_esp, cant_rec, lote, fecha_venc, tipo_stock,
                      observaciones, id_detalle, id_recepcion, tenant_id, tenant_id))
            else:
                if not id_material:
                    return jsonify({"ok": False, "msg": "Debe seleccionar un material."})
                id_detalle = execute_insert(cursor, """
                    INSERT INTO recepciones_detalle
                        (id_recepcion, id_material, lote, fecha_vencimiento,
                         cantidad_esperada, cantidad_recibida, tipo_stock, observaciones, tenant_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (id_recepcion, id_material, lote, fecha_venc,
                      cant_esp, cant_rec, tipo_stock, observaciones, tenant_id))

            conn.commit()
            return jsonify({"ok": True, "id_detalle": id_detalle})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "msg": str(e)})
    finally:
        conn.close()


# ============================================================================
# ELIMINAR ÍTEM (AJAX)
# ============================================================================
@recepciones_bp.route('/recepciones/eliminar_item/<int:id_detalle>', methods=['POST'])
def eliminar_item(id_detalle):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT r.estado FROM recepciones_detalle d
                JOIN recepciones_cabecera r ON d.id_recepcion = r.id_recepcion
                WHERE d.id_detalle = %s AND (%s IS NULL OR r.tenant_id = %s)
            """, (id_detalle, tenant_id, tenant_id))
            row = cursor.fetchone()
            if not row or row['estado'] != 'Abierta':
                return jsonify({"ok": False, "msg": "No se puede eliminar."})

            cursor.execute("DELETE FROM recepciones_detalle WHERE id_detalle = %s AND (%s IS NULL OR tenant_id = %s)", (id_detalle, tenant_id, tenant_id))
            conn.commit()
            return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "msg": str(e)})
    finally:
        conn.close()


# ============================================================================
# CERRAR RECEPCIÓN — impacta stockcontable
# ============================================================================
@recepciones_bp.route('/recepciones/cerrar/<int:id_recepcion>', methods=['POST'])
def cerrar(id_recepcion):
    id_ubicacion_destino = request.form.get('id_ubicacion_destino')
    if not id_ubicacion_destino:
        flash("Debe seleccionar la ubicación destino.", "warning")
        return redirect(url_for('recepciones.ver', id_recepcion=id_recepcion))

    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM recepciones_cabecera WHERE id_recepcion = %s AND estado = 'Abierta' AND (%s IS NULL OR tenant_id = %s)",
                (id_recepcion, tenant_id, tenant_id)
            )
            recepcion = cursor.fetchone()
            if not recepcion:
                flash("La recepción no existe o ya no está Abierta.", "danger")
                return redirect(url_for('recepciones.listar'))

            cursor.execute("""
                SELECT * FROM recepciones_detalle
                WHERE id_recepcion = %s AND cantidad_recibida > 0
                  AND (%s IS NULL OR tenant_id = %s)
            """, (id_recepcion, tenant_id, tenant_id))
            items = cursor.fetchall()

            if not items:
                flash("No hay ítems con cantidad recibida para cerrar la recepción.", "warning")
                return redirect(url_for('recepciones.ver', id_recepcion=id_recepcion))

            contenedor = recepcion['id_contenedor']
            ahora = datetime.now()
            usuario = session.get('nombre', 'sistema')

            for item in items:
                # El stock queda en la ubicación de recepción como StockSaliendo
                cols_stock = ['Ubicacion', 'Material', 'Lote', 'TipoStock', 'IDContenedor',
                              'StockTotal', 'StockDisponible', 'StockEntrando', 'StockSaliendo',
                              'UltimaEntrada', 'UltimoMovimiento', 'FechaVencimiento', 'UsuarioUltimoMov']
                sql_saliendo = upsert_incremental_sql('stockcontable', cols_stock, 'Ubicacion',
                                                      ['StockSaliendo'], ['UltimoMovimiento', 'UsuarioUltimoMov'])
                cursor.execute(sql_saliendo, (
                    recepcion['id_ubicacion_recep'], item['id_material'], item['lote'],
                    item['tipo_stock'], contenedor,
                    0, 0, 0, item['cantidad_recibida'],
                    None, ahora, item['fecha_vencimiento'], usuario
                ))

                # Crear StockEntrando en la ubicación destino
                sql_entrando = upsert_incremental_sql('stockcontable', cols_stock, 'Ubicacion',
                                                      ['StockEntrando'], ['UltimoMovimiento', 'UsuarioUltimoMov'])
                cursor.execute(sql_entrando, (
                    id_ubicacion_destino, item['id_material'], item['lote'],
                    item['tipo_stock'], contenedor,
                    0, 0, item['cantidad_recibida'], 0,
                    None, ahora, item['fecha_vencimiento'], usuario
                ))

            # Generar número de OMC
            anio_omc = ahora.year
            expr_omc = cast_as_int(substring_index("numero", "-", -1))
            cursor.execute(
                f"SELECT MAX({expr_omc}) AS max_seq "
                f"FROM omc WHERE {year_func('fecha_creacion')} = %s AND (%s IS NULL OR tenant_id = %s)",
                (anio_omc, tenant_id, tenant_id)
            )
            seq_omc = (cursor.fetchone()['max_seq'] or 0) + 1
            numero_omc = f"OMC-{anio_omc}-{seq_omc:05d}"

            id_omc_rec = execute_insert(cursor, """
                INSERT INTO omc
                    (numero, id_contenedor, id_ubicacion_origen, id_ubicacion_destino,
                     id_recepcion, estado, observaciones, usuario_creacion, fecha_creacion, tenant_id)
                VALUES (%s, %s, %s, %s, %s, 'Pendiente', %s, %s, %s, %s)
            """, (
                numero_omc, contenedor,
                recepcion['id_ubicacion_recep'], id_ubicacion_destino,
                id_recepcion,
                f"Generada al cerrar recepción {recepcion['numero']}",
                usuario, ahora, tenant_id
            ))
            cursor.execute("""
                INSERT INTO omc_contenedores
                    (id_omc, id_contenedor, id_contenedor_destino, id_ubicacion_origen)
                VALUES (%s, %s, NULL, %s)
            """, (id_omc_rec, contenedor, recepcion['id_ubicacion_recep']))

            # Cerrar cabecera
            cursor.execute("""
                UPDATE recepciones_cabecera
                SET estado = 'Cerrada', fecha_cierre = %s,
                    usuario_cierre = %s, id_ubicacion_destino = %s
                WHERE id_recepcion = %s AND (%s IS NULL OR tenant_id = %s)
            """, (ahora, usuario, id_ubicacion_destino, id_recepcion, tenant_id, tenant_id))

            conn.commit()
            flash(
                f"Recepción {recepcion['numero']} cerrada. "
                f"{len(items)} ítem(s) registrado(s). "
                f"OMC {numero_omc} generada para confirmar el traslado.",
                "success"
            )
            return redirect(url_for('recepciones.ver', id_recepcion=id_recepcion))

    except Exception as e:
        conn.rollback()
        flash(f"Error al cerrar la recepción (sin cambios guardados): {str(e)}", "danger")
        return redirect(url_for('recepciones.ver', id_recepcion=id_recepcion))
    finally:
        conn.close()


# ============================================================================
# ELIMINAR RECEPCIÓN (solo Abierta sin materiales)
# ============================================================================
@recepciones_bp.route('/recepciones/eliminar/<int:id_recepcion>', methods=['POST'])
def eliminar(id_recepcion):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT numero, estado FROM recepciones_cabecera WHERE id_recepcion = %s AND (%s IS NULL OR tenant_id = %s)",
                (id_recepcion, tenant_id, tenant_id)
            )
            rec = cursor.fetchone()
            if not rec or rec['estado'] != 'Abierta':
                flash("Solo se pueden eliminar recepciones Abiertas.", "warning")
                return redirect(url_for('recepciones.listar'))

            cursor.execute(
                "SELECT COUNT(*) AS total FROM recepciones_detalle WHERE id_recepcion = %s AND (%s IS NULL OR tenant_id = %s)",
                (id_recepcion, tenant_id, tenant_id)
            )
            if cursor.fetchone()['total'] > 0:
                flash("No se puede eliminar: la recepción tiene materiales asignados.", "danger")
                return redirect(url_for('recepciones.ver', id_recepcion=id_recepcion))

            cursor.execute(
                "DELETE FROM recepciones_cabecera WHERE id_recepcion = %s AND (%s IS NULL OR tenant_id = %s)",
                (id_recepcion, tenant_id, tenant_id)
            )
            conn.commit()
            flash(f"Recepción {rec['numero']} eliminada.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {str(e)}", "danger")
    finally:
        conn.close()
    return redirect(url_for('recepciones.listar'))


@recepciones_bp.route('/recepciones/confirmar_stock/<int:id_recepcion>', methods=['POST'])
def confirmar_stock(id_recepcion):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM recepciones_cabecera WHERE id_recepcion = %s AND estado = 'Cerrada' AND (%s IS NULL OR tenant_id = %s)",
                (id_recepcion, tenant_id, tenant_id)
            )
            recepcion = cursor.fetchone()
            if not recepcion:
                flash("La recepción no existe o no está en estado Cerrada.", "danger")
                return redirect(url_for('recepciones.ver', id_recepcion=id_recepcion))

            ahora = datetime.now()
            usuario = session.get('nombre', 'sistema')

            cursor.execute("""
                UPDATE stockcontable
                SET StockTotal       = StockTotal + StockEntrando,
                    StockDisponible  = StockDisponible + StockEntrando,
                    StockEntrando    = 0,
                    UltimaEntrada    = %s,
                    UltimoMovimiento = %s,
                    UsuarioUltimoMov = %s
                WHERE IDContenedor = %s AND StockEntrando > 0 AND (%s IS NULL OR tenant_id = %s)
            """, (ahora, ahora, usuario, recepcion['id_contenedor'], tenant_id, tenant_id))

            filas = cursor.rowcount

            cursor.execute(
                "UPDATE recepciones_cabecera SET estado = 'Confirmada' WHERE id_recepcion = %s AND (%s IS NULL OR tenant_id = %s)",
                (id_recepcion, tenant_id, tenant_id)
            )

            conn.commit()
            flash(f"Entrada confirmada. {filas} registro(s) de stock pasaron a Disponible.", "success")

    except Exception as e:
        conn.rollback()
        flash(f"Error al confirmar la entrada: {str(e)}", "danger")
    finally:
        conn.close()

    return redirect(url_for('recepciones.ver', id_recepcion=id_recepcion))


# ============================================================================
# ANULAR RECEPCIÓN
# ============================================================================
@recepciones_bp.route('/recepciones/anular/<int:id_recepcion>', methods=['POST'])
def anular(id_recepcion):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT numero, estado FROM recepciones_cabecera WHERE id_recepcion = %s AND (%s IS NULL OR tenant_id = %s)",
                (id_recepcion, tenant_id, tenant_id)
            )
            rec = cursor.fetchone()
            if not rec or rec['estado'] != 'Abierta':
                flash("Solo se pueden anular recepciones Abiertas.", "warning")
                return redirect(url_for('recepciones.listar'))

            usuario = session.get('nombre', 'sistema')
            cursor.execute("""
                UPDATE recepciones_cabecera
                SET estado = 'Anulada', fecha_cierre = %s, usuario_cierre = %s
                WHERE id_recepcion = %s AND (%s IS NULL OR tenant_id = %s)
            """, (datetime.now(), usuario, id_recepcion, tenant_id, tenant_id))
            conn.commit()
            flash(f"Recepción {rec['numero']} anulada.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {str(e)}", "danger")
    finally:
        conn.close()
    return redirect(url_for('recepciones.listar'))


# ============================================================================
# IMPORTAR RECEPCIONES
# ============================================================================
_CAMPOS_IMPORT_REC = [
    'agrupador', 'proveedor_codigo', 'ubicacion_recep', 'ubicacion_destino',
    'observaciones', 'material_codigo', 'lote', 'fecha_vencimiento', 'cantidad', 'tipo_stock'
]
_EJEMPLO_IMPORT_REC = [
    'LOTE-2024-001', 'PROV001', 'UB-RECEP', 'UB-DEPOSITO',
    'Importación masiva', 'MAT001', 'UNICO', '', '100', 'Libre Venta'
]


@recepciones_bp.route('/recepciones/importar', methods=['POST'])
def importar():
    file = request.files.get('archivo')
    if not file or not file.filename:
        return jsonify({'error': 'No se proporcionó archivo'}), 400
    try:
        rows = parse_file(file)
    except Exception as e:
        return jsonify({'error': f'Error al leer el archivo: {str(e)}'}), 400

    grupos = OrderedDict()
    for i, row in enumerate(rows, 1):
        agrupador = str(row.get('agrupador', '') or '').strip() or f'__fila_{i}__'
        grupos.setdefault(agrupador, []).append((i, row))

    insertados, errores = 0, []
    conn = get_db_connection()
    try:
        usuario = session.get('nombre', 'sistema')
        anio = datetime.now().year
        tenant_id = get_tenant_filter()

        for agrupador, filas in grupos.items():
            _, primera = filas[0]
            proveedor_cod  = str(primera.get('proveedor_codigo', '') or '').strip()
            ubic_recep_cod = str(primera.get('ubicacion_recep', '') or '').strip()
            ubic_dest_cod  = str(primera.get('ubicacion_destino', '') or '').strip()
            observaciones  = str(primera.get('observaciones', '') or '').strip() or None

            if not proveedor_cod:
                errores.append({'fila': filas[0][0], 'codigo': agrupador, 'razon': 'proveedor_codigo es obligatorio'})
                continue
            if not ubic_recep_cod:
                errores.append({'fila': filas[0][0], 'codigo': agrupador, 'razon': 'ubicacion_recep es obligatorio'})
                continue

            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id FROM proveedores WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)", (proveedor_cod, tenant_id, tenant_id))
                    prov = cursor.fetchone()
                    if not prov:
                        errores.append({'fila': filas[0][0], 'codigo': agrupador, 'razon': f'Proveedor "{proveedor_cod}" no encontrado'})
                        continue

                    cursor.execute("SELECT id FROM ubicaciones WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)", (ubic_recep_cod, tenant_id, tenant_id))
                    ubic_recep = cursor.fetchone()
                    if not ubic_recep:
                        errores.append({'fila': filas[0][0], 'codigo': agrupador, 'razon': f'Ubicación recep "{ubic_recep_cod}" no encontrada'})
                        continue

                    id_dest = None
                    if ubic_dest_cod:
                        cursor.execute("SELECT id FROM ubicaciones WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)", (ubic_dest_cod, tenant_id, tenant_id))
                        ubic_dest = cursor.fetchone()
                        if ubic_dest:
                            id_dest = ubic_dest['id']

                    expr_imp = cast_as_int(substring_index("numero", "-", -1))
                    cursor.execute(
                        f"SELECT MAX({expr_imp}) AS max_seq "
                        f"FROM recepciones_cabecera WHERE {year_func('fecha_recepcion')} = %s AND (%s IS NULL OR tenant_id = %s)", (anio, tenant_id, tenant_id)
                    )
                    seq = (cursor.fetchone()['max_seq'] or 0) + 1
                    numero = f"REC-{anio}-{seq:05d}"

                    id_recepcion = execute_insert(cursor, """
                        INSERT INTO recepciones_cabecera
                            (numero, id_proveedor, id_ubicacion_recep, id_ubicacion_destino,
                             observaciones, usuario_creacion, tenant_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (numero, prov['id'], ubic_recep['id'], id_dest, observaciones, usuario, tenant_id))

                    cursor.execute(
                        "UPDATE recepciones_cabecera SET id_contenedor = %s WHERE id_recepcion = %s AND (%s IS NULL OR tenant_id = %s)",
                        (f"RC{id_recepcion:05d}", id_recepcion, tenant_id, tenant_id)
                    )

                    lineas_ok = 0
                    for fila_num, row in filas:
                        material_cod = str(row.get('material_codigo', '') or '').strip()
                        if not material_cod:
                            continue
                        cursor.execute("SELECT id FROM materiales WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)", (material_cod, tenant_id, tenant_id))
                        mat = cursor.fetchone()
                        if not mat:
                            errores.append({'fila': fila_num, 'codigo': agrupador, 'razon': f'Material "{material_cod}" no encontrado'})
                            continue
                        cursor.execute("""
                            INSERT INTO recepciones_detalle
                                (id_recepcion, id_material, lote, fecha_vencimiento,
                                 cantidad_esperada, cantidad_recibida, tipo_stock, tenant_id)
                            VALUES (%s, %s, %s, %s, %s, 0, %s, %s)
                        """, (
                            id_recepcion, mat['id'],
                            str(row.get('lote', '') or '').strip() or 'UNICO',
                            str(row.get('fecha_vencimiento', '') or '').strip() or None,
                            float_or_zero(row.get('cantidad')),
                            str(row.get('tipo_stock', '') or '').strip() or 'Libre Venta',
                            tenant_id
                        ))
                        lineas_ok += 1

                    if lineas_ok == 0:
                        errores.append({'fila': filas[0][0], 'codigo': agrupador, 'razon': 'Ninguna línea de material válida'})
                    else:
                        insertados += 1

            except Exception as e:
                errores.append({'fila': filas[0][0], 'codigo': agrupador, 'razon': str(e)})

        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

    return jsonify({'insertados': insertados, 'omitidos': [], 'errores': errores})


@recepciones_bp.route('/recepciones/plantilla/<formato>')
def plantilla(formato):
    if formato == 'csv':
        return plantilla_csv(_CAMPOS_IMPORT_REC, _EJEMPLO_IMPORT_REC, 'plantilla_recepciones.csv')
    elif formato == 'json':
        return plantilla_json(_CAMPOS_IMPORT_REC, _EJEMPLO_IMPORT_REC, 'plantilla_recepciones.json')
    elif formato == 'xlsx':
        return plantilla_xlsx(_CAMPOS_IMPORT_REC, _EJEMPLO_IMPORT_REC, 'plantilla_recepciones.xlsx')
    return 'Formato no válido', 400
