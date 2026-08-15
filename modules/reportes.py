"""Reportes por tenant (Fase 5.3) y auditoria de stock (Fase 5.4).

Pagina /reportes con secciones: stock actual, stock valorizado, movimientos
(auditoria sobre stock_movimientos), recepciones y pedidos. Todas las tablas
llevan filtro de tenancy (%s IS NULL OR tenant_id = %s). Exportaciones CSV,
XLSX (y JSON para stock) reutilizando modules/batch_utils.
"""

import datetime

from flask import Blueprint, render_template, request

from modules.batch_utils import export_csv, export_json, export_xlsx
from modules.context import get_tenant_filter
from modules.db_config import get_db_connection
from modules.sql_dialect import limit_sql

reportes_bp = Blueprint('reportes', __name__)


def _parse_fecha(valor):
    if not valor:
        return None
    try:
        return datetime.datetime.strptime(valor, '%Y-%m-%d').strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        return None


def _stock_posiciones(conn, tenant_id):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT sc.ID, sc.Ubicacion, sc.Material, sc.IDContenedor, sc.Lote,
                   sc.TipoStock, sc.FechaVencimiento, sc.StockTotal,
                   sc.StockDisponible, sc.StockEntrando, sc.StockSaliendo,
                   sc.UltimaEntrada, sc.UltimoMovimiento, sc.UsuarioUltimoMov,
                   u.codigo AS ubicacion_codigo,
                   m.codigo AS material_codigo, m.nombre AS material_nombre,
                   m.costo_promedio,
                   ROUND(sc.StockDisponible * COALESCE(m.costo_promedio, 0), 2) AS valor_posicion
            FROM stockcontable sc
            LEFT JOIN ubicaciones u ON sc.Ubicacion = u.id
            LEFT JOIN materiales m ON sc.Material = m.id
            WHERE (sc.StockTotal <> 0 OR sc.StockDisponible <> 0
                   OR sc.StockEntrando <> 0 OR sc.StockSaliendo <> 0)
              AND (%s IS NULL OR sc.tenant_id = %s)
            ORDER BY u.codigo, sc.IDContenedor, sc.TipoStock, sc.Lote
        """, (tenant_id, tenant_id))
        return cursor.fetchall()


def _stock_valorizado(conn, tenant_id):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT m.codigo AS material_codigo, m.nombre AS material_nombre,
                   m.costo_promedio,
                   SUM(sc.StockDisponible) AS cantidad_disponible,
                   SUM(sc.StockTotal)     AS cantidad_total,
                   ROUND(SUM(sc.StockDisponible * COALESCE(m.costo_promedio, 0)), 2) AS valor_total
            FROM stockcontable sc
            JOIN materiales m ON sc.Material = m.id
            WHERE (%s IS NULL OR sc.tenant_id = %s)
            GROUP BY m.id, m.codigo, m.nombre, m.costo_promedio
            HAVING SUM(sc.StockDisponible) <> 0
            ORDER BY valor_total DESC
        """, (tenant_id, tenant_id))
        return cursor.fetchall()


def _movimientos(conn, tenant_id, accion=None, id_ubicacion=None, id_material=None,
                 desde=None, hasta=None, limite=300):
    cond = []
    params = []
    if accion:
        cond.append('sm.accion = %s')
        params.append(accion)
    if id_ubicacion:
        cond.append('sm.id_ubicacion = %s')
        params.append(id_ubicacion)
    if id_material:
        cond.append('sm.id_material = %s')
        params.append(id_material)
    if desde:
        cond.append('sm.fecha >= %s')
        params.append(desde + ' 00:00:00')
    if hasta:
        cond.append('sm.fecha <= %s')
        params.append(hasta + ' 23:59:59')
    where = ' AND ' + ' AND '.join(cond) if cond else ''
    sql = f"""
        SELECT sm.*, u.codigo AS ubicacion_codigo,
               m.codigo AS material_codigo, m.nombre AS material_nombre
        FROM stock_movimientos sm
        LEFT JOIN ubicaciones u ON sm.id_ubicacion = u.id
        LEFT JOIN materiales m ON sm.id_material = m.id
        WHERE (%s IS NULL OR sm.tenant_id = %s){where}
        ORDER BY sm.fecha DESC, sm.id DESC
        {limit_sql(limite)}
    """
    with conn.cursor() as cursor:
        cursor.execute(sql, [tenant_id, tenant_id, *params])
        return cursor.fetchall()


