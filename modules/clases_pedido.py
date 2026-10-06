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

clases_pedido_bp = Blueprint('clases_pedido', __name__)

NOMBRE_MAX = 100   # largo de clases_pedido.nombre


def _nombre(valor):
    """Nombre de la clase, verificado: obligatorio y dentro del largo de la columna."""
    valor = str(valor or '').strip()
    if not valor:
        raise DatoInvalido('El nombre es obligatorio.')
    if len(valor) > NOMBRE_MAX:
        raise DatoInvalido(f'Nombre: admite hasta {NOMBRE_MAX} caracteres.')
    return valor


def _activo(valor, por_defecto=True):
    """Estado: True = Activa. Acepta 1/0 (lista Estado, archivos) y on (casilla, formularios anteriores)."""
    valor = str(valor if valor is not None else '').strip().lower()
    if not valor:
        return por_defecto
    return valor in ('1', 'on', 'true', 'si', 'sí', 'yes')


def _nombre_en_uso(cursor, nombre, tenant_id, excluir_id=0):
    """El nombre identifica a la clase (el Intercambio y la importación de pedidos la buscan por nombre)."""
    cursor.execute("""SELECT id_clase FROM clases_pedido
                      WHERE nombre = %s AND id_clase <> %s AND (%s IS NULL OR tenant_id = %s)""",
                   (nombre, excluir_id, tenant_id, tenant_id))
    return cursor.fetchone() is not None


@clases_pedido_bp.route('/clases-pedido')
def listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Activas e inactivas: una clase inactiva se sigue viendo y se puede reactivar
            cursor.execute("""SELECT * FROM clases_pedido WHERE (%s IS NULL OR tenant_id = %s)
                              ORDER BY activo DESC, nombre ASC""", (tenant_id, tenant_id))
            clases = cursor.fetchall()
        return render_template('clases_pedido.html', clases=clases, nombre_max=NOMBRE_MAX)
    finally:
        conn.close()


