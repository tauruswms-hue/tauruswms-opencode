from decimal import Decimal, InvalidOperation

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

unidades_bp = Blueprint('unidades', __name__)

# Magnitudes admitidas (valor guardado -> rótulo). Es la única lista: la usan el
# formulario, la importación y la ayuda de la importación.
MAGNITUDES = {
    'CANTIDAD': 'Cantidad',
    'MASA': 'Masa',
    'VOLUMEN': 'Volumen',
    'LONGITUD': 'Longitud',
    'TIEMPO': 'Tiempo',
}
# Nombres que se usaron antes para lo mismo: se aceptan y se guardan con el valor actual
_MAGNITUDES_ANTERIORES = {'UNIDAD': 'CANTIDAD', 'PESO': 'MASA'}

# Largo máximo de cada texto (el de su columna)
_LARGOS = {'codigo': 50, 'nombre': 100, 'simbolo': 20}
MAX_DECIMALES = 4
# conversion_a_base es decimal(12,4): hasta 4 decimales y 8 enteros
CONVERSION_DECIMALES = 4
CONVERSION_MAX = Decimal('99999999.9999')


class BaseInexistente(DatoInvalido):
    """La unidad base indicada no existe (en una importación puede venir más abajo en el archivo)."""


def _decimal(valor, rotulo):
    """Número del formulario o del archivo (acepta coma decimal), o DatoInvalido."""
    try:
        numero = Decimal(str(valor).strip().replace(',', '.'))
    except InvalidOperation:
        numero = None
    if numero is None or not numero.is_finite():
        raise DatoInvalido(f'{rotulo}: "{valor}" no es un número válido.')
    return numero


def numero_para_mostrar(valor):
    """Número sin ceros de relleno y con coma decimal: 0.0010 -> '0,001', 1000.0000 -> '1000'."""
    texto = format(Decimal(str(valor)), 'f')
    if '.' in texto:
        texto = texto.rstrip('0').rstrip('.')
    return texto.replace('.', ',')


def _activo(valor, actual=True):
    """Estado que llega del formulario: lista Activa (1) / Inactiva (0). Sin dato, se conserva el actual."""
    valor = str(valor or '').strip().lower()
    if not valor:
        return bool(actual)
    return valor in ('1', 'on', 'true', 'si', 'sí')


def _plural(n, singular, plural):
    return f'{n} {singular if n == 1 else plural}'


def _magnitud(valor):
    """Magnitud normalizada, o None si no es una de las admitidas."""
    valor = str(valor or '').strip().upper()
    if not valor:
        return 'CANTIDAD'
    valor = _MAGNITUDES_ANTERIORES.get(valor, valor)
    return valor if valor in MAGNITUDES else None


def _texto(datos, campo, rotulo, obligatorio=False):
    valor = str(datos.get(campo) or '').strip()
    if obligatorio and not valor:
        raise DatoInvalido(f'{rotulo} es obligatorio.')
    if len(valor) > _LARGOS[campo]:
        raise DatoInvalido(f'{rotulo}: admite hasta {_LARGOS[campo]} caracteres.')
    return valor


def _validar(datos):
    """Valida los datos de una unidad (del formulario o de una fila importada)."""
    magnitud = _magnitud(datos.get('tipo_magnitud'))
    if magnitud is None:
        raise DatoInvalido(f'Tipo de magnitud "{datos.get("tipo_magnitud")}" no válido. '
                           f'Usar: {", ".join(MAGNITUDES)}.')
    conversion = _decimal(datos.get('conversion_a_base') or 1, 'Conversión a base')
    if conversion <= 0:
        raise DatoInvalido('Conversión a base: tiene que ser mayor que cero.')
    if conversion > CONVERSION_MAX:
        raise DatoInvalido('Conversión a base: tiene que ser menor que 100.000.000.')
    if conversion != round(conversion, CONVERSION_DECIMALES):
        # Con más decimales la base la redondea: 0,00001 quedaba guardado como 0
        raise DatoInvalido(f'Conversión a base: admite hasta {CONVERSION_DECIMALES} decimales.')
    decimales = _decimal(datos.get('decimales_permitidos') or 0, 'Decimales permitidos')
    if decimales != decimales.to_integral_value():
        raise DatoInvalido(f'Decimales permitidos: "{datos.get("decimales_permitidos")}" no es un número entero.')
    if not 0 <= decimales <= MAX_DECIMALES:
        raise DatoInvalido(f'Decimales permitidos: tiene que estar entre 0 y {MAX_DECIMALES}.')
    decimales = int(decimales)
    return {
        'codigo': _texto(datos, 'codigo', 'Código', obligatorio=True),
        'nombre': _texto(datos, 'nombre', 'Nombre', obligatorio=True),
        'simbolo': _texto(datos, 'simbolo', 'Símbolo') or None,
        'tipo_magnitud': magnitud,
        'conversion_a_base': conversion,
        # Código de la unidad base tal como llegó; _resolver_base lo verifica contra la base
        'unidad_base_referencia': str(datos.get('unidad_base_referencia') or '').strip(),
        'decimales_permitidos': decimales,
    }


