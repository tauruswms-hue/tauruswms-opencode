import json
import math
import os
import re
from collections import OrderedDict, defaultdict
from datetime import date, datetime
from decimal import Decimal

from flask import (
    Blueprint,
    Response,
    current_app,
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
    in_clause_sql,
    is_duplicate_key_error,
    limit_sql,
    quote,
    substring_index,
    upsert_incremental_sql,
)
from modules.sql_dialect import year as year_func

pedidos_bp = Blueprint('pedidos', __name__)

TIPOS_STOCK = ('Libre Venta', 'Calidad', 'Bloqueado', 'Mal Estado')
CANTIDAD_MAX = 99999999999.9999   # mayor valor de pedidos_detalle.cantidad, decimal(15,4)
DIRECCION_MAX = 255               # largo de pedidos_cabecera.direccion_entrega
# Estados en los que un pedido ya no admite cambios
ESTADOS_FINALES = ('Despachado', 'Anulado')


def _id(valor):
    """Id entero de un formulario o JSON, o 0 si no es un id."""
    try:
        return int(str(valor if valor is not None else '').strip() or 0)
    except ValueError:
        return 0


def _ids(valores):
    """Ids enteros de una lista recibida por JSON, sin repetir; los que no son ids se descartan."""
    ids = []
    for v in valores if isinstance(valores, (list, tuple)) else []:
        i = _id(v)
        if i and i not in ids:
            ids.append(i)
    return ids


def _numero_siguiente(cursor, tenant_id, anio):
    """Próximo número de pedido de la empresa: el mayor ya usado con el prefijo del año, más uno.

    No se cuenta la cantidad de pedidos: con un pedido borrado, o con uno fechado en
    otro año, la cuenta daba un número ya usado y no se podía crear ningún pedido más.
    """
    prefijo = f'PED-{anio}-'
    cursor.execute("SELECT nro_pedido FROM pedidos_cabecera WHERE nro_pedido LIKE %s AND (%s IS NULL OR tenant_id = %s)",
                   (prefijo + '%', tenant_id, tenant_id))
    usados = [int(m.group(1)) for m in (re.fullmatch(re.escape(prefijo) + r'(\d+)', r['nro_pedido']) for r in cursor.fetchall()) if m]
    return f'{prefijo}{max(usados, default=0) + 1:05d}'


def _fecha(valor):
    texto = str(valor or '').strip()[:10]
    if not texto:
        raise DatoInvalido('Fecha del pedido: es obligatoria.')
    try:
        datetime.strptime(texto, '%Y-%m-%d')
    except ValueError:
        raise DatoInvalido(f'Fecha del pedido: "{valor}" no es una fecha válida (formato AAAA-MM-DD).') from None
    return texto


def _referencia(cursor, tabla, columna_id, columna_nombre, valor, tenant_id, rotulo, actual=None, obligatorio=False):
    """Id de un registro de otro maestro (cliente, clase, ruta, transporte), de la empresa y activo.

    `actual` es el que el pedido ya tiene: se conserva aunque haya quedado inactivo.
    """
    id_ref = _id(valor)
    if not id_ref:
        if str(valor or '').strip() or obligatorio:
            raise DatoInvalido(f'{rotulo}: {"hay que elegirlo" if not str(valor or "").strip() else "el valor elegido no existe"}.')
        return None
    cursor.execute(f"SELECT {columna_nombre} AS nombre, activo FROM {tabla} WHERE {columna_id} = %s AND (%s IS NULL OR tenant_id = %s)",
                   (id_ref, tenant_id, tenant_id))
    fila = cursor.fetchone()
    if not fila:
        raise DatoInvalido(f'{rotulo}: el valor elegido no existe.')
    if not fila['activo'] and id_ref != actual:
        raise DatoInvalido(f'{rotulo}: "{fila["nombre"]}" está inactivo.')
    return id_ref


def _cantidad(valor):
    try:
        n = float(str(valor if valor is not None else '').strip().replace(',', '.'))
    except ValueError:
        n = math.nan
    if not math.isfinite(n):
        raise DatoInvalido(f'Cantidad: "{valor}" no es un número válido.')
    if n <= 0:
        raise DatoInvalido('Cantidad: tiene que ser mayor que cero.')
    if n > CANTIDAD_MAX:
        raise DatoInvalido('Cantidad: el valor es demasiado grande.')
    return n


def _renglon(cursor, id_material, cantidad, tipo_stock, tenant_id, renglones, ya_en_el_pedido=()):
    """Verifica un renglón y lo agrega a `renglones`: material activo de la empresa, cantidad y tipo de stock.

    El mismo material se puede pedir en tipos de stock distintos, pero no dos veces en el mismo.
    Los materiales que el pedido ya tenía (`ya_en_el_pedido`) se conservan aunque estén inactivos.
    """
    cursor.execute("SELECT codigo, activo FROM materiales WHERE id = %s AND (%s IS NULL OR tenant_id = %s)",
                   (id_material, tenant_id, tenant_id))
    material = cursor.fetchone()
    if not material:
        raise DatoInvalido('Renglones: el material elegido no existe.')
    if not material['activo'] and id_material not in ya_en_el_pedido:
        raise DatoInvalido(f'Renglones: el material "{material["codigo"]}" está inactivo.')
    tipo_stock = str(tipo_stock or '').strip() or TIPOS_STOCK[0]
    if tipo_stock not in TIPOS_STOCK:
        raise DatoInvalido(f'Tipo de stock: "{tipo_stock}" no es válido. Usar: {", ".join(TIPOS_STOCK)}.')
    try:
        cantidad = _cantidad(cantidad)
    except DatoInvalido as e:
        raise DatoInvalido(f'Material "{material["codigo"]}": {str(e)[0].lower()}{str(e)[1:]}') from None
    if any(r['id_material'] == id_material and r['tipo_stock'] == tipo_stock for r in renglones):
        raise DatoInvalido(f'El material "{material["codigo"]}" está repetido con el mismo tipo de stock ({tipo_stock}).')
    renglones.append({'id_material': id_material, 'cantidad': cantidad, 'tipo_stock': tipo_stock})


