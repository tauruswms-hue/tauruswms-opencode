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
from modules.sql_dialect import execute_insert, is_duplicate_key_error

transportes_bp = Blueprint('transportes', __name__)

# Largo máximo de cada texto (el de su columna)
_LARGOS = {'codigo': 100, 'razonsocial': 200, 'telefono': 50, 'email': 100}
_ROTULOS = {'codigo': 'Código', 'razonsocial': 'Razón social', 'telefono': 'Teléfono', 'email': 'Mail'}


def _texto(datos, campo, obligatorio=False):
    valor = str(datos.get(campo) or '').strip()
    if obligatorio and not valor:
        raise DatoInvalido(f'{_ROTULOS[campo]} es obligatorio.')
    if len(valor) > _LARGOS[campo]:
        raise DatoInvalido(f'{_ROTULOS[campo]}: admite hasta {_LARGOS[campo]} caracteres.')
    return valor or None


def _validar(datos):
    """Datos propios del transporte (formulario o fila importada), verificados."""
    email = _texto(datos, 'email')
    if email and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
        raise DatoInvalido('Mail: no tiene formato de dirección de correo.')
    try:
        cuit = cuit_para_guardar(datos.get('cuit'))     # opcional
    except ValueError as e:
        raise DatoInvalido(str(e)) from None
    return {
        'codigo': _texto(datos, 'codigo', obligatorio=True),
        'razonsocial': _texto(datos, 'razonsocial', obligatorio=True),
        'cuit': cuit,
        'telefono': _texto(datos, 'telefono'),
        'email': email,
    }


def _activo(valor, por_defecto=True):
    """Estado: True = Activo. Acepta 1/0 (lista Estado, archivos) y on (casilla, formularios anteriores)."""
    valor = str(valor if valor is not None else '').strip().lower()
    if not valor:
        return por_defecto
    return valor in ('1', 'on', 'true', 'si', 'sí', 'yes')


def _muelle(cursor, valor, tenant_id, por_codigo=False):
    """Id del muelle de salida: una ubicación del tenant cuyo tipo es de salida (operación 'S'). None si no se indica."""
    valor = str(valor if valor is not None else '').strip()
    if not valor:
        return None
    columna = 'u.codigo' if por_codigo else 'u.id'
    if not por_codigo and not valor.isdigit():
        raise DatoInvalido('Muelle de salida: valor inválido.')
    cursor.execute(f"""SELECT u.id, t.operacion FROM ubicaciones u
                       LEFT JOIN tipoubicacion t ON u.tipoubicacion = t.id
                       WHERE {columna} = %s AND (%s IS NULL OR u.tenant_id = %s)""", (valor, tenant_id, tenant_id))
    fila = cursor.fetchone()
    if not fila:
        raise DatoInvalido(f'Muelle de salida: no existe la ubicación "{valor}".' if por_codigo
                           else 'Muelle de salida: la ubicación elegida no existe.')
    if (fila['operacion'] or '').upper() != 'S':
        raise DatoInvalido('Muelle de salida: la ubicación tiene que ser de un tipo de salida.')
    return fila['id']


def _rutas_por_id(cursor, ids, observaciones, tenant_id):
    """Rutas que cubre el transporte, del formulario: [(id_ruta, observaciones)], sin vacías ni repetidas."""
    cursor.execute("SELECT id_ruta FROM rutas WHERE (%s IS NULL OR tenant_id = %s)", (tenant_id, tenant_id))
    validas = {r['id_ruta'] for r in cursor.fetchall()}
    rutas = []
    for i, valor in enumerate(ids):
        valor = str(valor or '').strip()
        if not valor:
            continue
        if not valor.isdigit() or int(valor) not in validas:
            raise DatoInvalido('Rutas: la ruta elegida no existe.')
        if any(r[0] == int(valor) for r in rutas):
            raise DatoInvalido('Rutas: hay una ruta repetida.')
        rutas.append((int(valor), (observaciones[i].strip() if i < len(observaciones) else '') or None))
    return rutas


