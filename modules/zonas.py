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

zonas_bp = Blueprint('zonas', __name__)

# Largo máximo de cada texto (el de su columna)
LARGOS = {'codigo': 20, 'nombre': 100}


def _validar(datos):
    """Código (siempre en mayúsculas), nombre y descripción de una zona, verificados."""
    codigo = str(datos.get('codigo') or '').strip().upper()
    nombre = str(datos.get('nombre') or '').strip()
    if not codigo:
        raise DatoInvalido('Código: es obligatorio.')
    if not nombre:
        raise DatoInvalido('Nombre: es obligatorio.')
    if len(codigo) > LARGOS['codigo']:
        raise DatoInvalido(f'Código: admite hasta {LARGOS["codigo"]} caracteres.')
    if len(nombre) > LARGOS['nombre']:
        raise DatoInvalido(f'Nombre: admite hasta {LARGOS["nombre"]} caracteres.')
    return {'codigo': codigo, 'nombre': nombre, 'descripcion': str(datos.get('descripcion') or '').strip() or None}


def _activo(valor, por_defecto=True):
    """Estado: True = Activa. Acepta 1/0 (lista Estado, archivos) y on (casilla, formularios anteriores)."""
    valor = str(valor if valor is not None else '').strip().lower()
    if not valor:
        return bool(por_defecto)
    return valor in ('1', 'on', 'true', 'si', 'sí', 'yes')


def _codigo_en_uso(cursor, codigo, tenant_id, excluir_id=0):
    cursor.execute("SELECT id FROM zonas WHERE codigo = %s AND id <> %s AND (%s IS NULL OR tenant_id = %s)",
                   (codigo, excluir_id, tenant_id, tenant_id))
    return cursor.fetchone() is not None


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
        return render_template('zonas.html', zonas=zonas, largos=LARGOS)
    finally:
        conn.close()


@zonas_bp.route('/zonas/guardar', methods=['POST'])
def guardar():
    tenant_id = get_tenant_filter()
    d = request.form
    conn = get_db_connection()
    try:
        # Sin id o vacío: es un alta
        try:
            z_id = int((d.get('id') or '0').strip() or 0)
        except ValueError:
            raise DatoInvalido('Zona inválida.') from None
        datos = _validar(d)

        with conn.cursor() as cursor:
            anterior = None
            if z_id:
                cursor.execute("SELECT activo FROM zonas WHERE id = %s AND (%s IS NULL OR tenant_id = %s)",
                               (z_id, tenant_id, tenant_id))
                anterior = cursor.fetchone()
                if not anterior:
                    raise DatoInvalido('La zona que se intenta modificar no existe.')
            if _codigo_en_uso(cursor, datos['codigo'], tenant_id, excluir_id=z_id):
                raise DatoInvalido(f'Ya existe una zona con el código "{datos["codigo"]}".')
            # Una zona nueva nace activa; al editar sin el dato se conserva el estado
            activo = _activo(d.get('activo'), por_defecto=bool(anterior['activo']) if anterior else True)

            aviso = ''
            if z_id:
                cursor.execute("UPDATE zonas SET codigo=%s, nombre=%s, descripcion=%s, activo=%s WHERE id=%s",
                               (datos['codigo'], datos['nombre'], datos['descripcion'], activo, z_id))
                if anterior['activo'] and not activo:
                    cursor.execute("SELECT COUNT(*) AS n FROM ubicaciones WHERE id_zona = %s", (z_id,))
                    n = cursor.fetchone()['n']
                    if n:
                        aviso = ('La zona quedó inactiva: no se ofrece para ubicaciones nuevas. La tiene '
                                 + ('1 ubicación, que la conserva.' if n == 1 else f'{n} ubicaciones, que la conservan.'))
            else:
                cursor.execute("INSERT INTO zonas (codigo, nombre, descripcion, activo, tenant_id) VALUES (%s, %s, %s, %s, %s)",
                               (datos['codigo'], datos['nombre'], datos['descripcion'], activo, tenant_id))
            conn.commit()
            flash("Zona guardada correctamente.", "success")
            if aviso:
                flash(aviso, "warning")
    except DatoInvalido as e:
        conn.rollback()
        flash(str(e), "danger")
    except Exception as e:
        conn.rollback()
        if is_duplicate_key_error(e):
            flash("Ya existe una zona con ese código.", "danger")
        else:
            flash(f"Error al guardar la zona: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('zonas.listar'))


@zonas_bp.route('/zonas/eliminar/<int:id>', methods=['POST'])
def eliminar(id):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT codigo FROM zonas WHERE id = %s AND (%s IS NULL OR tenant_id = %s)",
                           (id, tenant_id, tenant_id))
            zona = cursor.fetchone()
            if not zona:
                flash("Zona no encontrada.", "warning")
                return redirect(url_for('zonas.listar'))
            cursor.execute("SELECT COUNT(*) AS total FROM ubicaciones WHERE id_zona = %s", (id,))
            total = cursor.fetchone()['total']
            if total:
                flash(f'No se puede eliminar la zona "{zona["codigo"]}": tiene '
                      + ('1 ubicación asignada.' if total == 1 else f'{total} ubicaciones asignadas.')
                      + ' Se puede inactivar desde su edición.', "danger")
            else:
                cursor.execute("DELETE FROM zonas WHERE id = %s", (id,))
                conn.commit()
                flash("Zona eliminada.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"No se pudo eliminar la zona: {e!s}", "danger")
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
        rows = parse_file(file, request.form.get('hoja'))
    except Exception as e:
        return jsonify({'error': f'Error al leer el archivo: {e!s}'}), 400

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
                datos = _validar(row)
                with conn.cursor() as cursor:
                    if _codigo_en_uso(cursor, codigo, tenant_id):
                        omitidos.append(codigo)
                        continue
                    # Sin dato en activo, la zona nace activa
                    cursor.execute("""
                        INSERT INTO zonas (codigo, nombre, descripcion, activo, tenant_id)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (datos['codigo'], datos['nombre'], datos['descripcion'], _activo(row.get('activo')), tenant_id))
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
