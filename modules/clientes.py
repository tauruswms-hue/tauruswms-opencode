import re
from urllib.parse import urlparse

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
from modules.cuit import cuit_para_guardar, cuit_para_mostrar
from modules.db_config import get_db_connection

clientes_bp = Blueprint('clientes', __name__)

# Largo máximo de los textos del cliente (el de su columna)
_LARGOS = {'nombre_fantasia': 200, 'sitio_web': 255, 'email': 100, 'direccion': 255, 'contacto_nombre': 100}
_ROTULOS = {'nombre_fantasia': 'Nombre de fantasía', 'sitio_web': 'Sitio web', 'email': 'Mail principal',
            'direccion': 'Domicilio', 'contacto_nombre': 'Contacto'}


def _texto(datos, campo):
    """Texto opcional de un cliente: recortado, o None si está vacío. ValueError si no entra en la columna."""
    valor = str(datos.get(campo) or '').strip()
    if len(valor) > _LARGOS[campo]:
        raise ValueError(f'{_ROTULOS[campo]}: admite hasta {_LARGOS[campo]} caracteres.')
    return valor or None


def _email(datos):
    valor = _texto(datos, 'email')
    if valor and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', valor):
        raise ValueError('Mail principal: no tiene formato de dirección de correo.')
    return valor


def _sitio_web(datos):
    """Sitio web como dirección http(s). Si se escribe sin el protocolo (www.empresa.com) se completa con https://."""
    valor = _texto(datos, 'sitio_web')
    if not valor:
        return None
    if not re.match(r'^[a-z][a-z0-9+.-]*://', valor, re.I):
        valor = 'https://' + valor
    partes = urlparse(valor)
    if partes.scheme not in ('http', 'https') or '.' not in partes.netloc or ' ' in valor:
        raise ValueError('Sitio web: tiene que ser una dirección web, por ejemplo www.empresa.com.')
    if len(valor) > _LARGOS['sitio_web']:
        raise ValueError(f'Sitio web: admite hasta {_LARGOS["sitio_web"]} caracteres.')
    return valor


