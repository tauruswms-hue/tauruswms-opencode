import datetime

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
from werkzeug.security import check_password_hash

from modules.auditoria import registrar_movimiento
from modules.context import get_tenant_filter
from modules.db_config import _get_admin_connection, get_db_connection
from modules.sql_dialect import (
    cast_as_int,
    execute_insert,
    group_concat,
    limit_sql,
    quote,
    substring_index,
    upsert_incremental_sql,
)
from modules.sql_dialect import year as year_func

movil_bp = Blueprint('movil', __name__)


def _generar_numero_recepcion(cursor, tenant_id):
    anio = datetime.datetime.now().year
    expr = cast_as_int(substring_index("numero", "-", -1))
    cursor.execute(
        f"SELECT MAX({expr}) AS max_seq "
        f"FROM recepciones_cabecera WHERE {year_func('fecha_recepcion')} = %s AND (%s IS NULL OR tenant_id = %s)",
        (anio, tenant_id, tenant_id)
    )
    seq = (cursor.fetchone()['max_seq'] or 0) + 1
    return f"REC-{anio}-{seq:05d}"


# ============================================================================
# HUB
# ============================================================================
@movil_bp.route('/movil')
def hub():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS total FROM recepciones_cabecera WHERE estado = 'Abierta' AND (%s IS NULL OR tenant_id = %s)",
                (tenant_id, tenant_id)
            )
            recepciones_abiertas = cursor.fetchone()['total']

            cursor.execute(
                "SELECT COUNT(*) AS total FROM omc WHERE estado = 'Pendiente' AND (%s IS NULL OR tenant_id = %s)",
                (tenant_id, tenant_id)
            )
            omcs_pendientes = cursor.fetchone()['total']
    finally:
        conn.close()

    return render_template('movil_hub.html',
                           recepciones_abiertas=recepciones_abiertas,
                           omcs_pendientes=omcs_pendientes)


# ============================================================================
# RECEPCIÓN MÓVIL
# ============================================================================
@movil_bp.route('/movil/recepcion')
def recepcion_listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT r.*, p.razonsocial AS proveedor_nombre,
                       ur.codigo AS ubicacion_recep_codigo,
                       ud.codigo AS ubicacion_dest_codigo,
                       (SELECT COALESCE(SUM(d.cantidad_recibida), 0) FROM recepciones_detalle d
                        WHERE d.id_recepcion = r.id_recepcion) AS total_unidades
                FROM recepciones_cabecera r
                JOIN proveedores p ON r.id_proveedor = p.id
                JOIN ubicaciones ur ON r.id_ubicacion_recep = ur.id
                LEFT JOIN ubicaciones ud ON r.id_ubicacion_destino = ud.id
                WHERE (%s IS NULL OR r.tenant_id = %s)
                ORDER BY r.id_recepcion DESC
                {limit_sql(50)}
            """, (tenant_id, tenant_id))
            recepciones = cursor.fetchall()

            cursor.execute(
                "SELECT id, codigo, razonsocial FROM proveedores WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s) ORDER BY razonsocial",
                (tenant_id, tenant_id)
            )
            proveedores = cursor.fetchall()

            cursor.execute(f"""
                SELECT u.id, u.codigo, u.descipcion AS nombre
                FROM ubicaciones u
                JOIN tipoubicacion t ON u.tipoubicacion = t.id
                WHERE t.{quote('descripcion')} LIKE %s AND (%s IS NULL OR u.tenant_id = %s)
                ORDER BY u.codigo
            """, ('%Recepci%', tenant_id, tenant_id))
            ubicaciones = cursor.fetchall()
    finally:
        conn.close()

    return render_template('movil_recepcion.html',
                           recepciones=recepciones,
                           proveedores=proveedores,
                           ubicaciones=ubicaciones)


@movil_bp.route('/movil/recepcion/guardar', methods=['POST'])
def recepcion_guardar():
    d = request.form
    tenant_id = get_tenant_filter()
    id_proveedor = d.get('id_proveedor')
    id_ubicacion = d.get('id_ubicacion_recep')

    if not id_proveedor or not id_ubicacion:
        flash("Debe seleccionar proveedor y ubicación de recepción.", "warning")
        return redirect(url_for('movil.recepcion_listar'))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            numero = _generar_numero_recepcion(cursor, tenant_id)
            usuario = session.get('nombre', 'sistema')
            id_recepcion = execute_insert(cursor, """
                INSERT INTO recepciones_cabecera
                    (numero, id_proveedor, id_ubicacion_recep, id_ubicacion_destino,
                     id_contenedor, observaciones, usuario_creacion, tenant_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (numero, id_proveedor, id_ubicacion, None, '',
                  d.get('observaciones') or None, usuario, tenant_id))
            cursor.execute(
                "UPDATE recepciones_cabecera SET id_contenedor = %s WHERE id_recepcion = %s AND (%s IS NULL OR tenant_id = %s)",
                (f"RC{id_recepcion:05d}", id_recepcion, tenant_id, tenant_id)
            )
            conn.commit()
            flash(f"Recepción {numero} creada. Escanee los materiales.", "success")
            return redirect(url_for('movil.recepcion_detalle', id_recepcion=id_recepcion))
    except Exception as e:
        conn.rollback()
        flash(f"Error al crear la recepción: {e!s}", "danger")
        return redirect(url_for('movil.recepcion_listar'))
    finally:
        conn.close()


