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
    DatoInvalido,
    bool_col,
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
from modules.sql_dialect import quote

tipoubicacion_bp = Blueprint('tipoubicacion', __name__)

DESCRIPCION_MAX = 100   # largo de la columna tipoubicacion.descripcion

# Operación de las ubicaciones del tipo (valor guardado -> rótulo). La usan otras pantallas:
#   R: Recepciones y la app móvil ofrecen estas ubicaciones para recibir mercadería
#   S: Transportes las ofrece como muelle de salida
OPERACIONES = {'': 'Almacenamiento', 'R': 'Recepción', 'S': 'Salida (despacho)'}
# En un archivo se acepta la letra o el nombre
_OPERACION_POR_NOMBRE = {'almacenamiento': '', 'ninguna': '', 'recepcion': 'R', 'recepción': 'R',
                         'salida': 'S', 'despacho': 'S', 'salida (despacho)': 'S'}


def _descripcion(valor):
    valor = str(valor or '').strip()
    if not valor:
        raise DatoInvalido('Descripción: es obligatoria.')
    if len(valor) > DESCRIPCION_MAX:
        raise DatoInvalido(f'Descripción: admite hasta {DESCRIPCION_MAX} caracteres.')
    return valor


def _operacion(valor):
    """Operación a guardar: 'R', 'S' o None (almacenamiento)."""
    texto = str(valor if valor is not None else '').strip()
    codigo = texto.upper()
    if codigo not in OPERACIONES:
        codigo = _OPERACION_POR_NOMBRE.get(texto.lower())
    if codigo is None:
        raise DatoInvalido(f'Operación: "{texto}" no es válida. Usar: R (recepción), S (salida) o vacío.')
    return codigo or None


def _descripcion_en_uso(cursor, descripcion, tenant_id, excluir_id=0):
    cursor.execute(f"""SELECT id FROM tipoubicacion
                       WHERE {quote('descripcion')} = %s AND id <> %s AND (%s IS NULL OR tenant_id = %s)""",
                   (descripcion, excluir_id, tenant_id, tenant_id))
    return cursor.fetchone() is not None


