import math
from collections import OrderedDict
from datetime import datetime

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from modules.auditoria import registrar_movimiento
from modules.batch_utils import (
    DatoInvalido,
    parse_file,
    plantilla_csv,
    plantilla_json,
    plantilla_xlsx,
)
from modules.context import get_tenant_filter
from modules.db_config import _get_admin_connection, get_db_connection
from modules.sql_dialect import (
    cast_as_int,
    execute_insert,
    is_duplicate_key_error,
    limit_sql,
    quote,
    substring_index,
    upsert_incremental_sql,
)
from modules.sql_dialect import year as year_func

recepciones_bp = Blueprint('recepciones', __name__)

TIPOS_STOCK = ('Libre Venta', 'Calidad', 'Bloqueado', 'Mal Estado')
LOTE_MAX = 100                    # largo de recepciones_detalle.lote
LOTE_UNICO = 'UNICO'              # lote de los materiales que no llevan trazabilidad
CANTIDAD_MAX = 99999999999.9999   # mayor valor de las columnas decimal(15,4)


def _id(valor):
    """Id entero de un formulario o JSON, o 0 si no es un id."""
    try:
        return int(str(valor if valor is not None else '').strip() or 0)
    except ValueError:
        return 0


def _proveedor(cursor, valor, tenant_id):
    """Id de un proveedor activo de la empresa. DatoInvalido si falta, no existe o está inactivo."""
    id_proveedor = _id(valor)
    if not id_proveedor:
        raise DatoInvalido('Debe seleccionar un proveedor.')
    cursor.execute("SELECT razonsocial, activo FROM proveedores WHERE id = %s AND (%s IS NULL OR tenant_id = %s)",
                   (id_proveedor, tenant_id, tenant_id))
    fila = cursor.fetchone()
    if not fila:
        raise DatoInvalido('El proveedor elegido no existe.')
    if not fila['activo']:
        raise DatoInvalido(f'El proveedor "{fila["razonsocial"]}" está inactivo.')
    return id_proveedor


def _ubicacion(cursor, valor, tenant_id, rotulo, de_recepcion=False):
    """Id de una ubicación activa de la empresa; con `de_recepcion`, de un tipo de recepción (operación 'R')."""
    id_ubicacion = _id(valor)
    if not id_ubicacion:
        raise DatoInvalido(f'Debe seleccionar la {rotulo}.')
    cursor.execute("""SELECT u.codigo, u.activo, t.operacion FROM ubicaciones u
                      LEFT JOIN tipoubicacion t ON u.tipoubicacion = t.id
                      WHERE u.id = %s AND (%s IS NULL OR u.tenant_id = %s)""", (id_ubicacion, tenant_id, tenant_id))
    fila = cursor.fetchone()
    if not fila:
        raise DatoInvalido(f'La {rotulo} elegida no existe.')
    if not fila['activo']:
        raise DatoInvalido(f'La ubicación "{fila["codigo"]}" está inactiva.')
    if de_recepcion and (fila['operacion'] or '').strip().upper() != 'R':
        raise DatoInvalido(f'La ubicación "{fila["codigo"]}" no es de recepción: su tipo tiene que tener esa operación.')
    return id_ubicacion


def _destino(cursor, valor, tenant_id, id_ubicacion_recep):
    """Ubicación destino: activa, de la empresa y distinta de la de recepción."""
    id_destino = _ubicacion(cursor, valor, tenant_id, 'ubicación destino')
    if id_destino == id_ubicacion_recep:
        # El traslado se registra como salida del origen y entrada al destino: no pueden ser la misma
        raise DatoInvalido('La ubicación destino tiene que ser distinta de la ubicación de recepción.')
    return id_destino


def _cantidad(valor, rotulo):
    """Cantidad de un renglón (vacío = 0): un número, no negativo y que entre en la columna."""
    try:
        n = float(str(valor if valor is not None else '').strip().replace(',', '.') or 0)
    except ValueError:
        n = math.nan
    if not math.isfinite(n):
        raise DatoInvalido(f'{rotulo}: "{valor}" no es un número válido.')
    if n < 0:
        raise DatoInvalido(f'{rotulo}: no puede ser negativa.')
    if n > CANTIDAD_MAX:
        raise DatoInvalido(f'{rotulo}: el valor es demasiado grande.')
    return n


def _renglon(datos, cantidad_recibida='cantidad_recibida'):
    """Lote, vencimiento, cantidades y tipo de stock de un renglón, verificados."""
    lote = str(datos.get('lote') or '').strip() or LOTE_UNICO
    if len(lote) > LOTE_MAX:
        raise DatoInvalido(f'Lote: admite hasta {LOTE_MAX} caracteres.')
    vencimiento = str(datos.get('fecha_vencimiento') or '').strip()[:10] or None
    if vencimiento:
        try:
            datetime.strptime(vencimiento, '%Y-%m-%d')
        except ValueError:
            raise DatoInvalido(f'Fecha de vencimiento: "{datos.get("fecha_vencimiento")}" no es una fecha válida '
                               '(formato AAAA-MM-DD).') from None
    tipo_stock = str(datos.get('tipo_stock') or '').strip() or TIPOS_STOCK[0]
    if tipo_stock not in TIPOS_STOCK:
        raise DatoInvalido(f'Tipo de stock: "{tipo_stock}" no es válido. Usar: {", ".join(TIPOS_STOCK)}.')
    return {
        'lote': lote,
        'fecha_vencimiento': vencimiento,
        'cantidad_esperada': _cantidad(datos.get('cantidad_esperada'), 'Cantidad esperada'),
        'cantidad_recibida': _cantidad(datos.get(cantidad_recibida), 'Cantidad recibida') if cantidad_recibida else 0.0,
        'tipo_stock': tipo_stock,
    }


