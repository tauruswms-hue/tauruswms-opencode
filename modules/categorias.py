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

categorias_bp = Blueprint('categorias', __name__)

CODIGO_MAX = 50    # largo de categorias.codigo
NOMBRE_MAX = 100   # largo de categorias.nombre


def _texto(valor, rotulo, maximo):
    """Texto obligatorio, sin espacios en los extremos y dentro del largo de la columna."""
    valor = str(valor or '').strip()
    if not valor:
        raise DatoInvalido(f'{rotulo}: es obligatorio.')
    if len(valor) > maximo:
        raise DatoInvalido(f'{rotulo}: admite hasta {maximo} caracteres.')
    return valor


def _activo(valor, por_defecto=True):
    """Estado: True = Activa. Acepta 1/0 (lista Estado, archivos) y on (casilla, formularios anteriores)."""
    valor = str(valor if valor is not None else '').strip().lower()
    if not valor:
        return por_defecto
    return valor in ('1', 'on', 'true', 'si', 'sí', 'yes')


def _en_uso(cursor, columna, valor, tenant_id, excluir_id=0):
    """Otra categoría de la empresa (activa o no) ya tiene ese código o ese nombre."""
    cursor.execute(f"""SELECT id_categoria FROM categorias
                       WHERE {columna} = %s AND id_categoria <> %s AND (%s IS NULL OR tenant_id = %s)""",
                   (valor, excluir_id, tenant_id, tenant_id))
    return cursor.fetchone() is not None


def _validar(cursor, codigo, nombre, tenant_id, excluir_id=0):
    """Código y nombre verificados; ninguno puede repetirse en la empresa.

    El código es la clave con que Materiales y el Intercambio buscan la categoría;
    el nombre es lo que se ve al elegirla en un material.
    """
    codigo = _texto(codigo, 'Código', CODIGO_MAX)
    nombre = _texto(nombre, 'Nombre', NOMBRE_MAX)
    if _en_uso(cursor, 'codigo', codigo, tenant_id, excluir_id):
        raise DatoInvalido(f'Ya existe una categoría con el código "{codigo}".')
    if _en_uso(cursor, 'nombre', nombre, tenant_id, excluir_id):
        raise DatoInvalido(f'Ya existe una categoría con el nombre "{nombre}".')
    return codigo, nombre


@categorias_bp.route('/categorias')
def listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Activas e inactivas: una categoría inactiva se sigue viendo y se puede reactivar
            cursor.execute("""
                SELECT c.*, (SELECT COUNT(*) FROM materiales m WHERE m.categoria_id = c.id_categoria) AS materiales
                FROM categorias c
                WHERE (%s IS NULL OR c.tenant_id = %s)
                ORDER BY c.activo DESC, c.nombre ASC""", (tenant_id, tenant_id))
            categorias = cursor.fetchall()
        return render_template('categorias.html', categorias=categorias,
                               codigo_max=CODIGO_MAX, nombre_max=NOMBRE_MAX)
    finally:
        conn.close()