@tipoubicacion_bp.route('/tipoubicacion')
def listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT t.*, (SELECT COUNT(*) FROM ubicaciones u WHERE u.tipoubicacion = t.id) AS ubicaciones
                FROM tipoubicacion t
                WHERE (%s IS NULL OR t.tenant_id = %s)
                ORDER BY t.{quote('descripcion')}
            """, (tenant_id, tenant_id))
            tipos = [dict(t) for t in cursor.fetchall()]
        for t in tipos:
            t['operacion'] = (t.get('operacion') or '').strip().upper()
        return render_template('tipoubicacion.html', tipos=tipos, operaciones=OPERACIONES,
                               descripcion_max=DESCRIPCION_MAX)
    finally:
        conn.close()


@tipoubicacion_bp.route('/tipoubicacion/guardar', methods=['POST'])
def guardar():
    tenant_id = get_tenant_filter()
    d = request.form
    conn = get_db_connection()
    try:
        # Sin id o vacío: es un alta
        try:
            t_id = int((d.get('id') or '0').strip() or 0)
        except ValueError:
            raise DatoInvalido('Tipo de ubicación inválido.') from None
        # El campo del formulario se llamó "descipcion" (sin la r): se aceptan los dos nombres
        descripcion = _descripcion(d.get('descripcion') or d.get('descipcion'))
        soporte_picking = 1 if d.get('soporte_picking') else 0

        with conn.cursor() as cursor:
            anterior = None
            if t_id:
                cursor.execute("SELECT operacion FROM tipoubicacion WHERE id = %s AND (%s IS NULL OR tenant_id = %s)",
                               (t_id, tenant_id, tenant_id))
                anterior = cursor.fetchone()
                if not anterior:
                    raise DatoInvalido('El tipo de ubicación que se intenta modificar no existe.')
            if _descripcion_en_uso(cursor, descripcion, tenant_id, excluir_id=t_id):
                raise DatoInvalido(f'Ya existe un tipo de ubicación con la descripción "{descripcion}".')
            # Sin el dato (formularios anteriores), una edición conserva la operación que tenía
            if 'operacion' in d or not anterior:
                operacion = _operacion(d.get('operacion'))
            else:
                operacion = (anterior['operacion'] or '').strip().upper() or None

            if anterior and (anterior['operacion'] or '').strip().upper() == 'R' and operacion != 'R':
                # Si deja de ser de recepción, sus ubicaciones ya no se ofrecen para recibir
                cursor.execute("""SELECT COUNT(*) AS n FROM recepciones_cabecera r
                                  JOIN ubicaciones u ON u.id = r.id_ubicacion_recep
                                  WHERE u.tipoubicacion = %s AND r.estado IN ('Abierta', 'Cerrada')""", (t_id,))
                abiertas = cursor.fetchone()['n']
                if abiertas:
                    raise DatoInvalido('No se puede cambiar la operación: hay '
                                       + ('1 recepción sin confirmar' if abiertas == 1 else f'{abiertas} recepciones sin confirmar')
                                       + ' en ubicaciones de este tipo.')

            if t_id:
                cursor.execute(f"UPDATE tipoubicacion SET {quote('descripcion')}=%s, soporte_picking=%s, operacion=%s WHERE id=%s",
                               (descripcion, soporte_picking, operacion, t_id))
            else:
                cursor.execute(f"INSERT INTO tipoubicacion ({quote('descripcion')}, soporte_picking, operacion, tenant_id) "
                               "VALUES (%s, %s, %s, %s)", (descripcion, soporte_picking, operacion, tenant_id))
            conn.commit()
            flash("Tipo de ubicación guardado", "success")
    except DatoInvalido as e:
        conn.rollback()
        flash(str(e), "danger")
    except Exception as e:
        conn.rollback()
        flash(f"Error al guardar el tipo de ubicación: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('tipoubicacion.listar'))


@tipoubicacion_bp.route('/tipoubicacion/eliminar/<int:id>', methods=['POST'])
def eliminar(id):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"SELECT {quote('descripcion')} AS descripcion FROM tipoubicacion "
                           "WHERE id = %s AND (%s IS NULL OR tenant_id = %s)", (id, tenant_id, tenant_id))
            tipo = cursor.fetchone()
            if not tipo:
                flash("Tipo de ubicación no encontrado.", "warning")
                return redirect(url_for('tipoubicacion.listar'))

            cursor.execute("SELECT COUNT(*) AS total FROM ubicaciones WHERE tipoubicacion = %s", (id,))
            total = cursor.fetchone()['total']
            if total:
                flash(f'No se puede eliminar el tipo "{tipo["descripcion"]}": lo '
                      + ('usa 1 ubicación.' if total == 1 else f'usan {total} ubicaciones.'), "danger")
            else:
                cursor.execute("DELETE FROM tipoubicacion WHERE id = %s", (id,))
                conn.commit()
                flash("Tipo de ubicación eliminado", "success")
    except Exception as e:
        conn.rollback()
        flash(f"No se pudo eliminar el tipo de ubicación: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('tipoubicacion.listar'))


# ── Batch ─────────────────────────────────────────────────────────────────────
_CAMPOS_EXPORT = ['descripcion', 'operacion', 'soporte_picking']
_CAMPOS_IMPORT = ['descripcion', 'operacion', 'soporte_picking']
_EJEMPLO = ['Estantería', '', '1']


@tipoubicacion_bp.route('/tipoubicacion/importar', methods=['POST'])
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
            descripcion = str(row.get('descripcion', '') or '').strip()
            if not descripcion:
                errores.append({'fila': i, 'codigo': '(vacío)',
                                'razon': 'El campo descripcion es obligatorio'})
                continue
            try:
                descripcion = _descripcion(descripcion)
                operacion = _operacion(row.get('operacion'))
                with conn.cursor() as cursor:
                    if _descripcion_en_uso(cursor, descripcion, tenant_id):
                        omitidos.append(descripcion)
                        continue
                    cursor.execute(
                        f"INSERT INTO tipoubicacion ({quote('descripcion')}, soporte_picking, operacion, tenant_id) "
                        "VALUES (%s, %s, %s, %s)",
                        (descripcion, bool_col(row.get('soporte_picking', '0')), operacion, tenant_id))
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
                SELECT {quote('descripcion')} AS descripcion, operacion, soporte_picking
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
