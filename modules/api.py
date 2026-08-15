"""API REST /api/v1 para integraciones con sistemas externos (Fase 5.2).

Autenticación: header `Authorization: Bearer <token>`. El token se genera por
tenant desde el panel admin y se guarda como hash sha256 en `tenants.api_token`
(taurus_admin). Todos los endpoints quedan acotados al tenant del token.

Endpoints:
  GET  /api/v1/materiales[/<codigo>]         catálogo de materiales
  GET  /api/v1/ubicaciones                   catálogo de ubicaciones
  GET  /api/v1/stock                         stock por posición
  GET  /api/v1/recepciones[/<numero>]        recepciones
  GET  /api/v1/pedidos                       pedidos
  GET  /api/v1/omcs                          órdenes de movimiento (OMC)
  POST /api/v1/recepciones                   alta de recepción (+ items)
  POST /api/v1/recepciones/<numero>/agregar-item
  POST /api/v1/recepciones/<numero>/cerrar   cierra recepción (genera stock+OMC)
  POST /api/v1/omcs/<numero>/confirmar       pasa StockEntrando a Disponible
"""

import datetime
import hashlib
import json
from decimal import Decimal
from functools import wraps

from flask import Blueprint, g, jsonify, request

from modules.auditoria import registrar_movimiento
from modules.db_config import _get_admin_connection, get_db_connection
from modules.sql_dialect import (
    cast_as_int,
    execute_insert,
    limit_sql,
    quote,
    substring_index,
    upsert_incremental_sql,
)
from modules.sql_dialect import year as year_func

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

_MAX_LIMITE = 500


def _hash_token(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _serializable(valor):
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, (datetime.datetime, datetime.date, datetime.time)):
        return valor.isoformat()
    return valor


def _filas_json(filas):
    return [{k: _serializable(v) for k, v in fila.items()} for fila in filas]


def _error(mensaje, codigo=400):
    return jsonify({'ok': False, 'error': mensaje}), codigo


def _limite_param():
    try:
        limite = int(request.args.get('limite', 100))
    except (TypeError, ValueError):
        limite = 100
    return min(max(limite, 1), _MAX_LIMITE)


def _bool_param(nombre, default=True):
    valor = request.args.get(nombre)
    if valor is None:
        return default
    return valor.strip().lower() in ('1', 'true', 'si', 'yes')


def _requiere_token(f):
    """Exige `Authorization: Bearer <token>` y resuelve el tenant en `g`."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return _error('Falta el header Authorization: Bearer <token>', 401)
        token = auth[len('Bearer '):].strip()
        if not token:
            return _error('Token vacío', 401)
        try:
            conn = _get_admin_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, codigo, nombre, activo FROM tenants WHERE api_token = %s",
                (_hash_token(token),)
            )
            tenant = cursor.fetchone()
            cursor.close()
            conn.close()
        except Exception as e:
            return _error(f'Error interno de autenticación: {e!s}', 500)
        if not tenant:
            return _error('Token inválido', 401)
        if not tenant['activo']:
            return _error('El tenant está desactivado', 403)
        g.tenant_id = tenant['id']
        g.tenant_codigo = tenant['codigo']
        g.tenant_nombre = tenant['nombre']
        return f(*args, **kwargs)

    return wrapper


# ============================================================================
# CATÁLOGOS (lectura)
# ============================================================================
@api_bp.route('/materiales')
@_requiere_token
def materiales_listar():
    q = request.args.get('q', '').strip()
    activo = request.args.get('activo')
    tenant_id = g.tenant_id
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            condiciones = ["(%s IS NULL OR m.tenant_id = %s)"]
            params = [tenant_id, tenant_id]
            if q:
                like = f'%{q}%'
                condiciones.append("(m.codigo LIKE %s OR m.nombre LIKE %s "
                                    "OR COALESCE(m.codigo_barras, '') LIKE %s)")
                params += [like, like, like]
            if activo is not None:
                condiciones.append("m.activo = %s")
                params.append(1 if _bool_param('activo', True) else 0)
            where = ' AND '.join(condiciones)
            cursor.execute(f"""
                SELECT m.id, m.codigo, m.codigo_barras, m.nombre, m.descripcion,
                       m.trazabilidad, m.metodo_picking, m.stock_minimo,
                       m.stock_maximo, m.costo_promedio, m.ultimo_costo, m.activo,
                       un.nombre AS unidad_nombre
                FROM materiales m
                LEFT JOIN unidades_medida un ON m.unidad_medida_id = un.id_unidad
                WHERE {where}
                ORDER BY m.codigo
                {limit_sql(_limite_param())}
            """, params)
            filas = cursor.fetchall()
        return jsonify({'ok': True, 'total': len(filas), 'items': _filas_json(filas)})
    finally:
        conn.close()


@api_bp.route('/materiales/<codigo>')
@_requiere_token
def materiales_detalle(codigo):
    tenant_id = g.tenant_id
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT m.id, m.codigo, m.codigo_barras, m.nombre, m.descripcion,
                       m.trazabilidad, m.metodo_picking, m.stock_minimo,
                       m.stock_maximo, m.costo_promedio, m.ultimo_costo, m.activo,
                       un.nombre AS unidad_nombre
                FROM materiales m
                LEFT JOIN unidades_medida un ON m.unidad_medida_id = un.id_unidad
                WHERE (m.codigo = %s OR COALESCE(m.codigo_barras, '') = %s)
                  AND (%s IS NULL OR m.tenant_id = %s)
                {limit_sql(1)}
            """, (codigo, codigo, tenant_id, tenant_id))
            mat = cursor.fetchone()
        if not mat:
            return _error(f'Material "{codigo}" no encontrado', 404)
        return jsonify({'ok': True, 'material': _filas_json([mat])[0]})
    finally:
        conn.close()


