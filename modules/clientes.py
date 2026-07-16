from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, session
from modules.batch_utils import (parse_file, export_csv, export_json, export_xlsx,
                                  plantilla_csv, plantilla_json, plantilla_xlsx,
                                  int_or_none, bool_col)
from modules.db_config import get_db_connection

clientes_bp = Blueprint('clientes', __name__)


def get_tenant_filter():
    return session.get('tenant_id')


@clientes_bp.route('/clientes')
def listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT c.*, r.nombre_ruta, t.razonsocial as nombre_transporte
                FROM clientes c
                LEFT JOIN rutas r ON c.id_ruta = r.id_ruta
                LEFT JOIN transportes t ON c.id_transporte_predeterminado = t.id_transporte
                WHERE (%s IS NULL OR c.tenant_id = %s)
                ORDER BY c.razonsocial ASC
            """
            cursor.execute(sql, (tenant_id, tenant_id))
            clientes = cursor.fetchall()

            cursor.execute("SELECT * FROM rutas WHERE (%s IS NULL OR tenant_id = %s) ORDER BY nombre_ruta", (tenant_id, tenant_id))
            rutas = cursor.fetchall()

            cursor.execute("SELECT id_transporte, razonsocial FROM transportes WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s)", (tenant_id, tenant_id))
            transportes_all = cursor.fetchall()

            cursor.execute("SELECT id_transporte, id_ruta FROM transporte_rutas")
            rel_transp_rutas = cursor.fetchall()

        return render_template('clientes.html',
                               clientes=clientes,
                               rutas=rutas,
                               transportes_all=transportes_all,
                               rel_transp_rutas=rel_transp_rutas)
    finally:
        conn.close()


@clientes_bp.route('/clientes/guardar', methods=['POST'])
def guardar():
    d = request.form
    c_id = d.get('id_cliente')
    tenant_id = get_tenant_filter()
    activo_val = 1 if d.get('activo') else 0

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            params = (
                d.get('codigo'),
                d.get('razonsocial'),
                d.get('cuit') or None,
                d.get('direccion') or None,
                d.get('localidad') or None,
                d.get('provincia') or None,
                d.get('telefono') or None,
                d.get('email') or None,
                d.get('contacto_nombre') or None,
                d.get('id_ruta') or None,
                d.get('id_transporte_predeterminado') or None,
                activo_val
            )

            if c_id and c_id.strip():
                sql = """UPDATE clientes SET codigo=%s, razonsocial=%s, cuit=%s, 
                         direccion=%s, localidad=%s, provincia=%s, telefono=%s, 
                         email=%s, contacto_nombre=%s, id_ruta=%s, 
                         id_transporte_predeterminado=%s, activo=%s 
                         WHERE id_cliente=%s AND (%s IS NULL OR tenant_id = %s)"""
                cursor.execute(sql, params + (c_id, tenant_id, tenant_id))
            else:
                sql = """INSERT INTO clientes (codigo, razonsocial, cuit, direccion, 
                         localidad, provincia, telefono, email, contacto_nombre, 
                         id_ruta, id_transporte_predeterminado, activo, tenant_id) 
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                cursor.execute(sql, params + (tenant_id,))

            conn.commit()
            flash("Cliente guardado correctamente", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {str(e)}", "danger")
    finally:
        conn.close()
    return redirect(url_for('clientes.listar'))
# ── Batch ─────────────────────────────────────────────────────────────────────
_CAMPOS_EXPORT = ['codigo', 'razonsocial', 'cuit', 'direccion', 'localidad', 'provincia',
                  'telefono', 'email', 'contacto_nombre',
                  'id_ruta', 'nombre_ruta', 'id_transporte_predeterminado', 'nombre_transporte',
                  'activo']
_CAMPOS_IMPORT = ['codigo', 'razonsocial', 'cuit', 'direccion', 'localidad', 'provincia',
                  'telefono', 'email', 'contacto_nombre',
                  'id_ruta', 'id_transporte_predeterminado', 'activo']
_EJEMPLO_IMPORT = ['CLI001', 'Cliente de Ejemplo S.A.', '20-87654321-0',
                   'Av. Corrientes 1234', 'Buenos Aires', 'Buenos Aires',
                   '011-5555-6666', 'cliente@ejemplo.com', 'Juan Pérez',
                   '1', '1', '1']


@clientes_bp.route('/clientes/importar', methods=['POST'])
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
            razon = str(row.get('razonsocial', '') or '').strip()
            if not codigo or not razon:
                errores.append({'fila': i, 'codigo': codigo or '(vacío)',
                                'razon': 'Código y Razón Social son obligatorios'})
                continue
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id_cliente FROM clientes WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)", (codigo, tenant_id, tenant_id))
                    if cursor.fetchone():
                        omitidos.append(codigo)
                        continue
                    cursor.execute("""
                        INSERT INTO clientes
                            (codigo, razonsocial, cuit, direccion, localidad, provincia,
                             telefono, email, contacto_nombre,
                             id_ruta, id_transporte_predeterminado, activo, tenant_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        codigo, razon,
                        str(row.get('cuit', '') or '').strip() or None,
                        str(row.get('direccion', '') or '').strip() or None,
                        str(row.get('localidad', '') or '').strip() or None,
                        str(row.get('provincia', '') or '').strip() or None,
                        str(row.get('telefono', '') or '').strip() or None,
                        str(row.get('email', '') or '').strip() or None,
                        str(row.get('contacto_nombre', '') or '').strip() or None,
                        int_or_none(row.get('id_ruta')),
                        int_or_none(row.get('id_transporte_predeterminado')),
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


@clientes_bp.route('/clientes/exportar/<formato>')
def exportar(formato):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT c.codigo, c.razonsocial, c.cuit, c.direccion, c.localidad, c.provincia,
                       c.telefono, c.email, c.contacto_nombre,
                       c.id_ruta, r.nombre_ruta,
                       c.id_transporte_predeterminado, t.razonsocial AS nombre_transporte,
                       c.activo
                FROM clientes c
                LEFT JOIN rutas r ON c.id_ruta = r.id_ruta
                LEFT JOIN transportes t ON c.id_transporte_predeterminado = t.id_transporte
                WHERE (%s IS NULL OR c.tenant_id = %s)
                ORDER BY c.razonsocial
            """, (tenant_id, tenant_id))
            rows = cursor.fetchall()
    finally:
        conn.close()

    if formato == 'csv':
        return export_csv(rows, _CAMPOS_EXPORT, 'clientes.csv')
    elif formato == 'json':
        return export_json(rows, _CAMPOS_EXPORT, 'clientes.json')
    elif formato == 'xlsx':
        return export_xlsx(rows, _CAMPOS_EXPORT, 'clientes.xlsx')
    return 'Formato no válido', 400


@clientes_bp.route('/clientes/plantilla/<formato>')
def plantilla(formato):
    if formato == 'csv':
        return plantilla_csv(_CAMPOS_IMPORT, _EJEMPLO_IMPORT, 'plantilla_clientes.csv')
    elif formato == 'json':
        return plantilla_json(_CAMPOS_IMPORT, _EJEMPLO_IMPORT, 'plantilla_clientes.json')
    elif formato == 'xlsx':
        return plantilla_xlsx(_CAMPOS_IMPORT, _EJEMPLO_IMPORT, 'plantilla_clientes.xlsx')
    return 'Formato no válido', 400
