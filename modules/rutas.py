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
from modules.sql_dialect import is_duplicate_key_error

rutas_bp = Blueprint('rutas', __name__)

NOMBRE_MAX = 100   # largo de rutas.nombre_ruta


def _nombre(valor):
    """Nombre de la ruta, verificado: obligatorio y dentro del largo de la columna."""
    valor = str(valor or '').strip()
    if not valor:
        raise DatoInvalido('El nombre de la ruta es obligatorio.')
    if len(valor) > NOMBRE_MAX:
        raise DatoInvalido(f'Nombre: admite hasta {NOMBRE_MAX} caracteres.')
    return valor


def _activo(valor, por_defecto=True):
    """Estado: True = Activa. Acepta 1/0 (lista Estado, archivos) y on."""
    valor = str(valor if valor is not None else '').strip().lower()
    if not valor:
        return por_defecto
    return valor in ('1', 'on', 'true', 'si', 'sí', 'yes')


def _nombre_en_uso(cursor, nombre, tenant_id, excluir_id=0):
    """El nombre identifica a la ruta (clientes, transportes, importaciones e Intercambio la buscan por nombre)."""
    cursor.execute("""SELECT id_ruta FROM rutas
                      WHERE nombre_ruta = %s AND id_ruta <> %s AND (%s IS NULL OR tenant_id = %s)""",
                   (nombre, excluir_id, tenant_id, tenant_id))
    return cursor.fetchone() is not None


def _uso(cursor, id_ruta):
    """Cuántos transportes, clientes y pedidos tienen la ruta."""
    uso = {}
    for clave, tabla in (('transportes', 'transporte_rutas'), ('clientes', 'clientes'), ('pedidos', 'pedidos_cabecera')):
        cursor.execute(f"SELECT COUNT(*) AS total FROM {tabla} WHERE id_ruta = %s", (id_ruta,))
        uso[clave] = cursor.fetchone()['total']
    return uso


def _plural(cantidad, singular, plural):
    return f'{cantidad} {singular if cantidad == 1 else plural}'


@rutas_bp.route('/rutas')
def listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Activas e inactivas: una ruta inactiva se sigue viendo y se puede reactivar
            cursor.execute("""
                SELECT r.*,
                       (SELECT COUNT(*) FROM transporte_rutas tr WHERE tr.id_ruta = r.id_ruta) AS transportes,
                       (SELECT COUNT(*) FROM clientes c WHERE c.id_ruta = r.id_ruta) AS clientes
                FROM rutas r
                WHERE (%s IS NULL OR r.tenant_id = %s)
                ORDER BY r.activo DESC, r.nombre_ruta ASC""", (tenant_id, tenant_id))
            rutas = cursor.fetchall()
        return render_template('rutas.html', rutas=rutas, nombre_max=NOMBRE_MAX)
    finally:
        conn.close()