def _material_del_proveedor(cursor, id_material, id_proveedor, tenant_id, lote):
    """Verifica que el material se pueda recibir: activo, de la empresa y asignado al proveedor.

    Un material con trazabilidad por lote o serie tiene que traer su lote.
    """
    cursor.execute("""SELECT m.codigo, m.activo, m.trazabilidad,
                             (SELECT COUNT(*) FROM material_proveedor mp
                              WHERE mp.id_material = m.id AND mp.id_proveedor = %s) AS asignado
                      FROM materiales m WHERE m.id = %s AND (%s IS NULL OR m.tenant_id = %s)""",
                   (id_proveedor, id_material, tenant_id, tenant_id))
    material = cursor.fetchone()
    if not material:
        raise DatoInvalido('El material elegido no existe.')
    if not material['activo']:
        raise DatoInvalido(f'El material "{material["codigo"]}" está inactivo.')
    if not material['asignado']:
        raise DatoInvalido(f'El material "{material["codigo"]}" no está asignado al proveedor de la recepción.')
    trazabilidad = (material['trazabilidad'] or 'ninguna').lower()
    if trazabilidad in ('lote', 'serie') and lote.upper() == LOTE_UNICO:
        raise DatoInvalido(f'El material "{material["codigo"]}" lleva trazabilidad por {trazabilidad}: '
                           f'hay que indicar {"el lote" if trazabilidad == "lote" else "la serie"}.')
    return material


def _numero_siguiente(cursor, tenant_id, anio):
    expr = cast_as_int(substring_index("numero", "-", -1))
    cursor.execute(
        f"SELECT MAX({expr}) AS max_seq "
        f"FROM recepciones_cabecera WHERE {year_func('fecha_recepcion')} = %s AND (%s IS NULL OR tenant_id = %s)",
        (anio, tenant_id, tenant_id)
    )
    return f"REC-{anio}-{(cursor.fetchone()['max_seq'] or 0) + 1:05d}"


# ============================================================================
# LISTADO
# ============================================================================
@recepciones_bp.route('/recepciones')
def listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT r.*, p.razonsocial AS proveedor_nombre, p.codigo AS proveedor_codigo,
                       ur.codigo AS ubicacion_recep_codigo,
                       ud.codigo AS ubicacion_dest_codigo,
                       (SELECT COUNT(*) FROM recepciones_detalle d
                       WHERE d.id_recepcion = r.id_recepcion) AS total_items,
                       (SELECT COALESCE(SUM(d.cantidad_recibida), 0) FROM recepciones_detalle d
                       WHERE d.id_recepcion = r.id_recepcion) AS total_unidades
                FROM recepciones_cabecera r
                JOIN proveedores p ON r.id_proveedor = p.id
                JOIN ubicaciones ur ON r.id_ubicacion_recep = ur.id
                LEFT JOIN ubicaciones ud ON r.id_ubicacion_destino = ud.id
                WHERE (%s IS NULL OR r.tenant_id = %s)
                ORDER BY r.id_recepcion DESC
            """, (tenant_id, tenant_id))
            recepciones = cursor.fetchall()

        conn_admin = _get_admin_connection()
        try:
            with conn_admin.cursor() as cursor_admin:
                cursor_admin.execute("SELECT dias_filtro_fechas FROM tenants WHERE id = %s", (tenant_id,))
                param = cursor_admin.fetchone()
                dias_filtro = param['dias_filtro_fechas'] if param else 30
        finally:
            conn_admin.close()

        return render_template('recepciones.html', recepciones=recepciones, dias_filtro=dias_filtro)
    finally:
        conn.close()


# ============================================================================
# NUEVA RECEPCIÓN — formulario de cabecera
# ============================================================================
@recepciones_bp.route('/recepciones/nueva')
def nueva():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, codigo, razonsocial FROM proveedores WHERE activo = 1 AND (%s IS NULL OR proveedores.tenant_id = %s) ORDER BY razonsocial",
                (tenant_id, tenant_id)
            )
            proveedores = cursor.fetchall()

            cursor.execute(f"""
                SELECT u.id, u.codigo, u.descipcion AS nombre, t.{quote('descripcion')} AS tipo
                FROM ubicaciones u
                JOIN tipoubicacion t ON u.tipoubicacion = t.id
                WHERE t.operacion = 'R' AND u.activo = 1 AND (%s IS NULL OR u.tenant_id = %s)
                ORDER BY u.codigo
            """, (tenant_id, tenant_id))
            ubicaciones_recep = cursor.fetchall()

        ultima_ubicacion = session.get('ultima_ubicacion_recepcion')

        return render_template('recepciones_nueva.html',
                               proveedores=proveedores,
                               ubicaciones_recep=ubicaciones_recep,
                               ubicacion_default=ultima_ubicacion,
                               hoy=datetime.now().strftime('%Y-%m-%d'))
    finally:
        conn.close()


# ============================================================================
# GUARDAR CABECERA
# ============================================================================
@recepciones_bp.route('/recepciones/guardar', methods=['POST'])
def guardar():
    d = request.form
    tenant_id = get_tenant_filter()

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            id_proveedor = _proveedor(cursor, d.get('id_proveedor'), tenant_id)
            id_ubicacion_recep = _ubicacion(cursor, d.get('id_ubicacion_recep'), tenant_id, 'ubicación de recepción',
                                            de_recepcion=True)
            id_destino = (_destino(cursor, d.get('id_ubicacion_destino'), tenant_id, id_ubicacion_recep)
                          if (d.get('id_ubicacion_destino') or '').strip() else None)

            numero = _numero_siguiente(cursor, tenant_id, datetime.now().year)
            usuario = session.get('nombre', 'sistema')

            id_recepcion = execute_insert(cursor, """
                INSERT INTO recepciones_cabecera
                    (numero, id_proveedor, id_ubicacion_recep, id_ubicacion_destino,
                     id_contenedor, observaciones, usuario_creacion, tenant_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                numero,
                id_proveedor,
                id_ubicacion_recep,
                id_destino,
                '',
                (d.get('observaciones') or '').strip() or None,
                usuario,
                tenant_id
            ))

            # El contenedor se genera con el ID definitivo
            contenedor = f"RC{id_recepcion:05d}"
            cursor.execute(
                "UPDATE recepciones_cabecera SET id_contenedor = %s WHERE id_recepcion = %s AND (%s IS NULL OR tenant_id = %s)",
                (contenedor, id_recepcion, tenant_id, tenant_id)
            )
            conn.commit()
            session['ultima_ubicacion_recepcion'] = d.get('id_ubicacion_recep')
            if d.get('redirect_to') == 'listar':
                flash(f"Recepción {numero} creada — contenedor {contenedor}.", "success")
                return redirect(url_for('recepciones.listar'))
            flash(f"Recepción {numero} creada — contenedor {contenedor}. Agregue los materiales.", "success")
            return redirect(url_for('recepciones.ver', id_recepcion=id_recepcion))

    except DatoInvalido as e:
        conn.rollback()
        flash(str(e), "danger")
        return redirect(url_for('recepciones.nueva'))
    except Exception as e:
        conn.rollback()
        if is_duplicate_key_error(e):
            flash("No se pudo crear la recepción: otro usuario tomó el mismo número. Volver a intentar.", "danger")
        else:
            flash(f"Error al crear la recepción: {e!s}", "danger")
        return redirect(url_for('recepciones.nueva'))
    finally:
        conn.close()


