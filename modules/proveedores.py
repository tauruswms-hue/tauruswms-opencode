import re

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
from modules.cuit import cuit_para_guardar, cuit_para_mostrar
from modules.db_config import get_db_connection
from modules.sql_dialect import is_duplicate_key_error

proveedores_bp = Blueprint('proveedores', __name__)

DIRECCION_MAX = 500   # largo de la columna proveedores.direccion
# Largo máximo de los demás textos (el de su columna)
LARGOS = {'codigo': 50, 'razonsocial': 200, 'telefono': 50, 'email': 100}
# Control mínimo, el mismo que hace el navegador: algo@algo, sin espacios
_EMAIL = re.compile(r'^[^@\s]+@[^@\s]+$')


def _direccion(valor):
    """Dirección del proveedor; lanza ValueError si no entra en la columna."""
    valor = str(valor or '').strip()
    if len(valor) > DIRECCION_MAX:
        raise ValueError(f'Dirección: admite hasta {DIRECCION_MAX} caracteres (tiene {len(valor)}).')
    return valor or None


def _texto(datos, campo, rotulo, obligatorio=False):
    valor = str(datos.get(campo) or '').strip()
    if obligatorio and not valor:
        raise DatoInvalido(f'{rotulo}: es obligatorio.')
    if len(valor) > LARGOS[campo]:
        raise DatoInvalido(f'{rotulo}: admite hasta {LARGOS[campo]} caracteres.')
    return valor or None


def _validar(datos):
    """Datos de un proveedor (del formulario o de una fila importada) listos para guardar.

    Lanza ValueError (DatoInvalido incluido) con un mensaje para mostrar al usuario.
    """
    email = _texto(datos, 'email', 'Email')
    if email and not _EMAIL.match(email):
        raise DatoInvalido(f'Email: "{email}" no es una dirección válida.')
    return {
        'codigo': _texto(datos, 'codigo', 'Código', obligatorio=True),
        'razonsocial': _texto(datos, 'razonsocial', 'Razón Social', obligatorio=True),
        'cuit': cuit_para_guardar(datos.get('cuit')),
        'direccion': _direccion(datos.get('direccion')),
        'telefono': _texto(datos, 'telefono', 'Teléfono'),
        'email': email,
    }


def _activo(valor, por_defecto=True):
    """Estado: True = Activo. Acepta 1/0 (lista Estado, archivos); sin dato, el valor por defecto."""
    valor = str(valor if valor is not None else '').strip().lower()
    if not valor:
        return bool(por_defecto)
    return valor in ('1', 'on', 'true', 'si', 'sí', 'yes')


def _codigo_en_uso(cursor, codigo, tenant_id, excluir_id=0):
    cursor.execute("""SELECT id FROM proveedores
                      WHERE codigo = %s AND id <> %s AND (%s IS NULL OR tenant_id = %s)""",
                   (codigo, excluir_id, tenant_id, tenant_id))
    return cursor.fetchone() is not None


@proveedores_bp.route('/proveedores')
def listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Activos e inactivos: un proveedor inactivo se sigue viendo y se puede reactivar
            cursor.execute("""SELECT p.*, (SELECT COUNT(DISTINCT mp.id_material) FROM material_proveedor mp
                                           WHERE mp.id_proveedor = p.id) AS materiales
                              FROM proveedores p WHERE (%s IS NULL OR p.tenant_id = %s)
                              ORDER BY p.activo DESC, p.razonsocial ASC""", (tenant_id, tenant_id))
            proveedores = [dict(p) for p in cursor.fetchall()]
        for p in proveedores:
            # Los CUIT cargados antes como 11 dígitos se muestran y editan ya formateados
            p['cuit'] = cuit_para_mostrar(p.get('cuit'))
        return render_template('proveedores.html', proveedores=proveedores, direccion_max=DIRECCION_MAX, largos=LARGOS)
    finally:
        conn.close()


