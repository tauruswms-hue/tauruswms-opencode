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

categorias_bp = Blueprint('categorias', __name__)


@categorias_bp.route('/categorias')
def listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM categorias WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s) ORDER BY nombre ASC", (tenant_id, tenant_id))
            categorias = cursor.fetchall()
        return render_template('categorias.html', categorias=categorias)
    finally:
        conn.close()


@categorias_bp.route('/categorias/guardar', methods=['POST'])
def guardar():
    d = request.form
    c_id = d.get('id_categoria')
    tenant_id = get_tenant_filter()

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if c_id and c_id.strip():
                sql = "UPDATE categorias SET codigo=%s, nombre=%s, descripcion=%s, activo=%s WHERE id_categoria=%s AND (%s IS NULL OR tenant_id = %s)"
                cursor.execute(sql, (d.get('codigo'), d.get('nombre'), d.get('descripcion'), 1 if d.get('activo') else 0, c_id, tenant_id, tenant_id))
            else:
                sql = "INSERT INTO categorias (codigo, nombre, descripcion, activo, tenant_id) VALUES (%s, %s, %s, %s, %s)"
                cursor.execute(sql, (d.get('codigo'), d.get('nombre'), d.get('descripcion'), 1 if d.get('activo') else 0, tenant_id))

            conn.commit()
            flash("Categoría guardada con éxito", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('categorias.listar'))


@categorias_bp.route('/categorias/eliminar/<int:id>', methods=['POST'])
def eliminar(id):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE categorias SET activo = 0 WHERE id_categoria = %s AND (%s IS NULL OR tenant_id = %s)", (id, tenant_id, tenant_id))
            conn.commit()
            flash("Categoría inactivada", "success")
    finally:
        conn.close()
    return redirect(url_for('categorias.listar'))


# ── Batch ─────────────────────────────────────────────────────────────────────
_CAMPOS = ['codigo', 'nombre', 'descripcion', 'activo']
_EJEMPLO = ['CAT001', 'Novelas', 'Libros de ficción y narrativa', '1']


@categorias_bp.route('/categorias/importar', methods=['POST'])
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
            codigo = str(row.get('codigo', '') or '').strip()
            nombre = str(row.get('nombre', '') or '').strip()
            if not codigo or not nombre:
                errores.append({'fila': i, 'codigo': codigo or '(vacío)', 'razon': 'Código y Nombre son obligatorios'})
                continue
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id_categoria FROM categorias WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)", (codigo, tenant_id, tenant_id))
                    if cursor.fetchone():
                        omitidos.append(codigo)
                        continue
                    activo = 1 if str(row.get('activo', '1')).strip().lower() in ('1', 'true', 'si', 'sí', 'yes') else 0
                    cursor.execute("""
                        INSERT INTO categorias (codigo, nombre, descripcion, activo, tenant_id)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        codigo,
                        nombre,
                        str(row.get('descripcion', '') or '').strip() or None,
                        activo,
                        tenant_id
                    ))
                    insertados += 1
            except Exception as e:
                errores.append({'fila': i, 'codigo': codigo, 'razon': str(e)})
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()
    return jsonify({'insertados': insertados, 'omitidos': omitidos, 'errores': errores})


@categorias_bp.route('/categorias/exportar/<formato>')
def exportar(formato):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT codigo, nombre, descripcion, activo
                FROM categorias
                WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s)
                ORDER BY nombre
            """, (tenant_id, tenant_id))
            rows = cursor.fetchall()
    finally:
        conn.close()

    if formato == 'csv':
        return export_csv(rows, _CAMPOS, 'categorias.csv')
    elif formato == 'json':
        return export_json(rows, _CAMPOS, 'categorias.json')
    elif formato == 'xlsx':
        return export_xlsx(rows, _CAMPOS, 'categorias.xlsx')
    return 'Formato no válido', 400


@categorias_bp.route('/categorias/plantilla/<formato>')
def plantilla(formato):
    if formato == 'csv':
        return plantilla_csv(_CAMPOS, _EJEMPLO, 'plantilla_categorias.csv')
    elif formato == 'json':
        return plantilla_json(_CAMPOS, _EJEMPLO, 'plantilla_categorias.json')
    elif formato == 'xlsx':
        return plantilla_xlsx(_CAMPOS, _EJEMPLO, 'plantilla_categorias.xlsx')
    return 'Formato no válido', 400
