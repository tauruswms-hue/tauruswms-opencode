import datetime
import math

from flask import Blueprint, jsonify, render_template, request, session

from modules.auditoria import registrar_movimiento
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
from modules.sql_dialect import is_duplicate_key_error, upsert_coalesce_sql

stockcontable_bp = Blueprint('stockcontable', __name__)


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


TIPOS_STOCK = ('Libre Venta', 'Calidad', 'Bloqueado', 'Mal Estado')
LOTE_MAX = 100                    # largo de stockcontable.Lote
LOTE_UNICO = 'UNICO'
CONTENEDOR_MAX = 10               # largo de stockcontable.IDContenedor
CANTIDAD_MAX = 99999999999.9999   # mayor valor de las columnas decimal(15,4)


def _texto(valor):
    return str(valor).strip() if valor is not None else ''


def _tipo_stock(valor):
    """Tipo de stock válido (sin distinguir mayúsculas); vacío = Libre Venta."""
    texto = _texto(valor)
    if not texto:
        return 'Libre Venta'
    for tipo in TIPOS_STOCK:
        if tipo.lower() == texto.lower():
            return tipo
    raise DatoInvalido(f'Tipo de stock: "{texto}" no es válido (use {", ".join(TIPOS_STOCK[:-1])} o {TIPOS_STOCK[-1]}).')


def _lote(valor):
    lote = _texto(valor) or LOTE_UNICO
    if len(lote) > LOTE_MAX:
        raise DatoInvalido(f'Lote: admite hasta {LOTE_MAX} caracteres.')
    return lote


def _vencimiento(valor):
    """Fecha de vencimiento (AAAA-MM-DD; un XLSX la trae con hora) o None si está vacía."""
    texto = _texto(valor)[:10]
    if not texto:
        return None
    try:
        return datetime.datetime.strptime(texto, '%Y-%m-%d').date()
    except ValueError:
        raise DatoInvalido(f'Fecha de vencimiento: "{_texto(valor)}" no es una fecha válida (formato AAAA-MM-DD).') from None


def _cantidad(valor, rotulo):
    try:
        n = float(_texto(valor).replace(',', '.'))
    except ValueError:
        n = math.nan
    if not math.isfinite(n):
        raise DatoInvalido(f'{rotulo}: "{_texto(valor)}" no es un número válido.')
    if n < 0:
        raise DatoInvalido(f'{rotulo}: no puede ser negativo.')
    if n > CANTIDAD_MAX:
        raise DatoInvalido(f'{rotulo}: el valor es demasiado grande.')
    return n


def _fecha_texto(fecha):
    return fecha.strftime('%d/%m/%Y') if fecha else '-'