# ============================================================================
# VER / GESTIONAR RECEPCIÓN
# ============================================================================
@recepciones_bp.route('/recepciones/ver/<int:id_recepcion>')
def ver(id_recepcion):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT r.*, p.razonsocial AS proveedor_nombre, p.codigo AS proveedor_codigo,
                       ur.codigo AS ubicacion_recep_codigo, ur.descipcion AS ubicacion_recep_nombre,
                       ud.id AS ubicacion_dest_id,
                       ud.codigo AS ubicacion_dest_codigo, ud.descipcion AS ubicacion_dest_nombre
                FROM recepciones_cabecera r
                JOIN proveedores p ON r.id_proveedor = p.id
                JOIN ubicaciones ur ON r.id_ubicacion_recep = ur.id
                LEFT JOIN ubicaciones ud ON r.id_ubicacion_destino = ud.id
                WHERE r.id_recepcion = %s AND (%s IS NULL OR r.tenant_id = %s)
            """, (id_recepcion, tenant_id, tenant_id))
            recepcion = cursor.fetchone()

            if not recepcion:
                flash("Recepción no encontrada.", "danger")
                return redirect(url_for('recepciones.listar'))

            cursor.execute("""
                SELECT d.*, m.codigo AS material_codigo, m.nombre AS material_nombre,
                       mp.codigo_referencia_prov,
                       un.nombre AS unidad_nombre
                FROM recepciones_detalle d
                JOIN materiales m ON d.id_material = m.id
                LEFT JOIN material_proveedor mp
                       ON mp.id_material = m.id AND mp.id_proveedor = %s
                LEFT JOIN unidades_medida un ON m.unidad_medida_id = un.id_unidad
                WHERE d.id_recepcion = %s
                  AND (%s IS NULL OR d.tenant_id = %s)
                ORDER BY d.id_detalle
            """, (recepcion['id_proveedor'], id_recepcion, tenant_id, tenant_id))
            detalle = cursor.fetchall()

            # Materiales disponibles del proveedor para el selector
            cursor.execute("""
                SELECT m.id, m.codigo, m.nombre,
                       COALESCE(m.codigo_barras, '') AS codigo_barras,
                       mp.codigo_referencia_prov,
                       un.nombre AS unidad_nombre
                FROM materiales m
                JOIN material_proveedor mp ON m.id = mp.id_material
                LEFT JOIN unidades_medida un ON m.unidad_medida_id = un.id_unidad
                WHERE mp.id_proveedor = %s AND m.activo = 1 AND (%s IS NULL OR m.tenant_id = %s)
                ORDER BY m.nombre
            """, (recepcion['id_proveedor'], tenant_id, tenant_id))
            materiales = cursor.fetchall()

            # Ubicaciones para el modal de cierre
            cursor.execute(f"""
                SELECT u.id, u.codigo, u.descipcion AS nombre, t.{quote('descripcion')} AS tipo
                FROM ubicaciones u
                JOIN tipoubicacion t ON u.tipoubicacion = t.id
                WHERE u.activo = 1 AND (%s IS NULL OR u.tenant_id = %s)
                ORDER BY u.codigo
            """, (tenant_id, tenant_id))
            ubicaciones_destino = cursor.fetchall()

            # OMC relacionada (si existe)
            cursor.execute(f"""
                SELECT id_omc, numero, estado
                FROM omc
                WHERE id_recepcion = %s AND (%s IS NULL OR tenant_id = %s)
                ORDER BY id_omc DESC {limit_sql(1)}
            """, (id_recepcion, tenant_id, tenant_id))
            omc_relacionada = cursor.fetchone()

        return render_template('recepciones_ver.html',
                               recepcion=recepcion,
                               detalle=detalle,
                               materiales=materiales,
                               ubicaciones_destino=ubicaciones_destino,
                               omc_relacionada=omc_relacionada)
    finally:
        conn.close()


# ============================================================================
# BÚSQUEDA DE MATERIALES (AJAX)
# ============================================================================
@recepciones_bp.route('/recepciones/buscar_materiales/<int:id_proveedor>')
def buscar_materiales(id_proveedor):
    q = request.args.get('q', '').strip()
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            like = f'%{q}%'
            cursor.execute(f"""
                SELECT m.id, m.codigo, m.nombre,
                       COALESCE(m.codigo_barras, '') AS codigo_barras,
                       mp.codigo_referencia_prov,
                       un.nombre AS unidad_nombre
                FROM materiales m
                JOIN material_proveedor mp ON m.id = mp.id_material
                LEFT JOIN unidades_medida un ON m.unidad_medida_id = un.id_unidad
                WHERE mp.id_proveedor = %s AND m.activo = 1 AND (%s IS NULL OR m.tenant_id = %s)
                  AND (m.nombre LIKE %s OR m.codigo LIKE %s
                       OR m.codigo_barras LIKE %s OR mp.codigo_referencia_prov LIKE %s)
                ORDER BY m.nombre
                {limit_sql(20)}
            """, (id_proveedor, tenant_id, tenant_id, like, like, like, like))
            return jsonify(cursor.fetchall())
    finally:
        conn.close()


@recepciones_bp.route('/recepciones/buscar_barcode/<int:id_proveedor>')
def buscar_barcode(id_proveedor):
    """Búsqueda exacta por código de barras (usado por lector)."""
    barcode = request.args.get('barcode', '').strip()
    if not barcode:
        return jsonify({})
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT m.id, m.codigo, m.nombre,
                       COALESCE(m.codigo_barras, '') AS codigo_barras,
                       mp.codigo_referencia_prov,
                       un.nombre AS unidad_nombre
                FROM materiales m
                JOIN material_proveedor mp ON m.id = mp.id_material
                LEFT JOIN unidades_medida un ON m.unidad_medida_id = un.id_unidad
                WHERE mp.id_proveedor = %s AND m.activo = 1 AND (%s IS NULL OR m.tenant_id = %s)
                  AND (m.codigo_barras = %s OR m.codigo = %s
                       OR mp.codigo_referencia_prov = %s)
                {limit_sql(1)}
            """, (id_proveedor, tenant_id, tenant_id, barcode, barcode, barcode))
            mat = cursor.fetchone()
            return jsonify(mat or {})
    finally:
        conn.close()


