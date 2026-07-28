from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from modules.batch_utils import (parse_file, export_csv, export_json, export_xlsx,
                                  plantilla_csv, plantilla_json, plantilla_xlsx)
from modules.db_config import get_db_connection

proveedores_bp = Blueprint('proveedores', __name__)


def get_tenant_filter():
    return session.get('tenant_id')


@proveedores_bp.route('/proveedores')
def listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM proveedores WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s) ORDER BY razonsocial ASC", (tenant_id, tenant_id))
            proveedores = cursor.fetchall()
        return render_template('proveedores.html', proveedores=proveedores)
    finally:
        conn.close()


@proveedores_bp.route('/proveedores/guardar', methods=['POST'])
def guardar():
    d = request.form
    p_id = d.get('id')
    tenant_id = get_tenant_filter()

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if p_id and p_id.strip():
                sql = """UPDATE proveedores SET codigo=%s, razonsocial=%s, cuit=%s, 
                         direccion=%s, telefono=%s, email=%s WHERE id=%s AND (%s IS NULL OR tenant_id = %s)"""
                cursor.execute(sql, (d.get('codigo'), d.get('razonsocial'), d.get('cuit'),
                                     d.get('direccion'), d.get('telefono'), d.get('email'),
                                     p_id, tenant_id, tenant_id))
            else:
                sql = """INSERT INTO proveedores (codigo, razonsocial, cuit, direccion, telefono, email, tenant_id) 
                         VALUES (%s, %s, %s, %s, %s, %s, %s)"""
                cursor.execute(sql, (d.get('codigo'), d.get('razonsocial'), d.get('cuit'),
                                     d.get('direccion'), d.get('telefono'), d.get('email'), tenant_id))

            conn.commit()
            flash("Proveedor guardado correctamente", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {str(e)}", "danger")
    finally:
        conn.close()
    return redirect(url_for('proveedores.listar'))


@proveedores_bp.route('/proveedores/eliminar/<int:id>', methods=['POST'])
def eliminar(id):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE proveedores SET activo = 0 WHERE id = %s AND (%s IS NULL OR tenant_id = %s)", (id, tenant_id, tenant_id))
            conn.commit()
            flash("Proveedor inactivado", "success")
    finally:
        conn.close()
    return redirect(url_for('proveedores.listar'))
# ── Batch ─────────────────────────────────────────────────────────────────────
_CAMPOS = ['codigo', 'razonsocial', 'cuit', 'direccion', 'telefono', 'email']
_EJEMPLO = ['PROV001', 'Proveedor de Ejemplo S.A.', '30-12345678-9',
            'Av. Siempre Viva 742', '011-4444-5555', 'contacto@ejemplo.com']


@proveedores_bp.route('/proveedores/importar', methods=['POST'])
def importar():
    file = request.files.get('archivo')
    if not file or not file.filename:
        return jsonify({'error': 'No se proporcionó archivo'}), 400
    try:
        rows = parse_file(file)
    except Exception as e:
        return jsonify({'error': f'Error al leer el archivo: {str(e)}'}), 400

    tenant_id = get_tenant_filter()
    insertados, omitidos, errores = 0, [], []
    conn = get_db_connection()
    try:
        for i, row in enumerate(rows, 1):
            codigo = str(row.get('codigo', '') or '').strip()
            razon = str(row.get('razonsocial', '') or '').strip()
            if not codigo or not razon:
                errores.append({'fila': i, 'codigo': codigo or '(vacío)',
                                'razon': 'Código y Razón Social son obligatorios'})
                continue
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id FROM proveedores WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)", (codigo, tenant_id, tenant_id))
                    if cursor.fetchone():
                        omitidos.append(codigo)
                        continue
                    cursor.execute("""
                        INSERT INTO proveedores (codigo, razonsocial, cuit, direccion, telefono, email, tenant_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        codigo, razon,
                        str(row.get('cuit', '') or '').strip() or None,
                        str(row.get('direccion', '') or '').strip() or None,
                        str(row.get('telefono', '') or '').strip() or None,
                        str(row.get('email', '') or '').strip() or None,
                        tenant_id,
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


@proveedores_bp.route('/proveedores/exportar/<formato>')
def exportar(formato):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT codigo, razonsocial, cuit, direccion, telefono, email "
                           "FROM proveedores WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s) ORDER BY razonsocial", (tenant_id, tenant_id))
            rows = cursor.fetchall()
    finally:
        conn.close()

    if formato == 'csv':
        return export_csv(rows, _CAMPOS, 'proveedores.csv')
    elif formato == 'json':
        return export_json(rows, _CAMPOS, 'proveedores.json')
    elif formato == 'xlsx':
        return export_xlsx(rows, _CAMPOS, 'proveedores.xlsx')
    return 'Formato no válido', 400


@proveedores_bp.route('/proveedores/plantilla/<formato>')
def plantilla(formato):
    if formato == 'csv':
        return plantilla_csv(_CAMPOS, _EJEMPLO, 'plantilla_proveedores.csv')
    elif formato == 'json':
        return plantilla_json(_CAMPOS, _EJEMPLO, 'plantilla_proveedores.json')
    elif formato == 'xlsx':
        return plantilla_xlsx(_CAMPOS, _EJEMPLO, 'plantilla_proveedores.xlsx')
    return 'Formato no válido', 400