@proveedores_bp.route('/proveedores/guardar', methods=['POST'])
def guardar():
    d = request.form
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        # Sin id o vacío: es un alta
        try:
            p_id = int((d.get('id') or '0').strip() or 0)
        except ValueError:
            raise DatoInvalido('Proveedor inválido.') from None
        datos = _validar(d)

        with conn.cursor() as cursor:
            anterior = None
            if p_id:
                cursor.execute("SELECT activo FROM proveedores WHERE id = %s AND (%s IS NULL OR tenant_id = %s)",
                               (p_id, tenant_id, tenant_id))
                anterior = cursor.fetchone()
                if not anterior:
                    raise DatoInvalido('El proveedor que se intenta modificar no existe.')
            if _codigo_en_uso(cursor, datos['codigo'], tenant_id, excluir_id=p_id):
                raise DatoInvalido(f'Ya existe un proveedor con el código "{datos["codigo"]}".')
            # Un proveedor nuevo nace activo; al editar sin el dato se conserva el estado
            activo = _activo(d.get('activo'), por_defecto=anterior['activo'] if anterior else True)

            valores = (datos['codigo'], datos['razonsocial'], datos['cuit'], datos['direccion'],
                       datos['telefono'], datos['email'], activo)
            if p_id:
                cursor.execute("""UPDATE proveedores SET codigo=%s, razonsocial=%s, cuit=%s,
                                  direccion=%s, telefono=%s, email=%s, activo=%s WHERE id=%s""", (*valores, p_id))
            else:
                cursor.execute("""INSERT INTO proveedores (codigo, razonsocial, cuit, direccion, telefono, email, activo, tenant_id)
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""", (*valores, tenant_id))
            conn.commit()
            flash("Proveedor guardado correctamente", "success")
    except ValueError as e:
        conn.rollback()
        flash(str(e), "danger")
    except Exception as e:
        conn.rollback()
        if is_duplicate_key_error(e):
            flash("Ya existe un proveedor con ese código.", "danger")
        else:
            flash(f"Error al guardar el proveedor: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('proveedores.listar'))


@proveedores_bp.route('/proveedores/eliminar/<int:id>', methods=['POST'])
def eliminar(id):
    """Inactiva el proveedor (no se borra: los materiales y recepciones que lo tienen lo conservan)."""
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT razonsocial, activo FROM proveedores WHERE id = %s AND (%s IS NULL OR tenant_id = %s)",
                           (id, tenant_id, tenant_id))
            proveedor = cursor.fetchone()
            if not proveedor:
                flash("Proveedor no encontrado.", "warning")
                return redirect(url_for('proveedores.listar'))
            if not proveedor['activo']:
                flash(f'El proveedor "{proveedor["razonsocial"]}" ya estaba inactivo.', "info")
                return redirect(url_for('proveedores.listar'))

            cursor.execute("UPDATE proveedores SET activo = %s WHERE id = %s", (False, id))
            cursor.execute("SELECT COUNT(DISTINCT id_material) AS n FROM material_proveedor WHERE id_proveedor = %s", (id,))
            materiales = cursor.fetchone()['n']
            conn.commit()

            mensaje = (f'El proveedor "{proveedor["razonsocial"]}" quedó inactivo: ya no se ofrece para '
                       'recepciones ni materiales nuevos.')
            if materiales:
                mensaje += (' Lo tiene asignado 1 material, que lo conserva.' if materiales == 1 else
                            f' Lo tienen asignado {materiales} materiales, que lo conservan.')
            flash(mensaje + ' Se puede reactivar desde su edición.', "warning" if materiales else "success")
    except Exception as e:
        conn.rollback()
        flash(f"No se pudo inactivar el proveedor: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('proveedores.listar'))


# ── Batch ─────────────────────────────────────────────────────────────────────
_CAMPOS = ['codigo', 'razonsocial', 'cuit', 'direccion', 'telefono', 'email', 'activo']
_EJEMPLO = ['PROV001', 'Proveedor de Ejemplo S.A.', '30-12345678-9',
            'Av. Siempre Viva 742', '011-4444-5555', 'contacto@ejemplo.com', '1']


@proveedores_bp.route('/proveedores/importar', methods=['POST'])
def importar():
    file = request.files.get('archivo')
    if not file or not file.filename:
        return jsonify({'error': 'No se proporcionó archivo'}), 400
    try:
        rows = parse_file(file, request.form.get('hoja'))
    except Exception as e:
        return jsonify({'error': f'Error al leer el archivo: {e!s}'}), 400

    tenant_id = get_tenant_filter()
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
                datos = _validar(row)
                with conn.cursor() as cursor:
                    if _codigo_en_uso(cursor, codigo, tenant_id):
                        omitidos.append(codigo)
                        continue
                    cursor.execute("""
                        INSERT INTO proveedores (codigo, razonsocial, cuit, direccion, telefono, email, activo, tenant_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (datos['codigo'], datos['razonsocial'], datos['cuit'], datos['direccion'],
                          datos['telefono'], datos['email'], _activo(row.get('activo')), tenant_id))
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


@proveedores_bp.route('/proveedores/exportar/<formato>')
def exportar(formato):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Con los inactivos, que llevan su estado en la columna activo
            cursor.execute("SELECT codigo, razonsocial, cuit, direccion, telefono, email, activo "
                           "FROM proveedores WHERE (%s IS NULL OR tenant_id = %s) ORDER BY razonsocial", (tenant_id, tenant_id))
            rows = cursor.fetchall()
    finally:
        conn.close()

    if formato == 'csv':
        return export_csv(rows, _CAMPOS, 'proveedores.csv')
    elif formato == 'json':
        return export_json(rows, _CAMPOS, 'proveedores.json')
    elif formato == 'xlsx':
        return export_xlsx(rows, _CAMPOS, 'proveedores.xlsx')
    return 'Formato no válido', 400


@proveedores_bp.route('/proveedores/plantilla/<formato>')
def plantilla(formato):
    if formato == 'csv':
        return plantilla_csv(_CAMPOS, _EJEMPLO, 'plantilla_proveedores.csv')
    elif formato == 'json':
        return plantilla_json(_CAMPOS, _EJEMPLO, 'plantilla_proveedores.json')
    elif formato == 'xlsx':
        return plantilla_xlsx(_CAMPOS, _EJEMPLO, 'plantilla_proveedores.xlsx')
    return 'Formato no válido', 400