@movil_bp.route('/movil/recepcion/<int:id_recepcion>')
def recepcion_detalle(id_recepcion):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT r.*, p.razonsocial AS proveedor_nombre,
                       ur.codigo AS ubicacion_recep_codigo, ur.descipcion AS ubicacion_recep_nombre
                FROM recepciones_cabecera r
                JOIN proveedores p ON r.id_proveedor = p.id
                JOIN ubicaciones ur ON r.id_ubicacion_recep = ur.id
                WHERE r.id_recepcion = %s AND (%s IS NULL OR r.tenant_id = %s)
            """, (id_recepcion, tenant_id, tenant_id))
            recepcion = cursor.fetchone()
            if not recepcion:
                flash("Recepción no encontrada.", "danger")
                return redirect(url_for('movil.recepcion_listar'))

            cursor.execute("""
                SELECT d.*, m.codigo AS material_codigo, m.nombre AS material_nombre,
                       COALESCE(m.codigo_barras, '') AS codigo_barras,
                       un.nombre AS unidad_nombre
                FROM recepciones_detalle d
                JOIN materiales m ON d.id_material = m.id
                LEFT JOIN unidades_medida un ON m.unidad_medida_id = un.id_unidad
                WHERE d.id_recepcion = %s AND (%s IS NULL OR d.tenant_id = %s)
                ORDER BY d.id_detalle
            """, (id_recepcion, tenant_id, tenant_id))
            items = cursor.fetchall()

            cursor.execute("""
                SELECT u.id, u.codigo, u.descipcion AS nombre
                FROM ubicaciones u
                JOIN tipoubicacion t ON u.tipoubicacion = t.id
                WHERE (%s IS NULL OR u.tenant_id = %s)
                ORDER BY u.codigo
            """, (tenant_id, tenant_id))
            ubicaciones_destino = cursor.fetchall()
    finally:
        conn.close()

    return render_template('movil_recepcion_detalle.html',
                           recepcion=recepcion,
                           items=items,
                           ubicaciones_destino=ubicaciones_destino)


@movil_bp.route('/movil/recepcion/<int:id_recepcion>/buscar')
def recepcion_buscar(id_recepcion):
    """Búsqueda exacta por código de barras / código / referencia del proveedor."""
    barcode = request.args.get('barcode', '').strip()
    if not barcode:
        return jsonify({})
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id_proveedor FROM recepciones_cabecera
                WHERE id_recepcion = %s AND (%s IS NULL OR tenant_id = %s)
            """, (id_recepcion, tenant_id, tenant_id))
            rec = cursor.fetchone()
            if not rec:
                return jsonify({"error": "Recepción no encontrada"}), 404

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
            """, (rec['id_proveedor'], tenant_id, tenant_id, barcode, barcode, barcode))
            mat = cursor.fetchone()
            return jsonify(mat or {})
    finally:
        conn.close()


@movil_bp.route('/movil/recepcion/<int:id_recepcion>/agregar', methods=['POST'])
def recepcion_agregar(id_recepcion):
    d = request.json or {}
    id_material = d.get('id_material')
    lote = (d.get('lote') or 'UNICO').strip() or 'UNICO'
    fecha_venc = d.get('fecha_vencimiento') or None
    cantidad = float(d.get('cantidad') or 0)
    tipo_stock = d.get('tipo_stock') or 'Libre Venta'
    id_detalle = d.get('id_detalle')
    tenant_id = get_tenant_filter()

    if not id_material and not id_detalle:
        return jsonify({"ok": False, "msg": "Material no reconocido."})

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT estado FROM recepciones_cabecera WHERE id_recepcion = %s AND (%s IS NULL OR tenant_id = %s)",
                (id_recepcion, tenant_id, tenant_id)
            )
            rec = cursor.fetchone()
            if not rec or rec['estado'].upper() != 'ABIERTA':
                return jsonify({"ok": False, "msg": "La recepción no está Abierta."})

            if id_detalle:
                cursor.execute("""
                    UPDATE recepciones_detalle
                    SET cantidad_esperada=%s, cantidad_recibida=%s, lote=%s,
                        fecha_vencimiento=%s, tipo_stock=%s
                    WHERE id_detalle=%s AND id_recepcion=%s
                      AND (%s IS NULL OR tenant_id = %s)
                """, (cantidad, cantidad, lote, fecha_venc, tipo_stock,
                      id_detalle, id_recepcion, tenant_id, tenant_id))
            else:
                id_detalle = execute_insert(cursor, """
                    INSERT INTO recepciones_detalle
                        (id_recepcion, id_material, lote, fecha_vencimiento,
                         cantidad_esperada, cantidad_recibida, tipo_stock, tenant_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (id_recepcion, id_material, lote, fecha_venc,
                      cantidad, cantidad, tipo_stock, tenant_id))
            conn.commit()
            return jsonify({"ok": True, "id_detalle": id_detalle})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "msg": str(e)})
    finally:
        conn.close()


