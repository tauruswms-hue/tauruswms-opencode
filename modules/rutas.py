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

rutas_bp = Blueprint('rutas', __name__)


@rutas_bp.route('/rutas')
def listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM rutas WHERE (%s IS NULL OR tenant_id = %s) ORDER BY nombre_ruta ASC", (tenant_id, tenant_id))
            rutas = cursor.fetchall()
        return render_template('rutas.html', rutas=rutas)
    finally:
        conn.close()


@rutas_bp.route('/rutas/guardar', methods=['POST'])
def guardar():
    d = request.form
    r_id = d.get('id_ruta')
    tenant_id = get_tenant_filter()

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            nombre = d.get('nombre_ruta')
            descripcion = d.get('descripcion')

            if r_id and r_id.strip():
                sql = "UPDATE rutas SET nombre_ruta=%s, descripcion=%s WHERE id_ruta=%s AND (%s IS NULL OR tenant_id = %s)"
                cursor.execute(sql, (nombre, descripcion, r_id, tenant_id, tenant_id))
            else:
                sql = "INSERT INTO rutas (nombre_ruta, descripcion, tenant_id) VALUES (%s, %s, %s)"
                cursor.execute(sql, (nombre, descripcion, tenant_id))

            conn.commit()
            flash("Ruta guardada correctamente", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('rutas.listar'))


@rutas_bp.route('/rutas/eliminar/<int:id>', methods=['POST'])
def eliminar(id):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Nota: Si la ruta está asignada a un transporte, fallará por FK (lo cual es correcto)
            cursor.execute("DELETE FROM rutas WHERE id_ruta = %s AND (%s IS NULL OR tenant_id = %s)", (id, tenant_id, tenant_id))
            conn.commit()
            flash("Ruta eliminada", "success")
    except Exception:
        flash("No se puede eliminar la ruta porque está asignada a uno o más transportes.", "danger")
    finally:
        conn.close()
    return redirect(url_for('rutas.listar'))


# ── Batch ─────────────────────────────────────────────────────────────────────
_CAMPOS = ['nombre_ruta', 'descripcion']
_EJEMPLO = ['Zona Norte', 'Ruta de reparto zona norte']


@rutas_bp.route('/rutas/importar', methods=['POST'])
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
            nombre = str(row.get('nombre_ruta', '') or '').strip()
            if not nombre:
                errores.append({'fila': i, 'codigo': '(vacío)', 'razon': 'El campo nombre_ruta es obligatorio'})
                continue
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT id_ruta FROM rutas WHERE nombre_ruta = %s AND (%s IS NULL OR tenant_id = %s)",
                        (nombre, tenant_id, tenant_id))
                    if cursor.fetchone():
                        omitidos.append(nombre)
                        continue
                    cursor.execute(
                        "INSERT INTO rutas (nombre_ruta, descripcion, tenant_id) VALUES (%s, %s, %s)",
                        (nombre, str(row.get('descripcion', '') or '').strip() or None, tenant_id))
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


@rutas_bp.route('/rutas/exportar/<formato>')
def exportar(formato):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT nombre_ruta, descripcion FROM rutas WHERE (%s IS NULL OR tenant_id = %s) ORDER BY nombre_ruta",
                (tenant_id, tenant_id))
            rows = cursor.fetchall()
    finally:
        conn.close()

    if formato == 'csv':
        return export_csv(rows, _CAMPOS, 'rutas.csv')
    elif formato == 'json':
        return export_json(rows, _CAMPOS, 'rutas.json')
    elif formato == 'xlsx':
        return export_xlsx(rows, _CAMPOS, 'rutas.xlsx')
    return 'Formato no válido', 400


@rutas_bp.route('/rutas/plantilla/<formato>')
def plantilla(formato):
    if formato == 'csv':
        return plantilla_csv(_CAMPOS, _EJEMPLO, 'plantilla_rutas.csv')
    elif formato == 'json':
        return plantilla_json(_CAMPOS, _EJEMPLO, 'plantilla_rutas.json')
    elif formato == 'xlsx':
        return plantilla_xlsx(_CAMPOS, _EJEMPLO, 'plantilla_rutas.xlsx')
    return 'Formato no válido', 400