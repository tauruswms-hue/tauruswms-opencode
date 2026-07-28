from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from modules.db_config import get_db_connection
from modules.sql_dialect import quote
from modules.batch_utils import (parse_file, export_csv, export_json, export_xlsx,
                                  plantilla_csv, plantilla_json, plantilla_xlsx,
                                  bool_col)

tipoubicacion_bp = Blueprint('tipoubicacion', __name__)


def get_tenant_filter():
    return session.get('tenant_id')


@tipoubicacion_bp.route('/tipoubicacion')
def listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM tipoubicacion 
                WHERE (%s IS NULL OR tenant_id = %s) 
                ORDER BY id DESC
            """, (tenant_id, tenant_id))
            tipos = cursor.fetchall()
        return render_template('tipoubicacion.html', tipos=tipos)
    finally:
        conn.close()


@tipoubicacion_bp.route('/tipoubicacion/guardar', methods=['POST'])
def guardar():
    tenant_id = get_tenant_filter()
    descripcion     = request.form.get('descipcion')
    soporte_picking = 1 if request.form.get('soporte_picking') else 0
    t_id = request.form.get('id')

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if t_id and t_id.strip():
                sql = f"UPDATE tipoubicacion SET {quote('descripcion')}=%s, soporte_picking=%s WHERE id=%s AND (%s IS NULL OR tenant_id = %s)"
                cursor.execute(sql, (descripcion, soporte_picking, t_id, tenant_id, tenant_id))
            else:
                sql = f"INSERT INTO tipoubicacion ({quote('descripcion')}, soporte_picking, tenant_id) VALUES (%s, %s, %s)"
                cursor.execute(sql, (descripcion, soporte_picking, tenant_id))

            conn.commit()
            flash("Tipo de ubicación guardado", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {str(e)}", "danger")
    finally:
        conn.close()
    return redirect(url_for('tipoubicacion.listar'))


@tipoubicacion_bp.route('/tipoubicacion/eliminar/<int:id>', methods=['POST'])
def eliminar(id):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT count(*) as total FROM ubicaciones 
                WHERE tipoubicacion = %s AND (%s IS NULL OR tenant_id = %s)
            """, (id, tenant_id, tenant_id))
            result = cursor.fetchone()

            if result['total'] > 0:
                flash("No se puede eliminar porque está en uso por ubicaciones.", "danger")
            else:
                cursor.execute("DELETE FROM tipoubicacion WHERE id = %s AND (%s IS NULL OR tenant_id = %s)", 
                               (id, tenant_id, tenant_id))
                conn.commit()
                flash("Tipo de ubicación eliminado", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    finally:
        conn.close()
    return redirect(url_for('tipoubicacion.listar'))


# ── Batch ─────────────────────────────────────────────────────────────────────
_CAMPOS_EXPORT = ['descripcion', 'soporte_picking']
_CAMPOS_IMPORT = ['descripcion', 'soporte_picking']
_EJEMPLO = ['Estantería', '1']


@tipoubicacion_bp.route('/tipoubicacion/importar', methods=['POST'])
def importar():
    tenant_id = get_tenant_filter()
    file = request.files.get('archivo')
    if not file or not file.filename:
        return jsonify({'error': 'No se proporcionó archivo'}), 400
    try:
        rows = parse_file(file)
    except Exception as e:
        return jsonify({'error': f'Error al leer el archivo: {str(e)}'}), 400

    insertados, omitidos, errores = 0, [], []
    conn = get_db_connection()
    try:
        for i, row in enumerate(rows, 1):
            descripcion = str(row.get('descripcion', '') or '').strip()
            if not descripcion:
                errores.append({'fila': i, 'codigo': '(vacío)',
                                'razon': 'El campo descripcion es obligatorio'})
                continue
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"SELECT id FROM tipoubicacion WHERE {quote('descripcion')} = %s AND (%s IS NULL OR tenant_id = %s)",
                        (descripcion, tenant_id, tenant_id))
                    if cursor.fetchone():
                        omitidos.append(descripcion)
                        continue
                    cursor.execute(
                        f"INSERT INTO tipoubicacion ({quote('descripcion')}, soporte_picking, tenant_id) VALUES (%s, %s, %s)",
                        (descripcion, bool_col(row.get('soporte_picking', '0')), tenant_id))
                    insertados += 1
            except Exception as e:
                errores.append({'fila': i, 'codigo': descripcion, 'razon': str(e)})
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()
    return jsonify({'insertados': insertados, 'omitidos': omitidos, 'errores': errores})


@tipoubicacion_bp.route('/tipoubicacion/exportar/<formato>')
def exportar(formato):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT {quote('descripcion')} AS descripcion, soporte_picking
                FROM tipoubicacion
                WHERE (%s IS NULL OR tenant_id = %s)
                ORDER BY {quote('descripcion')}
            """, (tenant_id, tenant_id))
            rows = cursor.fetchall()
    finally:
        conn.close()

    if formato == 'csv':
        return export_csv(rows, _CAMPOS_EXPORT, 'tipos_ubicacion.csv')
    elif formato == 'json':
        return export_json(rows, _CAMPOS_EXPORT, 'tipos_ubicacion.json')
    elif formato == 'xlsx':
        return export_xlsx(rows, _CAMPOS_EXPORT, 'tipos_ubicacion.xlsx')
    return 'Formato no válido', 400


@tipoubicacion_bp.route('/tipoubicacion/plantilla/<formato>')
def plantilla(formato):
    if formato == 'csv':
        return plantilla_csv(_CAMPOS_IMPORT, _EJEMPLO, 'plantilla_tipos_ubicacion.csv')
    elif formato == 'json':
        return plantilla_json(_CAMPOS_IMPORT, _EJEMPLO, 'plantilla_tipos_ubicacion.json')
    elif formato == 'xlsx':
        return plantilla_xlsx(_CAMPOS_IMPORT, _EJEMPLO, 'plantilla_tipos_ubicacion.xlsx')
    return 'Formato no válido', 400