def _rutas_por_nombre(cursor, texto, tenant_id):
    """Rutas indicadas en un archivo por su nombre, separadas por punto y coma."""
    nombres = [n.strip() for n in str(texto or '').split(';') if n.strip()]
    if not nombres:
        return []
    cursor.execute("SELECT id_ruta, nombre_ruta FROM rutas WHERE (%s IS NULL OR tenant_id = %s)", (tenant_id, tenant_id))
    por_nombre = {r['nombre_ruta'].strip().lower(): r['id_ruta'] for r in cursor.fetchall()}
    rutas = []
    for nombre in nombres:
        id_ruta = por_nombre.get(nombre.lower())
        if id_ruta is None:
            raise DatoInvalido(f'Rutas: no existe la ruta "{nombre}".')
        if all(r[0] != id_ruta for r in rutas):
            rutas.append((id_ruta, None))
    return rutas


def _guardar_rutas(cursor, id_transporte, rutas, tenant_id):
    cursor.execute("DELETE FROM transporte_rutas WHERE id_transporte = %s", (id_transporte,))
    for id_ruta, observaciones in rutas:
        cursor.execute("""INSERT INTO transporte_rutas (id_transporte, id_ruta, observaciones, tenant_id)
                          VALUES (%s, %s, %s, %s)""", (id_transporte, id_ruta, observaciones, tenant_id))


def _codigo_en_uso(cursor, codigo, tenant_id, excluir_id=0):
    cursor.execute("""SELECT id_transporte FROM transportes
                      WHERE codigo = %s AND id_transporte <> %s AND (%s IS NULL OR tenant_id = %s)""",
                   (codigo, excluir_id, tenant_id, tenant_id))
    return cursor.fetchone() is not None