def _unidades_del_tenant(cursor, tenant_id):
    cursor.execute("""SELECT id_unidad, codigo, simbolo, tipo_magnitud, unidad_base_referencia
                      FROM unidades_medida WHERE (%s IS NULL OR tenant_id = %s)""", (tenant_id, tenant_id))
    return [dict(u) for u in cursor.fetchall()]


def _base_de(unidad, por_codigo):
    """Unidad base de `unidad` (dict de la tabla), o None si es ella misma una unidad base.

    La base se guarda por código. Un valor que no corresponde a ninguna unidad
    (datos anteriores, que guardaban un símbolo suelto) cuenta como "sin base".
    """
    base = por_codigo.get(str(unidad.get('unidad_base_referencia') or '').strip().lower())
    return base if base and base['id_unidad'] != unidad['id_unidad'] else None


def _resolver_base(cursor, datos, tenant_id, u_id=0):
    """Completa en `datos` la unidad base y la conversión, ya verificadas.

    La unidad base es aquella sobre la que se calculan los múltiplos y
    submúltiplos (1000 mm = 1 m: la base del milímetro es el metro y su
    conversión 0,001). Tiene que ser otra unidad de la misma magnitud. Sin
    unidad base, la unidad es ella misma una base y su conversión es 1.
    """
    referencia = datos['unidad_base_referencia']
    unidades = _unidades_del_tenant(cursor, tenant_id) if referencia else []
    por_codigo = {u['codigo'].lower(): u for u in unidades}
    base = por_codigo.get(referencia.lower()) if referencia else None
    if referencia and base is None:
        # Archivos anteriores indicaban la base por su símbolo: se acepta si no hay ambigüedad
        candidatas = [u for u in unidades if (u['simbolo'] or '').lower() == referencia.lower()
                      and u['id_unidad'] != u_id and _magnitud(u['tipo_magnitud']) == datos['tipo_magnitud']]
        base = candidatas[0] if len(candidatas) == 1 else None
    propias = {datos['codigo'].lower(), (datos['simbolo'] or '').lower()}
    if base is not None and base['id_unidad'] == u_id:
        base = None   # referida a sí misma
    if base is None and (not referencia or referencia.lower() in propias):
        # Sin unidad base (o referida a sí misma, como en datos anteriores): es una unidad base
        datos['unidad_base_referencia'] = None
        datos['conversion_a_base'] = Decimal(1)
        return
    if base is None:
        raise BaseInexistente(f'Unidad base: no existe una unidad con el código "{referencia}".')
    if _magnitud(base['tipo_magnitud']) != datos['tipo_magnitud']:
        raise DatoInvalido(f'Unidad base: "{base["codigo"]}" es de otra magnitud '
                           f'({MAGNITUDES.get(_magnitud(base["tipo_magnitud"]), base["tipo_magnitud"])}).')
    # Que la cadena de bases no vuelva a esta unidad (A sobre B y B sobre A)
    eslabon, pasos = base, 0
    while eslabon and pasos <= len(unidades):
        if u_id and eslabon['id_unidad'] == u_id:
            raise DatoInvalido(f'Unidad base: "{base["codigo"]}" ya se calcula a partir de esta unidad '
                               '(referencia circular).')
        eslabon, pasos = _base_de(eslabon, por_codigo), pasos + 1
    datos['unidad_base_referencia'] = base['codigo']