@api_bp.route('/ubicaciones')
@_requiere_token
def ubicaciones_listar():
    q = request.args.get('q', '').strip()
    tipo = request.args.get('tipo', '').strip()
    tenant_id = g.tenant_id
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            condiciones = ["(%s IS NULL OR u.tenant_id = %s)"]
            params = [tenant_id, tenant_id]
            if q:
                like = f'%{q}%'
                condiciones.append("(u.codigo LIKE %s OR u.descipcion LIKE %s OR u.nombre LIKE %s)")
                params += [like, like, like]
            if tipo:
                condiciones.append(f"t.{quote('descripcion')} LIKE %s")
                params.append(f'%{tipo}%')
            where = ' AND '.join(condiciones)
            cursor.execute(f"""
                SELECT u.id, u.codigo, u.descipcion AS nombre,
                       t.{quote('descripcion')} AS tipo, u.zona, u.activo,
                       u.disponible_entrada, u.disponible_salida
                FROM ubicaciones u
                JOIN tipoubicacion t ON u.tipoubicacion = t.id
                WHERE {where}
                ORDER BY u.codigo
                {limit_sql(_limite_param())}
            """, params)
            filas = cursor.fetchall()
        return jsonify({'ok': True, 'total': len(filas), 'items': _filas_json(filas)})
    finally:
        conn.close()


@api_bp.route('/stock')
@_requiere_token
def stock_listar():
    ubicacion = request.args.get('ubicacion', '').strip()
    material = request.args.get('material', '').strip()
    lote = request.args.get('lote', '').strip()
    tipo_stock = request.args.get('tipo_stock', '').strip()
    solo_saldos = _bool_param('todos', True)
    tenant_id = g.tenant_id
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            condiciones = ["(%s IS NULL OR s.tenant_id = %s)"]
            params = [tenant_id, tenant_id]
            if ubicacion:
                condiciones.append("u.codigo = %s")
                params.append(ubicacion)
            if material:
                condiciones.append("(m.codigo = %s OR COALESCE(m.codigo_barras, '') = %s)")
                params += [material, material]
            if lote:
                condiciones.append("s.Lote = %s")
                params.append(lote)
            if tipo_stock:
                condiciones.append("s.TipoStock = %s")
                params.append(tipo_stock)
            if solo_saldos:
                condiciones.append("(s.StockTotal <> 0 OR s.StockDisponible <> 0 "
                                   "OR s.StockEntrando <> 0 OR s.StockSaliendo <> 0)")
            where = ' AND '.join(condiciones)
            cursor.execute(f"""
                SELECT u.codigo AS ubicacion_codigo, m.codigo AS material_codigo,
                       m.nombre AS material_nombre, s.Lote, s.TipoStock,
                       s.IDContenedor, s.FechaVencimiento,
                       s.StockTotal, s.StockDisponible, s.StockEntrando, s.StockSaliendo,
                       s.UltimoMovimiento, s.UsuarioUltimoMov
                FROM stockcontable s
                JOIN ubicaciones u ON s.Ubicacion = u.id
                JOIN materiales m ON s.Material = m.id
                WHERE {where}
                ORDER BY u.codigo, m.codigo, s.Lote
                {limit_sql(_limite_param())}
            """, params)
            filas = cursor.fetchall()
        return jsonify({'ok': True, 'total': len(filas), 'items': _filas_json(filas)})
    finally:
        conn.close()


