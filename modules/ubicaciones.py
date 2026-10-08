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
from modules.sql_dialect import is_duplicate_key_error, quote

ubicaciones_bp = Blueprint('ubicaciones', __name__)

# Largo máximo de cada texto (el de su columna)
LARGOS = {'codigo': 50, 'descipcion': 200, 'coordenada': 20}
ENTERO_MAX = 2147483647   # mayor valor de las columnas int (capacidad, orden de picking)
_COORDENADAS = ('coordenadaA', 'coordenadaB', 'coordenadaC', 'coordenadaD')
_SI = ('1', 'on', 'true', 'si', 'sí', 'yes')


def _texto(datos, campo, rotulo, maximo, obligatorio=False):
    valor = str(datos.get(campo) or '').strip()
    if obligatorio and not valor:
        raise DatoInvalido(f'{rotulo}: es obligatorio.')
    if len(valor) > maximo:
        raise DatoInvalido(f'{rotulo}: admite hasta {maximo} caracteres.')
    return valor or None


def _entero(valor, rotulo):
    """Entero no negativo de un formulario o de un archivo (vacío = 0; una planilla puede traer "10.0")."""
    texto = str(valor if valor is not None else '').strip()
    if not texto:
        return 0
    try:
        numero = float(texto)
        if numero != int(numero):
            raise ValueError
    except (ValueError, OverflowError):
        raise DatoInvalido(f'{rotulo}: "{texto}" no es un número entero.') from None
    if numero < 0:
        raise DatoInvalido(f'{rotulo}: no puede ser negativo.')
    if numero > ENTERO_MAX:
        raise DatoInvalido(f'{rotulo}: el valor es demasiado grande.')
    return int(numero)


def _validar(datos):
    """Datos propios de una ubicación (formulario o fila importada), verificados."""
    validos = {
        'codigo': _texto(datos, 'codigo', 'Código', LARGOS['codigo'], obligatorio=True),
        'descipcion': _texto(datos, 'descipcion', 'Descripción', LARGOS['descipcion']),
        'orden_picking': _entero(datos.get('orden_picking'), 'Orden de picking'),
        'capacidad_maxima': _entero(datos.get('capacidad_maxima'), 'Capacidad máxima'),
    }
    for eje, campo in zip('ABCD', _COORDENADAS, strict=True):
        validos[campo] = _texto(datos, campo, f'Coordenada {eje}', LARGOS['coordenada'])
    return validos


def _activo(valor, por_defecto=True):
    """Estado: True = Activa. Acepta 1/0 (lista Estado, archivos); sin dato, el valor por defecto."""
    valor = str(valor if valor is not None else '').strip().lower()
    if not valor:
        return bool(por_defecto)
    return valor in _SI


def _tipo(cursor, valor, tenant_id, por_nombre=False):
    """Id del tipo de ubicación (None si no se indica). En un archivo se acepta su nombre o su id."""
    valor = str(valor if valor is not None else '').strip()
    if not valor:
        return None
    filtro = "(%s IS NULL OR tenant_id = %s)"
    if por_nombre:
        cursor.execute(f"SELECT id FROM tipoubicacion WHERE {quote('descripcion')} = %s AND {filtro}",
                       (valor, tenant_id, tenant_id))
        filas = cursor.fetchall()
        if len(filas) > 1:
            raise DatoInvalido(f'Tipo de ubicación: hay más de un tipo llamado "{valor}"; indicar su ID.')
        if filas:
            return filas[0]['id']
    numero = valor[:-2] if valor.endswith('.0') else valor
    if numero.isdigit():
        cursor.execute(f"SELECT id FROM tipoubicacion WHERE id = %s AND {filtro}", (int(numero), tenant_id, tenant_id))
        fila = cursor.fetchone()
        if fila:
            return fila['id']
    raise DatoInvalido(f'Tipo de ubicación: no existe "{valor}".' if por_nombre
                       else 'Tipo de ubicación: el valor elegido no existe.')


def _zona(cursor, valor, tenant_id, por_codigo=False):
    """Id de la zona (None si no se indica). En un archivo se acepta su código o su id."""
    valor = str(valor if valor is not None else '').strip()
    if not valor:
        return None
    filtro = "(%s IS NULL OR tenant_id = %s)"
    if por_codigo:
        cursor.execute(f"SELECT id FROM zonas WHERE codigo = %s AND {filtro}", (valor, tenant_id, tenant_id))
        fila = cursor.fetchone()
        if fila:
            return fila['id']
    numero = valor[:-2] if valor.endswith('.0') else valor
    if numero.isdigit():
        cursor.execute(f"SELECT id FROM zonas WHERE id = %s AND {filtro}", (int(numero), tenant_id, tenant_id))
        fila = cursor.fetchone()
        if fila:
            return fila['id']
    raise DatoInvalido(f'Zona: no existe "{valor}".' if por_codigo else 'Zona: el valor elegido no existe.')


