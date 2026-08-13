from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
import re
from modules.db_config import get_db_connection
from modules.batch_utils import (parse_file, export_csv, export_json, export_xlsx,
                                  plantilla_csv, plantilla_json, plantilla_xlsx,
                                  int_or_none, bool_col)
from modules.sql_dialect import execute_insert

transportes_bp = Blueprint('transportes', __name__)


def get_tenant_filter():
    return session.get('tenant_id')


def validar_cuit(cuit):
    cuit = re.sub(r'[^0-9]', '', str(cuit))
    return len(cuit) == 11


@transportes_bp.route('/transportes')
def listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM transportes WHERE (%s IS NULL OR tenant_id = %s) ORDER BY razonsocial", (tenant_id, tenant_id))
            transportes = cursor.fetchall()
            cursor.execute("SELECT * FROM rutas WHERE (%s IS NULL OR tenant_id = %s) ORDER BY nombre_ruta", (tenant_id, tenant_id))
            rutas_lista = cursor.fetchall()
            cursor.execute("SELECT * FROM transporte_rutas WHERE (%s IS NULL OR tenant_id = %s)", (tenant_id, tenant_id))
            relaciones = cursor.fetchall()
            cursor.execute("""
                SELECT u.id, u.codigo, u.descipcion
                FROM ubicaciones u
                JOIN tipoubicacion t ON u.tipoubicacion = t.id
                WHERE t.operacion = 'S' AND (%s IS NULL OR u.tenant_id = %s)
                ORDER BY u.codigo
            """, (tenant_id, tenant_id))
            muelles = cursor.fetchall()
        return render_template('transportes.html', transportes=transportes, rutas_lista=rutas_lista,
                               relaciones=relaciones, muelles=muelles)
    finally:
        conn.close()


@transportes_bp.route('/transportes/guardar', methods=['POST'])
def guardar():
    d = request.form
    t_id = d.get('id_transporte')
    tenant_id = get_tenant_filter()
    cuit = d.get('cuit')
    email = d.get('email')

    if cuit and not validar_cuit(cuit):
        flash("Error: El CUIT debe contener 11 dígitos numéricos.", "danger")
        return redirect(url_for('transportes.listar'))

    rutas_ids = request.form.getlist('rutas_ids[]')
    rutas_obs = request.form.getlist('rutas_obs[]')

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            params = (
                d.get('codigo'),
                d.get('razonsocial'),
                re.sub(r'[^0-9]', '', cuit) if cuit else None,
                d.get('telefono'),
                email if email else None,
                1 if d.get('activo') else 0,
                d.get('id_muelle_salida') or None
            )

            if t_id and t_id.strip():
                sql = """UPDATE transportes SET codigo=%s, razonsocial=%s, cuit=%s,
                         telefono=%s, email=%s, activo=%s, id_muelle_salida=%s WHERE id_transporte=%s AND (%s IS NULL OR tenant_id = %s)"""
                cursor.execute(sql, params + (t_id, tenant_id, tenant_id))
                current_id = t_id
            else:
                current_id = execute_insert(cursor, """INSERT INTO transportes (codigo, razonsocial, cuit, telefono, email, activo, id_muelle_salida, tenant_id)
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""", params + (tenant_id,))

            cursor.execute("DELETE FROM transporte_rutas WHERE id_transporte = %s AND (%s IS NULL OR tenant_id = %s)", (current_id, tenant_id, tenant_id))
            for i in range(len(rutas_ids)):
                if rutas_ids[i]:
                    cursor.execute("""
                        INSERT INTO transporte_rutas (id_transporte, id_ruta, observaciones, tenant_id) 
                        VALUES (%s, %s, %s, %s)
                    """, (current_id, rutas_ids[i], rutas_obs[i], tenant_id))

            conn.commit()
            flash("Transporte guardado exitosamente.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {str(e)}", "danger")
    finally:
        conn.close()
    return redirect(url_for('transportes.listar'))


# ── Batch ─────────────────────────────────────────────────────────────────────
_CAMPOS_EXPORT = ['codigo', 'razonsocial', 'cuit', 'telefono', 'email', 'activo']
_CAMPOS_IMPORT = ['codigo', 'razonsocial', 'cuit', 'telefono', 'email', 'activo']
_EJEMPLO_IMPORT = ['TRA001', 'Transporte Ejemplo S.A.', '30-12345678-9',
                   '011-4444-5555', 'transporte@ejemplo.com', '1']


@transportes_bp.route('/transportes/importar', methods=['POST'])
def importar():
    tenant_id = get_tenant_filter()
    file = request.files.get('archivo')
    if not file or not file.filename:
        return jsonify({'error': 'No se proporcionó archivo'}), 400
    try:
        rows = parse_file(file, request.form.get('hoja'))
    except Exception as e:
        return jsonify({'error': f'Error al leer el archivo: {str(e)}'}), 400

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
                    cursor.execute(
                        "SELECT id_transporte FROM transportes WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)",
                        (codigo, tenant_id, tenant_id))
                    if cursor.fetchone():
                        omitidos.append(codigo)
                        continue
                    cursor.execute("""
                        INSERT INTO transportes (codigo, razonsocial, cuit, telefono, email, activo, tenant_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        codigo, razon,
                        str(row.get('cuit', '') or '').strip() or None,
                        str(row.get('telefono', '') or '').strip() or None,
                        str(row.get('email', '') or '').strip() or None,
                        bool_col(row.get('activo', '1')),
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


@transportes_bp.route('/transportes/exportar/<formato>')
def exportar(formato):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT codigo, razonsocial, cuit, telefono, email, activo
                FROM transportes
                WHERE (%s IS NULL OR tenant_id = %s)
                ORDER BY razonsocial
            """, (tenant_id, tenant_id))
            rows = cursor.fetchall()
    finally:
        conn.close()

    if formato == 'csv':
        return export_csv(rows, _CAMPOS_EXPORT, 'transportes.csv')
    elif formato == 'json':
        return export_json(rows, _CAMPOS_EXPORT, 'transportes.json')
    elif formato == 'xlsx':
        return export_xlsx(rows, _CAMPOS_EXPORT, 'transportes.xlsx')
    return 'Formato no válido', 400


@transportes_bp.route('/transportes/plantilla/<formato>')
def plantilla(formato):
    if formato == 'csv':
        return plantilla_csv(_CAMPOS_IMPORT, _EJEMPLO_IMPORT, 'plantilla_transportes.csv')
    elif formato == 'json':
        return plantilla_json(_CAMPOS_IMPORT, _EJEMPLO_IMPORT, 'plantilla_transportes.json')
    elif formato == 'xlsx':
        return plantilla_xlsx(_CAMPOS_IMPORT, _EJEMPLO_IMPORT, 'plantilla_transportes.xlsx')
    return 'Formato no válido', 400