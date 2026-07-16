from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from modules.batch_utils import (parse_file, export_csv, export_json, export_xlsx,
                                  plantilla_csv, plantilla_json, plantilla_xlsx,
                                  int_or_none, bool_col)
from modules.db_config import get_db_connection

ubicaciones_bp = Blueprint('ubicaciones', __name__)


def get_tenant_filter():
    return session.get('tenant_id')


@ubicaciones_bp.route('/ubicaciones')
def listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT u.*, t.`descipción` AS tipo_nombre,
                       z.codigo AS zona_codigo, z.nombre AS zona_nombre
                FROM ubicaciones u
                LEFT JOIN tipoubicacion t ON u.tipoubicacion = t.id
                LEFT JOIN zonas z ON u.id_zona = z.id
                WHERE (%s IS NULL OR u.tenant_id = %s)
                ORDER BY z.codigo, u.orden_picking, u.codigo
            """, (tenant_id, tenant_id))
            ubicaciones = cursor.fetchall()

            cursor.execute("SELECT * FROM tipoubicacion WHERE (%s IS NULL OR tenant_id = %s) ORDER BY `descipción`", (tenant_id, tenant_id))
            tipos = cursor.fetchall()

            cursor.execute("SELECT id, codigo, nombre FROM zonas WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s) ORDER BY codigo", (tenant_id, tenant_id))
            zonas = cursor.fetchall()

        return render_template('ubicaciones.html',
                               ubicaciones=ubicaciones,
                               tipos=tipos,
                               zonas=zonas)
    finally:
        conn.close()


@ubicaciones_bp.route('/ubicaciones/guardar', methods=['POST'])
def guardar():
    d = request.form
    u_id = d.get('id')
    tenant_id = get_tenant_filter()

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if u_id and u_id.strip():
                sql = """UPDATE ubicaciones SET
                         codigo=%s, descipcion=%s, tipoubicacion=%s, id_zona=%s, orden_picking=%s,
                         coordenadaA=%s, coordenadaB=%s, coordenadaC=%s, coordenadaD=%s,
                         capacidad_maxima=%s, disponible_entrada=%s, disponible_salida=%s
                         WHERE id=%s"""
                cursor.execute(sql, (
                    d.get('codigo'), d.get('descipcion'), d.get('tipoubicacion') or None,
                    d.get('id_zona') or None, int(d.get('orden_picking') or 0),
                    d.get('coordenadaA'), d.get('coordenadaB'), d.get('coordenadaC'), d.get('coordenadaD'),
                    int(d.get('capacidad_maxima') or 0), 1 if d.get('disponible_entrada') else 0,
                    1 if d.get('disponible_salida') else 0, u_id))
            else:
                sql = """INSERT INTO ubicaciones
                         (codigo, descipcion, tipoubicacion, id_zona, orden_picking,
                          coordenadaA, coordenadaB, coordenadaC, coordenadaD,
                          capacidad_maxima, disponible_entrada, disponible_salida, tenant_id)
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                cursor.execute(sql, (
                    d.get('codigo'), d.get('descipcion'), d.get('tipoubicacion') or None,
                    d.get('id_zona') or None, int(d.get('orden_picking') or 0),
                    d.get('coordenadaA'), d.get('coordenadaB'), d.get('coordenadaC'), d.get('coordenadaD'),
                    int(d.get('capacidad_maxima') or 0), 1 if d.get('disponible_entrada') else 0,
                    1 if d.get('disponible_salida') else 0, tenant_id))

            conn.commit()
            flash("Ubicación guardada", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {str(e)}", "danger")
    finally:
        conn.close()
    return redirect(url_for('ubicaciones.listar'))

# ── Batch: definición de columnas ─────────────────────────────────────────────
_CAMPOS_EXPORT = ['codigo', 'descipcion', 'tipo_nombre', 'tipoubicacion',
                  'zona_codigo', 'id_zona', 'orden_picking',
                  'coordenadaA', 'coordenadaB', 'coordenadaC', 'coordenadaD',
                  'capacidad_maxima', 'disponible_entrada', 'disponible_salida']
_CAMPOS_IMPORT = ['codigo', 'descipcion', 'tipoubicacion', 'id_zona',
                  'orden_picking', 'coordenadaA', 'coordenadaB', 'coordenadaC', 'coordenadaD',
                  'capacidad_maxima', 'disponible_entrada', 'disponible_salida']
_EJEMPLO_IMPORT = ['UB-001', 'Pasillo A - Estante 1', '1', '1',
                   '10', 'A1', 'B2', 'C3', '', '100', '1', '1']


@ubicaciones_bp.route('/ubicaciones/importar', methods=['POST'])
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
            if not codigo:
                errores.append({'fila': i, 'codigo': '(vacío)', 'razon': 'Código es obligatorio'})
                continue
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id FROM ubicaciones WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)", (codigo, tenant_id, tenant_id))
                    if cursor.fetchone():
                        omitidos.append(codigo)
                        continue
                    cursor.execute("""
                        INSERT INTO ubicaciones
                            (codigo, descipcion, tipoubicacion, id_zona, orden_picking,
                             coordenadaA, coordenadaB, coordenadaC, coordenadaD,
                             capacidad_maxima, disponible_entrada, disponible_salida, tenant_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        codigo,
                        str(row.get('descipcion', '') or '').strip() or None,
                        int_or_none(row.get('tipoubicacion')),
                        int_or_none(row.get('id_zona')),
                        int(float(row.get('orden_picking') or 0)),
                        str(row.get('coordenadaA', '') or '').strip() or None,
                        str(row.get('coordenadaB', '') or '').strip() or None,
                        str(row.get('coordenadaC', '') or '').strip() or None,
                        str(row.get('coordenadaD', '') or '').strip() or None,
                        int(float(row.get('capacidad_maxima') or 0)),
                        bool_col(row.get('disponible_entrada', '1')),
                        bool_col(row.get('disponible_salida', '1')),
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


@ubicaciones_bp.route('/ubicaciones/exportar/<formato>')
def exportar(formato):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT u.codigo, u.descipcion, t.`descipción` AS tipo_nombre, u.tipoubicacion,
                       z.codigo AS zona_codigo, u.id_zona, u.orden_picking,
                       u.coordenadaA, u.coordenadaB, u.coordenadaC, u.coordenadaD,
                       u.capacidad_maxima, u.disponible_entrada, u.disponible_salida
                FROM ubicaciones u
                LEFT JOIN tipoubicacion t ON u.tipoubicacion = t.id
                LEFT JOIN zonas z ON u.id_zona = z.id
                ORDER BY z.codigo, u.orden_picking, u.codigo
            """)
            rows = cursor.fetchall()
    finally:
        conn.close()

    if formato == 'csv':
        return export_csv(rows, _CAMPOS_EXPORT, 'ubicaciones.csv')
    elif formato == 'json':
        return export_json(rows, _CAMPOS_EXPORT, 'ubicaciones.json')
    elif formato == 'xlsx':
        return export_xlsx(rows, _CAMPOS_EXPORT, 'ubicaciones.xlsx')
    return 'Formato no válido', 400


@ubicaciones_bp.route('/ubicaciones/plantilla/<formato>')
def plantilla(formato):
    if formato == 'csv':
        return plantilla_csv(_CAMPOS_IMPORT, _EJEMPLO_IMPORT, 'plantilla_ubicaciones.csv')
    elif formato == 'json':
        return plantilla_json(_CAMPOS_IMPORT, _EJEMPLO_IMPORT, 'plantilla_ubicaciones.json')
    elif formato == 'xlsx':
        return plantilla_xlsx(_CAMPOS_IMPORT, _EJEMPLO_IMPORT, 'plantilla_ubicaciones.xlsx')
    return 'Formato no válido', 400