@movil_bp.route('/movil/recepcion/<int:id_recepcion>/eliminar_item/<int:id_detalle>', methods=['POST'])
def recepcion_eliminar_item(id_recepcion, id_detalle):
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
            if not row or row['estado'].upper() != 'ABIERTA':
                return jsonify({"ok": False, "msg": "No se puede eliminar."})
            cursor.execute(
                "DELETE FROM recepciones_detalle WHERE id_detalle = %s AND id_recepcion = %s AND (%s IS NULL OR tenant_id = %s)",
                (id_detalle, id_recepcion, tenant_id, tenant_id)
            )
            conn.commit()
            return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "msg": str(e)})
    finally:
        conn.close()


@movil_bp.route('/movil/recepcion/<int:id_recepcion>/cerrar', methods=['POST'])
def recepcion_cerrar(id_recepcion):
    id_ubicacion_destino = request.form.get('id_ubicacion_destino')
    if not id_ubicacion_destino:
        flash("Debe seleccionar la ubicación destino.", "warning")
        return redirect(url_for('movil.recepcion_detalle', id_recepcion=id_recepcion))

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
                return redirect(url_for('movil.recepcion_listar'))

            cursor.execute("""
                SELECT * FROM recepciones_detalle
                WHERE id_recepcion = %s AND cantidad_recibida > 0
                  AND (%s IS NULL OR tenant_id = %s)
            """, (id_recepcion, tenant_id, tenant_id))
            items = cursor.fetchall()
            if not items:
                flash("No hay ítems con cantidad recibida para cerrar la recepción.", "warning")
                return redirect(url_for('movil.recepcion_detalle', id_recepcion=id_recepcion))

            contenedor = recepcion['id_contenedor']
            ahora = datetime.datetime.now()
            usuario = session.get('nombre', 'sistema')

            for item in items:
                cols_stock = ['Ubicacion', 'Material', 'Lote', 'TipoStock', 'IDContenedor',
                              'StockTotal', 'StockDisponible', 'StockEntrando', 'StockSaliendo',
                              'UltimaEntrada', 'UltimoMovimiento', 'FechaVencimiento', 'UsuarioUltimoMov', 'tenant_id']
                sql_saliendo = upsert_incremental_sql('stockcontable', cols_stock, ['Ubicacion', 'Material', 'IDContenedor'],
                                                      ['StockSaliendo'], ['UltimoMovimiento', 'UsuarioUltimoMov'])
                cursor.execute(sql_saliendo, (
                    recepcion['id_ubicacion_recep'], item['id_material'], item['lote'],
                    item['tipo_stock'], contenedor,
                    0, 0, 0, item['cantidad_recibida'],
                    None, ahora, item['fecha_vencimiento'], usuario, tenant_id
                ))
                registrar_movimiento(
                    conn, tenant_id=tenant_id, accion='RECEPCION', usuario=usuario,
                    modulo='movil', id_ubicacion=recepcion['id_ubicacion_recep'],
                    id_material=item['id_material'], id_contenedor=contenedor,
                    lote=item['lote'], tipo_stock=item['tipo_stock'],
                    cantidad=-item['cantidad_recibida'],
                    detalle=f"Stock saliendo al cerrar recepción {recepcion['numero']}")

                sql_entrando = upsert_incremental_sql('stockcontable', cols_stock, ['Ubicacion', 'Material', 'IDContenedor'],
                                                      ['StockEntrando'], ['UltimoMovimiento', 'UsuarioUltimoMov'])
                cursor.execute(sql_entrando, (
                    id_ubicacion_destino, item['id_material'], item['lote'],
                    item['tipo_stock'], contenedor,
                    0, 0, item['cantidad_recibida'], 0,
                    None, ahora, item['fecha_vencimiento'], usuario, tenant_id
                ))
                registrar_movimiento(
                    conn, tenant_id=tenant_id, accion='RECEPCION', usuario=usuario,
                    modulo='movil', id_ubicacion=id_ubicacion_destino,
                    id_material=item['id_material'], id_contenedor=contenedor,
                    lote=item['lote'], tipo_stock=item['tipo_stock'],
                    cantidad=item['cantidad_recibida'],
                    detalle=f"Stock entrando al cerrar recepción {recepcion['numero']}")

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
                f"Generada al cerrar recepción {recepcion['numero']} (móvil)",
                usuario, ahora, tenant_id
            ))
            cursor.execute("""
                INSERT INTO omc_contenedores
                    (id_omc, id_contenedor, id_contenedor_destino, id_ubicacion_origen)
                VALUES (%s, %s, NULL, %s)
            """, (id_omc_rec, contenedor, recepcion['id_ubicacion_recep']))

            cursor.execute("""
                UPDATE recepciones_cabecera
                SET estado = 'Cerrada', fecha_cierre = %s,
                    usuario_cierre = %s, id_ubicacion_destino = %s
                WHERE id_recepcion = %s AND (%s IS NULL OR tenant_id = %s)
            """, (ahora, usuario, id_ubicacion_destino, id_recepcion, tenant_id, tenant_id))

            conn.commit()
            flash(f"Recepción {recepcion['numero']} cerrada. OMC {numero_omc} generada.", "success")
            return redirect(url_for('movil.recepcion_detalle', id_recepcion=id_recepcion))
    except Exception as e:
        conn.rollback()
        flash(f"Error al cerrar la recepción: {e!s}", "danger")
        return redirect(url_for('movil.recepcion_detalle', id_recepcion=id_recepcion))
    finally:
        conn.close()