def _codigo_en_uso(cursor, codigo, tenant_id, excluir_id=0):
    cursor.execute("""SELECT id FROM ubicaciones
                      WHERE codigo = %s AND id <> %s AND (%s IS NULL OR tenant_id = %s)""",
                   (codigo, excluir_id, tenant_id, tenant_id))
    return cursor.fetchone() is not None


def _impide_inactivar(cursor, id_ubicacion):
    """Motivo por el que la ubicación no se puede inactivar todavía ('' si se puede).

    Una ubicación inactiva deja de ofrecerse en recepciones, OMC, pedidos y la app
    móvil: si tuviera stock u operaciones abiertas, quedarían sin poder terminarse.
    """
    cursor.execute("""SELECT COUNT(*) AS n FROM stockcontable
                      WHERE Ubicacion = %s AND (StockTotal <> 0 OR StockEntrando <> 0 OR StockSaliendo <> 0)""",
                   (id_ubicacion,))
    posiciones = cursor.fetchone()['n']
    cursor.execute("""SELECT COUNT(*) AS n FROM recepciones_cabecera
                      WHERE (id_ubicacion_recep = %s OR id_ubicacion_destino = %s)
                        AND estado IN ('Abierta', 'Cerrada')""", (id_ubicacion, id_ubicacion))
    recepciones = cursor.fetchone()['n']
    cursor.execute("""SELECT COUNT(*) AS n FROM omc
                      WHERE (id_ubicacion_origen = %s OR id_ubicacion_destino = %s) AND estado = 'Pendiente'""",
                   (id_ubicacion, id_ubicacion))
    omc = cursor.fetchone()['n']
    motivos = []
    if posiciones:
        motivos.append('tiene stock' if posiciones == 1 else f'tiene stock en {posiciones} posiciones')
    if recepciones:
        motivos.append('tiene 1 recepción sin confirmar' if recepciones == 1
                       else f'tiene {recepciones} recepciones sin confirmar')
    if omc:
        motivos.append('tiene 1 OMC pendiente' if omc == 1 else f'tiene {omc} OMC pendientes')
    return ' y '.join(motivos)


def _aviso_muelle(cursor, id_ubicacion):
    """Aviso si la ubicación es el muelle de salida de algún transporte ('' si no lo es)."""
    cursor.execute("SELECT COUNT(*) AS n FROM transportes WHERE id_muelle_salida = %s", (id_ubicacion,))
    n = cursor.fetchone()['n']
    if not n:
        return ''
    return (' Es el muelle de salida de 1 transporte, que la conserva; conviene asignarle otro.' if n == 1 else
            f' Es el muelle de salida de {n} transportes, que la conservan; conviene asignarles otro.')