def _codigo_en_uso(cursor, codigo, tenant_id, excluir_id=0):
    cursor.execute("""SELECT id_unidad FROM unidades_medida
                      WHERE codigo = %s AND id_unidad <> %s AND (%s IS NULL OR tenant_id = %s)""",
                   (codigo, excluir_id, tenant_id, tenant_id))
    return cursor.fetchone() is not None


@ unidades_bp.route('/unidades')
def unidades():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Activas e inactivas: una unidad inactiva se sigue viendo y se puede reactivar
            # Con la cantidad de materiales que la usan, como unidad de medida o del volumen
            cursor.execute("""SELECT u.*, (SELECT COUNT(*) FROM materiales m
                                           WHERE m.unidad_medida_id = u.id_unidad
                                              OR m.volumen_unidad_id = u.id_unidad) AS materiales
                              FROM unidades_medida u WHERE (%s IS NULL OR u.tenant_id = %s)
                              ORDER BY u.activo DESC, u.id_unidad DESC""", (tenant_id, tenant_id))
            res_unidades = [dict(u) for u in cursor.fetchall()]
        por_codigo = {u['codigo'].lower(): u for u in res_unidades}
        for u in res_unidades:
            # Valores guardados con un nombre anterior (UNIDAD, PESO) se muestran con el actual
            u['tipo_magnitud'] = _magnitud(u.get('tipo_magnitud')) or u.get('tipo_magnitud')
        for u in res_unidades:
            base = _base_de(u, por_codigo)
            u['unidad_base_referencia'] = base['codigo'] if base else ''
            u['equivalencia'] = (f"1 {u['simbolo'] or u['codigo']} = {numero_para_mostrar(u['conversion_a_base'])} "
                                 f"{base['simbolo'] or base['codigo']}") if base else ''
        return render_template('unidades.html', unidades=res_unidades, magnitudes=MAGNITUDES,
                               max_decimales=MAX_DECIMALES, largos=_LARGOS)
    finally:
        conn.close()