# ============================================================================
# PICKING MÓVIL
# ============================================================================
@movil_bp.route('/movil/picking')
def picking_listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT o.id_omc, o.numero, o.id_ubicacion_destino,
                       ud.codigo AS destino_codigo, ud.descipcion AS destino_nombre,
                       p.nro_pedido AS pedido_numero,
                       r.numero AS recepcion_numero,
                       {group_concat('oc.id_contenedor', 'oc.id_contenedor')} AS contenedores
                FROM omc o
                JOIN ubicaciones ud ON o.id_ubicacion_destino = ud.id
                LEFT JOIN pedidos_cabecera p ON o.id_pedido = p.id_pedido
                LEFT JOIN recepciones_cabecera r ON o.id_recepcion = r.id_recepcion
                LEFT JOIN omc_contenedores oc ON o.id_omc = oc.id_omc
                WHERE o.estado = 'Pendiente' AND (%s IS NULL OR o.tenant_id = %s)
                GROUP BY o.id_omc
                ORDER BY o.id_omc DESC
                {limit_sql(50)}
            """, (tenant_id, tenant_id))
            omcs = cursor.fetchall()
    finally:
        conn.close()

    return render_template('movil_picking.html', omcs=omcs)


@movil_bp.route('/movil/picking/<int:id_omc>')
def picking_detalle(id_omc):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT o.*, ud.codigo AS destino_codigo, ud.descipcion AS destino_nombre,
                       p.nro_pedido AS pedido_numero,
                       r.numero AS recepcion_numero
                FROM omc o
                JOIN ubicaciones ud ON o.id_ubicacion_destino = ud.id
                LEFT JOIN pedidos_cabecera p ON o.id_pedido = p.id_pedido
                LEFT JOIN recepciones_cabecera r ON o.id_recepcion = r.id_recepcion
                WHERE o.id_omc = %s AND o.estado = 'Pendiente' AND (%s IS NULL OR o.tenant_id = %s)
            """, (id_omc, tenant_id, tenant_id))
            omc = cursor.fetchone()
            if not omc:
                flash("OMC no encontrada o no está Pendiente.", "danger")
                return redirect(url_for('movil.picking_listar'))

            cursor.execute("""
                SELECT oc.id_contenedor, oc.id_ubicacion_origen,
                       u.codigo AS origen_codigo, u.descipcion AS origen_nombre
                FROM omc_contenedores oc
                JOIN ubicaciones u ON oc.id_ubicacion_origen = u.id
                WHERE oc.id_omc = %s AND (%s IS NULL OR u.tenant_id = %s)
                ORDER BY oc.id
            """, (id_omc, tenant_id, tenant_id))
            contenedores = cursor.fetchall()

            stock_origen = []
            for cont in contenedores:
                cursor.execute("""
                    SELECT sc.*, m.codigo AS mat_codigo, m.nombre AS mat_nombre,
                           u.codigo AS ubi_codigo, %s AS contenedor_id
                    FROM stockcontable sc
                    JOIN materiales m ON sc.Material = m.id
                    JOIN ubicaciones u ON sc.Ubicacion = u.id
                    WHERE sc.IDContenedor = %s AND sc.Ubicacion = %s
                      AND (%s IS NULL OR sc.tenant_id = %s)
                    ORDER BY m.codigo
                """, (cont['id_contenedor'], cont['id_contenedor'], cont['id_ubicacion_origen'], tenant_id, tenant_id))
                stock_origen.extend(cursor.fetchall())
    finally:
        conn.close()

    return render_template('movil_picking_detalle.html',
                           omc=omc,
                           contenedores=contenedores,
                           stock_origen=stock_origen)