@ubicaciones_bp.route('/ubicaciones')
def listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT u.*, t.{quote('descripcion')} AS tipo_nombre,
                       z.codigo AS zona_codigo, z.nombre AS zona_nombre
                FROM ubicaciones u
                LEFT JOIN tipoubicacion t ON u.tipoubicacion = t.id
                LEFT JOIN zonas z ON u.id_zona = z.id
                WHERE (%s IS NULL OR u.tenant_id = %s)
                ORDER BY z.codigo, u.orden_picking, u.codigo
            """, (tenant_id, tenant_id))
            ubicaciones = cursor.fetchall()

            cursor.execute(f"SELECT * FROM tipoubicacion WHERE (%s IS NULL OR tenant_id = %s) ORDER BY {quote('descripcion')}", (tenant_id, tenant_id))
            tipos = cursor.fetchall()

            # Con las inactivas: la ficha las oculta, salvo la que la ubicación ya tiene
            cursor.execute("SELECT id, codigo, nombre, activo FROM zonas WHERE (%s IS NULL OR tenant_id = %s) ORDER BY codigo", (tenant_id, tenant_id))
            zonas = cursor.fetchall()

        return render_template('ubicaciones.html',
                               ubicaciones=ubicaciones,
                               tipos=tipos,
                               zonas=zonas,
                               largos=LARGOS)
    finally:
        conn.close()


@ubicaciones_bp.route('/ubicaciones/guardar', methods=['POST'])
def guardar():
    d = request.form
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        # Sin id o vacío: es un alta
        try:
            u_id = int((d.get('id') or '0').strip() or 0)
        except ValueError:
            raise DatoInvalido('Ubicación inválida.') from None
        datos = _validar(d)

        with conn.cursor() as cursor:
            anterior = None
            if u_id:
                cursor.execute("SELECT activo FROM ubicaciones WHERE id = %s AND (%s IS NULL OR tenant_id = %s)",
                               (u_id, tenant_id, tenant_id))
                anterior = cursor.fetchone()
                if not anterior:
                    raise DatoInvalido('La ubicación que se intenta modificar no existe.')
            if _codigo_en_uso(cursor, datos['codigo'], tenant_id, excluir_id=u_id):
                raise DatoInvalido(f'Ya existe una ubicación con el código "{datos["codigo"]}".')
            # Una ubicación nueva nace activa; al editar sin el dato se conserva el estado
            activo = _activo(d.get('activo'), por_defecto=bool(anterior['activo']) if anterior else True)
            aviso = ''
            if anterior and anterior['activo'] and not activo:
                motivo = _impide_inactivar(cursor, u_id)
                if motivo:
                    raise DatoInvalido(f'No se puede inactivar la ubicación: {motivo}.')
                aviso = _aviso_muelle(cursor, u_id)

            valores = (datos['codigo'], datos['descipcion'], _tipo(cursor, d.get('tipoubicacion'), tenant_id),
                       _zona(cursor, d.get('id_zona'), tenant_id), datos['orden_picking'],
                       *(datos[c] for c in _COORDENADAS), datos['capacidad_maxima'],
                       1 if d.get('disponible_entrada') else 0, 1 if d.get('disponible_salida') else 0, activo)
            if u_id:
                cursor.execute("""UPDATE ubicaciones SET
                         codigo=%s, descipcion=%s, tipoubicacion=%s, id_zona=%s, orden_picking=%s,
                         coordenadaA=%s, coordenadaB=%s, coordenadaC=%s, coordenadaD=%s,
                         capacidad_maxima=%s, disponible_entrada=%s, disponible_salida=%s, activo=%s
                         WHERE id=%s""", (*valores, u_id))
            else:
                cursor.execute("""INSERT INTO ubicaciones
                         (codigo, descipcion, tipoubicacion, id_zona, orden_picking,
                          coordenadaA, coordenadaB, coordenadaC, coordenadaD,
                          capacidad_maxima, disponible_entrada, disponible_salida, activo, tenant_id)
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", (*valores, tenant_id))

            conn.commit()
            flash("Ubicación guardada", "success")
            if aviso:
                flash('La ubicación quedó inactiva.' + aviso, "warning")
    except DatoInvalido as e:
        conn.rollback()
        flash(str(e), "danger")
    except Exception as e:
        conn.rollback()
        if is_duplicate_key_error(e):
            flash("Ya existe una ubicación con ese código.", "danger")
        else:
            flash(f"Error al guardar la ubicación: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('ubicaciones.listar'))


@ubicaciones_bp.route('/ubicaciones/eliminar/<int:id>', methods=['POST'])
def eliminar(id):
    """Inactiva la ubicación (no se borra: los movimientos que la nombran la conservan)."""
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT codigo, activo FROM ubicaciones WHERE id = %s AND (%s IS NULL OR tenant_id = %s)",
                           (id, tenant_id, tenant_id))
            ubicacion = cursor.fetchone()
            if not ubicacion:
                flash("Ubicación no encontrada.", "warning")
                return redirect(url_for('ubicaciones.listar'))
            if not ubicacion['activo']:
                flash(f'La ubicación "{ubicacion["codigo"]}" ya estaba inactiva.', "info")
                return redirect(url_for('ubicaciones.listar'))
            motivo = _impide_inactivar(cursor, id)
            if motivo:
                flash(f'No se puede inactivar la ubicación "{ubicacion["codigo"]}": {motivo}.', "danger")
                return redirect(url_for('ubicaciones.listar'))

            cursor.execute("UPDATE ubicaciones SET activo = %s WHERE id = %s", (False, id))
            aviso = _aviso_muelle(cursor, id)
            conn.commit()
            flash(f'La ubicación "{ubicacion["codigo"]}" quedó inactiva: ya no se ofrece en recepciones, OMC ni pedidos.'
                  + aviso + ' Se puede reactivar desde su edición.', "warning" if aviso else "success")
    except Exception as e:
        conn.rollback()
        flash(f"No se pudo inactivar la ubicación: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('ubicaciones.listar'))


# ── Batch: definición de columnas ─────────────────────────────────────────────
# tipoubicacion lleva el nombre del tipo e id_zona el código de la zona: es lo que
# lee la importación y lo que vale en cualquier servidor (los ID internos cambian).
_CAMPOS_EXPORT = ['codigo', 'descipcion', 'tipo_nombre', 'tipoubicacion',
                  'zona_codigo', 'id_zona', 'orden_picking',
                  'coordenadaA', 'coordenadaB', 'coordenadaC', 'coordenadaD',
                  'capacidad_maxima', 'disponible_entrada', 'disponible_salida', 'activo']
_CAMPOS_IMPORT = ['codigo', 'descipcion', 'tipoubicacion', 'id_zona',
                  'orden_picking', 'coordenadaA', 'coordenadaB', 'coordenadaC', 'coordenadaD',
                  'capacidad_maxima', 'disponible_entrada', 'disponible_salida', 'activo']
# El tipo y la zona del ejemplo van vacíos: dependen de los tipos y zonas de cada instalación
_EJEMPLO_IMPORT = ['UB-001', 'Pasillo A - Estante 1', '', '',
                   '10', 'A1', 'B2', 'C3', '', '100', '1', '1', '1']


def _si_no(valor, por_defecto=True):
    valor = str(valor if valor is not None else '').strip().lower()
    return (1 if por_defecto else 0) if not valor else (1 if valor in _SI else 0)


@ubicaciones_bp.route('/ubicaciones/importar', methods=['POST'])
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
            if not codigo:
                errores.append({'fila': i, 'codigo': '(vacío)', 'razon': 'Código es obligatorio'})
                continue
            try:
                datos = _validar(row)
                with conn.cursor() as cursor:
                    if _codigo_en_uso(cursor, codigo, tenant_id):
                        omitidos.append(codigo)
                        continue
                    cursor.execute("""
                        INSERT INTO ubicaciones
                            (codigo, descipcion, tipoubicacion, id_zona, orden_picking,
                             coordenadaA, coordenadaB, coordenadaC, coordenadaD,
                             capacidad_maxima, disponible_entrada, disponible_salida, activo, tenant_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        datos['codigo'], datos['descipcion'],
                        _tipo(cursor, row.get('tipoubicacion'), tenant_id, por_nombre=True),
                        _zona(cursor, row.get('id_zona'), tenant_id, por_codigo=True),
                        datos['orden_picking'], *(datos[c] for c in _COORDENADAS), datos['capacidad_maxima'],
                        _si_no(row.get('disponible_entrada')), _si_no(row.get('disponible_salida')),
                        _activo(row.get('activo')), tenant_id,
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


@ubicaciones_bp.route('/ubicaciones/exportar/<formato>')
def exportar(formato):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT u.codigo, u.descipcion, t.{quote('descripcion')} AS tipo_nombre, u.tipoubicacion,
                       z.codigo AS zona_codigo, u.id_zona, u.orden_picking,
                       u.coordenadaA, u.coordenadaB, u.coordenadaC, u.coordenadaD,
                       u.capacidad_maxima, u.disponible_entrada, u.disponible_salida, u.activo
                FROM ubicaciones u
                LEFT JOIN tipoubicacion t ON u.tipoubicacion = t.id
                LEFT JOIN zonas z ON u.id_zona = z.id
                WHERE (%s IS NULL OR u.tenant_id = %s)
                ORDER BY z.codigo, u.orden_picking, u.codigo
            """, (tenant_id, tenant_id))
            rows = [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()
    for r in rows:
        r['tipoubicacion'] = r['tipo_nombre'] or r['tipoubicacion']
        r['id_zona'] = r['zona_codigo'] or r['id_zona']

    if formato == 'csv':
        return export_csv(rows, _CAMPOS_EXPORT, 'ubicaciones.csv')
    elif formato == 'json':
        return export_json(rows, _CAMPOS_EXPORT, 'ubicaciones.json')
    elif formato == 'xlsx':
        return export_xlsx(rows, _CAMPOS_EXPORT, 'ubicaciones.xlsx')
    return 'Formato no válido', 400


@ubicaciones_bp.route('/ubicaciones/plantilla/<formato>')
def plantilla(formato):
    if formato == 'csv':
        return plantilla_csv(_CAMPOS_IMPORT, _EJEMPLO_IMPORT, 'plantilla_ubicaciones.csv')
    elif formato == 'json':
        return plantilla_json(_CAMPOS_IMPORT, _EJEMPLO_IMPORT, 'plantilla_ubicaciones.json')
    elif formato == 'xlsx':
        return plantilla_xlsx(_CAMPOS_IMPORT, _EJEMPLO_IMPORT, 'plantilla_ubicaciones.xlsx')
    return 'Formato no válido', 400