@stockcontable_bp.route('/stockcontable/editar/<int:stock_id>', methods=['POST'])
def editar(stock_id):
    """Cambia tipo de stock, lote y vencimiento de una posición (no las cantidades)."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'ok': False, 'error': 'Sin datos'}), 400
    try:
        tipo_stock = _tipo_stock(data.get('tipo_stock'))
        if not _texto(data.get('lote')):
            raise DatoInvalido('El lote no puede estar vacío.')
        lote = _lote(data.get('lote'))
        fecha_venc = _vencimiento(data.get('fecha_vencimiento'))
    except DatoInvalido as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

    tenant_id = get_tenant_filter()
    usuario = session.get('nombre', 'sistema')
    ahora = datetime.datetime.now()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT Ubicacion, Material, IDContenedor, TipoStock, Lote, FechaVencimiento,
                       StockEntrando, StockSaliendo, UltimoMovimiento, UsuarioUltimoMov
                FROM stockcontable
                WHERE ID = %s AND (%s IS NULL OR tenant_id = %s)
            """, (stock_id, tenant_id, tenant_id))
            posicion = cursor.fetchone()
            if not posicion:
                return jsonify({'ok': False, 'error': 'La posición de stock no existe.'}), 404
            if posicion['StockEntrando'] or posicion['StockSaliendo']:
                # Una OMC en curso la va a mover: lo que mueve tiene que llegar como salió
                return jsonify({'ok': False, 'error': f'El contenedor {posicion["IDContenedor"]} tiene una OMC en curso: '
                                                      'confirmala o anulala antes de editar la posición.'}), 400

            cambios = []
            if posicion['TipoStock'] != tipo_stock:
                cambios.append(f'tipo de stock {posicion["TipoStock"]} → {tipo_stock}')
            if posicion['Lote'] != lote:
                cambios.append(f'lote {posicion["Lote"]} → {lote}')
            if posicion['FechaVencimiento'] != fecha_venc:
                cambios.append(f'vencimiento {_fecha_texto(posicion["FechaVencimiento"])} → {_fecha_texto(fecha_venc)}')

            if cambios:
                cursor.execute("""
                    UPDATE stockcontable
                    SET TipoStock = %s, Lote = %s, FechaVencimiento = %s, UltimoMovimiento = %s, UsuarioUltimoMov = %s
                    WHERE ID = %s
                """, (tipo_stock, lote, fecha_venc, ahora, usuario, stock_id))
                registrar_movimiento(
                    conn, tenant_id=tenant_id, accion='AJUSTE', usuario=usuario,
                    modulo='stockcontable', id_ubicacion=posicion['Ubicacion'],
                    id_material=posicion['Material'], id_contenedor=posicion['IDContenedor'],
                    lote=lote, tipo_stock=tipo_stock,
                    detalle='Edición de posición: ' + '; '.join(cambios))
                conn.commit()
                ultimo, quien = ahora, usuario
            else:
                ultimo, quien = posicion['UltimoMovimiento'], posicion['UsuarioUltimoMov']
        return jsonify({
            'ok': True,
            'cambios': len(cambios),
            'tipo_stock': tipo_stock,
            'lote': lote,
            'fecha_vencimiento': _fecha_texto(fecha_venc),
            'ultimo_movimiento': ultimo.strftime('%d/%m/%Y %H:%M') if ultimo else '-',
            'usuario': quien or '-',
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': f'No se pudo guardar: {e!s}'}), 500
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
                   'LOTE-2024-01', 'Libre Venta', '100', '', '2027-12-31']


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


def _activo_por_codigo(cursor, tabla, codigo, tenant_id, rotulo):
    """Id de una ubicación o un material de la empresa, por código, que esté activo."""
    cursor.execute(f"SELECT id, activo FROM {tabla} WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)",
                   (codigo, tenant_id, tenant_id))
    fila = cursor.fetchone()
    if not fila:
        raise DatoInvalido(f'{rotulo} "{codigo}" no existe.')
    if not fila['activo']:
        raise DatoInvalido(f'{rotulo} "{codigo}" está inactiva.' if rotulo == 'La ubicación'
                           else f'{rotulo} "{codigo}" está inactivo.')
    return fila['id']


def _posicion_importada(cursor, row, tenant_id):
    """Datos verificados de una fila del archivo, o None si la posición ya existe (se omite).

    Las columnas se leen sin distinguir mayúsculas: el lector de archivos las pasa a minúsculas.
    """
    valor = {k.lower(): v for k, v in row.items()}.get
    ub_cod, mat_cod, contenedor = (_texto(valor(c)) for c in ('ubicacion_codigo', 'material_codigo', 'idcontenedor'))
    faltan = [c for c, v in (('ubicacion_codigo', ub_cod), ('material_codigo', mat_cod), ('IDContenedor', contenedor)) if not v]
    if faltan:
        raise DatoInvalido(f'Falta {", ".join(faltan)}: son obligatorios.')
    if len(contenedor) > CONTENEDOR_MAX:
        raise DatoInvalido(f'IDContenedor: admite hasta {CONTENEDOR_MAX} caracteres.')

    p = {'ubicacion_codigo': ub_cod, 'material_codigo': mat_cod, 'contenedor': contenedor,
         'lote': _lote(valor('lote')), 'tipo': _tipo_stock(valor('tipostock')),
         'vencimiento': _vencimiento(valor('fechavencimiento'))}
    if not _texto(valor('stocktotal')):
        raise DatoInvalido('StockTotal: es obligatorio.')
    p['total'] = _cantidad(valor('stocktotal'), 'StockTotal')
    if p['total'] <= 0:
        raise DatoInvalido('StockTotal: tiene que ser mayor que cero.')
    # Sin disponible informado, todo lo cargado queda disponible
    p['disponible'] = _cantidad(valor('stockdisponible'), 'StockDisponible') if _texto(valor('stockdisponible')) else p['total']
    if p['disponible'] > p['total']:
        raise DatoInvalido('StockDisponible: no puede ser mayor que StockTotal.')

    p['ubicacion'] = _activo_por_codigo(cursor, 'ubicaciones', ub_cod, tenant_id, 'La ubicación')
    p['material'] = _activo_por_codigo(cursor, 'materiales', mat_cod, tenant_id, 'El material')

    cursor.execute("""
        SELECT sc.Ubicacion, sc.Material, u.codigo FROM stockcontable sc
        LEFT JOIN ubicaciones u ON u.id = sc.Ubicacion
        WHERE sc.IDContenedor = %s AND (%s IS NULL OR sc.tenant_id = %s)
    """, (contenedor, tenant_id, tenant_id))
    for otra in cursor.fetchall():
        if otra['Ubicacion'] != p['ubicacion']:
            # Un contenedor está en un solo lugar
            raise DatoInvalido(f'El contenedor {contenedor} ya está en la ubicación {otra["codigo"]}.')
        if otra['Material'] == p['material']:
            return None
    return p


@stockcontable_bp.route('/stockcontable/importar', methods=['POST'])
def importar():
    """Carga inicial de stock: inserta posiciones nuevas y omite las que ya existen (Ubicacion, Material, IDContenedor).

    Cada fila es una posición independiente: las válidas se cargan y las demás se informan con su motivo.
    """
    file = request.files.get('archivo')
    if not file or not file.filename:
        return jsonify({'error': 'No se proporcionó archivo'}), 400
    try:
        rows = parse_file(file, request.form.get('hoja'))
    except Exception as e:
        return jsonify({'error': f'Error al leer el archivo: {e!s}'}), 400

    usuario = session.get('nombre', 'sistema')
    ahora = datetime.datetime.now()
    tenant_id = get_tenant_filter()
    insertados, omitidos, errores = 0, [], []

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            for i, row in enumerate(rows, 1):
                valor = {k.lower(): v for k, v in row.items()}.get
                codigo = '/'.join(_texto(valor(c)) for c in ('ubicacion_codigo', 'material_codigo', 'idcontenedor'))
                try:
                    p = _posicion_importada(cursor, row, tenant_id)
                    if p is None:
                        omitidos.append(codigo)
                        continue
                    cursor.execute("""
                        INSERT INTO stockcontable
                            (Ubicacion, Material, IDContenedor, Lote, TipoStock,
                             StockTotal, StockDisponible, StockEntrando, StockSaliendo,
                             UltimaEntrada, UltimoMovimiento, UsuarioUltimoMov, FechaVencimiento, tenant_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 0, 0, %s, %s, %s, %s, %s)
                    """, (p['ubicacion'], p['material'], p['contenedor'], p['lote'], p['tipo'],
                          p['total'], p['disponible'], ahora, ahora, usuario, p['vencimiento'], tenant_id))
                except DatoInvalido as e:
                    errores.append({'fila': i, 'codigo': codigo, 'razon': str(e)})
                    continue
                except Exception as e:
                    if is_duplicate_key_error(e):
                        omitidos.append(codigo)
                        continue
                    raise
                registrar_movimiento(
                    conn, tenant_id=tenant_id, accion='IMPORTACION', usuario=usuario,
                    modulo='stockcontable', id_ubicacion=p['ubicacion'], id_material=p['material'],
                    id_contenedor=p['contenedor'], lote=p['lote'], tipo_stock=p['tipo'],
                    cantidad=p['total'], detalle=f'Carga inicial de stock ({codigo})')
                insertados += 1
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'No se pudo importar: {e!s}'}), 500
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
