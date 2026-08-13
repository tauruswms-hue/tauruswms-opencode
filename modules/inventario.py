from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
import datetime
from modules.db_config import get_db_connection
from modules.sql_dialect import execute_insert, limit_sql, in_clause_sql

inventario_bp = Blueprint('inventario', __name__)


def get_tenant_filter():
    return session.get('tenant_id')


def _siguiente_numero(cursor, tenant_id):
    anio = datetime.date.today().year
    cursor.execute(
        f"SELECT numero FROM inventarios_cabecera WHERE numero LIKE %s AND (%s IS NULL OR tenant_id = %s) ORDER BY id DESC {limit_sql(1)}",
        (f'INV-{anio}-%', tenant_id, tenant_id)
    )
    row = cursor.fetchone()
    if row:
        ultimo = int(row['numero'].split('-')[-1])
    else:
        ultimo = 0
    return f'INV-{anio}-{ultimo + 1:05d}'


# ── Listar inventarios ────────────────────────────────────────────────────────

@inventario_bp.route('/inventario')
def listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT ic.*,
                       COUNT(id2.id)                                   AS total_lineas,
                       SUM(id2.stock_contado IS NOT NULL)              AS lineas_contadas,
                       SUM(ABS(COALESCE(id2.stock_contado,0) - id2.stock_sistema) > 0
                           AND id2.stock_contado IS NOT NULL)          AS lineas_con_diferencia
                FROM inventarios_cabecera ic
                LEFT JOIN inventarios_detalle id2 ON id2.id_inventario = ic.id
                WHERE (%s IS NULL OR ic.tenant_id = %s)
                GROUP BY ic.id
                ORDER BY ic.id DESC
            """, (tenant_id, tenant_id))
            inventarios = cursor.fetchall()

            cursor.execute("""
                SELECT DISTINCT u.id, u.codigo, u.descipcion
                FROM stockcontable sc
                JOIN ubicaciones u ON sc.Ubicacion = u.id
                WHERE (sc.StockTotal > 0 OR sc.StockDisponible > 0)
                  AND (%s IS NULL OR u.tenant_id = %s)
                ORDER BY u.codigo
            """, (tenant_id, tenant_id))
            ubicaciones = cursor.fetchall()

            cursor.execute("""
                SELECT DISTINCT m.id, m.codigo, m.nombre
                FROM stockcontable sc
                JOIN materiales m ON sc.Material = m.id
                WHERE (sc.StockTotal > 0 OR sc.StockDisponible > 0)
                  AND (%s IS NULL OR m.tenant_id = %s)
                ORDER BY m.codigo
            """, (tenant_id, tenant_id))
            materiales = cursor.fetchall()

        return render_template('inventario.html',
                               inventarios=inventarios,
                               ubicaciones=ubicaciones,
                               materiales=materiales)
    finally:
        conn.close()


# ── Crear nuevo inventario ────────────────────────────────────────────────────

@inventario_bp.route('/inventario/crear', methods=['POST'])
def crear():
    descripcion   = request.form.get('descripcion', '').strip()
    modo          = request.form.get('modo', 'todo')
    id_material   = request.form.get('id_material', '').strip()
    id_ubicaciones = request.form.getlist('id_ubicaciones')
    usuario = session.get('nombre', 'sistema')
    tenant_id = get_tenant_filter()

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            numero = _siguiente_numero(cursor, tenant_id)

            where_extra = "AND (sc.StockTotal > 0 OR sc.StockDisponible > 0)"
            params = []

            if modo == 'material' and id_material:
                where_extra += " AND sc.Material = %s"
                params.append(int(id_material))

            elif modo == 'ubicaciones' and id_ubicaciones:
                placeholders = in_clause_sql(id_ubicaciones)
                where_extra += f" AND sc.Ubicacion IN ({placeholders})"
                params.extend([int(x) for x in id_ubicaciones])

            cursor.execute(f"""
                SELECT sc.Ubicacion, sc.Material, sc.IDContenedor, sc.Lote,
                       sc.TipoStock, sc.StockTotal
                FROM stockcontable sc
                WHERE 1=1 AND (%s IS NULL OR sc.tenant_id = %s) {where_extra}
                ORDER BY sc.Ubicacion, sc.Material, sc.IDContenedor
            """, (tenant_id, tenant_id) + tuple(params))
            posiciones = cursor.fetchall()

            if not posiciones:
                flash('No se encontraron posiciones de stock con los filtros seleccionados.', 'warning')
                return redirect(url_for('inventario.listar'))

            id_inventario = execute_insert(cursor,
                "INSERT INTO inventarios_cabecera (numero, descripcion, usuario_creacion, tenant_id) VALUES (%s, %s, %s, %s)",
                (numero, descripcion or None, usuario, tenant_id)
            )

            cursor.executemany("""
                INSERT INTO inventarios_detalle
                    (id_inventario, id_ubicacion, id_material, id_contenedor, lote, tipo_stock, stock_sistema, tenant_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, [
                (id_inventario, p['Ubicacion'], p['Material'],
                 p['IDContenedor'], p['Lote'], p['TipoStock'], p['StockTotal'], tenant_id)
                for p in posiciones
            ])

        conn.commit()
        flash(f'Inventario {numero} creado con {len(posiciones)} posiciones.', 'success')
        return redirect(url_for('inventario.detalle', id_inventario=id_inventario))
    except Exception as e:
        conn.rollback()
        flash(f'Error al crear inventario: {str(e)}', 'danger')
        return redirect(url_for('inventario.listar'))
    finally:
        conn.close()


# ── Detalle / conteo ──────────────────────────────────────────────────────────