@api_bp.route('/recepciones')
@_requiere_token
def recepciones_listar():
    estado = request.args.get('estado', '').strip()
    proveedor = request.args.get('proveedor', '').strip()
    tenant_id = g.tenant_id
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            condiciones = ["(%s IS NULL OR r.tenant_id = %s)"]
            params = [tenant_id, tenant_id]
            if estado:
                condiciones.append("r.estado = %s")
                params.append(estado)
            if proveedor:
                condiciones.append("(p.codigo = %s OR p.razonsocial LIKE %s)")
                params += [proveedor, f'%{proveedor}%']
            where = ' AND '.join(condiciones)
            cursor.execute(f"""
                SELECT r.id_recepcion, r.numero, r.estado, r.fecha_recepcion,
                       r.fecha_cierre, r.id_contenedor, r.observaciones,
                       p.codigo AS proveedor_codigo, p.razonsocial AS proveedor_nombre,
                       ur.codigo AS ubicacion_recep_codigo,
                       ud.codigo AS ubicacion_destino_codigo,
                       (SELECT COUNT(*) FROM recepciones_detalle d
                        WHERE d.id_recepcion = r.id_recepcion) AS total_items,
                       (SELECT COALESCE(SUM(d.cantidad_recibida), 0) FROM recepciones_detalle d
                        WHERE d.id_recepcion = r.id_recepcion) AS total_unidades
                FROM recepciones_cabecera r
                JOIN proveedores p ON r.id_proveedor = p.id
                JOIN ubicaciones ur ON r.id_ubicacion_recep = ur.id
                LEFT JOIN ubicaciones ud ON r.id_ubicacion_destino = ud.id
                WHERE {where}
                ORDER BY r.id_recepcion DESC
                {limit_sql(_limite_param())}
            """, params)
            filas = cursor.fetchall()
        return jsonify({'ok': True, 'total': len(filas), 'items': _filas_json(filas)})
    finally:
        conn.close()