@movil_bp.route('/movil/picking/<int:id_omc>/confirmar', methods=['POST'])
def picking_confirmar(id_omc):
    tenant_id = get_tenant_filter()
    if session.get('rol', '').upper() != 'ADMIN':
        flash("Solo un administrador puede confirmar una OMC.", "danger")
        return redirect(url_for('movil.picking_detalle', id_omc=id_omc))

    password = request.form.get('password_admin', '')
    if not password:
        flash("Debe ingresar la contraseña de administrador.", "warning")
        return redirect(url_for('movil.picking_detalle', id_omc=id_omc))

    conn_admin = _get_admin_connection()
    try:
        with conn_admin.cursor() as cursor_admin:
            cursor_admin.execute(
                "SELECT password_hash FROM usuarios WHERE id = %s AND activo = 1",
                (session.get('user_id'),)
            )
            user = cursor_admin.fetchone()
    finally:
        conn_admin.close()

    if not user or not check_password_hash(user['password_hash'], password):
        flash("Contraseña incorrecta.", "danger")
        return redirect(url_for('movil.picking_detalle', id_omc=id_omc))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM omc WHERE id_omc = %s AND estado = 'Pendiente' AND (%s IS NULL OR tenant_id = %s)",
                (id_omc, tenant_id, tenant_id)
            )
            omc = cursor.fetchone()
            if not omc:
                flash("La OMC no existe o no está en estado Pendiente.", "danger")
                return redirect(url_for('movil.picking_listar'))

            ahora = datetime.datetime.now()
            usuario = session.get('nombre', 'sistema')

            cursor.execute("""
                SELECT oc.id_contenedor, oc.id_ubicacion_origen,
                       u.codigo AS origen_codigo
                FROM omc_contenedores oc
                JOIN ubicaciones u ON oc.id_ubicacion_origen = u.id
                WHERE oc.id_omc = %s AND (%s IS NULL OR u.tenant_id = %s)
                ORDER BY oc.id
            """, (id_omc, tenant_id, tenant_id))
            contenedores = cursor.fetchall()

            materiales_confirmados = []
            if omc.get('id_pedido'):
                for cont in contenedores:
                    cont_dest = cont.get('id_contenedor_destino') or cont['id_contenedor']
                    cursor.execute("""
                        SELECT Material, StockEntrando AS cantidad
                        FROM stockcontable
                        WHERE IDContenedor = %s AND Ubicacion = %s AND StockEntrando > 0
                          AND (%s IS NULL OR tenant_id = %s)
                    """, (cont_dest, omc['id_ubicacion_destino'], tenant_id, tenant_id))
                    materiales_confirmados.extend(cursor.fetchall())

            filas = 0
            for cont in contenedores:
                cont_dest = cont.get('id_contenedor_destino') or cont['id_contenedor']

                cursor.execute("""
                    SELECT Material, Lote, TipoStock, StockSaliendo AS cantidad
                    FROM stockcontable
                    WHERE IDContenedor = %s AND Ubicacion = %s AND StockSaliendo > 0
                      AND (%s IS NULL OR tenant_id = %s)
                """, (cont['id_contenedor'], cont['id_ubicacion_origen'], tenant_id, tenant_id))
                origen_salientes = cursor.fetchall()

                cursor.execute("""
                    SELECT Ubicacion, Material, Lote, TipoStock,
                           SUM(StockEntrando) AS cantidad
                    FROM stockcontable
                    WHERE IDContenedor = %s AND Ubicacion = %s AND StockEntrando > 0
                      AND (%s IS NULL OR tenant_id = %s)
                    GROUP BY Ubicacion, Material, Lote, TipoStock
                """, (cont_dest, omc['id_ubicacion_destino'], tenant_id, tenant_id))
                destino_entrantes = cursor.fetchall()

                cursor.execute("""
                    DELETE FROM stockcontable
                    WHERE IDContenedor = %s AND Ubicacion = %s
                      AND (%s IS NULL OR tenant_id = %s)
                """, (cont['id_contenedor'], cont['id_ubicacion_origen'], tenant_id, tenant_id))
                cursor.execute("""
                    UPDATE stockcontable
                    SET StockTotal       = StockTotal       + StockEntrando,
                        StockDisponible  = StockDisponible  + StockEntrando,
                        StockEntrando    = 0,
                        UltimaEntrada    = %s,
                        UltimoMovimiento = %s,
                        UsuarioUltimoMov = %s
                    WHERE IDContenedor = %s AND Ubicacion = %s AND StockEntrando > 0
                      AND (%s IS NULL OR tenant_id = %s)
                """, (ahora, ahora, usuario, cont_dest, omc['id_ubicacion_destino'], tenant_id, tenant_id))
                filas += cursor.rowcount

                for rec in origen_salientes:
                    registrar_movimiento(
                        conn, tenant_id=tenant_id, accion='CONFIRMAR_OMC', usuario=usuario,
                        modulo='movil', id_ubicacion=cont['id_ubicacion_origen'],
                        id_material=rec['Material'], id_contenedor=cont['id_contenedor'],
                        lote=rec['Lote'], tipo_stock=rec['TipoStock'], cantidad=-rec['cantidad'],
                        detalle=f"Stock sale del origen al confirmar OMC {omc['numero']}")
                for rec in destino_entrantes:
                    registrar_movimiento(
                        conn, tenant_id=tenant_id, accion='CONFIRMAR_OMC', usuario=usuario,
                        modulo='movil', id_ubicacion=rec['Ubicacion'],
                        id_material=rec['Material'], id_contenedor=cont_dest,
                        lote=rec['Lote'], tipo_stock=rec['TipoStock'], cantidad=rec['cantidad'],
                        detalle=f"Stock pasó a Disponible en destino (OMC {omc['numero']})")

            cursor.execute("""
                UPDATE omc
                SET estado = 'Confirmada', fecha_confirmacion = %s, usuario_confirmacion = %s
                WHERE id_omc = %s AND (%s IS NULL OR tenant_id = %s)
            """, (ahora, usuario, id_omc, tenant_id, tenant_id))

            if omc['id_recepcion']:
                cursor.execute("""
                    UPDATE recepciones_cabecera
                    SET estado = 'Confirmada'
                    WHERE id_recepcion = %s AND estado = 'Cerrada'
                      AND (%s IS NULL OR tenant_id = %s)
                """, (omc['id_recepcion'], tenant_id, tenant_id))

            if omc.get('id_pedido'):
                for mat in materiales_confirmados:
                    cursor.execute("""
                        UPDATE pedidos_detalle
                        SET Cantidad_preparada = Cantidad_preparada + %s
                        WHERE id_pedido = %s AND id_material = %s
                          AND (%s IS NULL OR tenant_id = %s)
                    """, (mat['cantidad'], omc['id_pedido'], mat['Material'], tenant_id, tenant_id))
                cursor.execute("""
                    SELECT COUNT(*) AS total,
                           SUM(CASE WHEN estado = 'Confirmada' THEN 1 ELSE 0 END) AS confirmadas
                    FROM omc
                    WHERE id_pedido = %s AND estado != 'Anulada'
                      AND (%s IS NULL OR tenant_id = %s)
                """, (omc['id_pedido'], tenant_id, tenant_id))
                counts = cursor.fetchone()
                if counts and counts['total'] > 0 and counts['total'] == counts['confirmadas']:
                    cursor.execute("""
                        UPDATE pedidos_cabecera SET estado = 'Preparado'
                        WHERE id_pedido = %s AND estado NOT IN ('Preparado', 'Despachado', 'Anulado')
                          AND (%s IS NULL OR tenant_id = %s)
                    """, (omc['id_pedido'], tenant_id, tenant_id))

            conn.commit()
            flash(f"OMC {omc['numero']} confirmada. {filas} registro(s) de stock pasaron a Disponible.", "success")
            return redirect(url_for('movil.picking_listar'))
    except Exception as e:
        conn.rollback()
        flash(f"Error al confirmar la OMC: {e!s}", "danger")
        return redirect(url_for('movil.picking_detalle', id_omc=id_omc))
    finally:
        conn.close()