# ============================================================================
# BÚSQUEDA DE UBICACIONES (AJAX)
# ============================================================================
@recepciones_bp.route('/recepciones/buscar_ubicaciones')
def buscar_ubicaciones():
    q = request.args.get('q', '').strip()
    tipo = request.args.get('tipo', '')  # 'recep' filtra solo tipo Recepcion
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            like = f'%{q}%'
            if tipo == 'recep':
                cursor.execute(f"""
                    SELECT u.id, u.codigo, u.descipcion AS nombre, t.{quote('descripcion')} AS tipo
                    FROM ubicaciones u
                    JOIN tipoubicacion t ON u.tipoubicacion = t.id
                    WHERE t.operacion = 'R' AND u.activo = 1
                      AND (u.codigo LIKE %s OR u.descipcion LIKE %s)
                      AND (%s IS NULL OR u.tenant_id = %s)
                    ORDER BY u.codigo
                    {limit_sql(20)}
                """, (like, like, tenant_id, tenant_id))
            else:
                cursor.execute(f"""
                    SELECT u.id, u.codigo, u.descipcion AS nombre, t.{quote('descripcion')} AS tipo
                    FROM ubicaciones u
                    JOIN tipoubicacion t ON u.tipoubicacion = t.id
                    WHERE (u.codigo LIKE %s OR u.descipcion LIKE %s) AND u.activo = 1
                      AND (%s IS NULL OR u.tenant_id = %s)
                    ORDER BY u.codigo
                    {limit_sql(20)}
                """, (like, like, tenant_id, tenant_id))
            return jsonify(cursor.fetchall())
    finally:
        conn.close()


# ============================================================================
# GUARDAR ÍTEM (AJAX)
# ============================================================================
@recepciones_bp.route('/recepciones/guardar_item', methods=['POST'])
def guardar_item():
    d = request.json or {}
    id_recepcion  = _id(d.get('id_recepcion'))
    id_material   = _id(d.get('id_material'))
    observaciones = (d.get('observaciones') or '').strip() or None
    id_detalle    = _id(d.get('id_detalle'))
    tenant_id = get_tenant_filter()

    conn = get_db_connection()
    try:
        renglon = _renglon(d)
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT estado, id_proveedor FROM recepciones_cabecera WHERE id_recepcion = %s AND (%s IS NULL OR tenant_id = %s)",
                (id_recepcion, tenant_id, tenant_id)
            )
            rec = cursor.fetchone()
            if not rec or rec['estado'].upper() != 'ABIERTA':
                return jsonify({"ok": False, "msg": "La recepción no está Abierta."})

            if id_detalle:
                cursor.execute("SELECT id_material FROM recepciones_detalle WHERE id_detalle = %s AND id_recepcion = %s",
                               (id_detalle, id_recepcion))
                actual = cursor.fetchone()
                if not actual:
                    raise DatoInvalido('El renglón que se intenta modificar no existe.')
                _material_del_proveedor(cursor, actual['id_material'], rec['id_proveedor'], tenant_id, renglon['lote'])
                cursor.execute("""
                    UPDATE recepciones_detalle
                    SET cantidad_esperada=%s, cantidad_recibida=%s, lote=%s,
                        fecha_vencimiento=%s, tipo_stock=%s, observaciones=%s
                    WHERE id_detalle=%s AND id_recepcion=%s
                """, (renglon['cantidad_esperada'], renglon['cantidad_recibida'], renglon['lote'],
                      renglon['fecha_vencimiento'], renglon['tipo_stock'], observaciones, id_detalle, id_recepcion))
            else:
                if not id_material:
                    return jsonify({"ok": False, "msg": "Debe seleccionar un material."})
                material = _material_del_proveedor(cursor, id_material, rec['id_proveedor'], tenant_id, renglon['lote'])
                # La recepción usa un solo contenedor, y el stock admite una fila por material dentro de un
                # contenedor: con dos renglones del mismo material, el segundo lote se fundía con el primero.
                cursor.execute("SELECT COUNT(*) AS n FROM recepciones_detalle WHERE id_recepcion = %s AND id_material = %s",
                               (id_recepcion, id_material))
                if cursor.fetchone()['n']:
                    raise DatoInvalido(f'El material "{material["codigo"]}" ya está cargado en esta recepción. '
                                       'Para recibir otro lote o tipo de stock del mismo material, hacer otra recepción.')
                id_detalle = execute_insert(cursor, """
                    INSERT INTO recepciones_detalle
                        (id_recepcion, id_material, lote, fecha_vencimiento,
                         cantidad_esperada, cantidad_recibida, tipo_stock, observaciones, tenant_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (id_recepcion, id_material, renglon['lote'], renglon['fecha_vencimiento'],
                      renglon['cantidad_esperada'], renglon['cantidad_recibida'], renglon['tipo_stock'],
                      observaciones, tenant_id))

            conn.commit()
            return jsonify({"ok": True, "id_detalle": id_detalle})
    except DatoInvalido as e:
        conn.rollback()
        return jsonify({"ok": False, "msg": str(e)})
    except Exception as e:
        conn.rollback()
        if is_duplicate_key_error(e):
            return jsonify({"ok": False, "msg": "Ese material ya está cargado en la recepción."})
        return jsonify({"ok": False, "msg": f"No se pudo guardar el renglón: {e!s}"})
    finally:
        conn.close()


# ============================================================================
# ELIMINAR ÍTEM (AJAX)
# ============================================================================
@recepciones_bp.route('/recepciones/eliminar_item/<int:id_detalle>', methods=['POST'])
def eliminar_item(id_detalle):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT r.estado FROM recepciones_detalle d
                JOIN recepciones_cabecera r ON d.id_recepcion = r.id_recepcion
                WHERE d.id_detalle = %s AND (%s IS NULL OR r.tenant_id = %s)
            """, (id_detalle, tenant_id, tenant_id))
            row = cursor.fetchone()
            if not row or row['estado'].upper() != 'ABIERTA':
                return jsonify({"ok": False, "msg": "No se puede eliminar."})

            cursor.execute("DELETE FROM recepciones_detalle WHERE id_detalle = %s AND (%s IS NULL OR tenant_id = %s)", (id_detalle, tenant_id, tenant_id))
            conn.commit()
            return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "msg": str(e)})
    finally:
        conn.close()