@ unidades_bp.route('/unidades/guardar', methods=['POST'])
def guardar():
    d = request.form
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        # Sin id, vacío o 0: es un alta
        try:
            u_id = int((d.get('id_unidad') or '0').strip() or 0)
        except ValueError:
            raise DatoInvalido('Unidad inválida.') from None
        datos = _validar(d)

        with conn.cursor() as cursor:
            anterior = None
            if u_id:
                cursor.execute("""SELECT codigo, tipo_magnitud, activo FROM unidades_medida
                                  WHERE id_unidad = %s AND (%s IS NULL OR tenant_id = %s)""",
                               (u_id, tenant_id, tenant_id))
                anterior = cursor.fetchone()
                if not anterior:
                    raise DatoInvalido('La unidad que se intenta modificar no existe.')
            # Una unidad nueva nace activa; al editar sin el dato se conserva el estado
            activo = _activo(d.get('activo'), actual=anterior['activo'] if anterior else True)
            if _codigo_en_uso(cursor, datos['codigo'], tenant_id, excluir_id=u_id):
                raise DatoInvalido(f'Ya existe una unidad con el código "{datos["codigo"]}".')
            _resolver_base(cursor, datos, tenant_id, u_id)

            if anterior:
                # Unidades que se calculan a partir de esta
                cursor.execute("""SELECT COUNT(*) AS n FROM unidades_medida
                                  WHERE unidad_base_referencia = %s AND id_unidad <> %s
                                    AND (%s IS NULL OR tenant_id = %s)""",
                               (anterior['codigo'], u_id, tenant_id, tenant_id))
                derivadas = cursor.fetchone()['n']
                if derivadas and _magnitud(anterior['tipo_magnitud']) != datos['tipo_magnitud']:
                    raise DatoInvalido(f'No se puede cambiar la magnitud: {derivadas} unidad(es) usan esta como '
                                       'unidad base.')
                if _magnitud(anterior['tipo_magnitud']) == 'VOLUMEN' and datos['tipo_magnitud'] != 'VOLUMEN':
                    # El volumen de un material solo se puede expresar en una unidad de volumen
                    cursor.execute("SELECT COUNT(*) AS n FROM materiales WHERE volumen_unidad_id = %s", (u_id,))
                    con_volumen = cursor.fetchone()['n']
                    if con_volumen:
                        raise DatoInvalido('No se puede cambiar la magnitud: '
                                           f'{_plural(con_volumen, "material expresa", "materiales expresan")} '
                                           'su volumen en esta unidad.')
                if derivadas and anterior['codigo'] != datos['codigo']:
                    # La base se guarda por código: si cambia, se actualiza en las que la usan
                    cursor.execute("""UPDATE unidades_medida SET unidad_base_referencia = %s
                                      WHERE unidad_base_referencia = %s AND (%s IS NULL OR tenant_id = %s)""",
                                   (datos['codigo'], anterior['codigo'], tenant_id, tenant_id))

            valores = (datos['codigo'], datos['nombre'], datos['simbolo'], datos['tipo_magnitud'],
                       datos['conversion_a_base'], datos['unidad_base_referencia'],
                       datos['decimales_permitidos'], activo)
            if u_id:
                cursor.execute("""UPDATE unidades_medida SET
                         codigo=%s, nombre=%s, simbolo=%s, tipo_magnitud=%s,
                         conversion_a_base=%s, unidad_base_referencia=%s,
                         decimales_permitidos=%s, activo=%s
                         WHERE id_unidad=%s""", (*valores, u_id))
            else:
                cursor.execute("""INSERT INTO unidades_medida
                         (codigo, nombre, simbolo, tipo_magnitud, conversion_a_base,
                          unidad_base_referencia, decimales_permitidos, activo, tenant_id)
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""", (*valores, tenant_id))

            conn.commit()
            flash("Unidad guardada correctamente", "success")
    except DatoInvalido as e:
        conn.rollback()
        flash(str(e), "danger")
    except Exception as e:
        conn.rollback()
        if is_duplicate_key_error(e):
            flash("Ya existe una unidad con ese código.", "danger")
        else:
            flash(f"Error al guardar la unidad: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('unidades.unidades'))


@unidades_bp.route('/unidades/eliminar/<int:id>', methods=['POST'])
def eliminar(id):
    """Inactiva la unidad (no se borra: los materiales que la usan la conservan)."""
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT codigo, activo FROM unidades_medida WHERE id_unidad = %s AND (%s IS NULL OR tenant_id = %s)",
                           (id, tenant_id, tenant_id))
            unidad = cursor.fetchone()
            if not unidad:
                flash("Unidad no encontrada.", "warning")
                return redirect(url_for('unidades.unidades'))
            if not unidad['activo']:
                flash(f'La unidad "{unidad["codigo"]}" ya estaba inactiva.', "info")
                return redirect(url_for('unidades.unidades'))

            cursor.execute("UPDATE unidades_medida SET activo = %s WHERE id_unidad = %s", (False, id))
            # Materiales que la usan, como unidad de medida o como unidad del volumen
            cursor.execute("SELECT COUNT(*) AS n FROM materiales WHERE unidad_medida_id = %s OR volumen_unidad_id = %s",
                           (id, id))
            en_uso = cursor.fetchone()['n']
            # Unidades que se calculan a partir de esta
            cursor.execute("""SELECT COUNT(*) AS n FROM unidades_medida
                              WHERE unidad_base_referencia = %s AND id_unidad <> %s
                                AND (%s IS NULL OR tenant_id = %s)""", (unidad['codigo'], id, tenant_id, tenant_id))
            derivadas = cursor.fetchone()['n']
            conn.commit()

            mensaje = f'La unidad "{unidad["codigo"]}" quedó inactiva: ya no se ofrece para materiales nuevos.'
            if en_uso:
                mensaje += (f' La usa{"n" if en_uso != 1 else ""} {en_uso} material{"es" if en_uso != 1 else ""}, '
                            f'que la conserva{"n" if en_uso != 1 else ""}.')
            if derivadas:
                mensaje += (f' Es la unidad base de {_plural(derivadas, "unidad, que se sigue", "unidades, que se siguen")} '
                            'calculando sobre ella.')
            flash(mensaje + ' Se puede reactivar desde su edición.', "warning" if en_uso or derivadas else "success")
    except Exception as e:
        conn.rollback()
        flash(f"No se pudo inactivar la unidad: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('unidades.unidades'))


# ── Batch ─────────────────────────────────────────────────────────────────────
_CAMPOS = ['codigo', 'nombre', 'simbolo', 'tipo_magnitud', 'conversion_a_base', 'unidad_base_referencia', 'decimales_permitidos', 'activo']
# La unidad de ejemplo es una unidad base: no tiene unidad base y su conversión es 1
_EJEMPLO = ['UND', 'Unidad', 'U', 'CANTIDAD', '1', '', '0', '1']


@ unidades_bp.route('/unidades/importar', methods=['POST'])
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
        # Una unidad puede venir antes que su unidad base (la exportación ordenaba por nombre): esas filas
        # se dejan para otra vuelta, y se repite mientras alguna vuelta logre cargar algo.
        pendientes, ultima_vuelta = list(enumerate(rows, 1)), False
        while pendientes:
            postergadas, antes = [], insertados
            for i, row in pendientes:
                codigo = str(row.get('codigo', '') or '').strip()
                nombre = str(row.get('nombre', '') or '').strip()
                if not codigo or not nombre:
                    errores.append({'fila': i, 'codigo': codigo or '(vacío)', 'razon': 'Código y Nombre son obligatorios'})
                    continue
                try:
                    insertados += _importar_fila(conn, row, codigo, tenant_id, omitidos)
                except BaseInexistente as e:
                    if ultima_vuelta:
                        errores.append({'fila': i, 'codigo': codigo, 'razon': str(e)})
                    else:
                        postergadas.append((i, row))
                except Exception as e:
                    errores.append({'fila': i, 'codigo': codigo, 'razon': str(e)})
            # Si la vuelta no cargó nada, a las que quedan les falta la base: la próxima las informa
            ultima_vuelta = insertados == antes
            pendientes = postergadas
        errores.sort(key=lambda e: e['fila'])
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()
    return jsonify({'insertados': insertados, 'omitidos': omitidos, 'errores': errores})


def _importar_fila(conn, row, codigo, tenant_id, omitidos):
    """Carga una fila del archivo. Devuelve 1 si la insertó y 0 si la omitió por código repetido."""
    datos = _validar(row)
    with conn.cursor() as cursor:
        if _codigo_en_uso(cursor, codigo, tenant_id):
            omitidos.append(codigo)
            return 0
        _resolver_base(cursor, datos, tenant_id)
        activo = str(row.get('activo', '') or '1').strip().lower() in ('1', 'true', 'si', 'sí', 'yes')
        cursor.execute("""
            INSERT INTO unidades_medida
                (codigo, nombre, simbolo, tipo_magnitud, conversion_a_base,
                 unidad_base_referencia, decimales_permitidos, activo, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (datos['codigo'], datos['nombre'], datos['simbolo'], datos['tipo_magnitud'],
              datos['conversion_a_base'], datos['unidad_base_referencia'],
              datos['decimales_permitidos'], activo, tenant_id))
    return 1


@ unidades_bp.route('/unidades/exportar/<formato>')
def exportar(formato):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT codigo, nombre, simbolo, tipo_magnitud, conversion_a_base, 
                       unidad_base_referencia, decimales_permitidos, activo
                FROM unidades_medida
                WHERE (%s IS NULL OR tenant_id = %s)
                ORDER BY CASE WHEN unidad_base_referencia IS NULL THEN 0 ELSE 1 END, nombre
            """, (tenant_id, tenant_id))
            rows = cursor.fetchall()
    finally:
        conn.close()

    if formato == 'csv':
        return export_csv(rows, _CAMPOS, 'unidades_medida.csv')
    elif formato == 'json':
        return export_json(rows, _CAMPOS, 'unidades_medida.json')
    elif formato == 'xlsx':
        return export_xlsx(rows, _CAMPOS, 'unidades_medida.xlsx')
    return 'Formato no válido', 400


@ unidades_bp.route('/unidades/plantilla/<formato>')
def plantilla(formato):
    if formato == 'csv':
        return plantilla_csv(_CAMPOS, _EJEMPLO, 'plantilla_unidades.csv')
    elif formato == 'json':
        return plantilla_json(_CAMPOS, _EJEMPLO, 'plantilla_unidades.json')
    elif formato == 'xlsx':
        return plantilla_xlsx(_CAMPOS, _EJEMPLO, 'plantilla_unidades.xlsx')
    return 'Formato no válido', 400