def _recepciones(conn, tenant_id):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT r.id_recepcion, r.numero, r.estado, r.fecha_recepcion,
                   r.id_contenedor, r.observaciones,
                   p.razonsocial AS proveedor,
                   u.codigo AS ubicacion_recep,
                   (SELECT COUNT(*) FROM recepciones_detalle d
                     WHERE d.id_recepcion = r.id_recepcion) AS total_items,
                   (SELECT COALESCE(SUM(d.cantidad_recibida), 0) FROM recepciones_detalle d
                     WHERE d.id_recepcion = r.id_recepcion) AS total_unidades
            FROM recepciones_cabecera r
            LEFT JOIN proveedores p ON r.id_proveedor = p.id
            LEFT JOIN ubicaciones u ON r.id_ubicacion_recep = u.id
            WHERE (%s IS NULL OR r.tenant_id = %s)
            ORDER BY r.fecha_recepcion DESC
        """, (tenant_id, tenant_id))
        return cursor.fetchall()


def _pedidos(conn, tenant_id):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT p.id_pedido, p.nro_pedido, p.estado, p.fecha_pedido,
                   p.observaciones,
                   c.razonsocial AS cliente,
                   (SELECT COUNT(*) FROM pedidos_detalle d
                     WHERE d.id_pedido = p.id_pedido) AS total_items,
                   (SELECT COALESCE(SUM(d.cantidad), 0) FROM pedidos_detalle d
                     WHERE d.id_pedido = p.id_pedido) AS total_unidades
            FROM pedidos_cabecera p
            LEFT JOIN clientes c ON p.id_cliente = c.id_cliente
            WHERE (%s IS NULL OR p.tenant_id = %s)
            ORDER BY p.fecha_pedido DESC
        """, (tenant_id, tenant_id))
        return cursor.fetchall()


def _kpis(conn, tenant_id):
    kpis = {}
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*) AS total, estado FROM pedidos_cabecera
            WHERE (%s IS NULL OR tenant_id = %s)
            GROUP BY estado
        """, (tenant_id, tenant_id))
        kpis['pedidos_por_estado'] = {r['estado']: r['total'] for r in cursor.fetchall()}

        cursor.execute("""
            SELECT COUNT(*) AS total FROM pedidos_cabecera
            WHERE estado = 'Despachado' AND (%s IS NULL OR tenant_id = %s)
        """, (tenant_id, tenant_id))
        kpis['pedidos_despachados'] = cursor.fetchone()['total']

        cursor.execute("""
            SELECT ROUND(COALESCE(SUM(StockDisponible), 0), 2) AS total
            FROM stockcontable WHERE (%s IS NULL OR tenant_id = %s)
        """, (tenant_id, tenant_id))
        kpis['stock_total'] = cursor.fetchone()['total']

        cursor.execute("""
            SELECT TipoStock, ROUND(SUM(StockDisponible), 2) AS cantidad
            FROM stockcontable
            WHERE (%s IS NULL OR tenant_id = %s)
            GROUP BY TipoStock
        """, (tenant_id, tenant_id))
        kpis['stock_por_tipo'] = {r['TipoStock']: r['cantidad'] for r in cursor.fetchall()}

        cursor.execute("""
            SELECT COUNT(*) AS total FROM recepciones_cabecera
            WHERE estado = 'Abierta' AND (%s IS NULL OR tenant_id = %s)
        """, (tenant_id, tenant_id))
        kpis['recepciones_abiertas'] = cursor.fetchone()['total']

        cursor.execute("""
            SELECT COUNT(*) AS total FROM omc
            WHERE estado = 'Pendiente' AND (%s IS NULL OR tenant_id = %s)
        """, (tenant_id, tenant_id))
        kpis['omc_pendientes'] = cursor.fetchone()['total']

        cursor.execute("""
            SELECT ROUND(COALESCE(SUM(StockDisponible * COALESCE(m.costo_promedio, 0)), 0), 2) AS total
            FROM stockcontable sc
            JOIN materiales m ON sc.Material = m.id
            WHERE (%s IS NULL OR sc.tenant_id = %s)
        """, (tenant_id, tenant_id))
        kpis['stock_valorizado_total'] = cursor.fetchone()['total']

        cursor.execute("""
            SELECT accion, COUNT(*) AS total
            FROM stock_movimientos
            WHERE (%s IS NULL OR tenant_id = %s)
            GROUP BY accion
        """, (tenant_id, tenant_id))
        kpis['movimientos_por_accion'] = {r['accion']: r['total'] for r in cursor.fetchall()}
        kpis['movimientos_total'] = sum(int(v) for v in kpis['movimientos_por_accion'].values())
    return kpis


def _acciones_disponibles(conn, tenant_id):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT accion FROM stock_movimientos
            WHERE (%s IS NULL OR tenant_id = %s)
            ORDER BY accion
        """, (tenant_id, tenant_id))
        return [r['accion'] for r in cursor.fetchall()]