@inventario_bp.route('/inventario/<int:id_inventario>')
def ver_inventario(id_inventario):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM inventarios_cabecera WHERE id = %s AND (%s IS NULL OR tenant_id = %s)", 
                (id_inventario, tenant_id, tenant_id)
            )
            inventario = cursor.fetchone()
            if not inventario:
                flash('Inventario no encontrado.', 'danger')
                return redirect(url_for('inventario.listar'))

            cursor.execute("""
                SELECT d.*,
                       u.codigo      AS ubicacion_codigo,
                       u.descipcion  AS ubicacion_descripcion,
                       m.codigo      AS material_codigo,
                       m.nombre      AS material_nombre
                FROM inventarios_detalle d
                LEFT JOIN ubicaciones u ON d.id_ubicacion = u.id
                LEFT JOIN materiales  m ON d.id_material  = m.id
                WHERE d.id_inventario = %s
                  AND (%s IS NULL OR d.tenant_id = %s)
                ORDER BY u.codigo, m.codigo, d.id_contenedor
            """, (id_inventario, tenant_id, tenant_id))
            lineas = cursor.fetchall()

        return render_template('inventario_detalle.html',
                               inventario=inventario, lineas=lineas)
    finally:
        conn.close()


# ── Guardar conteo de una línea (AJAX) ────────────────────────────────────────

@inventario_bp.route('/inventario/linea/<int:id_linea>/contar', methods=['POST'])
def guardar_conteo(id_linea):
    tenant_id = get_tenant_filter()
    data = request.get_json()
    if data is None:
        return jsonify({'ok': False, 'error': 'Sin datos'}), 400

    try:
        cantidad = float(data.get('cantidad'))
        if cantidad < 0:
            return jsonify({'ok': False, 'error': 'La cantidad no puede ser negativa'}), 400
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'Cantidad inválida'}), 400

    usuario = session.get('nombre', 'sistema')
    ahora = datetime.datetime.now()

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Verificar que el inventario esté Abierto y pertenezca al tenant
            cursor.execute("""
                SELECT ic.estado, d.stock_sistema
                FROM inventarios_detalle d
                JOIN inventarios_cabecera ic ON ic.id = d.id_inventario
                WHERE d.id = %s AND (%s IS NULL OR ic.tenant_id = %s)
            """, (id_linea, tenant_id, tenant_id))
            row = cursor.fetchone()
            if not row:
                return jsonify({'ok': False, 'error': 'Línea no encontrada'}), 404
            if row['estado'].upper() != 'ABIERTO':
                return jsonify({'ok': False, 'error': 'El inventario está cerrado'}), 400

            stock_sistema = float(row['stock_sistema'])
            diferencia = cantidad - stock_sistema

            cursor.execute("""
                UPDATE inventarios_detalle
                SET stock_contado  = %s,
                    fecha_conteo   = %s,
                    usuario_conteo = %s
                WHERE id = %s
                  AND (%s IS NULL OR tenant_id = %s)
            """, (cantidad, ahora, usuario, id_linea, tenant_id, tenant_id))
        conn.commit()
        return jsonify({
            'ok': True,
            'stock_contado': cantidad,
            'diferencia': diferencia,
            'fecha': ahora.strftime('%d/%m/%Y %H:%M'),
            'usuario': usuario
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


# ── Anular inventario ─────────────────────────────────────────────────────────

@inventario_bp.route('/inventario/<int:id_inventario>/anular', methods=['POST'])
def anular(id_inventario):
    tenant_id = get_tenant_filter()
    usuario = session.get('nombre', 'sistema')
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT estado FROM inventarios_cabecera WHERE id = %s AND (%s IS NULL OR tenant_id = %s)", 
                (id_inventario, tenant_id, tenant_id)
            )
            row = cursor.fetchone()
            if not row or row['estado'].upper() != 'ABIERTO':
                flash('Solo se pueden anular inventarios en estado Abierto.', 'warning')
                return redirect(url_for('inventario.detalle', id_inventario=id_inventario))

            cursor.execute("""
                UPDATE inventarios_cabecera
                SET estado = 'Anulado', fecha_anulacion = %s, usuario_anulacion = %s
                WHERE id = %s AND (%s IS NULL OR tenant_id = %s)
            """, (datetime.datetime.now(), usuario, id_inventario, tenant_id, tenant_id))
        conn.commit()
        flash('Inventario anulado.', 'warning')
    except Exception as e:
        conn.rollback()
        flash(f'Error al anular inventario: {str(e)}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('inventario.detalle', id_inventario=id_inventario))


# ── Cerrar inventario ─────────────────────────────────────────────────────────

@inventario_bp.route('/inventario/<int:id_inventario>/cerrar', methods=['POST'])
def cerrar(id_inventario):
    tenant_id = get_tenant_filter()
    usuario = session.get('nombre', 'sistema')
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT estado FROM inventarios_cabecera WHERE id = %s AND (%s IS NULL OR tenant_id = %s)", 
                (id_inventario, tenant_id, tenant_id)
            )
            row = cursor.fetchone()
            if not row or row['estado'].upper() != 'ABIERTO':
                flash('El inventario no existe o ya está cerrado.', 'warning')
                return redirect(url_for('inventario.detalle', id_inventario=id_inventario))

            cursor.execute("""
                UPDATE inventarios_cabecera
                SET estado = 'Cerrado', fecha_cierre = %s, usuario_cierre = %s
                WHERE id = %s AND (%s IS NULL OR tenant_id = %s)
            """, (datetime.datetime.now(), usuario, id_inventario, tenant_id, tenant_id))
        conn.commit()
        flash('Inventario cerrado correctamente.', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error al cerrar inventario: {str(e)}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('inventario.detalle', id_inventario=id_inventario))