@transportes_bp.route('/transportes')
def listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT t.*, u.codigo AS muelle_codigo, u.descipcion AS muelle_descripcion
                FROM transportes t
                LEFT JOIN ubicaciones u ON t.id_muelle_salida = u.id
                WHERE (%s IS NULL OR t.tenant_id = %s)
                ORDER BY t.razonsocial
            """, (tenant_id, tenant_id))
            transportes = [dict(t) for t in cursor.fetchall()]
            cursor.execute("SELECT * FROM rutas WHERE (%s IS NULL OR tenant_id = %s) ORDER BY nombre_ruta", (tenant_id, tenant_id))
            rutas_lista = cursor.fetchall()
            cursor.execute("SELECT * FROM transporte_rutas WHERE (%s IS NULL OR tenant_id = %s)", (tenant_id, tenant_id))
            relaciones = cursor.fetchall()
            cursor.execute("""
                SELECT u.id, u.codigo, u.descipcion
                FROM ubicaciones u
                JOIN tipoubicacion t ON u.tipoubicacion = t.id
                WHERE t.operacion = 'S' AND (%s IS NULL OR u.tenant_id = %s)
                ORDER BY u.codigo
            """, (tenant_id, tenant_id))
            muelles = cursor.fetchall()

        nombre_ruta = {r['id_ruta']: r['nombre_ruta'] for r in rutas_lista}
        for t in transportes:
            # Los CUIT cargados antes como 11 dígitos se muestran y editan ya formateados
            t['cuit'] = cuit_para_mostrar(t.get('cuit'))
            t['rutas_nombres'] = sorted(nombre_ruta[r['id_ruta']] for r in relaciones
                                        if r['id_transporte'] == t['id_transporte'] and r['id_ruta'] in nombre_ruta)
        return render_template('transportes.html', transportes=transportes, rutas_lista=rutas_lista,
                               relaciones=relaciones, muelles=muelles, largos=_LARGOS)
    finally:
        conn.close()


@transportes_bp.route('/transportes/guardar', methods=['POST'])
def guardar():
    d = request.form
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        try:
            t_id = int((d.get('id_transporte') or '0').strip() or 0)
        except ValueError:
            raise DatoInvalido('Transporte inválido.') from None
        datos = _validar(d)
        # Sin el campo Estado, un alta nace activa; en una edición equivale a Inactivo (casilla sin tildar)
        activo = _activo(d.get('activo'), por_defecto=not t_id)

        with conn.cursor() as cursor:
            if t_id:
                cursor.execute("SELECT id_transporte FROM transportes WHERE id_transporte = %s AND (%s IS NULL OR tenant_id = %s)",
                               (t_id, tenant_id, tenant_id))
                if not cursor.fetchone():
                    raise DatoInvalido('El transporte que se intenta modificar no existe.')
            if _codigo_en_uso(cursor, datos['codigo'], tenant_id, excluir_id=t_id):
                raise DatoInvalido(f'Ya existe un transporte con el código "{datos["codigo"]}".')
            muelle = _muelle(cursor, d.get('id_muelle_salida'), tenant_id)
            rutas = _rutas_por_id(cursor, request.form.getlist('rutas_ids[]'), request.form.getlist('rutas_obs[]'),
                                  tenant_id)

            params = (datos['codigo'], datos['razonsocial'], datos['cuit'], datos['telefono'], datos['email'],
                      activo, muelle)
            if t_id:
                cursor.execute("""UPDATE transportes SET codigo=%s, razonsocial=%s, cuit=%s,
                                  telefono=%s, email=%s, activo=%s, id_muelle_salida=%s
                                  WHERE id_transporte=%s""", (*params, t_id))
            else:
                t_id = execute_insert(cursor, """INSERT INTO transportes
                                  (codigo, razonsocial, cuit, telefono, email, activo, id_muelle_salida, tenant_id)
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""", (*params, tenant_id),
                                      id_col='id_transporte')
            _guardar_rutas(cursor, t_id, rutas, tenant_id)

            conn.commit()
            flash("Transporte guardado exitosamente.", "success")
    except DatoInvalido as e:
        conn.rollback()
        flash(str(e), "danger")
    except Exception as e:
        conn.rollback()
        if is_duplicate_key_error(e):
            flash("Ya existe un transporte con ese código.", "danger")
        else:
            flash(f"Error al guardar el transporte: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('transportes.listar'))


@transportes_bp.route('/transportes/eliminar/<int:id_transporte>', methods=['POST'])
def eliminar(id_transporte):
    """Inactiva el transporte (no se borra: los clientes y pedidos que lo usan lo conservan)."""
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""SELECT codigo, activo FROM transportes
                              WHERE id_transporte = %s AND (%s IS NULL OR tenant_id = %s)""",
                           (id_transporte, tenant_id, tenant_id))
            transporte = cursor.fetchone()
            if not transporte:
                flash("Transporte no encontrado.", "warning")
                return redirect(url_for('transportes.listar'))
            if not transporte['activo']:
                flash(f'El transporte "{transporte["codigo"]}" ya estaba inactivo.', "info")
                return redirect(url_for('transportes.listar'))

            cursor.execute("UPDATE transportes SET activo = %s WHERE id_transporte = %s", (False, id_transporte))
            cursor.execute("SELECT COUNT(*) AS n FROM clientes WHERE id_transporte_predeterminado = %s", (id_transporte,))
            clientes = cursor.fetchone()['n']
            conn.commit()

            mensaje = f'El transporte "{transporte["codigo"]}" quedó inactivo: ya no se ofrece para clientes ni pedidos nuevos.'
            if clientes:
                mensaje += (f' Lo tiene{"n" if clientes != 1 else ""} como transporte habitual {clientes} '
                            f'cliente{"s" if clientes != 1 else ""}, que lo conserva{"n" if clientes != 1 else ""}.')
            flash(mensaje + ' Se puede reactivar desde su edición.', "warning" if clientes else "success")
    except Exception as e:
        conn.rollback()
        flash(f"No se pudo inactivar el transporte: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('transportes.listar'))


# ── Batch ─────────────────────────────────────────────────────────────────────
_CAMPOS_EXPORT = ['codigo', 'razonsocial', 'cuit', 'telefono', 'email', 'muelle_salida', 'rutas', 'activo']
_CAMPOS_IMPORT = ['codigo', 'razonsocial', 'cuit', 'telefono', 'email', 'muelle_salida', 'rutas', 'activo']
# El muelle y las rutas del ejemplo van vacíos: dependen de las ubicaciones y rutas de cada instalación
_EJEMPLO_IMPORT = ['TRA001', 'Transporte Ejemplo S.A.', '30-12345678-9',
                   '011-4444-5555', 'transporte@ejemplo.com', '', '', '1']


@transportes_bp.route('/transportes/importar', methods=['POST'])
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
                    muelle = _muelle(cursor, row.get('muelle_salida'), tenant_id, por_codigo=True)
                    rutas = _rutas_por_nombre(cursor, row.get('rutas'), tenant_id)
                    id_nuevo = execute_insert(cursor, """
                        INSERT INTO transportes (codigo, razonsocial, cuit, telefono, email, activo,
                                                 id_muelle_salida, tenant_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (datos['codigo'], datos['razonsocial'], datos['cuit'], datos['telefono'], datos['email'],
                          _activo(row.get('activo')), muelle, tenant_id), id_col='id_transporte')
                    _guardar_rutas(cursor, id_nuevo, rutas, tenant_id)
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


@transportes_bp.route('/transportes/exportar/<formato>')
def exportar(formato):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT t.id_transporte, t.codigo, t.razonsocial, t.cuit, t.telefono, t.email, t.activo,
                       u.codigo AS muelle_salida
                FROM transportes t
                LEFT JOIN ubicaciones u ON t.id_muelle_salida = u.id
                WHERE (%s IS NULL OR t.tenant_id = %s)
                ORDER BY t.razonsocial
            """, (tenant_id, tenant_id))
            rows = [dict(r) for r in cursor.fetchall()]
            cursor.execute("""
                SELECT tr.id_transporte, r.nombre_ruta FROM transporte_rutas tr
                JOIN rutas r ON r.id_ruta = tr.id_ruta
                WHERE (%s IS NULL OR tr.tenant_id = %s)
                ORDER BY r.nombre_ruta
            """, (tenant_id, tenant_id))
            por_transporte = {}
            for r in cursor.fetchall():
                por_transporte.setdefault(r['id_transporte'], []).append(r['nombre_ruta'])
    finally:
        conn.close()
    for r in rows:
        # Mismo formato que acepta la importación: nombres separados por punto y coma
        r['rutas'] = '; '.join(por_transporte.get(r['id_transporte'], []))
        r['cuit'] = cuit_para_mostrar(r.get('cuit'))

    if formato == 'csv':
        return export_csv(rows, _CAMPOS_EXPORT, 'transportes.csv')
    elif formato == 'json':
        return export_json(rows, _CAMPOS_EXPORT, 'transportes.json')
    elif formato == 'xlsx':
        return export_xlsx(rows, _CAMPOS_EXPORT, 'transportes.xlsx')
    return 'Formato no válido', 400


@transportes_bp.route('/transportes/plantilla/<formato>')
def plantilla(formato):
    if formato == 'csv':
        return plantilla_csv(_CAMPOS_IMPORT, _EJEMPLO_IMPORT, 'plantilla_transportes.csv')
    elif formato == 'json':
        return plantilla_json(_CAMPOS_IMPORT, _EJEMPLO_IMPORT, 'plantilla_transportes.json')
    elif formato == 'xlsx':
        return plantilla_xlsx(_CAMPOS_IMPORT, _EJEMPLO_IMPORT, 'plantilla_transportes.xlsx')
    return 'Formato no válido', 400