@clases_pedido_bp.route('/clases-pedido/guardar', methods=['POST'])
def guardar():
    d = request.form
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        try:
            id_clase = int((d.get('id_clase') or '0').strip() or 0)
        except ValueError:
            raise DatoInvalido('Clase de pedido inválida.') from None
        nombre = _nombre(d.get('nombre'))
        # Sin el campo Estado, un alta nace activa; en una edición equivale a Inactiva (casilla sin tildar)
        activo = _activo(d.get('activo'), por_defecto=not id_clase)

        with conn.cursor() as cursor:
            if id_clase:
                cursor.execute("SELECT id_clase FROM clases_pedido WHERE id_clase = %s AND (%s IS NULL OR tenant_id = %s)",
                               (id_clase, tenant_id, tenant_id))
                if not cursor.fetchone():
                    raise DatoInvalido('La clase de pedido que se intenta modificar no existe.')
            if _nombre_en_uso(cursor, nombre, tenant_id, excluir_id=id_clase):
                raise DatoInvalido(f'Ya existe una clase de pedido con el nombre "{nombre}".')

            if id_clase:
                cursor.execute("UPDATE clases_pedido SET nombre = %s, activo = %s WHERE id_clase = %s",
                               (nombre, activo, id_clase))
            else:
                cursor.execute("INSERT INTO clases_pedido (nombre, activo, tenant_id) VALUES (%s, %s, %s)",
                               (nombre, activo, tenant_id))
            conn.commit()
            flash("Clase de pedido guardada con éxito", "success")
    except DatoInvalido as e:
        conn.rollback()
        flash(str(e), "danger")
    except Exception as e:
        conn.rollback()
        if is_duplicate_key_error(e):
            flash("Ya existe una clase de pedido con ese nombre.", "danger")
        else:
            flash(f"Error al guardar la clase de pedido: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('clases_pedido.listar'))


@clases_pedido_bp.route('/clases-pedido/eliminar/<int:id_clase>', methods=['POST'])
def eliminar(id_clase):
    """Inactiva la clase (no se borra: los pedidos que la tienen la conservan)."""
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT nombre, activo FROM clases_pedido WHERE id_clase = %s AND (%s IS NULL OR tenant_id = %s)",
                           (id_clase, tenant_id, tenant_id))
            clase = cursor.fetchone()
            if not clase:
                flash("Clase de pedido no encontrada.", "warning")
                return redirect(url_for('clases_pedido.listar'))
            if not clase['activo']:
                flash(f'La clase "{clase["nombre"]}" ya estaba inactiva.', "info")
                return redirect(url_for('clases_pedido.listar'))

            cursor.execute("UPDATE clases_pedido SET activo = %s WHERE id_clase = %s", (False, id_clase))
            cursor.execute("SELECT COUNT(*) AS total FROM pedidos_cabecera WHERE id_clase = %s", (id_clase,))
            pedidos = cursor.fetchone()['total']
            conn.commit()

            mensaje = f'La clase "{clase["nombre"]}" quedó inactiva: ya no se ofrece al cargar pedidos.'
            if pedidos:
                mensaje += (f' La tiene{"n" if pedidos != 1 else ""} {pedidos} pedido{"s" if pedidos != 1 else ""}, '
                            f'que la conserva{"n" if pedidos != 1 else ""}.')
            flash(mensaje + ' Se puede reactivar desde su edición.', "warning" if pedidos else "success")
    except Exception as e:
        conn.rollback()
        flash(f"No se pudo inactivar la clase de pedido: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('clases_pedido.listar'))


# ── Batch ─────────────────────────────────────────────────────────────────────
_CAMPOS = ['nombre', 'activo']
_EJEMPLO = ['Urgente', '1']


@clases_pedido_bp.route('/clases-pedido/importar', methods=['POST'])
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
            nombre = str(row.get('nombre', '') or '').strip()
            if not nombre:
                errores.append({'fila': i, 'codigo': '(vacío)', 'razon': 'El campo nombre es obligatorio'})
                continue
            try:
                nombre = _nombre(nombre)
                with conn.cursor() as cursor:
                    if _nombre_en_uso(cursor, nombre, tenant_id):
                        omitidos.append(nombre)
                        continue
                    cursor.execute(
                        "INSERT INTO clases_pedido (nombre, activo, tenant_id) VALUES (%s, %s, %s)",
                        (nombre, _activo(row.get('activo')), tenant_id))
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


@clases_pedido_bp.route('/clases-pedido/exportar/<formato>')
def exportar(formato):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Con las inactivas: la columna "activo" indica el estado de cada una
            cursor.execute(
                "SELECT nombre, activo FROM clases_pedido WHERE (%s IS NULL OR tenant_id = %s) ORDER BY nombre",
                (tenant_id, tenant_id))
            rows = cursor.fetchall()
    finally:
        conn.close()

    if formato == 'csv':
        return export_csv(rows, _CAMPOS, 'clases_pedido.csv')
    elif formato == 'json':
        return export_json(rows, _CAMPOS, 'clases_pedido.json')
    elif formato == 'xlsx':
        return export_xlsx(rows, _CAMPOS, 'clases_pedido.xlsx')
    return 'Formato no válido', 400


@clases_pedido_bp.route('/clases-pedido/plantilla/<formato>')
def plantilla(formato):
    if formato == 'csv':
        return plantilla_csv(_CAMPOS, _EJEMPLO, 'plantilla_clases_pedido.csv')
    elif formato == 'json':
        return plantilla_json(_CAMPOS, _EJEMPLO, 'plantilla_clases_pedido.json')
    elif formato == 'xlsx':
        return plantilla_xlsx(_CAMPOS, _EJEMPLO, 'plantilla_clases_pedido.xlsx')
    return 'Formato no válido', 400


@clases_pedido_bp.route('/clases-pedido/plantilla-datos/<formato>')
def plantilla_datos(formato):
    """XLSX/CSV/JSON listo para importar con las clases sugeridas y las de la empresa.

    Las clases sugeridas son las que trae la instalación (Venta, Reposicion,
    Muestra, Devolucion): se crean sin empresa (tenant_id NULL) y ninguna empresa
    las ve hasta que las incorpora importando este archivo.
    """
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT nombre, activo FROM clases_pedido "
                "WHERE (tenant_id IS NULL OR tenant_id = %s OR %s IS NULL) ORDER BY nombre",
                (tenant_id, tenant_id))
            rows = cursor.fetchall()
    finally:
        conn.close()

    if formato == 'xlsx':
        return export_xlsx(rows, _CAMPOS, 'clases_pedido_importar.xlsx')
    elif formato == 'csv':
        return export_csv(rows, _CAMPOS, 'clases_pedido_importar.csv')
    elif formato == 'json':
        return export_json(rows, _CAMPOS, 'clases_pedido_importar.json')
    return 'Formato no válido', 400