# ============================================================================
# CERRAR RECEPCIÓN — impacta stockcontable
# ============================================================================
@recepciones_bp.route('/recepciones/cerrar/<int:id_recepcion>', methods=['POST'])
def cerrar(id_recepcion):
    id_ubicacion_destino = request.form.get('id_ubicacion_destino')
    if not id_ubicacion_destino:
        flash("Debe seleccionar la ubicación destino.", "warning")
        return redirect(url_for('recepciones.ver', id_recepcion=id_recepcion))

    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM recepciones_cabecera WHERE id_recepcion = %s AND estado = 'Abierta' AND (%s IS NULL OR tenant_id = %s)",
                (id_recepcion, tenant_id, tenant_id)
            )
            recepcion = cursor.fetchone()
            if not recepcion:
                flash("La recepción no existe o ya no está Abierta.", "danger")
                return redirect(url_for('recepciones.listar'))
            try:
                id_ubicacion_destino = _destino(cursor, id_ubicacion_destino, tenant_id, recepcion['id_ubicacion_recep'])
            except DatoInvalido as e:
                flash(str(e), "danger")
                return redirect(url_for('recepciones.ver', id_recepcion=id_recepcion))

            cursor.execute("""
                SELECT * FROM recepciones_detalle
                WHERE id_recepcion = %s AND cantidad_recibida > 0
                  AND (%s IS NULL OR tenant_id = %s)
            """, (id_recepcion, tenant_id, tenant_id))
            items = cursor.fetchall()

            if not items:
                flash("No hay ítems con cantidad recibida para cerrar la recepción.", "warning")
                return redirect(url_for('recepciones.ver', id_recepcion=id_recepcion))

            contenedor = recepcion['id_contenedor']
            ahora = datetime.now()
            usuario = session.get('nombre', 'sistema')

            for item in items:
                # El stock queda en la ubicación de recepción como StockSaliendo
                cols_stock = ['Ubicacion', 'Material', 'Lote', 'TipoStock', 'IDContenedor',
                              'StockTotal', 'StockDisponible', 'StockEntrando', 'StockSaliendo',
                              'UltimaEntrada', 'UltimoMovimiento', 'FechaVencimiento', 'UsuarioUltimoMov', 'tenant_id']
                sql_saliendo = upsert_incremental_sql('stockcontable', cols_stock, ['Ubicacion', 'Material', 'IDContenedor'],
                                                      ['StockSaliendo'], ['UltimoMovimiento', 'UsuarioUltimoMov'])
                cursor.execute(sql_saliendo, (
                    recepcion['id_ubicacion_recep'], item['id_material'], item['lote'],
                    item['tipo_stock'], contenedor,
                    0, 0, 0, item['cantidad_recibida'],
                    None, ahora, item['fecha_vencimiento'], usuario, tenant_id
                ))
                registrar_movimiento(
                    conn, tenant_id=tenant_id, accion='RECEPCION', usuario=usuario,
                    modulo='recepciones', id_ubicacion=recepcion['id_ubicacion_recep'],
                    id_material=item['id_material'], id_contenedor=contenedor,
                    lote=item['lote'], tipo_stock=item['tipo_stock'],
                    cantidad=-item['cantidad_recibida'],
                    detalle=f"Stock saliendo al cerrar recepción {recepcion['numero']}")

                # Crear StockEntrando en la ubicación destino
                sql_entrando = upsert_incremental_sql('stockcontable', cols_stock, ['Ubicacion', 'Material', 'IDContenedor'],
                                                      ['StockEntrando'], ['UltimoMovimiento', 'UsuarioUltimoMov'])
                cursor.execute(sql_entrando, (
                    id_ubicacion_destino, item['id_material'], item['lote'],
                    item['tipo_stock'], contenedor,
                    0, 0, item['cantidad_recibida'], 0,
                    None, ahora, item['fecha_vencimiento'], usuario, tenant_id
                ))
                registrar_movimiento(
                    conn, tenant_id=tenant_id, accion='RECEPCION', usuario=usuario,
                    modulo='recepciones', id_ubicacion=id_ubicacion_destino,
                    id_material=item['id_material'], id_contenedor=contenedor,
                    lote=item['lote'], tipo_stock=item['tipo_stock'],
                    cantidad=item['cantidad_recibida'],
                    detalle=f"Stock entrando al cerrar recepción {recepcion['numero']}")

            # Generar número de OMC
            anio_omc = ahora.year
            expr_omc = cast_as_int(substring_index("numero", "-", -1))
            cursor.execute(
                f"SELECT MAX({expr_omc}) AS max_seq "
                f"FROM omc WHERE {year_func('fecha_creacion')} = %s AND (%s IS NULL OR tenant_id = %s)",
                (anio_omc, tenant_id, tenant_id)
            )
            seq_omc = (cursor.fetchone()['max_seq'] or 0) + 1
            numero_omc = f"OMC-{anio_omc}-{seq_omc:05d}"

            id_omc_rec = execute_insert(cursor, """
                INSERT INTO omc
                    (numero, id_contenedor, id_ubicacion_origen, id_ubicacion_destino,
                     id_recepcion, estado, observaciones, usuario_creacion, fecha_creacion, tenant_id)
                VALUES (%s, %s, %s, %s, %s, 'Pendiente', %s, %s, %s, %s)
            """, (
                numero_omc, contenedor,
                recepcion['id_ubicacion_recep'], id_ubicacion_destino,
                id_recepcion,
                f"Generada al cerrar recepción {recepcion['numero']}",
                usuario, ahora, tenant_id
            ))
            cursor.execute("""
                INSERT INTO omc_contenedores
                    (id_omc, id_contenedor, id_contenedor_destino, id_ubicacion_origen)
                VALUES (%s, %s, NULL, %s)
            """, (id_omc_rec, contenedor, recepcion['id_ubicacion_recep']))

            # Cerrar cabecera
            cursor.execute("""
                UPDATE recepciones_cabecera
                SET estado = 'Cerrada', fecha_cierre = %s,
                    usuario_cierre = %s, id_ubicacion_destino = %s
                WHERE id_recepcion = %s AND (%s IS NULL OR tenant_id = %s)
            """, (ahora, usuario, id_ubicacion_destino, id_recepcion, tenant_id, tenant_id))

            conn.commit()
            flash(
                f"Recepción {recepcion['numero']} cerrada. "
                f"{len(items)} ítem(s) registrado(s). "
                f"OMC {numero_omc} generada para confirmar el traslado.",
                "success"
            )
            return redirect(url_for('recepciones.ver', id_recepcion=id_recepcion))

    except Exception as e:
        conn.rollback()
        flash(f"Error al cerrar la recepción (sin cambios guardados): {e!s}", "danger")
        return redirect(url_for('recepciones.ver', id_recepcion=id_recepcion))
    finally:
        conn.close()


