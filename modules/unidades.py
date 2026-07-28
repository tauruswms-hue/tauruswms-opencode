from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, session
from modules.db_config import get_db_connection
from modules.batch_utils import (parse_file, export_csv, export_json, export_xlsx,
                                 plantilla_csv, plantilla_json, plantilla_xlsx)

unidades_bp = Blueprint('unidades', __name__)


def get_tenant_filter():
    return session.get('tenant_id')


@ unidades_bp.route('/unidades')
def unidades():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM unidades_medida WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s) ORDER BY id_unidad DESC", (tenant_id, tenant_id))
            res_unidades = cursor.fetchall()
        return render_template('unidades.html', unidades=res_unidades)
    finally:
        conn.close()


@ unidades_bp.route('/unidades/guardar', methods=['POST'])
def guardar():
    d = request.form
    u_id = d.get('id_unidad')
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if u_id and u_id.strip():
                sql = """UPDATE unidades_medida SET 
                         codigo=%s, nombre=%s, simbolo=%s, tipo_magnitud=%s, 
                         conversion_a_base=%s, unidad_base_referencia=%s, 
                         decimales_permitidos=%s, activo=%s
                         WHERE id_unidad=%s AND (%s IS NULL OR tenant_id = %s)"""
                cursor.execute(sql, (
                    d.get('codigo'), d.get('nombre'), d.get('simbolo'), d.get('tipo_magnitud'),
                    float(d.get('conversion_a_base') or 1), d.get('unidad_base_referencia') or 'U',
                    int(d.get('decimales_permitidos') or 0), 1 if d.get('activo') else 0,
                    u_id, tenant_id, tenant_id))
            else:
                sql = """INSERT INTO unidades_medida 
                         (codigo, nombre, simbolo, tipo_magnitud, conversion_a_base, 
                          unidad_base_referencia, decimales_permitidos, activo, tenant_id) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                cursor.execute(sql, (
                    d.get('codigo'), d.get('nombre'), d.get('simbolo'), d.get('tipo_magnitud'),
                    float(d.get('conversion_a_base') or 1), d.get('unidad_base_referencia') or 'U',
                    int(d.get('decimales_permitidos') or 0), 1 if d.get('activo') else 0, tenant_id))

            conn.commit()
            flash("Unidad guardada correctamente", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {str(e)}", "danger")
    finally:
        conn.close()
    return redirect(url_for('unidades.unidades'))


@unidades_bp.route('/unidades/eliminar/<int:id>', methods=['POST'])
def eliminar(id):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE unidades_medida SET activo = 0 WHERE id_unidad = %s AND (%s IS NULL OR tenant_id = %s)", (id, tenant_id, tenant_id))
            conn.commit()
    finally:
        conn.close()
    return redirect(url_for('unidades.unidades'))


# ── Batch ─────────────────────────────────────────────────────────────────────
_CAMPOS = ['codigo', 'nombre', 'simbolo', 'tipo_magnitud', 'conversion_a_base', 'unidad_base_referencia', 'decimales_permitidos', 'activo']
_EJEMPLO = ['UND', 'Unidad', 'U', 'CANTIDAD', '1', 'U', '0', '1']


@ unidades_bp.route('/unidades/importar', methods=['POST'])
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
            codigo = str(row.get('codigo', '') or '').strip()
            nombre = str(row.get('nombre', '') or '').strip()
            if not codigo or not nombre:
                errores.append({'fila': i, 'codigo': codigo or '(vacío)', 'razon': 'Código y Nombre son obligatorios'})
                continue
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id_unidad FROM unidades_medida WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)", (codigo, tenant_id, tenant_id))
                    if cursor.fetchone():
                        omitidos.append(codigo)
                        continue
                    activo = 1 if str(row.get('activo', '1')).strip().lower() in ('1', 'true', 'si', 'sí', 'yes') else 0
                    cursor.execute("""
                        INSERT INTO unidades_medida 
                            (codigo, nombre, simbolo, tipo_magnitud, conversion_a_base, 
                             unidad_base_referencia, decimales_permitidos, activo, tenant_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        codigo,
                        nombre,
                        str(row.get('simbolo', '') or '').strip() or None,
                        str(row.get('tipo_magnitud', '') or '').strip() or 'CANTIDAD',
                        float(row.get('conversion_a_base')) if row.get('conversion_a_base') else 1.0,
                        str(row.get('unidad_base_referencia', '') or '').strip() or 'U',
                        int(row.get('decimales_permitidos')) if row.get('decimales_permitidos') else 0,
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


@ unidades_bp.route('/unidades/exportar/<formato>')
def exportar(formato):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT codigo, nombre, simbolo, tipo_magnitud, conversion_a_base, 
                       unidad_base_referencia, decimales_permitidos, activo
                FROM unidades_medida
                WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s)
                ORDER BY nombre
            """, (tenant_id, tenant_id))
            rows = cursor.fetchall()
    finally:
        conn.close()

    if formato == 'csv':
        return export_csv(rows, _CAMPOS, 'unidades_medida.csv')
    elif formato == 'json':
        return export_json(rows, _CAMPOS, 'unidades_medida.json')
    elif formato == 'xlsx':
        return export_xlsx(rows, _CAMPOS, 'unidades_medida.xlsx')
    return 'Formato no válido', 400


@ unidades_bp.route('/unidades/plantilla/<formato>')
def plantilla(formato):
    if formato == 'csv':
        return plantilla_csv(_CAMPOS, _EJEMPLO, 'plantilla_unidades.csv')
    elif formato == 'json':
        return plantilla_json(_CAMPOS, _EJEMPLO, 'plantilla_unidades.json')
    elif formato == 'xlsx':
        return plantilla_xlsx(_CAMPOS, _EJEMPLO, 'plantilla_unidades.xlsx')
    return 'Formato no válido', 400