@categorias_bp.route('/categorias/guardar', methods=['POST'])
def guardar():
    d = request.form
    tenant_id = get_tenant_filter()

    conn = get_db_connection()
    try:
        try:
            c_id = int((d.get('id_categoria') or '0').strip() or 0)
        except ValueError:
            raise DatoInvalido('Categoría inválida.') from None
        descripcion = (d.get('descripcion') or '').strip() or None
        # Sin el campo Estado, un alta nace activa; en una edición equivale a Inactiva (casilla sin tildar)
        activo = _activo(d.get('activo'), por_defecto=not c_id)

        with conn.cursor() as cursor:
            if c_id:
                cursor.execute("SELECT id_categoria FROM categorias WHERE id_categoria = %s AND (%s IS NULL OR tenant_id = %s)",
                               (c_id, tenant_id, tenant_id))
                if not cursor.fetchone():
                    raise DatoInvalido('La categoría que se intenta modificar no existe.')
            codigo, nombre = _validar(cursor, d.get('codigo'), d.get('nombre'), tenant_id, excluir_id=c_id)

            if c_id:
                cursor.execute("UPDATE categorias SET codigo = %s, nombre = %s, descripcion = %s, activo = %s WHERE id_categoria = %s",
                               (codigo, nombre, descripcion, activo, c_id))
            else:
                cursor.execute("INSERT INTO categorias (codigo, nombre, descripcion, activo, tenant_id) VALUES (%s, %s, %s, %s, %s)",
                               (codigo, nombre, descripcion, activo, tenant_id))

            conn.commit()
            flash("Categoría guardada con éxito", "success")
    except DatoInvalido as e:
        conn.rollback()
        flash(str(e), "danger")
    except Exception as e:
        conn.rollback()
        if is_duplicate_key_error(e):
            flash("Ya existe una categoría con ese código.", "danger")
        else:
            flash(f"Error al guardar la categoría: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('categorias.listar'))


@categorias_bp.route('/categorias/eliminar/<int:id>', methods=['POST'])
def eliminar(id):
    """Inactiva la categoría. No se borra: los materiales que la tienen la conservan."""
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT nombre, activo FROM categorias WHERE id_categoria = %s AND (%s IS NULL OR tenant_id = %s)",
                           (id, tenant_id, tenant_id))
            categoria = cursor.fetchone()
            if not categoria:
                flash("Categoría no encontrada.", "warning")
                return redirect(url_for('categorias.listar'))
            if not categoria['activo']:
                flash(f'La categoría "{categoria["nombre"]}" ya estaba inactiva.', "info")
                return redirect(url_for('categorias.listar'))

            cursor.execute("UPDATE categorias SET activo = %s WHERE id_categoria = %s", (False, id))
            cursor.execute("SELECT COUNT(*) AS total FROM materiales WHERE categoria_id = %s", (id,))
            materiales = cursor.fetchone()['total']
            conn.commit()

            mensaje = f'La categoría "{categoria["nombre"]}" quedó inactiva: ya no se ofrece al cargar materiales.'
            if materiales:
                mensaje += (f' La tiene{"n" if materiales != 1 else ""} {materiales} '
                            f'material{"es" if materiales != 1 else ""}, que la conserva{"n" if materiales != 1 else ""}.')
            flash(mensaje + ' Se puede reactivar desde su edición.', "warning" if materiales else "success")
    except Exception as e:
        conn.rollback()
        flash(f"No se pudo inactivar la categoría: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('categorias.listar'))


# ── Batch ─────────────────────────────────────────────────────────────────────
_CAMPOS = ['codigo', 'nombre', 'descripcion', 'activo']
_EJEMPLO = ['CAT001', 'Novelas', 'Libros de ficción y narrativa', '1']


@categorias_bp.route('/categorias/importar', methods=['POST'])
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
            codigo = str(row.get('codigo', '') or '').strip()
            nombre = str(row.get('nombre', '') or '').strip()
            if not codigo or not nombre:
                errores.append({'fila': i, 'codigo': codigo or '(vacío)', 'razon': 'Código y Nombre son obligatorios'})
                continue
            try:
                with conn.cursor() as cursor:
                    # Un código que ya existe se omite; lo demás (largos, nombre repetido) es un error de la fila
                    if _en_uso(cursor, 'codigo', codigo, tenant_id):
                        omitidos.append(codigo)
                        continue
                    codigo, nombre = _validar(cursor, codigo, nombre, tenant_id)
                    cursor.execute("""
                        INSERT INTO categorias (codigo, nombre, descripcion, activo, tenant_id)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        codigo,
                        nombre,
                        str(row.get('descripcion', '') or '').strip() or None,
                        _activo(row.get('activo')),   # sin dato, activa
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


@categorias_bp.route('/categorias/exportar/<formato>')
def exportar(formato):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Con las inactivas: la columna "activo" indica el estado de cada una
            cursor.execute("""
                SELECT codigo, nombre, descripcion, activo
                FROM categorias
                WHERE (%s IS NULL OR tenant_id = %s)
                ORDER BY nombre
            """, (tenant_id, tenant_id))
            rows = cursor.fetchall()
    finally:
        conn.close()

    if formato == 'csv':
        return export_csv(rows, _CAMPOS, 'categorias.csv')
    elif formato == 'json':
        return export_json(rows, _CAMPOS, 'categorias.json')
    elif formato == 'xlsx':
        return export_xlsx(rows, _CAMPOS, 'categorias.xlsx')
    return 'Formato no válido', 400


@categorias_bp.route('/categorias/plantilla/<formato>')
def plantilla(formato):
    if formato == 'csv':
        return plantilla_csv(_CAMPOS, _EJEMPLO, 'plantilla_categorias.csv')
    elif formato == 'json':
        return plantilla_json(_CAMPOS, _EJEMPLO, 'plantilla_categorias.json')
    elif formato == 'xlsx':
        return plantilla_xlsx(_CAMPOS, _EJEMPLO, 'plantilla_categorias.xlsx')
    return 'Formato no válido', 400
