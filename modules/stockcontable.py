from flask import Blueprint, render_template, request, jsonify, session
import datetime
from modules.batch_utils import (parse_file, export_csv, export_json, export_xlsx,
                                  plantilla_csv, plantilla_json, plantilla_xlsx,
                                  int_or_none, float_or_zero)
from modules.db_config import get_db_connection
from modules.sql_dialect import upsert_coalesce_sql

stockcontable_bp = Blueprint('stockcontable', __name__)


def get_tenant_filter():
    return session.get('tenant_id')


@stockcontable_bp.route('/stockcontable')
def listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT
                    sc.*,
                    u.codigo      AS ubicacion_codigo,
                    u.descipcion  AS ubicacion_descripcion,
                    m.codigo      AS material_codigo,
                    m.nombre      AS material_nombre
                FROM stockcontable sc
                LEFT JOIN ubicaciones u ON sc.Ubicacion = u.id
                LEFT JOIN materiales  m ON sc.Material  = m.id
                WHERE (%s IS NULL OR sc.tenant_id = %s)
                ORDER BY u.codigo, sc.IDContenedor, sc.TipoStock, sc.Lote
            """
            cursor.execute(sql, (tenant_id, tenant_id))
            stocks = cursor.fetchall()

            cursor.execute("""
                SELECT id, codigo, descipcion FROM ubicaciones 
                WHERE (%s IS NULL OR tenant_id = %s) 
                ORDER BY codigo
            """, (tenant_id, tenant_id))
            ubicaciones = cursor.fetchall()

            cursor.execute("""
                SELECT id, codigo, nombre FROM materiales 
                WHERE (%s IS NULL OR tenant_id = %s) 
                ORDER BY codigo
            """, (tenant_id, tenant_id))
            materiales = cursor.fetchall()

        return render_template(
            'stockcontable.html',
            stocks=stocks,
            ubicaciones=ubicaciones,
            materiales=materiales
        )
    finally:
        conn.close()


# -------------------------------------------------------------------
# Las siguientes funciones son de uso interno, llamadas desde los
# módulos de Ingresos, Pedidos, Ajustes y Movimientos internos.
# No exponen rutas HTTP propias.
# -------------------------------------------------------------------

def upsert_posicion(conn, ubicacion_id, material_id, contenedor,
                    lote='UNICO', tipo_stock='Libre Venta',
                    delta_total=0, delta_disponible=0,
                    delta_entrando=0, delta_saliendo=0,
                    ultima_entrada=None, ultima_salida=None,
                    ultimo_movimiento=None, fecha_vencimiento=None,
                    usuario_ultimo_mov=None, tenant_id=None):
    """
    Inserta o actualiza una posición de stock contable.
    Clave única: (Ubicacion, Material, IDContenedor).
    Los deltas se suman al stock existente.
    """
    cols = ['Ubicacion', 'Material', 'IDContenedor', 'Lote', 'TipoStock',
            'StockTotal', 'StockDisponible', 'StockEntrando', 'StockSaliendo',
            'UltimaEntrada', 'UltimaSalida', 'UltimoMovimiento', 'UsuarioUltimoMov',
            'FechaVencimiento', 'tenant_id']
    increment = ['StockTotal', 'StockDisponible', 'StockEntrando', 'StockSaliendo']
    coalesce = ['UltimaEntrada', 'UltimaSalida', 'UltimoMovimiento', 'UsuarioUltimoMov', 'FechaVencimiento']
    sql = upsert_coalesce_sql('stockcontable', cols, ['Ubicacion', 'Material', 'IDContenedor'], increment, coalesce)
    with conn.cursor() as cursor:
        cursor.execute(sql, (
            ubicacion_id, material_id, contenedor,
            lote, tipo_stock,
            delta_total, delta_disponible, delta_entrando, delta_saliendo,
            ultima_entrada, ultima_salida, ultimo_movimiento, usuario_ultimo_mov,
            fecha_vencimiento, tenant_id
        ))


@stockcontable_bp.route('/stockcontable/editar/<int:stock_id>', methods=['POST'])
def editar(stock_id):
    tenant_id = get_tenant_filter()
    data = request.get_json()
    if not data:
        return jsonify({'ok': False, 'error': 'Sin datos'}), 400

    tipo_stock       = data.get('tipo_stock', '').strip()
    lote             = data.get('lote', '').strip()
    fecha_venc_str   = data.get('fecha_vencimiento', '').strip()

    tipos_validos = {'Libre Venta', 'Calidad', 'Bloqueado', 'Mal Estado'}
    if tipo_stock not in tipos_validos:
        return jsonify({'ok': False, 'error': 'Tipo de stock inválido'}), 400
    if not lote:
        return jsonify({'ok': False, 'error': 'El lote no puede estar vacío'}), 400

    fecha_venc = None
    if fecha_venc_str:
        try:
            fecha_venc = datetime.datetime.strptime(fecha_venc_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'ok': False, 'error': 'Fecha de vencimiento inválida'}), 400

    usuario = session.get('username', 'sistema')
    ahora   = datetime.datetime.now()

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE stockcontable
                SET TipoStock        = %s,
                    Lote             = %s,
                    FechaVencimiento = %s,
                    UltimoMovimiento = %s,
                    UsuarioUltimoMov = %s
                WHERE ID = %s AND (%s IS NULL OR tenant_id = %s)
            """, (tipo_stock, lote, fecha_venc, ahora, usuario, stock_id, tenant_id, tenant_id))
        conn.commit()
        return jsonify({
            'ok': True,
            'tipo_stock':       tipo_stock,
            'lote':             lote,
            'fecha_vencimiento': fecha_venc.strftime('%d/%m/%Y') if fecha_venc else '-',
            'ultimo_movimiento': ahora.strftime('%d/%m/%Y %H:%M'),
            'usuario':          usuario
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()

# ── Batch ─────────────────────────────────────────────────────────────────────
_CAMPOS_EXPORT = ['ubicacion_codigo', 'ubicacion_descripcion', 'material_codigo', 'material_nombre',
                  'IDContenedor', 'Lote', 'TipoStock', 'FechaVencimiento',
                  'StockTotal', 'StockDisponible', 'StockEntrando', 'StockSaliendo',
                  'UltimaEntrada', 'UltimaSalida', 'UltimoMovimiento', 'UsuarioUltimoMov']
_CAMPOS_IMPORT = ['ubicacion_codigo', 'material_codigo', 'IDContenedor',
                  'Lote', 'TipoStock', 'StockTotal', 'StockDisponible', 'FechaVencimiento']
_EJEMPLO_IMPORT = ['UB-001', 'MAT001', 'CONT-001',
                   'LOTE-2024-01', 'Libre Venta', '100', '100', '2025-12-31']


@stockcontable_bp.route('/stockcontable/exportar/<formato>')
def exportar(formato):
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT u.codigo AS ubicacion_codigo, u.descipcion AS ubicacion_descripcion,
                       m.codigo AS material_codigo, m.nombre AS material_nombre,
                       sc.IDContenedor, sc.Lote, sc.TipoStock, sc.FechaVencimiento,
                       sc.StockTotal, sc.StockDisponible, sc.StockEntrando, sc.StockSaliendo,
                       sc.UltimaEntrada, sc.UltimaSalida, sc.UltimoMovimiento, sc.UsuarioUltimoMov
                FROM stockcontable sc
                LEFT JOIN ubicaciones u ON sc.Ubicacion = u.id
                LEFT JOIN materiales m ON sc.Material = m.id
                WHERE (%s IS NULL OR sc.tenant_id = %s)
                ORDER BY u.codigo, sc.IDContenedor
            """, (tenant_id, tenant_id))
            rows = cursor.fetchall()
    finally:
        conn.close()

    if formato == 'csv':
        return export_csv(rows, _CAMPOS_EXPORT, 'stock.csv')
    elif formato == 'json':
        return export_json(rows, _CAMPOS_EXPORT, 'stock.json')
    elif formato == 'xlsx':
        return export_xlsx(rows, _CAMPOS_EXPORT, 'stock.xlsx')
    return 'Formato no válido', 400


@stockcontable_bp.route('/stockcontable/importar', methods=['POST'])
def importar():
    """Carga inicial de stock. Inserta posiciones nuevas; omite duplicados (Ubicacion, Material, IDContenedor)."""
    file = request.files.get('archivo')
    if not file or not file.filename:
        return jsonify({'error': 'No se proporcionó archivo'}), 400
    try:
        rows = parse_file(file, request.form.get('hoja'))
    except Exception as e:
        return jsonify({'error': f'Error al leer el archivo: {str(e)}'}), 400

    usuario = session.get('nombre', 'sistema')
    ahora = datetime.datetime.now()
    tenant_id = get_tenant_filter()
    tipos_validos = {'Libre Venta', 'Calidad', 'Bloqueado', 'Mal Estado'}
    insertados, omitidos, errores = 0, [], []

    conn = get_db_connection()
    try:
        for i, row in enumerate(rows, 1):
            ub_cod = str(row.get('ubicacion_codigo', '') or '').strip()
            mat_cod = str(row.get('material_codigo', '') or '').strip()
            contenedor = str(row.get('IDContenedor', '') or '').strip()
            if not ub_cod or not mat_cod or not contenedor:
                errores.append({'fila': i, 'codigo': f'{ub_cod}/{mat_cod}',
                                'razon': 'ubicacion_codigo, material_codigo e IDContenedor son obligatorios'})
                continue
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id FROM ubicaciones WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)", (ub_cod, tenant_id, tenant_id))
                    ub_row = cursor.fetchone()
                    if not ub_row:
                        errores.append({'fila': i, 'codigo': ub_cod, 'razon': f'Ubicación "{ub_cod}" no encontrada'})
                        continue
                    cursor.execute("SELECT id FROM materiales WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)", (mat_cod, tenant_id, tenant_id))
                    mat_row = cursor.fetchone()
                    if not mat_row:
                        errores.append({'fila': i, 'codigo': mat_cod, 'razon': f'Material "{mat_cod}" no encontrado'})
                        continue

                    ub_id, mat_id = ub_row['id'], mat_row['id']

                    cursor.execute(
                        "SELECT ID FROM stockcontable WHERE Ubicacion=%s AND Material=%s AND IDContenedor=%s AND (%s IS NULL OR tenant_id = %s)",
                        (ub_id, mat_id, contenedor, tenant_id, tenant_id)
                    )
                    if cursor.fetchone():
                        omitidos.append(f'{ub_cod}/{mat_cod}/{contenedor}')
                        continue

                    tipo = str(row.get('TipoStock', '') or '').strip()
                    if tipo not in tipos_validos:
                        tipo = 'Libre Venta'

                    lote = str(row.get('Lote', '') or '').strip() or 'UNICO'
                    total = float_or_zero(row.get('StockTotal'))
                    disp = float_or_zero(row.get('StockDisponible'))

                    fecha_venc = None
                    fv_str = str(row.get('FechaVencimiento', '') or '').strip()
                    if fv_str:
                        try:
                            fecha_venc = datetime.datetime.strptime(fv_str[:10], '%Y-%m-%d').date()
                        except ValueError:
                            pass

                    cursor.execute("""
                        INSERT INTO stockcontable
                            (Ubicacion, Material, IDContenedor, Lote, TipoStock,
                             StockTotal, StockDisponible, StockEntrando, StockSaliendo,
                             UltimaEntrada, UltimoMovimiento, UsuarioUltimoMov, FechaVencimiento, tenant_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 0, 0, %s, %s, %s, %s, %s)
                    """, (ub_id, mat_id, contenedor, lote, tipo,
                          total, disp, ahora, ahora, usuario, fecha_venc, tenant_id))
                    insertados += 1
            except Exception as e:
                errores.append({'fila': i, 'codigo': f'{ub_cod}/{mat_cod}', 'razon': str(e)})
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()
    return jsonify({'insertados': insertados, 'omitidos': omitidos, 'errores': errores})


@stockcontable_bp.route('/stockcontable/plantilla/<formato>')
def plantilla(formato):
    if formato == 'csv':
        return plantilla_csv(_CAMPOS_IMPORT, _EJEMPLO_IMPORT, 'plantilla_stock.csv')
    elif formato == 'json':
        return plantilla_json(_CAMPOS_IMPORT, _EJEMPLO_IMPORT, 'plantilla_stock.json')
    elif formato == 'xlsx':
        return plantilla_xlsx(_CAMPOS_IMPORT, _EJEMPLO_IMPORT, 'plantilla_stock.xlsx')
    return 'Formato no válido', 400