def _activo(valor, por_defecto=True):
    """Estado del cliente: True = Activo. Acepta 1/0 (lista Estado) y on (casilla, formularios anteriores)."""
    valor = str(valor if valor is not None else '').strip().lower()
    if not valor:
        return por_defecto
    return valor in ('1', 'on', 'true', 'si', 'sí', 'yes')


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
            clientes = [dict(c) for c in cursor.fetchall()]
            for c in clientes:
                # Los CUIT cargados antes sin guiones se muestran y editan ya formateados
                c['cuit'] = cuit_para_mostrar(c.get('cuit'))

            cursor.execute("SELECT * FROM rutas WHERE (%s IS NULL OR tenant_id = %s) ORDER BY nombre_ruta", (tenant_id, tenant_id))
            rutas = cursor.fetchall()

            cursor.execute("SELECT id_transporte, razonsocial FROM transportes WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s)", (tenant_id, tenant_id))
            transportes_all = cursor.fetchall()

            cursor.execute("SELECT id_transporte, id_ruta FROM transporte_rutas WHERE (%s IS NULL OR tenant_id = %s)", (tenant_id, tenant_id))
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
    # Sin el campo Estado, un alta nace activa; en una edición equivale a Inactivo (casilla sin tildar)
    activo_val = _activo(d.get('activo'), por_defecto=not (c_id and c_id.strip()))
    try:
        cuit = cuit_para_guardar(d.get('cuit'))
        nombre_fantasia = _texto(d, 'nombre_fantasia')
        sitio_web = _sitio_web(d)
        email = _email(d)
        direccion = _texto(d, 'direccion')
        contacto = _texto(d, 'contacto_nombre')
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for('clientes.listar'))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            params = (
                d.get('codigo'),
                d.get('razonsocial'),
                cuit,
                direccion,
                d.get('localidad') or None,
                d.get('provincia') or None,
                d.get('telefono') or None,
                email,
                contacto,
                d.get('id_ruta') or None,
                d.get('id_transporte_predeterminado') or None,
                activo_val,
                nombre_fantasia,
                sitio_web,
            )

            if c_id and c_id.strip():
                sql = """UPDATE clientes SET codigo=%s, razonsocial=%s, cuit=%s,
                         direccion=%s, localidad=%s, provincia=%s, telefono=%s,
                         email=%s, contacto_nombre=%s, id_ruta=%s,
                         id_transporte_predeterminado=%s, activo=%s,
                         nombre_fantasia=%s, sitio_web=%s
                         WHERE id_cliente=%s AND (%s IS NULL OR tenant_id = %s)"""
                cursor.execute(sql, (*params, c_id, tenant_id, tenant_id))
            else:
                sql = """INSERT INTO clientes (codigo, razonsocial, cuit, direccion,
                         localidad, provincia, telefono, email, contacto_nombre,
                         id_ruta, id_transporte_predeterminado, activo,
                         nombre_fantasia, sitio_web, tenant_id)
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                cursor.execute(sql, (*params, tenant_id))

            conn.commit()
            flash("Cliente guardado correctamente", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('clientes.listar'))


@clientes_bp.route('/clientes/eliminar/<int:id_cliente>', methods=['POST'])
def eliminar(id_cliente):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE clientes SET activo = 0 WHERE id_cliente = %s AND (%s IS NULL OR tenant_id = %s)",
                (id_cliente, tenant_id, tenant_id))
            conn.commit()
            flash("Cliente inactivado", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('clientes.listar'))
# ── Batch ─────────────────────────────────────────────────────────────────────
_CAMPOS_EXPORT = ['codigo', 'razonsocial', 'nombre_fantasia', 'cuit', 'direccion', 'localidad', 'provincia',
                  'telefono', 'email', 'sitio_web', 'contacto_nombre',
                  'id_ruta', 'nombre_ruta', 'id_transporte_predeterminado', 'nombre_transporte',
                  'activo']
_CAMPOS_IMPORT = ['codigo', 'razonsocial', 'nombre_fantasia', 'cuit', 'direccion', 'localidad', 'provincia',
                  'telefono', 'email', 'sitio_web', 'contacto_nombre',
                  'id_ruta', 'id_transporte_predeterminado', 'activo']
_EJEMPLO_IMPORT = ['CLI001', 'Cliente de Ejemplo S.A.', 'El Ejemplo', '20-87654321-0',
                   'Av. Corrientes 1234', 'Buenos Aires', 'Buenos Aires',
                   '011-5555-6666', 'cliente@ejemplo.com', 'www.ejemplo.com', 'Juan Pérez',
                   'Zona Centro', 'TRA005', '1']


def _resolver_ruta(cursor, ref, tenant_id):
    """Resuelve id_ruta: acepta un ID numérico o el nombre de la ruta."""
    if not ref:
        return None
    if ref.isdigit():
        return int(ref)
    cursor.execute(
        "SELECT id_ruta FROM rutas WHERE nombre_ruta = %s AND (%s IS NULL OR tenant_id = %s)",
        (ref, tenant_id, tenant_id))
    row = cursor.fetchone()
    return row['id_ruta'] if row else None


def _resolver_transporte(cursor, ref, tenant_id):
    """Resuelve id_transporte: acepta un ID numérico o el codigo del transporte."""
    if not ref:
        return None
    if ref.isdigit():
        return int(ref)
    cursor.execute(
        "SELECT id_transporte FROM transportes WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)",
        (ref, tenant_id, tenant_id))
    row = cursor.fetchone()
    return row['id_transporte'] if row else None


@clientes_bp.route('/clientes/importar', methods=['POST'])
def importar():
    tenant_id = get_tenant_filter()
    file = request.files.get('archivo')
    if not file or not file.filename:
        return jsonify({'error': 'No se proporcionó archivo'}), 400
    try:
        rows = parse_file(file, request.form.get('hoja'))
    except Exception as e:
        return jsonify({'error': f'Error al leer el archivo: {e!s}'}), 400

    insertados, actualizados, omitidos, errores = 0, 0, [], []
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
                    id_ruta = _resolver_ruta(cursor, str(row.get('id_ruta', '') or '').strip(), tenant_id)
                    id_transporte = _resolver_transporte(cursor, str(row.get('id_transporte_predeterminado', '') or '').strip(), tenant_id)
                    cursor.execute("SELECT id_cliente FROM clientes WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)", (codigo, tenant_id, tenant_id))
                    existing = cursor.fetchone()
                    if existing:
                        cursor.execute("""
                            UPDATE clientes
                            SET id_ruta = %s, id_transporte_predeterminado = %s
                            WHERE id_cliente = %s
                        """, (id_ruta, id_transporte, existing['id_cliente']))
                        actualizados += 1
                        continue
                    cursor.execute("""
                        INSERT INTO clientes
                            (codigo, razonsocial, cuit, direccion, localidad, provincia,
                             telefono, email, contacto_nombre,
                             id_ruta, id_transporte_predeterminado, activo,
                             nombre_fantasia, sitio_web, tenant_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        codigo, razon,
                        cuit_para_guardar(row.get('cuit')),
                        _texto(row, 'direccion'),
                        str(row.get('localidad', '') or '').strip() or None,
                        str(row.get('provincia', '') or '').strip() or None,
                        str(row.get('telefono', '') or '').strip() or None,
                        _email(row),
                        _texto(row, 'contacto_nombre'),
                        id_ruta,
                        id_transporte,
                        _activo(row.get('activo')),
                        _texto(row, 'nombre_fantasia'),
                        _sitio_web(row),
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
    return jsonify({'insertados': insertados, 'actualizados': actualizados,
                    'omitidos': omitidos, 'errores': errores})


@clientes_bp.route('/clientes/exportar/<formato>')
def exportar(formato):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT c.codigo, c.razonsocial, c.nombre_fantasia, c.cuit, c.direccion, c.localidad, c.provincia,
                       c.telefono, c.email, c.sitio_web, c.contacto_nombre,
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