# ============================================================================
# ELIMINAR RECEPCIÓN (solo Abierta sin materiales)
# ============================================================================
@recepciones_bp.route('/recepciones/eliminar/<int:id_recepcion>', methods=['POST'])
def eliminar(id_recepcion):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT numero, estado FROM recepciones_cabecera WHERE id_recepcion = %s AND (%s IS NULL OR tenant_id = %s)",
                (id_recepcion, tenant_id, tenant_id)
            )
            rec = cursor.fetchone()
            if not rec or rec['estado'].upper() != 'ABIERTA':
                flash("Solo se pueden eliminar recepciones Abiertas.", "warning")
                return redirect(url_for('recepciones.listar'))

            cursor.execute(
                "SELECT COUNT(*) AS total FROM recepciones_detalle WHERE id_recepcion = %s AND (%s IS NULL OR tenant_id = %s)",
                (id_recepcion, tenant_id, tenant_id)
            )
            if cursor.fetchone()['total'] > 0:
                flash("No se puede eliminar: la recepción tiene materiales asignados.", "danger")
                return redirect(url_for('recepciones.ver', id_recepcion=id_recepcion))

            cursor.execute(
                "DELETE FROM recepciones_cabecera WHERE id_recepcion = %s AND (%s IS NULL OR tenant_id = %s)",
                (id_recepcion, tenant_id, tenant_id)
            )
            conn.commit()
            flash(f"Recepción {rec['numero']} eliminada.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('recepciones.listar'))


@recepciones_bp.route('/recepciones/confirmar_stock/<int:id_recepcion>', methods=['POST'])
def confirmar_stock(id_recepcion):
    """Confirma la entrada de una recepción Cerrada que no tiene una OMC pendiente.

    Al cerrar una recepción se genera una OMC, y el stock se confirma confirmando
    esa OMC. Esta acción queda para las recepciones cerradas sin OMC (anteriores)
    o cuya OMC ya no está pendiente.
    """
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM recepciones_cabecera WHERE id_recepcion = %s AND estado = 'Cerrada' AND (%s IS NULL OR tenant_id = %s)",
                (id_recepcion, tenant_id, tenant_id)
            )
            recepcion = cursor.fetchone()
            if not recepcion:
                flash("La recepción no existe o no está en estado Cerrada.", "danger")
                return redirect(url_for('recepciones.ver', id_recepcion=id_recepcion))

            # Con una OMC pendiente, confirmar desde acá dejaba el stock disponible en el destino sin
            # cerrar la OMC: si después se la anulaba, el stock quedaba también en el origen (duplicado).
            cursor.execute("SELECT numero FROM omc WHERE id_recepcion = %s AND estado = 'Pendiente'", (id_recepcion,))
            pendiente = cursor.fetchone()
            if pendiente:
                flash(f"La entrada de esta recepción se confirma confirmando la OMC {pendiente['numero']}.", "warning")
                return redirect(url_for('recepciones.ver', id_recepcion=id_recepcion))

            ahora = datetime.now()
            usuario = session.get('nombre', 'sistema')
            contenedor = recepcion['id_contenedor']

            cursor.execute("""
                SELECT Material, Lote, TipoStock, Ubicacion,
                       SUM(StockEntrando) AS cantidad
                FROM stockcontable
                WHERE IDContenedor = %s AND StockEntrando > 0
                  AND (%s IS NULL OR tenant_id = %s)
                GROUP BY Ubicacion, Material, Lote, TipoStock
            """, (contenedor, tenant_id, tenant_id))
            movimientos = cursor.fetchall()

            cursor.execute("""
                UPDATE stockcontable
                SET StockTotal       = StockTotal + StockEntrando,
                    StockDisponible  = StockDisponible + StockEntrando,
                    StockEntrando    = 0,
                    UltimaEntrada    = %s,
                    UltimoMovimiento = %s,
                    UsuarioUltimoMov = %s
                WHERE IDContenedor = %s AND StockEntrando > 0 AND (%s IS NULL OR tenant_id = %s)
            """, (ahora, ahora, usuario, contenedor, tenant_id, tenant_id))
            filas = cursor.rowcount

            if movimientos:
                # El stock ya entró al destino: se quita el "saliendo" que quedaba en la ubicación de recepción
                cursor.execute("""DELETE FROM stockcontable
                                  WHERE IDContenedor = %s AND Ubicacion = %s AND StockTotal = 0 AND StockEntrando = 0
                                    AND (%s IS NULL OR tenant_id = %s)""",
                               (contenedor, recepcion['id_ubicacion_recep'], tenant_id, tenant_id))
                cursor.execute("""UPDATE stockcontable SET StockSaliendo = 0
                                  WHERE IDContenedor = %s AND Ubicacion = %s AND (%s IS NULL OR tenant_id = %s)""",
                               (contenedor, recepcion['id_ubicacion_recep'], tenant_id, tenant_id))
                destino = recepcion['id_ubicacion_destino']
            else:
                # Sin stock por entrar (su OMC se anuló): la mercadería quedó en la ubicación de recepción
                destino = recepcion['id_ubicacion_recep']

            for mov in movimientos:
                registrar_movimiento(
                    conn, tenant_id=tenant_id, accion='CONFIRMAR_RECEPCION', usuario=usuario,
                    modulo='recepciones', id_ubicacion=mov['Ubicacion'],
                    id_material=mov['Material'], id_contenedor=contenedor,
                    lote=mov['Lote'], tipo_stock=mov['TipoStock'], cantidad=mov['cantidad'],
                    detalle=f"Stock pasó a Disponible (recepción {recepcion['numero']})")

            cursor.execute(
                "UPDATE recepciones_cabecera SET estado = 'Confirmada', id_ubicacion_destino = %s WHERE id_recepcion = %s",
                (destino, id_recepcion)
            )

            conn.commit()
            if movimientos:
                flash(f"Entrada confirmada. {filas} registro(s) de stock pasaron a Disponible.", "success")
            else:
                flash("Recepción confirmada: la mercadería quedó disponible en la ubicación de recepción.", "success")

    except Exception as e:
        conn.rollback()
        flash(f"Error al confirmar la entrada: {e!s}", "danger")
    finally:
        conn.close()

    return redirect(url_for('recepciones.ver', id_recepcion=id_recepcion))