# ============================================================================
# INVENTARIO MÓVIL (consulta por escaneo)
# ============================================================================
@movil_bp.route('/movil/inventario')
def inventario():
    return render_template('movil_inventario.html')


@movil_bp.route('/movil/inventario/buscar')
def inventario_buscar():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({"ok": False, "msg": "Ingrese un código o nombre."})
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            like = f'%{q}%'
            cursor.execute(f"""
                SELECT m.id, m.codigo, m.nombre,
                       COALESCE(m.codigo_barras, '') AS codigo_barras,
                       un.nombre AS unidad_nombre
                FROM materiales m
                LEFT JOIN unidades_medida un ON m.unidad_medida_id = un.id_unidad
                WHERE m.activo = 1 AND (%s IS NULL OR m.tenant_id = %s)
                  AND (m.codigo_barras = %s OR m.codigo = %s OR m.nombre LIKE %s)
                ORDER BY m.codigo
                {limit_sql(1)}
            """, (tenant_id, tenant_id, q, q, like))
            mat = cursor.fetchone()
            if not mat:
                return jsonify({"ok": False, "msg": "Material no encontrado."})

            cursor.execute("""
                SELECT u.codigo AS ubicacion_codigo, u.descipcion AS ubicacion_nombre,
                       sc.IDContenedor, sc.Lote, sc.TipoStock,
                       sc.StockTotal, sc.StockDisponible,
                       sc.StockEntrando, sc.StockSaliendo, sc.FechaVencimiento
                FROM stockcontable sc
                LEFT JOIN ubicaciones u ON sc.Ubicacion = u.id
                WHERE sc.Material = %s AND (sc.StockTotal > 0 OR sc.StockDisponible > 0)
                  AND (%s IS NULL OR sc.tenant_id = %s)
                ORDER BY u.codigo, sc.IDContenedor
            """, (mat['id'], tenant_id, tenant_id))
            posiciones = cursor.fetchall()
            return jsonify({"ok": True, "material": mat, "posiciones": posiciones})
    finally:
        conn.close()