@rutas_bp.route('/rutas/guardar', methods=['POST'])
def guardar():
    d = request.form
    tenant_id = get_tenant_filter()

    conn = get_db_connection()
    try:
        try:
            id_ruta = int((d.get('id_ruta') or '0').strip() or 0)
        except ValueError:
            raise DatoInvalido('Ruta inválida.') from None
        nombre = _nombre(d.get('nombre_ruta'))
        descripcion = (d.get('descripcion') or '').strip() or None
        # Sin el campo Estado, un alta nace activa y una edición conserva el estado que tenía
        activo = _activo(d.get('activo'), por_defecto=None)

        with conn.cursor() as cursor:
            if id_ruta:
                cursor.execute("SELECT activo FROM rutas WHERE id_ruta = %s AND (%s IS NULL OR tenant_id = %s)",
                               (id_ruta, tenant_id, tenant_id))
                actual = cursor.fetchone()
                if not actual:
                    raise DatoInvalido('La ruta que se intenta modificar no existe.')
                if activo is None:
                    activo = bool(actual['activo'])
            elif activo is None:
                activo = True
            if _nombre_en_uso(cursor, nombre, tenant_id, excluir_id=id_ruta):
                raise DatoInvalido(f'Ya existe una ruta con el nombre "{nombre}".')

            if id_ruta:
                cursor.execute("UPDATE rutas SET nombre_ruta = %s, descripcion = %s, activo = %s WHERE id_ruta = %s",
                               (nombre, descripcion, activo, id_ruta))
            else:
                cursor.execute("INSERT INTO rutas (nombre_ruta, descripcion, activo, tenant_id) VALUES (%s, %s, %s, %s)",
                               (nombre, descripcion, activo, tenant_id))

            conn.commit()
            flash("Ruta guardada correctamente", "success")
    except DatoInvalido as e:
        conn.rollback()
        flash(str(e), "danger")
    except Exception as e:
        conn.rollback()
        if is_duplicate_key_error(e):
            flash("Ya existe una ruta con ese nombre.", "danger")
        else:
            flash(f"Error al guardar la ruta: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('rutas.listar'))


@rutas_bp.route('/rutas/eliminar/<int:id>', methods=['POST'])
def eliminar(id):
    """Inactiva la ruta. No se borra: los transportes, clientes y pedidos que la tienen la conservan."""
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT nombre_ruta, activo FROM rutas WHERE id_ruta = %s AND (%s IS NULL OR tenant_id = %s)",
                           (id, tenant_id, tenant_id))
            ruta = cursor.fetchone()
            if not ruta:
                flash("Ruta no encontrada.", "warning")
                return redirect(url_for('rutas.listar'))
            if not ruta['activo']:
                flash(f'La ruta "{ruta["nombre_ruta"]}" ya estaba inactiva.', "info")
                return redirect(url_for('rutas.listar'))

            cursor.execute("UPDATE rutas SET activo = %s WHERE id_ruta = %s", (False, id))
            uso = _uso(cursor, id)
            conn.commit()

            mensaje = (f'La ruta "{ruta["nombre_ruta"]}" quedó inactiva: ya no se ofrece al cargar '
                       'clientes, transportes ni pedidos.')
            partes = [texto for cantidad, texto in (
                (uso['transportes'], _plural(uso['transportes'], 'transporte', 'transportes')),
                (uso['clientes'], _plural(uso['clientes'], 'cliente', 'clientes')),
                (uso['pedidos'], _plural(uso['pedidos'], 'pedido', 'pedidos'))) if cantidad]
            if partes:
                mensaje += f' La siguen teniendo: {", ".join(partes)}.'
            flash(mensaje + ' Se puede reactivar desde su edición.', "warning" if partes else "success")
    except Exception as e:
        conn.rollback()
        flash(f"No se pudo inactivar la ruta: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('rutas.listar'))


# ── Batch ─────────────────────────────────────────────────────────────────────
_CAMPOS = ['nombre_ruta', 'descripcion', 'activo']
_EJEMPLO = ['Zona Norte', 'Ruta de reparto zona norte', '1']


@rutas_bp.route('/rutas/importar', methods=['POST'])
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
            nombre = str(row.get('nombre_ruta', '') or '').strip()
            if not nombre:
                errores.append({'fila': i, 'codigo': '(vacío)', 'razon': 'El campo nombre_ruta es obligatorio'})
                continue
            try:
                nombre = _nombre(nombre)
                with conn.cursor() as cursor:
                    if _nombre_en_uso(cursor, nombre, tenant_id):
                        omitidos.append(nombre)
                        continue
                    cursor.execute(
                        "INSERT INTO rutas (nombre_ruta, descripcion, activo, tenant_id) VALUES (%s, %s, %s, %s)",
                        (nombre, str(row.get('descripcion', '') or '').strip() or None,
                         _activo(row.get('activo')), tenant_id))
                    insertados += 1
            except Exception as e:
                errores.append({'fila': i, 'codigo': nombre, 'razon': str(e)})
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()
    return jsonify({'insertados': insertados, 'omitidos': omitidos, 'errores': errores})


@rutas_bp.route('/rutas/exportar/<formato>')
def exportar(formato):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Con las inactivas: la columna "activo" indica el estado de cada una
            cursor.execute(
                "SELECT nombre_ruta, descripcion, activo FROM rutas WHERE (%s IS NULL OR tenant_id = %s) ORDER BY nombre_ruta",
                (tenant_id, tenant_id))
            rows = cursor.fetchall()
    finally:
        conn.close()

    if formato == 'csv':
        return export_csv(rows, _CAMPOS, 'rutas.csv')
    elif formato == 'json':
        return export_json(rows, _CAMPOS, 'rutas.json')
    elif formato == 'xlsx':
        return export_xlsx(rows, _CAMPOS, 'rutas.xlsx')
    return 'Formato no válido', 400


@rutas_bp.route('/rutas/plantilla/<formato>')
def plantilla(formato):
    if formato == 'csv':
        return plantilla_csv(_CAMPOS, _EJEMPLO, 'plantilla_rutas.csv')
    elif formato == 'json':
        return plantilla_json(_CAMPOS, _EJEMPLO, 'plantilla_rutas.json')
    elif formato == 'xlsx':
        return plantilla_xlsx(_CAMPOS, _EJEMPLO, 'plantilla_rutas.xlsx')
    return 'Formato no válido', 400