def _ubicaciones_catalog(conn, tenant_id):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT u.id, u.codigo
            FROM ubicaciones u
            WHERE (%s IS NULL OR u.tenant_id = %s)
            ORDER BY u.codigo
        """, (tenant_id, tenant_id))
        return cursor.fetchall()


def _materiales_catalog(conn, tenant_id):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT m.id, m.codigo, m.nombre
            FROM materiales m
            WHERE (%s IS NULL OR m.tenant_id = %s)
            ORDER BY m.codigo
        """, (tenant_id, tenant_id))
        return cursor.fetchall()


@reportes_bp.route('/reportes')
def listar():
    tenant_id = get_tenant_filter()
    accion = request.args.get('accion') or None
    id_ubicacion = request.args.get('id_ubicacion') or None
    id_material = request.args.get('id_material') or None
    desde = _parse_fecha(request.args.get('desde'))
    hasta = _parse_fecha(request.args.get('hasta'))

    conn = get_db_connection()
    try:
        filtros = {'accion': accion, 'id_ubicacion': id_ubicacion, 'id_material': id_material,
                   'desde': desde, 'hasta': hasta}
        movimientos = _movimientos(conn, tenant_id, accion=accion, id_ubicacion=id_ubicacion,
                                   id_material=id_material, desde=desde, hasta=hasta, limite=300)
        return render_template(
            'reportes.html',
            kpis=_kpis(conn, tenant_id),
            stock=_stock_posiciones(conn, tenant_id),
            valorizado=_stock_valorizado(conn, tenant_id),
            movimientos=movimientos,
            recepciones=_recepciones(conn, tenant_id),
            pedidos=_pedidos(conn, tenant_id),
            filtros=filtros,
            acciones=_acciones_disponibles(conn, tenant_id),
            ubicaciones=_ubicaciones_catalog(conn, tenant_id),
            materiales=_materiales_catalog(conn, tenant_id),
        )
    finally:
        conn.close()


@reportes_bp.route('/reportes/exportar/<tipo>/<formato>')
def exportar(tipo, formato):
    tenant_id = get_tenant_filter()
    if tipo == 'movimientos':
        accion = request.args.get('accion') or None
        id_ubicacion = request.args.get('id_ubicacion') or None
        id_material = request.args.get('id_material') or None
        desde = _parse_fecha(request.args.get('desde'))
        hasta = _parse_fecha(request.args.get('hasta'))
        filtros = {'accion': accion, 'id_ubicacion': id_ubicacion, 'id_material': id_material,
                   'desde': desde, 'hasta': hasta}
    else:
        filtros = {}

    conn = get_db_connection()
    try:
        if tipo == 'stock':
            columnas = ['IDContenedor', 'Ubicacion', 'Material', 'Lote', 'TipoStock',
                        'FechaVencimiento', 'StockTotal', 'StockDisponible', 'StockEntrando',
                        'StockSaliendo', 'UltimoMovimiento', 'valor_posicion']
            filas = _stock_posiciones(conn, tenant_id)
            nombre_archivo = 'stock_actual'
        elif tipo == 'valorizado':
            columnas = ['material_codigo', 'material_nombre', 'costo_promedio',
                        'cantidad_total', 'cantidad_disponible', 'valor_total']
            filas = _stock_valorizado(conn, tenant_id)
            nombre_archivo = 'stock_valorizado'
        elif tipo == 'movimientos':
            columnas = ['fecha', 'accion', 'usuario', 'modulo', 'ubicacion_codigo',
                        'material_codigo', 'id_contenedor', 'lote', 'tipo_stock', 'cantidad', 'detalle']
            filas = _movimientos(conn, tenant_id, limite=5000, **filtros)
            nombre_archivo = 'movimientos_stock'
        elif tipo == 'recepciones':
            columnas = ['numero', 'estado', 'fecha_recepcion', 'proveedor', 'id_contenedor',
                        'ubicacion_recep', 'total_items', 'total_unidades']
            filas = _recepciones(conn, tenant_id)
            nombre_archivo = 'recepciones'
        elif tipo == 'pedidos':
            columnas = ['nro_pedido', 'estado', 'fecha_pedido', 'cliente',
                        'total_items', 'total_unidades']
            filas = _pedidos(conn, tenant_id)
            nombre_archivo = 'pedidos'
        else:
            from flask import flash, redirect, url_for
            flash('Tipo de reporte no valido.', 'error')
            return redirect(url_for('reportes.listar'))

        if formato == 'csv':
            return export_csv(filas, columnas, nombre_archivo + '.csv')
        if formato == 'xlsx':
            return export_xlsx(filas, columnas, nombre_archivo + '.xlsx')
        if formato == 'json':
            return export_json(filas, columnas, nombre_archivo + '.json')
        from flask import flash, redirect, url_for
        flash('Formato no valido.', 'error')
        return redirect(url_for('reportes.listar'))
    finally:
        conn.close()