@api_bp.route('/recepciones/<numero>')
@_requiere_token
def recepciones_detalle(numero):
    tenant_id = g.tenant_id
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT r.*, p.codigo AS proveedor_codigo, p.razonsocial AS proveedor_nombre,
                       ur.codigo AS ubicacion_recep_codigo,
                       ud.codigo AS ubicacion_destino_codigo
                FROM recepciones_cabecera r
                JOIN proveedores p ON r.id_proveedor = p.id
                JOIN ubicaciones ur ON r.id_ubicacion_recep = ur.id
                LEFT JOIN ubicaciones ud ON r.id_ubicacion_destino = ud.id
                WHERE r.numero = %s AND (%s IS NULL OR r.tenant_id = %s)
                {limit_sql(1)}
            """, (numero, tenant_id, tenant_id))
            recepcion = cursor.fetchone()
            if not recepcion:
                return _error(f'Recepción "{numero}" no encontrada', 404)
            cursor.execute("""
                SELECT d.id_detalle, d.lote, d.fecha_vencimiento, d.cantidad_esperada,
                       d.cantidad_recibida, d.tipo_stock, d.observaciones,
                       m.codigo AS material_codigo, m.nombre AS material_nombre,
                       mp.codigo_referencia_prov
                FROM recepciones_detalle d
                JOIN materiales m ON d.id_material = m.id
                LEFT JOIN material_proveedor mp
                       ON mp.id_material = m.id AND mp.id_proveedor = %s
                WHERE d.id_recepcion = %s AND (%s IS NULL OR d.tenant_id = %s)
                ORDER BY d.id_detalle
            """, (recepcion['id_proveedor'], recepcion['id_recepcion'], tenant_id, tenant_id))
            items = cursor.fetchall()
        data = _filas_json([recepcion])[0]
        data['items'] = _filas_json(items)
        return jsonify({'ok': True, 'recepcion': data})
    finally:
        conn.close()


@api_bp.route('/pedidos')
@_requiere_token
def pedidos_listar():
    estado = request.args.get('estado', '').strip()
    tenant_id = g.tenant_id
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            condiciones = ["(%s IS NULL OR p.tenant_id = %s)"]
            params = [tenant_id, tenant_id]
            if estado:
                condiciones.append("p.estado = %s")
                params.append(estado)
            where = ' AND '.join(condiciones)
            cursor.execute(f"""
                SELECT p.id_pedido, p.nro_pedido, p.fecha_pedido, p.estado,
                       p.direccion_entrega, p.observaciones, p.fecha_despacho,
                       c.codigo AS cliente_codigo, c.razonsocial AS cliente_nombre,
                       r.nombre_ruta, t.codigo AS transporte_codigo,
                       t.razonsocial AS transporte_nombre
                FROM pedidos_cabecera p
                JOIN clientes c ON p.id_cliente = c.id_cliente
                LEFT JOIN rutas r ON p.id_ruta = r.id_ruta
                LEFT JOIN transportes t ON p.id_transporte = t.id_transporte
                WHERE {where}
                ORDER BY p.fecha_pedido DESC, p.id_pedido DESC
                {limit_sql(_limite_param())}
            """, params)
            filas = cursor.fetchall()
        return jsonify({'ok': True, 'total': len(filas), 'items': _filas_json(filas)})
    finally:
        conn.close()


@api_bp.route('/omcs')
@_requiere_token
def omcs_listar():
    estado = request.args.get('estado', '').strip()
    tenant_id = g.tenant_id
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            condiciones = ["(%s IS NULL OR o.tenant_id = %s)"]
            params = [tenant_id, tenant_id]
            if estado:
                condiciones.append("o.estado = %s")
                params.append(estado)
            where = ' AND '.join(condiciones)
            cursor.execute(f"""
                SELECT o.id_omc, o.numero, o.estado, o.fecha_creacion,
                       o.fecha_confirmacion, o.id_contenedor,
                       uo.codigo AS origen_codigo, ud.codigo AS destino_codigo,
                       r.numero AS recepcion_numero, p.nro_pedido AS pedido_numero
                FROM omc o
                JOIN ubicaciones uo ON o.id_ubicacion_origen = uo.id
                JOIN ubicaciones ud ON o.id_ubicacion_destino = ud.id
                LEFT JOIN recepciones_cabecera r ON o.id_recepcion = r.id_recepcion
                LEFT JOIN pedidos_cabecera p ON o.id_pedido = p.id_pedido
                WHERE {where}
                ORDER BY o.id_omc DESC
                {limit_sql(_limite_param())}
            """, params)
            filas = cursor.fetchall()
        return jsonify({'ok': True, 'total': len(filas), 'items': _filas_json(filas)})
    finally:
        conn.close()


# ============================================================================
# OPERACIONES DE STOCK (escritura)
# ============================================================================
def _buscar_material(cursor, codigo, tenant_id):
    cursor.execute(f"""
        SELECT id, codigo, activo FROM materiales
        WHERE (codigo = %s OR COALESCE(codigo_barras, '') = %s)
          AND (%s IS NULL OR tenant_id = %s)
        ORDER BY id {limit_sql(1)}
    """, (codigo, codigo, tenant_id, tenant_id))
    return cursor.fetchone()


def _buscar_ubicacion(cursor, codigo, tenant_id):
    cursor.execute(f"""
        SELECT id, codigo, activo FROM ubicaciones
        WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)
        ORDER BY id {limit_sql(1)}
    """, (codigo, tenant_id, tenant_id))
    return cursor.fetchone()


@api_bp.route('/recepciones', methods=['POST'])
@_requiere_token
def recepciones_crear():
    d = request.get_json(silent=True) or {}
    proveedor_cod = str(d.get('proveedor_codigo', '') or '').strip()
    ubic_recep_cod = str(d.get('ubicacion_recep_codigo', '') or '').strip()
    ubic_dest_cod = str(d.get('ubicacion_destino_codigo', '') or '').strip()
    observaciones = str(d.get('observaciones', '') or '').strip() or None
    items = d.get('items') or []

    if not proveedor_cod:
        return _error('proveedor_codigo es obligatorio')
    if not ubic_recep_cod:
        return _error('ubicacion_recep_codigo es obligatorio')
    if not isinstance(items, list):
        return _error('items debe ser una lista')

    tenant_id = g.tenant_id
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM proveedores WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)",
                           (proveedor_cod, tenant_id, tenant_id))
            prov = cursor.fetchone()
            if not prov:
                return _error(f'Proveedor "{proveedor_cod}" no encontrado', 404)
            ubic_recep = _buscar_ubicacion(cursor, ubic_recep_cod, tenant_id)
            if not ubic_recep:
                return _error(f'Ubicación de recepción "{ubic_recep_cod}" no encontrada', 404)
            id_dest = None
            if ubic_dest_cod:
                dest = _buscar_ubicacion(cursor, ubic_dest_cod, tenant_id)
                if not dest:
                    return _error(f'Ubicación destino "{ubic_dest_cod}" no encontrada', 404)
                id_dest = dest['id']

            anio = datetime.datetime.now().year
            expr = cast_as_int(substring_index('numero', '-', -1))
            cursor.execute(
                f"SELECT MAX({expr}) AS max_seq "
                f"FROM recepciones_cabecera WHERE {year_func('fecha_recepcion')} = %s "
                f"AND (%s IS NULL OR tenant_id = %s)",
                (anio, tenant_id, tenant_id)
            )
            seq = (cursor.fetchone()['max_seq'] or 0) + 1
            numero = f'REC-{anio}-{seq:05d}'

            id_recepcion = execute_insert(cursor, """
                INSERT INTO recepciones_cabecera
                    (numero, id_proveedor, id_ubicacion_recep, id_ubicacion_destino,
                     id_contenedor, observaciones, usuario_creacion, tenant_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (numero, prov['id'], ubic_recep['id'], id_dest, '',
                  observaciones, 'API', tenant_id))
            contenedor = f'RC{id_recepcion:05d}'
            cursor.execute(
                "UPDATE recepciones_cabecera SET id_contenedor = %s WHERE id_recepcion = %s "
                "AND (%s IS NULL OR tenant_id = %s)",
                (contenedor, id_recepcion, tenant_id, tenant_id)
            )

            errores, insertados = [], 0
            for i, item in enumerate(items, 1):
                material_cod = str(item.get('material_codigo', '') or '').strip()
                if not material_cod:
                    errores.append({'item': i, 'error': 'material_codigo es obligatorio'})
                    continue
                try:
                    cantidad = float(item.get('cantidad') or 0)
                except (TypeError, ValueError):
                    errores.append({'item': i, 'material': material_cod,
                                    'error': 'cantidad inválida'})
                    continue
                if cantidad <= 0:
                    errores.append({'item': i, 'material': material_cod,
                                    'error': 'cantidad debe ser mayor a 0'})
                    continue
                mat = _buscar_material(cursor, material_cod, tenant_id)
                if not mat:
                    errores.append({'item': i, 'material': material_cod,
                                    'error': 'material no encontrado'})
                    continue
                if not mat['activo']:
                    errores.append({'item': i, 'material': material_cod,
                                    'error': 'material inactivo'})
                    continue
                cursor.execute("""
                    INSERT INTO recepciones_detalle
                        (id_recepcion, id_material, lote, fecha_vencimiento,
                         cantidad_esperada, cantidad_recibida, tipo_stock, tenant_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    id_recepcion, mat['id'],
                    str(item.get('lote', '') or '').strip() or 'UNICO',
                    str(item.get('fecha_vencimiento', '') or '').strip() or None,
                    cantidad, cantidad,
                    str(item.get('tipo_stock', '') or '').strip() or 'Libre Venta',
                    tenant_id
                ))
                insertados += 1

            if insertados == 0:
                conn.rollback()
                return _error('Ningún ítem válido para crear la recepción: ' +
                              json.dumps(errores, ensure_ascii=False))

            conn.commit()
        return jsonify({'ok': True, 'id_recepcion': id_recepcion, 'numero': numero,
                        'contenedor': contenedor,
                        'items_insertados': insertados, 'errores': errores})
    finally:
        conn.close()


@api_bp.route('/recepciones/<numero>/agregar-item', methods=['POST'])
@_requiere_token
def recepciones_agregar_item(numero):
    d = request.get_json(silent=True) or {}
    material_cod = str(d.get('material_codigo', '') or '').strip()
    lote = str(d.get('lote', '') or '').strip() or 'UNICO'
    fecha_venc = str(d.get('fecha_vencimiento', '') or '').strip() or None
    tipo_stock = str(d.get('tipo_stock', '') or '').strip() or 'Libre Venta'
    id_detalle = d.get('id_detalle')

    if not material_cod and not id_detalle:
        return _error('material_codigo es obligatorio (o id_detalle para actualizar)')
    try:
        cantidad = float(d.get('cantidad') or 0)
    except (TypeError, ValueError):
        return _error('cantidad inválida')
    if cantidad <= 0:
        return _error('cantidad debe ser mayor a 0')

    tenant_id = g.tenant_id
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id_recepcion, estado FROM recepciones_cabecera "
                "WHERE numero = %s AND (%s IS NULL OR tenant_id = %s)",
                (numero, tenant_id, tenant_id)
            )
            rec = cursor.fetchone()
            if not rec:
                return _error(f'Recepción "{numero}" no encontrada', 404)
            if rec['estado'].upper() != 'ABIERTA':
                return _error('La recepción no está en estado Abierta', 409)

            if id_detalle:
                cursor.execute("""
                    UPDATE recepciones_detalle
                    SET cantidad_esperada = %s, cantidad_recibida = %s, lote = %s,
                        fecha_vencimiento = %s, tipo_stock = %s
                    WHERE id_detalle = %s AND id_recepcion = %s
                      AND (%s IS NULL OR tenant_id = %s)
                """, (cantidad, cantidad, lote, fecha_venc, tipo_stock,
                      id_detalle, rec['id_recepcion'], tenant_id, tenant_id))
                if cursor.rowcount == 0:
                    return _error('Ítem no encontrado en la recepción', 404)
            else:
                mat = _buscar_material(cursor, material_cod, tenant_id)
                if not mat:
                    return _error(f'Material "{material_cod}" no encontrado', 404)
                if not mat['activo']:
                    return _error(f'Material "{material_cod}" inactivo', 409)
                id_detalle = execute_insert(cursor, """
                    INSERT INTO recepciones_detalle
                        (id_recepcion, id_material, lote, fecha_vencimiento,
                         cantidad_esperada, cantidad_recibida, tipo_stock, tenant_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (rec['id_recepcion'], mat['id'], lote, fecha_venc,
                      cantidad, cantidad, tipo_stock, tenant_id))
            conn.commit()
        return jsonify({'ok': True, 'id_detalle': id_detalle, 'numero': numero})
    finally:
        conn.close()


@api_bp.route('/recepciones/<numero>/cerrar', methods=['POST'])
@_requiere_token
def recepciones_cerrar(numero):
    d = request.get_json(silent=True) or {}
    tenant_id = g.tenant_id
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM recepciones_cabecera "
                "WHERE numero = %s AND estado = 'Abierta' AND (%s IS NULL OR tenant_id = %s)",
                (numero, tenant_id, tenant_id)
            )
            recepcion = cursor.fetchone()
            if not recepcion:
                return _error(f'Recepción "{numero}" no existe o no está Abierta', 404)

            id_ubicacion_destino = None
            dest_cod = str(d.get('ubicacion_destino_codigo', '') or '').strip()
            if dest_cod:
                dest = _buscar_ubicacion(cursor, dest_cod, tenant_id)
                if not dest:
                    return _error(f'Ubicación destino "{dest_cod}" no encontrada', 404)
                id_ubicacion_destino = dest['id']
            if not id_ubicacion_destino:
                id_ubicacion_destino = recepcion.get('id_ubicacion_destino')
            if not id_ubicacion_destino:
                return _error('Debe indicar ubicacion_destino_codigo (o fijarla al crear la recepción)', 400)

            cursor.execute("""
                SELECT * FROM recepciones_detalle
                WHERE id_recepcion = %s AND cantidad_recibida > 0
                  AND (%s IS NULL OR tenant_id = %s)
            """, (recepcion['id_recepcion'], tenant_id, tenant_id))
            items = cursor.fetchall()
            if not items:
                return _error('No hay ítems con cantidad recibida para cerrar', 409)

            contenedor = recepcion['id_contenedor']
            ahora = datetime.datetime.now()
            usuario = 'API'
            cols_stock = ['Ubicacion', 'Material', 'Lote', 'TipoStock', 'IDContenedor',
                          'StockTotal', 'StockDisponible', 'StockEntrando', 'StockSaliendo',
                          'UltimaEntrada', 'UltimoMovimiento', 'FechaVencimiento',
                          'UsuarioUltimoMov', 'tenant_id']

            for item in items:
                sql_saliendo = upsert_incremental_sql('stockcontable', cols_stock,
                                                      ['Ubicacion', 'Material', 'IDContenedor'],
                                                      ['StockSaliendo'],
                                                      ['UltimoMovimiento', 'UsuarioUltimoMov'])
                cursor.execute(sql_saliendo, (
                    recepcion['id_ubicacion_recep'], item['id_material'], item['lote'],
                    item['tipo_stock'], contenedor, 0, 0, 0, item['cantidad_recibida'],
                    None, ahora, item['fecha_vencimiento'], usuario, tenant_id
                ))
                registrar_movimiento(
                    conn, tenant_id=tenant_id, accion='API_RECEPCION', usuario=usuario,
                    modulo='api', id_ubicacion=recepcion['id_ubicacion_recep'],
                    id_material=item['id_material'], id_contenedor=contenedor,
                    lote=item['lote'], tipo_stock=item['tipo_stock'],
                    cantidad=-item['cantidad_recibida'],
                    detalle=f"Stock saliendo al cerrar recepción {recepcion['numero']}")
                sql_entrando = upsert_incremental_sql('stockcontable', cols_stock,
                                                      ['Ubicacion', 'Material', 'IDContenedor'],
                                                      ['StockEntrando'],
                                                      ['UltimoMovimiento', 'UsuarioUltimoMov'])
                cursor.execute(sql_entrando, (
                    id_ubicacion_destino, item['id_material'], item['lote'],
                    item['tipo_stock'], contenedor, 0, 0, item['cantidad_recibida'], 0,
                    None, ahora, item['fecha_vencimiento'], usuario, tenant_id
                ))
                registrar_movimiento(
                    conn, tenant_id=tenant_id, accion='API_RECEPCION', usuario=usuario,
                    modulo='api', id_ubicacion=id_ubicacion_destino,
                    id_material=item['id_material'], id_contenedor=contenedor,
                    lote=item['lote'], tipo_stock=item['tipo_stock'],
                    cantidad=item['cantidad_recibida'],
                    detalle=f"Stock entrando al cerrar recepción {recepcion['numero']}")

            anio_omc = ahora.year
            expr_omc = cast_as_int(substring_index('numero', '-', -1))
            cursor.execute(
                f"SELECT MAX({expr_omc}) AS max_seq "
                f"FROM omc WHERE {year_func('fecha_creacion')} = %s "
                f"AND (%s IS NULL OR tenant_id = %s)",
                (anio_omc, tenant_id, tenant_id)
            )
            seq_omc = (cursor.fetchone()['max_seq'] or 0) + 1
            numero_omc = f'OMC-{anio_omc}-{seq_omc:05d}'

            id_omc = execute_insert(cursor, """
                INSERT INTO omc
                    (numero, id_contenedor, id_ubicacion_origen, id_ubicacion_destino,
                     id_recepcion, estado, observaciones, usuario_creacion, fecha_creacion, tenant_id)
                VALUES (%s, %s, %s, %s, %s, 'Pendiente', %s, %s, %s, %s)
            """, (numero_omc, contenedor, recepcion['id_ubicacion_recep'],
                  id_ubicacion_destino, recepcion['id_recepcion'],
                  f'Generada al cerrar recepción {recepcion["numero"]} (API)', usuario,
                  ahora, tenant_id))
            cursor.execute("""
                INSERT INTO omc_contenedores
                    (id_omc, id_contenedor, id_contenedor_destino, id_ubicacion_origen)
                VALUES (%s, %s, NULL, %s)
            """, (id_omc, contenedor, recepcion['id_ubicacion_recep']))

            cursor.execute("""
                UPDATE recepciones_cabecera
                SET estado = 'Cerrada', fecha_cierre = %s,
                    usuario_cierre = %s, id_ubicacion_destino = %s
                WHERE id_recepcion = %s AND (%s IS NULL OR tenant_id = %s)
            """, (ahora, usuario, id_ubicacion_destino,
                  recepcion['id_recepcion'], tenant_id, tenant_id))
            conn.commit()
        return jsonify({'ok': True, 'numero': numero, 'numero_omc': numero_omc,
                        'id_omc': id_omc, 'items': len(items)})
    finally:
        conn.close()


