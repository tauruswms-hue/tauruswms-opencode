from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from modules.batch_utils import (
    bool_col,
    export_csv,
    export_json,
    export_xlsx,
    parse_file,
    plantilla_csv,
    plantilla_json,
    plantilla_xlsx,
)
from modules.context import get_tenant_filter
from modules.db_config import get_db_connection

clases_pedido_bp = Blueprint('clases_pedido', __name__)


@clases_pedido_bp.route('/clases-pedido')
def listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM clases_pedido WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s) ORDER BY nombre ASC", (tenant_id, tenant_id))
            clases = cursor.fetchall()
        return render_template('clases_pedido.html', clases=clases)
    finally:
        conn.close()


@clases_pedido_bp.route('/clases-pedido/guardar', methods=['POST'])
def guardar():
    d = request.form
    id_clase = d.get('id_clase')
    tenant_id = get_tenant_filter()

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if id_clase and id_clase.strip():
                sql = "UPDATE clases_pedido SET nombre=%s, activo=%s WHERE id_clase=%s AND (%s IS NULL OR tenant_id = %s)"
                cursor.execute(sql, (d.get('nombre'), 1 if d.get('activo') else 0, id_clase, tenant_id, tenant_id))
            else:
                sql = "INSERT INTO clases_pedido (nombre, activo, tenant_id) VALUES (%s, %s, %s)"
                cursor.execute(sql, (d.get('nombre'), 1 if d.get('activo') else 0, tenant_id))
            conn.commit()
            flash("Clase de pedido guardada con éxito", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('clases_pedido.listar'))


@clases_pedido_bp.route('/clases-pedido/eliminar/<int:id_clase>', methods=['POST'])
def eliminar(id_clase):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as total FROM pedidos_cabecera WHERE id_clase = %s AND (%s IS NULL OR tenant_id = %s)", (id_clase, tenant_id, tenant_id))
            if cursor.fetchone()['total'] > 0:
                flash("No se puede eliminar: existen pedidos vinculados a esta clase.", "warning")
            else:
                cursor.execute("UPDATE clases_pedido SET activo = 0 WHERE id_clase = %s AND (%s IS NULL OR tenant_id = %s)", (id_clase, tenant_id, tenant_id))
                conn.commit()
                flash("Clase de pedido inactivada.", "success")
    finally:
        conn.close()
    return redirect(url_for('clases_pedido.listar'))


# ── Batch ─────────────────────────────────────────────────────────────────────
_CAMPOS = ['nombre', 'activo']
_EJEMPLO = ['Urgente', '1']


@clases_pedido_bp.route('/clases-pedido/importar', methods=['POST'])
def importar():
    tenant_id = get_tenant_filter()
    file = request.files.get('archivo')
    if not file or not file.filename:
        return jsonify({'error': 'No se proporcionó archivo'}), 400
    try:
        rows = parse_file(file, request.form.get('hoja'))
    except Exception as e:
        return jsonify({'error': f'Error al leer el archivo: {e!s}'}), 400

    insertados, omitidos, errores = 0, [], []
    conn = get_db_connection()
    try:
        for i, row in enumerate(rows, 1):
            nombre = str(row.get('nombre', '') or '').strip()
            if not nombre:
                errores.append({'fila': i, 'codigo': '(vacío)', 'razon': 'El campo nombre es obligatorio'})
                continue
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT id_clase FROM clases_pedido WHERE nombre = %s AND (%s IS NULL OR tenant_id = %s)",
                        (nombre, tenant_id, tenant_id))
                    if cursor.fetchone():
                        omitidos.append(nombre)
                        continue
                    cursor.execute(
                        "INSERT INTO clases_pedido (nombre, activo, tenant_id) VALUES (%s, %s, %s)",
                        (nombre, bool_col(row.get('activo', '1')), tenant_id))
                    insertados += 1
            except Exception as e:
                errores.append({'fila': i, 'codigo': nombre, 'razon': str(e)})
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()
    return jsonify({'insertados': insertados, 'omitidos': omitidos, 'errores': errores})


@clases_pedido_bp.route('/clases-pedido/exportar/<formato>')
def exportar(formato):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT nombre, activo FROM clases_pedido WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s) ORDER BY nombre",
                (tenant_id, tenant_id))
            rows = cursor.fetchall()
    finally:
        conn.close()

    if formato == 'csv':
        return export_csv(rows, _CAMPOS, 'clases_pedido.csv')
    elif formato == 'json':
        return export_json(rows, _CAMPOS, 'clases_pedido.json')
    elif formato == 'xlsx':
        return export_xlsx(rows, _CAMPOS, 'clases_pedido.xlsx')
    return 'Formato no válido', 400


@clases_pedido_bp.route('/clases-pedido/plantilla/<formato>')
def plantilla(formato):
    if formato == 'csv':
        return plantilla_csv(_CAMPOS, _EJEMPLO, 'plantilla_clases_pedido.csv')
    elif formato == 'json':
        return plantilla_json(_CAMPOS, _EJEMPLO, 'plantilla_clases_pedido.json')
    elif formato == 'xlsx':
        return plantilla_xlsx(_CAMPOS, _EJEMPLO, 'plantilla_clases_pedido.xlsx')
    return 'Formato no válido', 400


@clases_pedido_bp.route('/clases-pedido/plantilla-datos/<formato>')
def plantilla_datos(formato):
    """XLSX/CSV/JSON con las clases de pedido reales, listo para importar."""
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT nombre, activo FROM clases_pedido "
                "WHERE (tenant_id IS NULL OR tenant_id = %s OR %s IS NULL) ORDER BY nombre",
                (tenant_id, tenant_id))
            rows = cursor.fetchall()
    finally:
        conn.close()

    if formato == 'xlsx':
        return export_xlsx(rows, _CAMPOS, 'clases_pedido_importar.xlsx')
    elif formato == 'csv':
        return export_csv(rows, _CAMPOS, 'clases_pedido_importar.csv')
    elif formato == 'json':
        return export_json(rows, _CAMPOS, 'clases_pedido_importar.json')
    return 'Formato no válido', 400