# --- LISTADO Y CONSOLA DE GESTIÓN ---
@pedidos_bp.route('/pedidos')
def listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT p.*, c.razonsocial as cliente_nombre, r.nombre_ruta, t.razonsocial as transporte_nombre,
                       cp.nombre as clase_nombre
                FROM pedidos_cabecera p
                JOIN clientes c ON p.id_cliente = c.id_cliente
                LEFT JOIN rutas r ON p.id_ruta = r.id_ruta
                LEFT JOIN transportes t ON p.id_transporte = t.id_transporte
                LEFT JOIN clases_pedido cp ON p.id_clase = cp.id_clase
                WHERE (%s IS NULL OR p.tenant_id = %s)
                ORDER BY p.id_pedido DESC
            """
            cursor.execute(sql, (tenant_id, tenant_id))
            pedidos = cursor.fetchall()
            cursor.execute("SELECT id_ruta, nombre_ruta FROM rutas WHERE (%s IS NULL OR tenant_id = %s) ORDER BY nombre_ruta", (tenant_id, tenant_id))
            rutas = cursor.fetchall()
            cursor.execute("SELECT id_transporte, razonsocial FROM transportes WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s) ORDER BY razonsocial", (tenant_id, tenant_id))
            transportes = cursor.fetchall()
            cursor.execute("SELECT id_transporte, id_ruta FROM transporte_rutas WHERE (%s IS NULL OR tenant_id = %s)", (tenant_id, tenant_id))
            transporte_rutas = cursor.fetchall()

        conn_admin = _get_admin_connection()
        try:
            with conn_admin.cursor() as cursor_admin:
                cursor_admin.execute("SELECT dias_filtro_fechas FROM tenants WHERE id = %s", (tenant_id,))
                param = cursor_admin.fetchone()
                dias_filtro = param['dias_filtro_fechas'] if param else 30
        finally:
            conn_admin.close()

        return render_template('pedidos.html', pedidos=pedidos, dias_filtro=dias_filtro,
                               rutas=rutas, transportes=transportes,
                               transporte_rutas=transporte_rutas)
    finally:
        conn.close()


# --- VISTAS DE DETALLE Y FORMULARIOS ---
@pedidos_bp.route('/pedidos/ver/<int:id_pedido>')
def ver_detalle(id_pedido):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql_cab = """
                SELECT p.*, c.razonsocial as cliente_nombre, c.codigo as cliente_codigo,
                       r.nombre_ruta, t.razonsocial as transporte_nombre
                FROM pedidos_cabecera p
                JOIN clientes c ON p.id_cliente = c.id_cliente
                LEFT JOIN rutas r ON p.id_ruta = r.id_ruta
                LEFT JOIN transportes t ON p.id_transporte = t.id_transporte
                WHERE p.id_pedido = %s AND (%s IS NULL OR p.tenant_id = %s)
            """
            cursor.execute(sql_cab, (id_pedido, tenant_id, tenant_id))
            pedido = cursor.fetchone()
            if not pedido:
                flash("El pedido no existe.", "warning")
                return redirect(url_for('pedidos.listar'))

            sql_det = """
                SELECT d.*, m.nombre as material_nombre, m.codigo as material_sku,
                       un.nombre as unidad_nombre
                FROM pedidos_detalle d
                JOIN materiales m ON d.id_material = m.id
                LEFT JOIN unidades_medida un ON m.unidad_medida_id = un.id_unidad
                WHERE d.id_pedido = %s AND (%s IS NULL OR d.tenant_id = %s)
            """
            cursor.execute(sql_det, (id_pedido, tenant_id, tenant_id))
            items = cursor.fetchall()
        return render_template('pedidos_detalle_ver.html', pedido=pedido, items=items)
    finally:
        conn.close()


@pedidos_bp.route('/pedidos/nuevo')
def nuevo():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id_cliente, razonsocial, codigo, direccion, id_ruta, id_transporte_predeterminado FROM clientes WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s)",
                (tenant_id, tenant_id)
            )
            clientes = cursor.fetchall()
            cursor.execute("SELECT * FROM rutas WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s) ORDER BY nombre_ruta", (tenant_id, tenant_id))
            rutas = cursor.fetchall()
            cursor.execute("SELECT id_transporte, razonsocial FROM transportes WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s)", (tenant_id, tenant_id))
            transportes = cursor.fetchall()
            cursor.execute("SELECT id_transporte, id_ruta FROM transporte_rutas WHERE (%s IS NULL OR tenant_id = %s)", (tenant_id, tenant_id))
            rel_transp_rutas = cursor.fetchall()
            cursor.execute("SELECT id, codigo, nombre FROM materiales WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s)", (tenant_id, tenant_id))
            materiales = cursor.fetchall()
            cursor.execute("SELECT id_clase, nombre, activo FROM clases_pedido WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s) ORDER BY nombre", (tenant_id, tenant_id))
            clases = cursor.fetchall()

            cursor.execute("SELECT id_transporte, id_muelle_salida FROM transportes WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s)", (tenant_id, tenant_id))
            transportes_muelles = {r['id_transporte']: r['id_muelle_salida'] for r in cursor.fetchall()}

        return render_template('pedidos_form.html', clientes=clientes, rutas=rutas,
                               transportes=transportes, rel_transp_rutas=rel_transp_rutas,
                               materiales=materiales, clases=clases,
                               transportes_muelles=transportes_muelles,
                               hoy=datetime.now().strftime('%Y-%m-%d'),
                               edit_mode=False)
    finally:
        conn.close()


@pedidos_bp.route('/pedidos/editar/<int:id_pedido>')
def editar(id_pedido):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM pedidos_cabecera WHERE id_pedido = %s AND (%s IS NULL OR tenant_id = %s)", (id_pedido, tenant_id, tenant_id))
            pedido = cursor.fetchone()

            if not pedido or pedido['estado'] != 'Pendiente':
                flash("El pedido no existe o ya no se puede modificar.", "warning")
                return redirect(url_for('pedidos.listar'))

            cursor.execute(
                "SELECT id_cliente, razonsocial, codigo, direccion, id_ruta, id_transporte_predeterminado FROM clientes WHERE (activo = 1 OR id_cliente = %s) AND (%s IS NULL OR tenant_id = %s)",
                (pedido['id_cliente'], tenant_id, tenant_id)
            )
            clientes = cursor.fetchall()
            # Las activas, más la que ya tiene el pedido aunque esté inactiva (si no, se perdería al guardar)
            cursor.execute("""SELECT * FROM rutas WHERE (activo = 1 OR id_ruta = %s) AND (%s IS NULL OR tenant_id = %s)
                              ORDER BY nombre_ruta""", (pedido['id_ruta'] or 0, tenant_id, tenant_id))
            rutas = cursor.fetchall()
            # Los activos, más el que ya tiene el pedido aunque esté inactivo (si no, se perdería al guardar)
            cursor.execute("""SELECT id_transporte, razonsocial, activo FROM transportes
                              WHERE (activo = 1 OR id_transporte = %s) AND (%s IS NULL OR tenant_id = %s)
                              ORDER BY razonsocial""", (pedido['id_transporte'] or 0, tenant_id, tenant_id))
            transportes = cursor.fetchall()
            cursor.execute("SELECT id_transporte, id_ruta FROM transporte_rutas WHERE (%s IS NULL OR tenant_id = %s)", (tenant_id, tenant_id))
            rel_transp_rutas = cursor.fetchall()
            # Los activos, más los que ya están en el pedido aunque estén inactivos (si no, el renglón quedaba en blanco)
            cursor.execute("""SELECT id, codigo, nombre, activo FROM materiales
                              WHERE (activo = 1 OR id IN (SELECT id_material FROM pedidos_detalle WHERE id_pedido = %s))
                                AND (%s IS NULL OR tenant_id = %s)
                              ORDER BY codigo""", (id_pedido, tenant_id, tenant_id))
            materiales = cursor.fetchall()
            cursor.execute("SELECT * FROM pedidos_detalle WHERE id_pedido = %s AND (%s IS NULL OR tenant_id = %s)", (id_pedido, tenant_id, tenant_id))
            detalle = cursor.fetchall()
            # Las activas, más la que ya tiene el pedido aunque esté inactiva (si no, se perdería al guardar)
            cursor.execute("""SELECT id_clase, nombre, activo FROM clases_pedido
                              WHERE (activo = 1 OR id_clase = %s) AND (%s IS NULL OR tenant_id = %s)
                              ORDER BY nombre""", (pedido['id_clase'] or 0, tenant_id, tenant_id))
            clases = cursor.fetchall()

        return render_template('pedidos_form.html', pedido=pedido, detalle=detalle,
                               clientes=clientes, rutas=rutas, transportes=transportes,
                               rel_transp_rutas=rel_transp_rutas, materiales=materiales,
                               clases=clases, transportes_muelles={}, edit_mode=True)
    finally:
        conn.close()


# --- PERSISTENCIA (GUARDAR / ELIMINAR) ---
@pedidos_bp.route('/pedidos/guardar', methods=['POST'])
def guardar():
    d = request.form
    id_pedido   = d.get('id_pedido')
    items       = request.form.getlist('items[]')
    cantidades  = request.form.getlist('cantidades[]')
    tipos_stock = request.form.getlist('tipos_stock[]')
    tenant_id = get_tenant_filter()

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            anterior, materiales_previos = None, set()
            if id_pedido:
                cursor.execute("""SELECT estado, id_cliente, id_clase, id_ruta, id_transporte FROM pedidos_cabecera
                                  WHERE id_pedido = %s AND (%s IS NULL OR tenant_id = %s)""", (_id(id_pedido), tenant_id, tenant_id))
                anterior = cursor.fetchone()
                if not anterior or anterior['estado'] != 'Pendiente':
                    flash("No se puede modificar un pedido procesado.", "danger")
                    return redirect(url_for('pedidos.listar'))
                id_pedido = _id(id_pedido)
                cursor.execute("SELECT id_material FROM pedidos_detalle WHERE id_pedido = %s", (id_pedido,))
                materiales_previos = {r['id_material'] for r in cursor.fetchall()}
            previo = anterior or {}

            # --- Validaciones (cualquier DatoInvalido corta sin guardar nada) ---
            id_cliente = _referencia(cursor, 'clientes', 'id_cliente', 'razonsocial', d.get('id_cliente'), tenant_id,
                                     'Cliente', actual=previo.get('id_cliente'), obligatorio=True)
            fecha_pedido = _fecha(d.get('fecha_pedido'))
            id_clase = _referencia(cursor, 'clases_pedido', 'id_clase', 'nombre', d.get('id_clase'), tenant_id,
                                   'Clase de pedido', actual=previo.get('id_clase'))
            id_ruta = _referencia(cursor, 'rutas', 'id_ruta', 'nombre_ruta', d.get('id_ruta'), tenant_id,
                                  'Ruta', actual=previo.get('id_ruta'))
            id_transporte = _referencia(cursor, 'transportes', 'id_transporte', 'razonsocial', d.get('id_transporte'),
                                        tenant_id, 'Transporte', actual=previo.get('id_transporte'))
            direccion = (d.get('direccion_entrega') or '').strip() or None
            if direccion and len(direccion) > DIRECCION_MAX:
                raise DatoInvalido(f'Dirección de entrega: admite hasta {DIRECCION_MAX} caracteres.')
            observaciones = (d.get('observaciones') or '').strip() or None

            renglones = []
            for i, item in enumerate(items):
                cantidad = cantidades[i] if i < len(cantidades) else ''
                if not str(item or '').strip() and not str(cantidad or '').strip():
                    continue                      # fila vacía del formulario
                if not _id(item):
                    raise DatoInvalido('Renglones: hay una fila sin material.')
                _renglon(cursor, _id(item), cantidad, tipos_stock[i] if i < len(tipos_stock) else '', tenant_id,
                         renglones, ya_en_el_pedido=materiales_previos)
            if not renglones:
                raise DatoInvalido('El pedido tiene que tener al menos un renglón.')

            # --- Guardado ---
            if id_pedido:
                cursor.execute("""UPDATE pedidos_cabecera SET id_cliente=%s, id_clase=%s, fecha_pedido=%s,
                                  id_ruta=%s, id_transporte=%s, direccion_entrega=%s, observaciones=%s
                                  WHERE id_pedido=%s""",
                               (id_cliente, id_clase, fecha_pedido, id_ruta, id_transporte, direccion, observaciones, id_pedido))
                cursor.execute("DELETE FROM pedidos_detalle WHERE id_pedido = %s", (id_pedido,))
            else:
                nro_pedido = _numero_siguiente(cursor, tenant_id, datetime.now().year)
                sql_cab = """INSERT INTO pedidos_cabecera (nro_pedido, id_cliente, id_clase, fecha_pedido, id_ruta,
                             id_transporte, direccion_entrega, observaciones, estado, tenant_id)
                             VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Pendiente', %s)"""
                id_pedido = execute_insert(cursor, sql_cab, (nro_pedido, id_cliente, id_clase, fecha_pedido, id_ruta,
                                                             id_transporte, direccion, observaciones, tenant_id))

            sql_det = "INSERT INTO pedidos_detalle (id_pedido, id_material, cantidad, tipo_stock, tenant_id) VALUES (%s, %s, %s, %s, %s)"
            for r in renglones:
                cursor.execute(sql_det, (id_pedido, r['id_material'], r['cantidad'], r['tipo_stock'], tenant_id))

            # --- OMC AUTOMÁTICA con todos los contenedores (solo pedidos nuevos) ---
            if not d.get('id_pedido'):
                contenedores = [c.strip().upper() for c in request.form.getlist('contenedores[]') if c.strip()]
                ahora   = datetime.now()
                usuario = session.get('nombre', 'sistema')

                # Muelle del transporte: sirve si es una ubicación activa de un tipo de salida
                muelle_id = None
                if id_transporte:
                    cursor.execute("""
                        SELECT u.id FROM transportes t
                        JOIN ubicaciones u    ON u.id = t.id_muelle_salida
                        JOIN tipoubicacion tu ON tu.id = u.tipoubicacion
                        WHERE t.id_transporte = %s AND u.activo = 1 AND tu.operacion = 'S'
                          AND (%s IS NULL OR t.tenant_id = %s)
                    """, (id_transporte, tenant_id, tenant_id))
                    row_t = cursor.fetchone()
                    if row_t:
                        muelle_id = row_t['id']

                contenedores_validos = []
                for contenedor in contenedores:
                    if not muelle_id:
                        flash(f"Contenedor {contenedor}: sin OMC — el transporte no tiene un muelle de salida activo.", "warning")
                        continue

                    cursor.execute(f"""
                        SELECT sc.Ubicacion, SUM(sc.StockDisponible) AS disp,
                               SUM(sc.StockSaliendo) AS sal, SUM(sc.StockEntrando) AS ent
                        FROM stockcontable sc
                        JOIN ubicaciones u    ON sc.Ubicacion    = u.id
                        JOIN tipoubicacion tu ON u.tipoubicacion = tu.id
                        WHERE sc.IDContenedor = %s
                          AND tu.soporte_picking = 1
                          AND (%s IS NULL OR sc.tenant_id = %s)
                        GROUP BY sc.Ubicacion
                        HAVING disp > 0 AND sal = 0 AND ent = 0
                        {limit_sql(1)}
                    """, (contenedor, tenant_id, tenant_id))
                    row_sc = cursor.fetchone()

                    if not row_sc:
                        flash(f"Contenedor {contenedor}: sin OMC — sin stock disponible en ubicación de picking o con movimientos pendientes.", "warning")
                        continue

                    id_origen = row_sc['Ubicacion']

                    cursor.execute("""
                        SELECT o.id_omc, o.numero FROM omc o
                        JOIN omc_contenedores oc ON o.id_omc = oc.id_omc
                        WHERE oc.id_contenedor = %s AND oc.id_ubicacion_origen = %s AND o.estado = 'Pendiente'
                          AND (%s IS NULL OR o.tenant_id = %s)
                    """, (contenedor, id_origen, tenant_id, tenant_id))
                    existente = cursor.fetchone()
                    if existente:
                        flash(f"Contenedor {contenedor}: ya existe OMC pendiente {existente['numero']}.", "warning")
                        continue

                    contenedores_validos.append({'contenedor': contenedor, 'id_origen': id_origen})

                if contenedores_validos:
                    # Generar UN SOLO número OMC para todos los contenedores
                    expr_omc = cast_as_int(substring_index("numero", "-", -1))
                    cursor.execute(
                        f"SELECT MAX({expr_omc}) AS max_seq "
                        f"FROM omc WHERE {year_func('fecha_creacion')} = %s AND (%s IS NULL OR tenant_id = %s)",
                        (ahora.year, tenant_id, tenant_id)
                    )
                    seq_omc = (cursor.fetchone()['max_seq'] or 0) + 1
                    omc_numero = f"OMC-{ahora.year}-{seq_omc:05d}"

                    # Stock operations per container
                    for cv in contenedores_validos:
                        cursor.execute("""
                            SELECT Material, Lote, TipoStock, StockDisponible AS cantidad
                            FROM stockcontable
                            WHERE IDContenedor = %s AND Ubicacion = %s AND StockDisponible > 0
                              AND (%s IS NULL OR tenant_id = %s)
                        """, (cv['contenedor'], cv['id_origen'], tenant_id, tenant_id))
                        origen_disponible = cursor.fetchall()

                        # StockSaliendo en origen
                        cursor.execute("""
                            UPDATE stockcontable
                            SET StockSaliendo = StockDisponible, StockDisponible = 0, StockTotal = 0,
                                UltimoMovimiento = %s, UsuarioUltimoMov = %s
                            WHERE IDContenedor = %s AND Ubicacion = %s AND StockDisponible > 0
                              AND (%s IS NULL OR tenant_id = %s)
                        """, (ahora, usuario, cv['contenedor'], cv['id_origen'], tenant_id, tenant_id))
                        for rec in origen_disponible:
                            registrar_movimiento(
                                conn, tenant_id=tenant_id, accion='PREPARAR_PEDIDO', usuario=usuario,
                                modulo='pedidos', id_ubicacion=cv['id_origen'],
                                id_material=rec['Material'], id_contenedor=cv['contenedor'],
                                lote=rec['Lote'], tipo_stock=rec['TipoStock'], cantidad=-rec['cantidad'],
                                detalle=f"Stock reservado al preparar pedido {nro_pedido}")

                        # StockEntrando en muelle
                        cursor.execute("""
                            SELECT Material, Lote, TipoStock, StockSaliendo, FechaVencimiento
                            FROM stockcontable
                            WHERE IDContenedor = %s AND Ubicacion = %s AND StockSaliendo > 0
                              AND (%s IS NULL OR tenant_id = %s)
                        """, (cv['contenedor'], cv['id_origen'], tenant_id, tenant_id))
                        for rec in cursor.fetchall():
                            cols_stock = ['Ubicacion', 'Material', 'Lote', 'TipoStock', 'IDContenedor',
                                          'StockTotal', 'StockDisponible', 'StockEntrando', 'StockSaliendo',
                                          'UltimaEntrada', 'UltimoMovimiento', 'FechaVencimiento', 'UsuarioUltimoMov', 'tenant_id']
                            sql_ent = upsert_incremental_sql('stockcontable', cols_stock, ['Ubicacion', 'Material', 'IDContenedor'],
                                                             ['StockEntrando'], ['UltimoMovimiento', 'UsuarioUltimoMov'])
                            cursor.execute(sql_ent, (muelle_id, rec['Material'], rec['Lote'], rec['TipoStock'],
                                  cv['contenedor'], 0, 0, rec['StockSaliendo'], 0,
                                  None, ahora, rec['FechaVencimiento'], usuario, tenant_id))
                            registrar_movimiento(
                                conn, tenant_id=tenant_id, accion='PREPARAR_PEDIDO', usuario=usuario,
                                modulo='pedidos', id_ubicacion=muelle_id,
                                id_material=rec['Material'], id_contenedor=cv['contenedor'],
                                lote=rec['Lote'], tipo_stock=rec['TipoStock'], cantidad=rec['StockSaliendo'],
                                detalle=f"Stock en muelle al preparar pedido {nro_pedido}")

                    # Crear UNA SOLA OMC para todos los contenedores
                    id_omc = execute_insert(cursor, """
                        INSERT INTO omc
                            (numero, id_contenedor, id_ubicacion_origen, id_ubicacion_destino,
                             id_recepcion, id_pedido, estado, observaciones,
                             usuario_creacion, fecha_creacion, tenant_id)
                        VALUES (%s, NULL, NULL, %s, NULL, %s, 'Pendiente', %s, %s, %s, %s)
                    """, (omc_numero, muelle_id, id_pedido,
                          f"Generada desde pedido {nro_pedido}", usuario, ahora, tenant_id))

                    # Insertar cada contenedor en omc_contenedores
                    for cv in contenedores_validos:
                        cursor.execute("""
                            INSERT INTO omc_contenedores
                                (id_omc, id_contenedor, id_contenedor_destino, id_ubicacion_origen, tenant_id)
                            VALUES (%s, %s, NULL, %s, %s)
                        """, (id_omc, cv['contenedor'], cv['id_origen'], tenant_id))

                    cursor.execute("""
                        UPDATE pedidos_cabecera SET estado = 'Trabajo OMC' WHERE id_pedido = %s
                          AND (%s IS NULL OR tenant_id = %s)
                    """, (id_pedido, tenant_id, tenant_id))
                    flash(f"Pedido {nro_pedido} guardado. OMC {omc_numero} generada con {len(contenedores_validos)} contenedor(es).", "success")
                else:
                    flash(f"Pedido {nro_pedido} guardado.", "success")
            else:
                flash("Pedido guardado con éxito.", "success")

            conn.commit()
    except DatoInvalido as e:
        conn.rollback()
        # Lo que se haya avisado de los contenedores no vale: no se guardó nada
        session.pop('_flashes', None)
        flash(str(e), "danger")
    except Exception as e:
        conn.rollback()
        session.pop('_flashes', None)
        if is_duplicate_key_error(e):
            flash("No se pudo guardar el pedido: otro usuario tomó el mismo número. Volver a intentar.", "danger")
        else:
            flash(f"Error al guardar el pedido: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('pedidos.listar'))


@pedidos_bp.route('/pedidos/eliminar/<int:id_pedido>', methods=['POST'])
def eliminar(id_pedido):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT nro_pedido, estado FROM pedidos_cabecera WHERE id_pedido = %s AND (%s IS NULL OR tenant_id = %s)", (id_pedido, tenant_id, tenant_id))
            p = cursor.fetchone()
            if not p:
                flash("El pedido no existe.", "warning")
                return redirect(url_for('pedidos.listar'))
            # Se anula un pedido Pendiente, o uno en Trabajo que todavía no tiene una OMC en curso o confirmada
            anulable = p['estado'] == 'Pendiente'
            if p['estado'] == 'Trabajo':
                cursor.execute("SELECT COUNT(*) AS n FROM omc WHERE id_pedido = %s AND estado IN ('Pendiente', 'Confirmada')",
                               (id_pedido,))
                anulable = cursor.fetchone()['n'] == 0
            if anulable:
                cursor.execute("UPDATE pedidos_cabecera SET estado = 'Anulado' WHERE id_pedido = %s", (id_pedido,))
                conn.commit()
                flash(f"Pedido {p['nro_pedido']} anulado.", "success")
            elif p['estado'] == 'Trabajo':
                flash(f"No se puede anular el pedido {p['nro_pedido']}: tiene una OMC pendiente o confirmada.", "warning")
            else:
                flash(f"No se puede anular el pedido {p['nro_pedido']}: está en estado {p['estado']}.", "warning")
    except Exception as e:
        conn.rollback()
        flash(f"No se pudo anular el pedido: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('pedidos.listar'))


# --- ACCIONES MASIVAS (CONSOLA) ---
@pedidos_bp.route('/pedidos/verificar_stock_masivo', methods=['POST'])
def verificar_stock_masivo():
    ids = _ids((request.get_json(silent=True) or {}).get('ids'))
    if not ids:
        return jsonify({"status": "error", "message": "No hay pedidos seleccionados"}), 400

    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            ph = in_clause_sql(ids)

            # Cabeceras de los pedidos seleccionados
            cursor.execute(f"""
                SELECT p.id_pedido, p.nro_pedido, p.estado,
                       c.razonsocial AS cliente_nombre, c.codigo AS cliente_codigo
                FROM pedidos_cabecera p
                JOIN clientes c ON p.id_cliente = c.id_cliente
                WHERE p.id_pedido IN ({ph})
                  AND (%s IS NULL OR p.tenant_id = %s)
                ORDER BY p.nro_pedido
            """, (*tuple(ids), tenant_id, tenant_id))
            pedidos = cursor.fetchall()

            # Detalle: cantidad solicitada por material+tipo_stock por pedido
            cursor.execute(f"""
                SELECT d.id_pedido, p.nro_pedido,
                       m.id AS id_material, m.codigo AS material_codigo, m.nombre AS material_nombre,
                       un.nombre AS unidad_nombre,
                       d.cantidad,
                       COALESCE(d.tipo_stock, 'Libre Venta') AS tipo_stock
                FROM pedidos_detalle d
                JOIN pedidos_cabecera p ON d.id_pedido = p.id_pedido
                JOIN materiales m       ON d.id_material = m.id
                LEFT JOIN unidades_medida un ON m.unidad_medida_id = un.id_unidad
                WHERE d.id_pedido IN ({ph})
                  AND (%s IS NULL OR d.tenant_id = %s)
                ORDER BY m.codigo, d.tipo_stock, p.nro_pedido
            """, (*tuple(ids), tenant_id, tenant_id))
            detalle_rows = cursor.fetchall()

            # Stock disponible por (material, tipo_stock)
            material_ids = list({r['id_material'] for r in detalle_rows})
            stock_map = {}  # key: (id_material, tipo_stock)
            if material_ids:
                ph2 = in_clause_sql(material_ids)
                # Solo lo que se puede pickear: ubicaciones activas de un tipo que soporta picking.
                # Con el stock de recepción o de los muelles el informe decía que alcanzaba cuando no.
                cursor.execute(f"""
                    SELECT sc.Material, sc.TipoStock,
                           SUM(sc.StockDisponible) AS stock_disponible,
                           SUM(sc.StockEntrando)   AS stock_entrando
                    FROM stockcontable sc
                    JOIN ubicaciones u    ON sc.Ubicacion    = u.id
                    JOIN tipoubicacion tu ON u.tipoubicacion = tu.id
                    WHERE sc.Material IN ({ph2})
                      AND tu.soporte_picking = 1 AND u.activo = 1
                      AND (%s IS NULL OR sc.tenant_id = %s)
                    GROUP BY sc.Material, sc.TipoStock
                """, (*tuple(material_ids), tenant_id, tenant_id))
                for row in cursor.fetchall():
                    # El tipo se compara sin distinguir mayúsculas: hay bases con el enum en mayúsculas ('LIBRE VENTA')
                    stock_map[(row['Material'], str(row['TipoStock'] or '').lower())] = {
                        'stock_disponible': float(row['stock_disponible'] or 0),
                        'stock_entrando':   float(row['stock_entrando']   or 0),
                    }

            # Consolidar por (material, tipo_stock)
            totales = defaultdict(lambda: {
                'material_codigo': '', 'material_nombre': '', 'unidad_nombre': '',
                'tipo_stock': '', 'cantidad_total': 0.0, 'pedidos': []
            })
            for r in detalle_rows:
                key = (r['id_material'], r['tipo_stock'])
                totales[key]['material_codigo'] = r['material_codigo']
                totales[key]['material_nombre'] = r['material_nombre']
                totales[key]['unidad_nombre']   = r['unidad_nombre'] or ''
                totales[key]['tipo_stock']       = r['tipo_stock']
                totales[key]['cantidad_total']  += float(r['cantidad'])
                totales[key]['pedidos'].append({
                    'nro_pedido': r['nro_pedido'],
                    'cantidad':   float(r['cantidad'])
                })

            # Construir líneas del informe
            lineas = []
            for (mid, ts), t in totales.items():
                st = stock_map.get((mid, str(ts or '').lower()), {'stock_disponible': 0.0, 'stock_entrando': 0.0})
                diferencia = st['stock_disponible'] - t['cantidad_total']
                lineas.append({
                    'id_material':      mid,
                    'material_codigo':  t['material_codigo'],
                    'material_nombre':  t['material_nombre'],
                    'unidad_nombre':    t['unidad_nombre'],
                    'tipo_stock':       ts,
                    'cantidad_total':   t['cantidad_total'],
                    'stock_disponible': st['stock_disponible'],
                    'stock_entrando':   st['stock_entrando'],
                    'diferencia':       diferencia,
                    'ok':               diferencia >= 0,
                    'pedidos':          t['pedidos'],
                })
            lineas.sort(key=lambda x: (x['ok'], x['material_codigo'], x['tipo_stock']))

            total_ok       = sum(1 for l in lineas if l['ok'])
            total_faltante = len(lineas) - total_ok

            return jsonify({
                "status": "ok",
                "pedidos":         pedidos,
                "lineas":          lineas,
                "total_ok":        total_ok,
                "total_faltante":  total_faltante,
                "fecha":           datetime.now().strftime('%d/%m/%Y %H:%M'),
            })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


@pedidos_bp.route('/pedidos/preparar_masivo', methods=['POST'])
def preparar_masivo():
    ids = _ids((request.get_json(silent=True) or {}).get('ids'))
    if not ids:
        return jsonify({"status": "error", "message": "No hay pedidos seleccionados"}), 400

    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = (f"UPDATE pedidos_cabecera SET estado = 'Trabajo' "
                   f"WHERE id_pedido IN ({in_clause_sql(ids)}) AND estado = 'Pendiente' "
                   f"AND (%s IS NULL OR tenant_id = %s)")
            cursor.execute(sql, (*tuple(ids), tenant_id, tenant_id))
            conn.commit()
            return jsonify(
                {"status": "success", "message": f"{cursor.rowcount} pedidos pasaron a estado 'Trabajo'."})
    finally:
        conn.close()


@pedidos_bp.route('/pedidos/resumen_preparar', methods=['POST'])
def resumen_preparar():
    ids = _ids((request.get_json(silent=True) or {}).get('ids'))
    if not ids:
        return jsonify({"status": "error", "message": "No hay pedidos seleccionados"}), 400

    tenant_id = get_tenant_filter()
    ph = in_clause_sql(ids)
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT COUNT(DISTINCT p.id_pedido)   AS cant_pedidos,
                       COUNT(DISTINCT p.id_cliente)  AS cant_clientes,
                       COUNT(DISTINCT d.id_material) AS cant_materiales,
                       COALESCE(SUM(d.cantidad), 0)  AS total_unidades
                FROM pedidos_cabecera p
                LEFT JOIN pedidos_detalle d ON d.id_pedido = p.id_pedido
                WHERE p.id_pedido IN ({ph})
                  AND (%s IS NULL OR p.tenant_id = %s)
            """, (*tuple(ids), tenant_id, tenant_id))
            row = cursor.fetchone()

            # Ubicaciones de picking con stock disponible para los materiales pedidos
            cursor.execute(f"""
                SELECT COUNT(DISTINCT sc.Ubicacion) AS cant_ubicaciones
                FROM pedidos_detalle d
                JOIN stockcontable sc ON sc.Material = d.id_material
                    AND sc.StockDisponible > 0
                JOIN ubicaciones u    ON sc.Ubicacion = u.id
                JOIN tipoubicacion tu ON u.tipoubicacion = tu.id
                    AND tu.soporte_picking = 1
                WHERE d.id_pedido IN ({ph})
                  AND (%s IS NULL OR sc.tenant_id = %s)
            """, (*tuple(ids), tenant_id, tenant_id))
            row_ubi = cursor.fetchone()

        return jsonify({
            "status": "ok",
            "cant_pedidos":    int(row['cant_pedidos']),
            "cant_clientes":   int(row['cant_clientes']),
            "cant_materiales": int(row['cant_materiales']),
            "total_unidades":  float(row['total_unidades']),
            "cant_ubicaciones":int(row_ubi['cant_ubicaciones'])
        })
    finally:
        conn.close()

# ============================================================================
# AJAX: Cambio masivo de ruta y/o transporte
# ============================================================================
@pedidos_bp.route('/pedidos/cambiar_ruta_transporte', methods=['POST'])
def cambiar_ruta_transporte():
    data         = request.get_json(silent=True) or {}
    ids          = _ids(data.get('ids'))
    id_ruta      = data.get('id_ruta')      # None = sin cambio
    id_transporte= data.get('id_transporte') # None = sin cambio
    tenant_id    = get_tenant_filter()

    if not ids:
        return jsonify({"status": "error", "message": "No hay pedidos seleccionados"}), 400
    if id_ruta is None and id_transporte is None:
        return jsonify({"status": "error", "message": "Debe seleccionar al menos un campo a modificar"}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            campos, valores = [], []
            if id_ruta is not None:
                campos.append("id_ruta = %s")
                valores.append(_referencia(cursor, 'rutas', 'id_ruta', 'nombre_ruta', id_ruta, tenant_id, 'Ruta'))
            if id_transporte is not None:
                campos.append("id_transporte = %s")
                valores.append(_referencia(cursor, 'transportes', 'id_transporte', 'razonsocial', id_transporte,
                                           tenant_id, 'Transporte'))

            # Un pedido despachado o anulado ya no cambia de ruta ni de transporte
            ph = in_clause_sql(ids)
            cursor.execute(
                f"UPDATE pedidos_cabecera SET {', '.join(campos)} WHERE id_pedido IN ({ph}) "
                f"AND estado NOT IN (%s, %s) AND (%s IS NULL OR tenant_id = %s)",
                (*valores, *ids, *ESTADOS_FINALES, tenant_id, tenant_id)
            )
            actualizados = cursor.rowcount
            cursor.execute(
                f"SELECT COUNT(*) AS n FROM pedidos_cabecera WHERE id_pedido IN ({ph}) "
                f"AND estado IN (%s, %s) AND (%s IS NULL OR tenant_id = %s)",
                (*ids, *ESTADOS_FINALES, tenant_id, tenant_id)
            )
            omitidos = cursor.fetchone()['n']
            conn.commit()
            mensaje = f"{actualizados} pedido(s) actualizados."
            if omitidos:
                mensaje += f" {omitidos} no se modificaron por estar despachados o anulados."
            return jsonify({"status": "success", "message": mensaje, "updated": actualizados})
    except DatoInvalido as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": f"No se pudo aplicar el cambio: {e!s}"}), 500
    finally:
        conn.close()


# ============================================================================
# AJAX: Buscar contenedores disponibles para pedidos (solo ubicaciones de picking)
# ============================================================================
@pedidos_bp.route('/pedidos/buscar_contenedores')
def buscar_contenedores():
    q    = request.args.get('q',    '').strip()
    ubi  = request.args.get('ubi',  '').strip()
    tipo = request.args.get('tipo', '').strip()
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # f-string: sin él, {quote(...)} llegaba tal cual a la base y la consulta fallaba siempre
            sql = f"""
                SELECT sc.IDContenedor,
                       u.id              AS ubicacion_id,
                       u.codigo          AS ubicacion_codigo,
                       u.descipcion      AS ubicacion_nombre,
                       tu.id             AS tipo_id,
                       tu.{quote('descripcion')}     AS tipo_nombre,
                       SUM(sc.StockDisponible) AS total_disponible
                FROM stockcontable sc
                JOIN ubicaciones u    ON sc.Ubicacion    = u.id
                JOIN tipoubicacion tu ON u.tipoubicacion = tu.id
                WHERE sc.IDContenedor LIKE %s
                  AND tu.soporte_picking = 1
                  AND (%s IS NULL OR u.tenant_id = %s)
            """
            params = [f'%{q}%', tenant_id, tenant_id]
            if ubi:
                sql += " AND (u.codigo LIKE %s OR u.descipcion LIKE %s)"
                params += [f'%{ubi}%', f'%{ubi}%']
            if tipo:
                sql += " AND tu.id = %s"
                params.append(_id(tipo))
            sql += f"""
                GROUP BY sc.IDContenedor, sc.Ubicacion, u.id, u.codigo, u.descipcion, tu.id, tu.{quote('descripcion')}
                HAVING SUM(sc.StockDisponible) > 0
                   AND SUM(sc.StockSaliendo)   = 0
                   AND SUM(sc.StockEntrando)   = 0
                ORDER BY u.codigo, sc.IDContenedor
                {limit_sql(30)}
            """
            cursor.execute(sql, params)
            filas = [dict(r) for r in cursor.fetchall()]
            for r in filas:
                r['total_disponible'] = float(r['total_disponible'] or 0)
            return jsonify(filas)
    finally:
        conn.close()


# ============================================================================
# AJAX: Filtros en cascada para selección de contenedores
# ============================================================================
@pedidos_bp.route('/pedidos/filtros/zonas')
def filtros_zonas():
    tenant_id = session.get('tenant_id')
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, codigo, nombre FROM zonas WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s) ORDER BY codigo", (tenant_id, tenant_id))
            return jsonify(cursor.fetchall())
    finally:
        conn.close()


@pedidos_bp.route('/pedidos/filtros/tipos')
def filtros_tipos():
    zona = request.args.get('zona', '').strip()
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = f"""
                SELECT DISTINCT tu.id, tu.{quote('descripcion')} AS nombre
                FROM tipoubicacion tu
                JOIN ubicaciones u ON u.tipoubicacion = tu.id
                WHERE tu.soporte_picking = 1
                  AND (%s IS NULL OR tu.tenant_id = %s)
            """
            params = [tenant_id, tenant_id]
            if zona:
                sql += " AND u.id_zona = %s"
                params.append(int(zona))
            sql += f" ORDER BY tu.{quote('descripcion')}"
            cursor.execute(sql, params)
            return jsonify(cursor.fetchall())
    finally:
        conn.close()


@pedidos_bp.route('/pedidos/filtros/ubicaciones')
def filtros_ubicaciones():
    tipo = request.args.get('tipo', '').strip()
    zona = request.args.get('zona', '').strip()
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT u.id, u.codigo, u.descipcion AS nombre
                FROM ubicaciones u
                JOIN tipoubicacion tu ON u.tipoubicacion = tu.id
                WHERE tu.soporte_picking = 1 AND u.activo = 1
                  AND (%s IS NULL OR u.tenant_id = %s)
            """
            params = [tenant_id, tenant_id]
            if tipo:
                sql += " AND u.tipoubicacion = %s"
                params.append(int(tipo))
            if zona:
                sql += " AND u.id_zona = %s"
                params.append(int(zona))
            sql += " ORDER BY u.codigo"
            cursor.execute(sql, params)
            return jsonify(cursor.fetchall())
    finally:
        conn.close()


@pedidos_bp.route('/pedidos/filtros/contenedores')
def filtros_contenedores():
    ubi  = request.args.get('ubi',  '').strip()
    tipo = request.args.get('tipo', '').strip()
    zona = request.args.get('zona', '').strip()
    tenant_id = get_tenant_filter()
    # Requiere al menos un filtro para evitar devolver miles de registros
    if not ubi and not tipo and not zona:
        return jsonify([])
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT sc.IDContenedor,
                       u.id           AS ubicacion_id,
                       u.codigo       AS ubicacion_codigo,
                       u.descipcion   AS ubicacion_nombre,
                       SUM(sc.StockDisponible) AS total_disponible
                FROM stockcontable sc
                JOIN ubicaciones u    ON sc.Ubicacion    = u.id
                JOIN tipoubicacion tu ON u.tipoubicacion = tu.id
                WHERE tu.soporte_picking = 1
                  AND sc.IDContenedor IS NOT NULL
                  AND sc.IDContenedor != ''
                  AND (%s IS NULL OR u.tenant_id = %s)
            """
            params = [tenant_id, tenant_id]
            if ubi:
                sql += " AND u.id = %s"
                params.append(int(ubi))
            if tipo:
                sql += " AND tu.id = %s"
                params.append(int(tipo))
            if zona:
                sql += " AND u.id_zona = %s"
                params.append(int(zona))
            sql += f"""
                GROUP BY sc.IDContenedor, sc.Ubicacion, u.id, u.codigo, u.descipcion
                HAVING SUM(sc.StockDisponible) > 0
                   AND SUM(sc.StockSaliendo)   = 0
                   AND SUM(sc.StockEntrando)   = 0
                ORDER BY u.codigo, sc.IDContenedor
                {limit_sql(300)}
            """
            cursor.execute(sql, params)
            return jsonify(cursor.fetchall())
    finally:
        conn.close()


# ============================================================================
# AJAX: Stock de un contenedor en ubicación de picking (para auto-rellenar materiales)
# ============================================================================
@pedidos_bp.route('/pedidos/contenedor_stock')
def contenedor_stock():
    contenedor = request.args.get('id_contenedor', '').strip().upper()
    if not contenedor:
        return jsonify({"status": "error", "message": "Contenedor requerido"}), 400

    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT sc.Material AS id_material,
                       m.codigo AS material_codigo,
                       m.nombre AS material_nombre,
                       sc.TipoStock AS tipo_stock,
                       sc.StockDisponible AS cantidad,
                       sc.Lote,
                       u.id AS id_ubicacion,
                       u.codigo AS ubicacion_codigo
                FROM stockcontable sc
                JOIN materiales m      ON sc.Material    = m.id
                JOIN ubicaciones u     ON sc.Ubicacion   = u.id
                JOIN tipoubicacion tu  ON u.tipoubicacion = tu.id
                WHERE sc.IDContenedor = %s
                  AND sc.StockDisponible > 0
                  AND sc.StockSaliendo = 0
                  AND sc.StockEntrando = 0
                  AND tu.soporte_picking = 1
                  AND (%s IS NULL OR u.tenant_id = %s)
                ORDER BY m.codigo
            """, (contenedor, tenant_id, tenant_id))
            rows = cursor.fetchall()
            if not rows:
                return jsonify({"status": "empty", "message": "El contenedor no tiene stock disponible en ubicaciones de picking o tiene movimientos pendientes."})
            for r in rows:
                r['cantidad'] = float(r['cantidad'])
            return jsonify({"status": "ok", "items": rows})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


# ============================================================================
# GENERACIÓN DE JSON DE PICKING
# ============================================================================
def _picking_serial(obj):
    """Serializador para tipos no serializables por defecto en JSON."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


@pedidos_bp.route('/pedidos/picking_json', methods=['POST'])
def picking_json():
    """
    Genera el documento JSON de picking para los pedidos seleccionados.
    Incluye: cabecera+detalle de pedidos, ubicaciones soporte_picking=1
    con stock de los materiales pedidos, y el stock en esas ubicaciones.
    Guarda el archivo en picking_docs/YYYY-MM/ y lo devuelve como descarga.
    """
    data_req  = request.get_json(silent=True) or {}
    ids       = _ids(data_req.get('ids'))
    modo      = data_req.get('modo', 'directa')
    tenant_id = get_tenant_filter()

    if not ids:
        return jsonify({"status": "error", "message": "No hay pedidos seleccionados"}), 400

    ph = in_clause_sql(ids)
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # ── 1. Cabecera de pedidos ────────────────────────────────────
            cursor.execute(f"""
                SELECT p.id_pedido, p.nro_pedido, p.fecha_pedido, p.estado,
                       p.direccion_entrega, p.observaciones,
                       c.codigo  AS cliente_codigo,
                       c.razonsocial AS cliente_nombre,
                       r.nombre_ruta,
                       t.razonsocial AS transporte_nombre,
                       cp.nombre AS clase_nombre
                FROM pedidos_cabecera p
                JOIN clientes c       ON p.id_cliente   = c.id_cliente
                LEFT JOIN rutas r     ON p.id_ruta      = r.id_ruta
                LEFT JOIN transportes t ON p.id_transporte = t.id_transporte
                LEFT JOIN clases_pedido cp ON p.id_clase = cp.id_clase
                WHERE p.id_pedido IN ({ph})
                  AND (%s IS NULL OR p.tenant_id = %s)
                ORDER BY p.nro_pedido
            """, (*tuple(ids), tenant_id, tenant_id))
            pedidos_cab = cursor.fetchall()

            # ── 2. Detalle de pedidos ─────────────────────────────────────
            cursor.execute(f"""
                SELECT d.id_pedido, d.id_material, d.cantidad, d.tipo_stock,
                       m.codigo AS material_codigo, m.nombre AS material_nombre,
                       un.nombre AS unidad_nombre
                FROM pedidos_detalle d
                JOIN materiales m ON d.id_material = m.id
                LEFT JOIN unidades_medida un ON m.unidad_medida_id = un.id_unidad
                WHERE d.id_pedido IN ({ph})
                  AND (%s IS NULL OR d.tenant_id = %s)
                ORDER BY d.id_pedido, m.codigo
            """, (*tuple(ids), tenant_id, tenant_id))
            detalle_rows = cursor.fetchall()

        material_ids = list({r['id_material'] for r in detalle_rows})

        # Agrupa detalle por pedido
        detalle_map = defaultdict(list)
        for r in detalle_rows:
            detalle_map[r['id_pedido']].append({
                'id_material':     r['id_material'],
                'material_codigo': r['material_codigo'],
                'material_nombre': r['material_nombre'],
                'unidad_nombre':   r['unidad_nombre'] or '',
                'cantidad':        float(r['cantidad'] or 0),
                'tipo_stock':      r['tipo_stock'],
            })

        pedidos_list = []
        for p in pedidos_cab:
            ped = dict(p)
            ped['detalle'] = detalle_map.get(p['id_pedido'], [])
            pedidos_list.append(ped)

        ubicaciones_list = []
        stock_list       = []

        if material_ids:
            ph2 = in_clause_sql(material_ids)
            with conn.cursor() as cursor:
                # ── 3. Ubicaciones picking con stock de los materiales ────
                cursor.execute(f"""
                    SELECT DISTINCT
                           u.id, u.codigo, u.descipcion AS descripcion,
                           tu.{quote('descripcion')} AS tipo_ubicacion,
                           tu.id AS id_tipo,
                           z.codigo AS zona_codigo, z.nombre AS zona_nombre,
                           u.orden_picking
                    FROM stockcontable sc
                    JOIN ubicaciones u    ON sc.Ubicacion    = u.id
                    JOIN tipoubicacion tu ON u.tipoubicacion = tu.id
                    LEFT JOIN zonas z     ON u.id_zona       = z.id
                    WHERE sc.Material IN ({ph2})
                      AND sc.StockDisponible > 0
                      AND tu.soporte_picking = 1
                      AND (%s IS NULL OR u.tenant_id = %s)
                    ORDER BY u.orden_picking, u.codigo
                """, (*tuple(material_ids), tenant_id, tenant_id))
                ubicaciones_list = [dict(r) for r in cursor.fetchall()]

                # ── 4. Stock en esas ubicaciones para los materiales pedidos
                ubi_ids = [u['id'] for u in ubicaciones_list]
                if ubi_ids:
                    ph3 = in_clause_sql(ubi_ids)
                    cursor.execute(f"""
                        SELECT sc.Ubicacion     AS id_ubicacion,
                               u.codigo         AS ubicacion_codigo,
                               u.descipcion     AS ubicacion_descripcion,
                               sc.Material      AS id_material,
                               m.codigo         AS material_codigo,
                               m.nombre         AS material_nombre,
                               sc.IDContenedor  AS id_contenedor,
                               sc.Lote          AS lote,
                               sc.TipoStock     AS tipo_stock,
                               sc.StockTotal    AS stock_total,
                               sc.StockDisponible AS stock_disponible,
                               sc.FechaVencimiento AS fecha_vencimiento
                        FROM stockcontable sc
                        JOIN ubicaciones u ON sc.Ubicacion = u.id
                        JOIN materiales m  ON sc.Material  = m.id
                        WHERE sc.Material  IN ({ph2})
                          AND sc.Ubicacion IN ({ph3})
                          AND sc.StockDisponible > 0
                          AND (%s IS NULL OR sc.tenant_id = %s)
                        ORDER BY u.orden_picking, u.codigo, m.codigo
                    """, tuple(material_ids) + tuple(ubi_ids) + (tenant_id, tenant_id))
                    for r in cursor.fetchall():
                        row = dict(r)
                        row['stock_total']      = float(row['stock_total']      or 0)
                        row['stock_disponible'] = float(row['stock_disponible'] or 0)
                        stock_list.append(row)

        # ── Armar documento ───────────────────────────────────────────────
        ahora   = datetime.now()
        usuario = session.get('nombre', 'sistema')

        documento = {
            "tarea_picking": {
                "fecha_generacion": ahora.strftime('%Y-%m-%d %H:%M:%S'),
                "modo":     modo,
                "usuario":  usuario,
                "tenant_id": tenant_id,
                "ids_pedidos": [int(i) for i in ids],
            },
            "pedidos":             pedidos_list,
            "ubicaciones_picking": ubicaciones_list,
            "stock_picking":       stock_list,
        }

        # ── Guardar en picking_docs/YYYY-MM/ ─────────────────────────────
        mes_dir  = ahora.strftime('%Y-%m')
        pick_dir = os.path.join(current_app.root_path, 'picking_docs', mes_dir)
        os.makedirs(pick_dir, exist_ok=True)
        filename = f"picking_{ahora.strftime('%Y%m%d_%H%M%S')}_{modo}.json"
        filepath = os.path.join(pick_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as fh:
            json.dump(documento, fh, ensure_ascii=False, indent=2, default=_picking_serial)

        # ── Devolver como descarga ────────────────────────────────────────
        json_str = json.dumps(documento, ensure_ascii=False, indent=2, default=_picking_serial)
        return Response(
            json_str,
            mimetype='application/json',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


# ============================================================================
# IMPORTAR PEDIDOS
# ============================================================================
_CAMPOS_IMPORT_PED = [
    'agrupador', 'cliente_codigo', 'fecha_pedido', 'observaciones',
    'material_codigo', 'cantidad', 'tipo_stock'
]
_EJEMPLO_IMPORT_PED = [
    'IMPORT-2024-001', 'CLI001', '2024-01-15', 'Importación masiva',
    'MAT001', '50', 'Libre Venta'
]


@pedidos_bp.route('/pedidos/importar', methods=['POST'])
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
        anio = datetime.now().year
        tenant_id = get_tenant_filter()

        for agrupador, filas in grupos.items():
            # Cada grupo es un pedido: se verifica entero antes de guardar nada, y se guarda todo o nada
            fila_cabecera, primera = filas[0]
            cliente_cod   = str(primera.get('cliente_codigo', '') or '').strip()
            observaciones = str(primera.get('observaciones', '') or '').strip() or None
            errores_grupo, id_pedido = [], None
            try:
                if not cliente_cod:
                    raise DatoInvalido('cliente_codigo es obligatorio')
                fecha_pedido = _fecha(str(primera.get('fecha_pedido', '') or '').strip() or datetime.now().strftime('%Y-%m-%d'))
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id_cliente FROM clientes WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)", (cliente_cod, tenant_id, tenant_id))
                    cliente = cursor.fetchone()
                    if not cliente:
                        raise DatoInvalido(f'Cliente "{cliente_cod}" no encontrado')
                    id_cliente = _referencia(cursor, 'clientes', 'id_cliente', 'razonsocial', cliente['id_cliente'],
                                             tenant_id, 'Cliente', obligatorio=True)

                    renglones = []
                    for fila_num, row in filas:
                        material_cod = str(row.get('material_codigo', '') or '').strip()
                        if not material_cod:
                            continue
                        try:
                            cursor.execute("SELECT id FROM materiales WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)", (material_cod, tenant_id, tenant_id))
                            mat = cursor.fetchone()
                            if not mat:
                                raise DatoInvalido(f'Material "{material_cod}" no encontrado')
                            _renglon(cursor, mat['id'], row.get('cantidad'), row.get('tipo_stock'), tenant_id, renglones)
                        except DatoInvalido as e:
                            errores_grupo.append({'fila': fila_num, 'codigo': agrupador, 'razon': str(e)})
                    if not renglones and not errores_grupo:
                        errores_grupo.append({'fila': fila_cabecera, 'codigo': agrupador,
                                              'razon': 'Ninguna línea de material válida'})
                    if errores_grupo:
                        errores.extend(errores_grupo)
                        continue

                    id_pedido = execute_insert(cursor, """
                        INSERT INTO pedidos_cabecera
                            (nro_pedido, id_cliente, fecha_pedido, observaciones, estado, tenant_id)
                        VALUES (%s, %s, %s, %s, 'Pendiente', %s)
                    """, (_numero_siguiente(cursor, tenant_id, anio), id_cliente, fecha_pedido, observaciones, tenant_id))
                    for r in renglones:
                        cursor.execute(
                            "INSERT INTO pedidos_detalle (id_pedido, id_material, cantidad, tipo_stock, tenant_id) VALUES (%s, %s, %s, %s, %s)",
                            (id_pedido, r['id_material'], r['cantidad'], r['tipo_stock'], tenant_id))
                    insertados += 1
            except DatoInvalido as e:
                errores.append({'fila': fila_cabecera, 'codigo': agrupador, 'razon': str(e)})
            except Exception as e:
                # Lo que se haya llegado a guardar de este grupo no queda
                if id_pedido:
                    with conn.cursor() as cursor:
                        cursor.execute("DELETE FROM pedidos_detalle WHERE id_pedido = %s", (id_pedido,))
                        cursor.execute("DELETE FROM pedidos_cabecera WHERE id_pedido = %s", (id_pedido,))
                errores.append({'fila': fila_cabecera, 'codigo': agrupador, 'razon': str(e)})

        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

    return jsonify({'insertados': insertados, 'omitidos': [], 'errores': errores})


@pedidos_bp.route('/pedidos/plantilla/<formato>')
def plantilla(formato):
    if formato == 'csv':
        return plantilla_csv(_CAMPOS_IMPORT_PED, _EJEMPLO_IMPORT_PED, 'plantilla_pedidos.csv')
    elif formato == 'json':
        return plantilla_json(_CAMPOS_IMPORT_PED, _EJEMPLO_IMPORT_PED, 'plantilla_pedidos.json')
    elif formato == 'xlsx':
        return plantilla_xlsx(_CAMPOS_IMPORT_PED, _EJEMPLO_IMPORT_PED, 'plantilla_pedidos.xlsx')
    return 'Formato no válido', 400
