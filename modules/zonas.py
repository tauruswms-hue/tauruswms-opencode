from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from modules.db_config import get_db_connection
from modules.batch_utils import (parse_file, export_csv, export_json, export_xlsx,
                                  plantilla_csv, plantilla_json, plantilla_xlsx,
                                  bool_col)

zonas_bp = Blueprint('zonas', __name__)


def get_tenant_filter():
    return session.get('tenant_id')


@zonas_bp.route('/zonas')
def listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT z.*,
                       (SELECT COUNT(*) FROM ubicaciones u WHERE u.id_zona = z.id AND (%s IS NULL OR u.tenant_id = %s)) AS total_ubicaciones
                FROM zonas z
                WHERE (%s IS NULL OR z.tenant_id = %s)
                ORDER BY z.codigo
            """, (tenant_id, tenant_id, tenant_id, tenant_id))
            zonas = cursor.fetchall()
        return render_template('zonas.html', zonas=zonas)
    finally:
        conn.close()


@zonas_bp.route('/zonas/guardar', methods=['POST'])
def guardar():
    tenant_id = get_tenant_filter()
    d = request.form
    z_id = d.get('id')
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if z_id and z_id.strip():
                cursor.execute("""
                    UPDATE zonas SET codigo=%s, nombre=%s, descripcion=%s, activo=%s
                    WHERE id=%s AND (%s IS NULL OR tenant_id = %s)
                """, (d.get('codigo'), d.get('nombre'),
                      d.get('descripcion') or None,
                      1 if d.get('activo') else 0, z_id, tenant_id, tenant_id))
            else:
                cursor.execute("""
                    INSERT INTO zonas (codigo, nombre, descripcion, activo, tenant_id)
                    VALUES (%s, %s, %s, %s, %s)
                """, (d.get('codigo'), d.get('nombre'),
                      d.get('descripcion') or None,
                      1 if d.get('activo') else 0, tenant_id))
            conn.commit()
            flash("Zona guardada correctamente.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {str(e)}", "danger")
    finally:
        conn.close()
    return redirect(url_for('zonas.listar'))


@zonas_bp.route('/zonas/eliminar/<int:id>')
def eliminar(id):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS total FROM ubicaciones WHERE id_zona = %s AND (%s IS NULL OR tenant_id = %s)", 
                (id, tenant_id, tenant_id)
            )
            if cursor.fetchone()['total'] > 0:
                flash("No se puede eliminar: la zona tiene ubicaciones asignadas.", "danger")
            else:
                cursor.execute("DELETE FROM zonas WHERE id = %s AND (%s IS NULL OR tenant_id = %s)", 
                               (id, tenant_id, tenant_id))
                conn.commit()
                flash("Zona eliminada.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {str(e)}", "danger")
    finally:
        conn.close()
    return redirect(url_for('zonas.listar'))


# ── Batch ─────────────────────────────────────────────────────────────────────
_CAMPOS = ['codigo', 'nombre', 'descripcion', 'activo']
_EJEMPLO = ['ZN-NORTE', 'Zona Norte', 'Sector norte del depósito', '1']


@zonas_bp.route('/zonas/importar', methods=['POST'])
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
            codigo = str(row.get('codigo', '') or '').strip().upper()
            nombre = str(row.get('nombre', '') or '').strip()
            if not codigo or not nombre:
                errores.append({'fila': i, 'codigo': codigo or '(vacío)',
                                'razon': 'Código y Nombre son obligatorios'})
                continue
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT id FROM zonas WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)",
                        (codigo, tenant_id, tenant_id))
                    if cursor.fetchone():
                        omitidos.append(codigo)
                        continue
                    cursor.execute("""
                        INSERT INTO zonas (codigo, nombre, descripcion, activo, tenant_id)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        codigo, nombre,
                        str(row.get('descripcion', '') or '').strip() or None,
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


@zonas_bp.route('/zonas/exportar/<formato>')
def exportar(formato):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT codigo, nombre, descripcion, activo FROM zonas WHERE (%s IS NULL OR tenant_id = %s) ORDER BY codigo",
                (tenant_id, tenant_id))
            rows = cursor.fetchall()
    finally:
        conn.close()

    if formato == 'csv':
        return export_csv(rows, _CAMPOS, 'zonas.csv')
    elif formato == 'json':
        return export_json(rows, _CAMPOS, 'zonas.json')
    elif formato == 'xlsx':
        return export_xlsx(rows, _CAMPOS, 'zonas.xlsx')
    return 'Formato no válido', 400


@zonas_bp.route('/zonas/plantilla/<formato>')
def plantilla(formato):
    if formato == 'csv':
        return plantilla_csv(_CAMPOS, _EJEMPLO, 'plantilla_zonas.csv')
    elif formato == 'json':
        return plantilla_json(_CAMPOS, _EJEMPLO, 'plantilla_zonas.json')
    elif formato == 'xlsx':
        return plantilla_xlsx(_CAMPOS, _EJEMPLO, 'plantilla_zonas.xlsx')
    return 'Formato no válido', 400