@api_bp.route('/omcs/<numero>/confirmar', methods=['POST'])
@_requiere_token
def omcs_confirmar(numero):
    tenant_id = g.tenant_id
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM omc WHERE numero = %s AND estado = 'Pendiente' "
                "AND (%s IS NULL OR tenant_id = %s)",
                (numero, tenant_id, tenant_id)
            )
            omc = cursor.fetchone()
            if not omc:
                return _error(f'OMC "{numero}" no existe o no está Pendiente', 404)
            if not omc.get('id_recepcion') or omc.get('id_pedido'):
                return _error('Solo se pueden confirmar OMCs de recepción por la API', 409)

            ahora = datetime.datetime.now()
            usuario = 'API'
            cursor.execute("""
                SELECT Ubicacion, Material, Lote, TipoStock,
                       SUM(StockEntrando) AS cantidad
                FROM stockcontable
                WHERE IDContenedor = %s AND StockEntrando > 0
                  AND (%s IS NULL OR tenant_id = %s)
                GROUP BY Ubicacion, Material, Lote, TipoStock
            """, (omc['id_contenedor'], tenant_id, tenant_id))
            movimientos = cursor.fetchall()

            cursor.execute("""
                UPDATE stockcontable
                SET StockTotal       = StockTotal + StockEntrando,
                    StockDisponible  = StockDisponible + StockEntrando,
                    StockEntrando    = 0,
                    UltimaEntrada    = %s,
                    UltimoMovimiento = %s,
                    UsuarioUltimoMov = %s
                WHERE IDContenedor = %s AND StockEntrando > 0
                  AND (%s IS NULL OR tenant_id = %s)
            """, (ahora, ahora, usuario, omc['id_contenedor'], tenant_id, tenant_id))
            filas = cursor.rowcount

            for mov in movimientos:
                registrar_movimiento(
                    conn, tenant_id=tenant_id, accion='API_CONFIRMAR_OMC', usuario=usuario,
                    modulo='api', id_ubicacion=mov['Ubicacion'], id_material=mov['Material'],
                    id_contenedor=omc['id_contenedor'], lote=mov['Lote'],
                    tipo_stock=mov['TipoStock'], cantidad=mov['cantidad'],
                    detalle=f"Stock pasó a Disponible (OMC {numero})")

            cursor.execute("""
                UPDATE omc SET estado = 'Confirmada',
                    fecha_confirmacion = %s, usuario_confirmacion = %s
                WHERE id_omc = %s AND (%s IS NULL OR tenant_id = %s)
            """, (ahora, usuario, omc['id_omc'], tenant_id, tenant_id))
            cursor.execute("""
                UPDATE recepciones_cabecera SET estado = 'Confirmada'
                WHERE id_recepcion = %s AND estado = 'Cerrada'
                  AND (%s IS NULL OR tenant_id = %s)
            """, (omc['id_recepcion'], tenant_id, tenant_id))
            conn.commit()
        return jsonify({'ok': True, 'numero': numero, 'filas_stock': filas})
    finally:
        conn.close()