# ============================================================================
# ANULAR RECEPCIÓN
# ============================================================================
@recepciones_bp.route('/recepciones/anular/<int:id_recepcion>', methods=['POST'])
def anular(id_recepcion):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT numero, estado FROM recepciones_cabecera WHERE id_recepcion = %s AND (%s IS NULL OR tenant_id = %s)",
                (id_recepcion, tenant_id, tenant_id)
            )
            rec = cursor.fetchone()
            if not rec or rec['estado'].upper() != 'ABIERTA':
                flash("Solo se pueden anular recepciones Abiertas.", "warning")
                return redirect(url_for('recepciones.listar'))

            usuario = session.get('nombre', 'sistema')
            cursor.execute("""
                UPDATE recepciones_cabecera
                SET estado = 'Anulada', fecha_cierre = %s, usuario_cierre = %s
                WHERE id_recepcion = %s AND (%s IS NULL OR tenant_id = %s)
            """, (datetime.now(), usuario, id_recepcion, tenant_id, tenant_id))
            conn.commit()
            flash(f"Recepción {rec['numero']} anulada.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('recepciones.listar'))


# ============================================================================
# IMPORTAR RECEPCIONES
# ============================================================================
_CAMPOS_IMPORT_REC = [
    'agrupador', 'proveedor_codigo', 'ubicacion_recep', 'ubicacion_destino',
    'observaciones', 'material_codigo', 'lote', 'fecha_vencimiento', 'cantidad', 'tipo_stock'
]
_EJEMPLO_IMPORT_REC = [
    'LOTE-2024-001', 'PROV001', 'UB-RECEP', 'UB-DEPOSITO',
    'Importación masiva', 'MAT001', 'UNICO', '', '100', 'Libre Venta'
]


@recepciones_bp.route('/recepciones/importar', methods=['POST'])
def importar():
    file = request.files.get('archivo')
    if not file or not file.filename:
        return jsonify({'error': 'No se proporcionó archivo'}), 400
    try:
        rows = parse_file(file, request.form.get('hoja'))
    except Exception as e:
        return jsonify({'error': f'Error al leer el archivo: {e!s}'}), 400

    grupos = OrderedDict()
    for i, row in enumerate(rows, 1):
        agrupador = str(row.get('agrupador', '') or '').strip() or f'__fila_{i}__'
        grupos.setdefault(agrupador, []).append((i, row))

    insertados, errores = 0, []
    conn = get_db_connection()
    try:
        usuario = session.get('nombre', 'sistema')
        anio = datetime.now().year
        tenant_id = get_tenant_filter()

        for agrupador, filas in grupos.items():
            # Cada grupo es una recepción: se verifica entero antes de guardar nada, y se guarda todo o nada
            fila_cabecera, primera = filas[0]
            errores_grupo = []
            id_recepcion = None
            try:
                with conn.cursor() as cursor:
                    cabecera = _cabecera_importada(cursor, primera, tenant_id)
                    lineas = []
                    for fila_num, row in filas:
                        try:
                            linea = _linea_importada(cursor, row, cabecera['id_proveedor'], tenant_id)
                            if linea is None:
                                continue
                            if any(x['id_material'] == linea['id_material'] for x in lineas):
                                raise DatoInvalido(f'El material "{row.get("material_codigo")}" está repetido en la recepción. '
                                                   'Otro lote del mismo material va en otra recepción (otro agrupador).')
                            lineas.append(linea)
                        except DatoInvalido as e:
                            errores_grupo.append({'fila': fila_num, 'codigo': agrupador, 'razon': str(e)})
                    if not lineas and not errores_grupo:
                        errores_grupo.append({'fila': fila_cabecera, 'codigo': agrupador,
                                              'razon': 'Ninguna línea de material válida'})
                    if errores_grupo:
                        errores.extend(errores_grupo)
                        continue

                    id_recepcion = execute_insert(cursor, """
                        INSERT INTO recepciones_cabecera
                            (numero, id_proveedor, id_ubicacion_recep, id_ubicacion_destino,
                             id_contenedor, observaciones, usuario_creacion, tenant_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (_numero_siguiente(cursor, tenant_id, anio), cabecera['id_proveedor'],
                          cabecera['id_ubicacion_recep'], cabecera['id_ubicacion_destino'], '',
                          cabecera['observaciones'], usuario, tenant_id))
                    cursor.execute("UPDATE recepciones_cabecera SET id_contenedor = %s WHERE id_recepcion = %s",
                                   (f"RC{id_recepcion:05d}", id_recepcion))
                    for linea in lineas:
                        cursor.execute("""
                            INSERT INTO recepciones_detalle
                                (id_recepcion, id_material, lote, fecha_vencimiento,
                                 cantidad_esperada, cantidad_recibida, tipo_stock, tenant_id)
                            VALUES (%s, %s, %s, %s, %s, 0, %s, %s)
                        """, (id_recepcion, linea['id_material'], linea['lote'], linea['fecha_vencimiento'],
                              linea['cantidad_esperada'], linea['tipo_stock'], tenant_id))
                    insertados += 1
            except DatoInvalido as e:
                errores.append({'fila': fila_cabecera, 'codigo': agrupador, 'razon': str(e)})
            except Exception as e:
                # Lo que se haya llegado a guardar de este grupo no queda: la cabecera arrastra sus renglones
                if id_recepcion:
                    with conn.cursor() as cursor:
                        cursor.execute("DELETE FROM recepciones_cabecera WHERE id_recepcion = %s", (id_recepcion,))
                errores.append({'fila': fila_cabecera, 'codigo': agrupador, 'razon': str(e)})

        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

    return jsonify({'insertados': insertados, 'omitidos': [], 'errores': errores})


def _por_codigo(cursor, tabla, columna_id, codigo, tenant_id):
    cursor.execute(f"SELECT {columna_id} AS id FROM {tabla} WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)",
                   (codigo, tenant_id, tenant_id))
    fila = cursor.fetchone()
    return fila['id'] if fila else None


def _cabecera_importada(cursor, row, tenant_id):
    """Proveedor y ubicaciones de un grupo del archivo (indicados por código), verificados."""
    proveedor_cod = str(row.get('proveedor_codigo', '') or '').strip()
    ubic_recep_cod = str(row.get('ubicacion_recep', '') or '').strip()
    ubic_dest_cod = str(row.get('ubicacion_destino', '') or '').strip()
    if not proveedor_cod:
        raise DatoInvalido('proveedor_codigo es obligatorio')
    if not ubic_recep_cod:
        raise DatoInvalido('ubicacion_recep es obligatorio')

    id_proveedor = _por_codigo(cursor, 'proveedores', 'id', proveedor_cod, tenant_id)
    if not id_proveedor:
        raise DatoInvalido(f'Proveedor "{proveedor_cod}" no encontrado')
    id_proveedor = _proveedor(cursor, id_proveedor, tenant_id)

    id_recep = _por_codigo(cursor, 'ubicaciones', 'id', ubic_recep_cod, tenant_id)
    if not id_recep:
        raise DatoInvalido(f'Ubicación recep "{ubic_recep_cod}" no encontrada')
    id_recep = _ubicacion(cursor, id_recep, tenant_id, 'ubicación de recepción', de_recepcion=True)

    id_destino = None
    if ubic_dest_cod:
        id_destino = _por_codigo(cursor, 'ubicaciones', 'id', ubic_dest_cod, tenant_id)
        if not id_destino:
            raise DatoInvalido(f'Ubicación destino "{ubic_dest_cod}" no encontrada')
        id_destino = _destino(cursor, id_destino, tenant_id, id_recep)
    return {'id_proveedor': id_proveedor, 'id_ubicacion_recep': id_recep, 'id_ubicacion_destino': id_destino,
            'observaciones': str(row.get('observaciones', '') or '').strip() or None}


def _linea_importada(cursor, row, id_proveedor, tenant_id):
    """Renglón de un grupo del archivo, verificado; None si la fila no trae material."""
    material_cod = str(row.get('material_codigo', '') or '').strip()
    if not material_cod:
        return None
    id_material = _por_codigo(cursor, 'materiales', 'id', material_cod, tenant_id)
    if not id_material:
        raise DatoInvalido(f'Material "{material_cod}" no encontrado')
    # En el archivo la cantidad es la esperada; la recibida se carga al recibir
    linea = _renglon({**row, 'cantidad_esperada': row.get('cantidad')}, cantidad_recibida=None)
    _material_del_proveedor(cursor, id_material, id_proveedor, tenant_id, linea['lote'])
    return {**linea, 'id_material': id_material}


@recepciones_bp.route('/recepciones/plantilla/<formato>')
def plantilla(formato):
    if formato == 'csv':
        return plantilla_csv(_CAMPOS_IMPORT_REC, _EJEMPLO_IMPORT_REC, 'plantilla_recepciones.csv')
    elif formato == 'json':
        return plantilla_json(_CAMPOS_IMPORT_REC, _EJEMPLO_IMPORT_REC, 'plantilla_recepciones.json')
    elif formato == 'xlsx':
        return plantilla_xlsx(_CAMPOS_IMPORT_REC, _EJEMPLO_IMPORT_REC, 'plantilla_recepciones.xlsx')
    return 'Formato no válido', 400
