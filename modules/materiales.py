import csv
import io
import json

import openpyxl
from dotenv import load_dotenv
from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from modules.batch_utils import (
    DatoInvalido,
    export_csv,
    export_json,
    export_xlsx,
    float_or_zero,
    int_or_none,
    parse_file,
)
from modules.context import get_tenant_filter
from modules.db_config import _get_admin_connection, get_db_connection
from modules.sql_dialect import cast_as_char, execute_insert, is_duplicate_key_error

load_dotenv()
materiales_bp = Blueprint('materiales', __name__)

PICKING_METODOS_LABELS = {
    'fifo': 'FIFO (Primero en entrar, primero en salir)',
    'lifo': 'LIFO (Último en entrar, primero en salir)',
    'fefo': 'FEFO (Próximo a vencer)',
    'libre': 'Picking Libre',
}


def _get_picking_metodos(tenant_id):
    """Devuelve la lista de métodos de picking habilitados para el tenant."""
    if not tenant_id:
        return list(PICKING_METODOS_LABELS.keys())
    conn = _get_admin_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT metodosdepicking FROM tenants WHERE id = %s", (tenant_id,))
            row = cursor.fetchone()
    finally:
        conn.close()
    if not row or not row.get('metodosdepicking'):
        return list(PICKING_METODOS_LABELS.keys())
    try:
        metodos = json.loads(row['metodosdepicking'])
    except Exception:
        metodos = row['metodosdepicking']
    if isinstance(metodos, str):
        metodos = [metodos]
    metodos = [m for m in metodos if m in PICKING_METODOS_LABELS]
    return metodos or list(PICKING_METODOS_LABELS.keys())


def _get_picking_metodo_default(tenant_id):
    """Devuelve el método de picking por defecto configurado para el tenant."""
    if not tenant_id:
        return 'libre'
    conn = _get_admin_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT metodo_picking_default FROM tenants WHERE id = %s", (tenant_id,))
            row = cursor.fetchone()
    finally:
        conn.close()
    default = (row.get('metodo_picking_default') or 'libre') if row else 'libre'
    return default if default in PICKING_METODOS_LABELS else 'libre'


def _metodo_picking_valido(metodo, default='libre', habilitados=None):
    """Método de picking a guardar: el pedido si está habilitado para el tenant; si no, el default."""
    habilitados = habilitados or list(PICKING_METODOS_LABELS)
    if metodo in habilitados:
        return metodo
    return default if default in habilitados else habilitados[0]


TRAZABILIDADES = ('ninguna', 'lote', 'serie')

# Tablas que guardan movimientos o existencias de un material: si alguna lo
# referencia, el material no se borra, se desactiva.
_USOS_MATERIAL = (
    ('stockcontable', 'Material'),
    ('stock_movimientos', 'id_material'),
    ('recepciones_detalle', 'id_material'),
    ('pedidos_detalle', 'id_material'),
    ('inventarios_detalle', 'id_material'),
)


def _numero(valor, rotulo, minimo=0.0):
    """Número de un campo del formulario (vacío = 0)."""
    try:
        n = float(valor or 0)
    except (TypeError, ValueError):
        raise DatoInvalido(f'{rotulo}: "{valor}" no es un número válido.') from None
    if n < minimo:
        raise DatoInvalido(f'{rotulo} no puede ser menor que {minimo:g}.')
    return n


def _id_del_tenant(cursor, tabla, columna_id, valor, tenant_id, rotulo):
    """Id de un registro de otra tabla (categoría, unidad, proveedor), verificando que sea del tenant."""
    try:
        valor = int(valor or 0)
    except (TypeError, ValueError):
        raise DatoInvalido(f'{rotulo}: valor inválido.') from None
    if not valor:
        return None
    cursor.execute(f"SELECT 1 AS ok FROM {tabla} WHERE {columna_id} = %s AND (%s IS NULL OR tenant_id = %s)",
                   (valor, tenant_id, tenant_id))
    if not cursor.fetchone():
        raise DatoInvalido(f'{rotulo}: el valor elegido no existe.')
    return valor


def validar_ean(barcode):
    if not barcode or not barcode.strip():
        return True, None
    barcode = barcode.strip()
    if not barcode.isdigit() or len(barcode) not in (8, 13):
        return False, 'El código de barras debe tener 8 (EAN-8) o 13 (EAN-13) dígitos numéricos.'
    es_ean8 = len(barcode) == 8
    digitos = [int(d) for d in barcode]
    suma = 0
    for i in range(len(digitos) - 1):
        peso = 3 if (i % 2 == 0 and es_ean8) or (i % 2 != 0 and not es_ean8) else 1
        suma += digitos[i] * peso
    check_calculado = (10 - (suma % 10)) % 10
    if check_calculado != digitos[-1]:
        return False, 'El código de barras tiene un dígito verificador inválido.'
    return True, None


def validar_gtin14(barcode):
    if not barcode or not barcode.strip():
        return True, None
    barcode = barcode.strip()
    if not barcode.isdigit() or len(barcode) != 14:
        return False, 'El GTIN-14 debe tener exactamente 14 dígitos numéricos.'
    digitos = [int(d) for d in barcode]
    suma = 0
    for i in range(13):
        peso = 3 if i % 2 == 0 else 1
        suma += digitos[i] * peso
    check_calculado = (10 - (suma % 10)) % 10
    if check_calculado != digitos[13]:
        return False, 'El GTIN-14 tiene un dígito verificador inválido.'
    return True, None


@materiales_bp.route('/materiales')
def listar():
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql_mat = """
                SELECT m.*, c.nombre as categoria_nombre,
                       p.razonsocial as proveedor_habitual,
                       u.nombre as unidad_medida_nombre, u.simbolo as unidad_medida_simbolo
                FROM materiales m
                LEFT JOIN categorias c ON m.categoria_id = c.id_categoria AND (%s IS NULL OR c.tenant_id = %s)
                LEFT JOIN material_proveedor mp ON mp.id_material = m.id AND mp.es_habitual = 1 AND (%s IS NULL OR mp.tenant_id = %s)
                LEFT JOIN proveedores p ON p.id = mp.id_proveedor AND (%s IS NULL OR p.tenant_id = %s)
                LEFT JOIN unidades_medida u ON m.unidad_medida_id = u.id_unidad AND (%s IS NULL OR u.tenant_id = %s)
                WHERE (%s IS NULL OR m.tenant_id = %s)
                ORDER BY m.id DESC
            """
            cursor.execute(sql_mat, (tenant_id, tenant_id, tenant_id, tenant_id, tenant_id, tenant_id, tenant_id, tenant_id, tenant_id, tenant_id))
            materiales = [dict(m) for m in cursor.fetchall()]
            for m in materiales:
                # Hay bases con el enum en mayúsculas ('LOTE'): la pantalla trabaja en minúsculas
                m['trazabilidad'] = (m.get('trazabilidad') or 'ninguna').lower()

            cursor.execute("SELECT * FROM categorias WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s)", (tenant_id, tenant_id))
            categorias = cursor.fetchall()

            cursor.execute("SELECT id, razonsocial FROM proveedores WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s)", (tenant_id, tenant_id))
            proveedores = cursor.fetchall()

            # Activas, más las inactivas que algún material ya usa (para no obligar a cambiarla al editarlo)
            cursor.execute("""
                SELECT id_unidad, codigo, nombre, simbolo, activo FROM unidades_medida
                WHERE (%s IS NULL OR tenant_id = %s)
                  AND (activo = 1 OR id_unidad IN (SELECT unidad_medida_id FROM materiales
                                                   WHERE unidad_medida_id IS NOT NULL
                                                     AND (%s IS NULL OR tenant_id = %s)))
                ORDER BY nombre
            """, (tenant_id, tenant_id, tenant_id, tenant_id))
            unidades = cursor.fetchall()

            cursor.execute("SELECT mp.* FROM material_proveedor mp WHERE %s IS NULL OR mp.tenant_id = %s", (tenant_id, tenant_id))
            relaciones = cursor.fetchall()

            cursor.execute(f"""
                SELECT id, id_material, nombre, codigo_barras,
                       {cast_as_char('cantidad_unidades')} AS cantidad_unidades,
                       peso_bruto, peso_neto
                FROM material_presentaciones
                WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s)
                ORDER BY id_material, cantidad_unidades
            """, (tenant_id, tenant_id))
            presentaciones = cursor.fetchall()

        return render_template('materiales.html',
                               materiales=materiales,
                               categorias=categorias,
                               proveedores=proveedores,
                               relaciones=relaciones,
                               presentaciones=presentaciones,
                               unidades=unidades,
                               picking_metodos=[{'value': m, 'label': PICKING_METODOS_LABELS[m]} for m in _get_picking_metodos(tenant_id)],
                               picking_metodo_default=_get_picking_metodo_default(tenant_id),
                               picking_labels=PICKING_METODOS_LABELS)
    finally:
        conn.close()


@materiales_bp.route('/materiales/guardar', methods=['POST'])
def guardar():
    d = request.form
    m_id = d.get('id')

    prov_ids = request.form.getlist('prov_ids[]')
    prov_codigos = request.form.getlist('prov_codigos[]')
    prov_habitual = d.get('prov_habitual', None)

    pres_nombres = request.form.getlist('pres_nombres[]')
    pres_barcodes = request.form.getlist('pres_barcodes[]')
    pres_cantidades = request.form.getlist('pres_cantidades[]')
    pres_pesos_brutos = request.form.getlist('pres_pesos_brutos[]')
    pres_pesos_netos = request.form.getlist('pres_pesos_netos[]')

    codigo = (d.get('codigo') or '').strip()
    nombre = (d.get('nombre') or '').strip()
    barcode = (d.get('codigo_barras') or '').strip()

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            tenant_id = get_tenant_filter()

            # --- Validaciones (cualquier DatoInvalido corta sin guardar nada) ---
            if not codigo or not nombre:
                raise DatoInvalido('Código y Nombre son obligatorios.')
            valido, error_msg = validar_ean(barcode)
            if not valido:
                raise DatoInvalido(error_msg or 'Código de barras inválido')

            if m_id:
                try:
                    m_id = int(m_id)
                except ValueError:
                    raise DatoInvalido('Material inválido.') from None
                cursor.execute("SELECT id FROM materiales WHERE id = %s AND (%s IS NULL OR tenant_id = %s)",
                               (m_id, tenant_id, tenant_id))
                if not cursor.fetchone():
                    raise DatoInvalido('El material que se intenta modificar no existe.')
            else:
                m_id = None
            otro = m_id or 0   # id a excluir al buscar duplicados

            cursor.execute("SELECT id FROM materiales WHERE codigo = %s AND id <> %s AND (%s IS NULL OR tenant_id = %s)",
                           (codigo, otro, tenant_id, tenant_id))
            if cursor.fetchone():
                raise DatoInvalido(f'Ya existe un material con el código "{codigo}".')
            if barcode:
                cursor.execute("""SELECT codigo FROM materiales
                                  WHERE codigo_barras = %s AND id <> %s AND (%s IS NULL OR tenant_id = %s)""",
                               (barcode, otro, tenant_id, tenant_id))
                repetido = cursor.fetchone()
                if repetido:
                    raise DatoInvalido(f'El código de barras {barcode} ya está asignado al material '
                                       f'"{repetido["codigo"]}".')

            stock_min = _numero(d.get('stock_minimo'), 'Stock mínimo')
            stock_max = _numero(d.get('stock_maximo'), 'Stock máximo')
            if stock_max and stock_min > stock_max:
                raise DatoInvalido('El stock mínimo no puede ser mayor que el stock máximo.')
            peso_bruto = _numero(d.get('peso_bruto'), 'Peso bruto') or None
            peso_neto = _numero(d.get('peso_neto'), 'Peso neto') or None
            categoria_id = _id_del_tenant(cursor, 'categorias', 'id_categoria', d.get('categoria_id'),
                                          tenant_id, 'Categoría')
            unidad_id = _id_del_tenant(cursor, 'unidades_medida', 'id_unidad', d.get('unidad_medida_id'),
                                       tenant_id, 'Unidad de medida')
            trazabilidad = d.get('trazabilidad') or 'ninguna'
            if trazabilidad not in TRAZABILIDADES:
                raise DatoInvalido('Trazabilidad inválida.')
            metodo_picking = _metodo_picking_valido((d.get('metodo_picking') or '').strip().lower(),
                                                    _get_picking_metodo_default(tenant_id),
                                                    _get_picking_metodos(tenant_id))

            # Proveedores: sin filas vacías ni repetidos; el habitual se indica por posición de la fila
            try:
                fila_habitual = int(prov_habitual) if prov_habitual not in (None, '') else None
            except ValueError:
                fila_habitual = None
            proveedores = []
            for i, prov_id in enumerate(prov_ids):
                if not prov_id:
                    continue
                prov_id = _id_del_tenant(cursor, 'proveedores', 'id', prov_id, tenant_id, 'Proveedor')
                if any(p['id'] == prov_id for p in proveedores):
                    raise DatoInvalido('Hay un proveedor repetido en la lista de proveedores.')
                proveedores.append({'id': prov_id,
                                    'codigo': (prov_codigos[i] if i < len(prov_codigos) else '').strip(),
                                    'habitual': 1 if fila_habitual == i else 0})

            # Presentaciones
            presentaciones = []
            for i, nombre_p in enumerate(pres_nombres):
                nombre_p = (nombre_p or '').strip()
                if not nombre_p:
                    continue
                gtin = (pres_barcodes[i] if i < len(pres_barcodes) else '').strip()
                valido_gtin, error_gtin = validar_gtin14(gtin)
                if not valido_gtin:
                    raise DatoInvalido(f'Presentación "{nombre_p}": {error_gtin}')
                if gtin and any(p['gtin'] == gtin for p in presentaciones):
                    raise DatoInvalido(f'Presentación "{nombre_p}": el GTIN-14 {gtin} está repetido.')
                if gtin:
                    cursor.execute("""SELECT m.codigo FROM material_presentaciones mp
                                      JOIN materiales m ON m.id = mp.id_material
                                      WHERE mp.codigo_barras = %s AND mp.id_material <> %s
                                        AND (%s IS NULL OR mp.tenant_id = %s)""",
                                   (gtin, otro, tenant_id, tenant_id))
                    usado = cursor.fetchone()
                    if usado:
                        raise DatoInvalido(f'Presentación "{nombre_p}": el GTIN-14 {gtin} ya lo usa el material '
                                           f'"{usado["codigo"]}".')
                rotulo = f'Presentación "{nombre_p}"'
                cantidad = (pres_cantidades[i] if i < len(pres_cantidades) else '') or 1
                presentaciones.append({
                    'nombre': nombre_p, 'gtin': gtin,
                    'cantidad': _numero(cantidad, f'{rotulo}: unidades', minimo=0.001),
                    'peso_bruto': _numero(pres_pesos_brutos[i] if i < len(pres_pesos_brutos) else '',
                                          f'{rotulo}: peso bruto') or None,
                    'peso_neto': _numero(pres_pesos_netos[i] if i < len(pres_pesos_netos) else '',
                                         f'{rotulo}: peso neto') or None,
                })

            # --- Guardado ---
            if m_id:
                cursor.execute("""
                    UPDATE materiales SET
                        codigo = %s, nombre = %s, descripcion = %s, codigo_barras = %s,
                        categoria_id = %s, stock_minimo = %s, stock_maximo = %s,
                        unidad_medida_id = %s, trazabilidad = %s, metodo_picking = %s,
                        peso_bruto = %s, peso_neto = %s
                    WHERE id = %s AND (%s IS NULL OR tenant_id = %s)
                """, (codigo, nombre, d.get('descripcion') or '',
                      barcode or None, categoria_id, stock_min, stock_max,
                      unidad_id, trazabilidad, metodo_picking, peso_bruto, peso_neto,
                      m_id, tenant_id, tenant_id))
                # El formulario manda "activo" (0 y, si está tildado, 1); sin ese campo no se toca
                estados = request.form.getlist('activo')
                if estados:
                    cursor.execute("UPDATE materiales SET activo = %s WHERE id = %s",
                                   (estados[-1] == '1', m_id))
                current_id = m_id
            else:
                current_id = execute_insert(cursor, """
                    INSERT INTO materiales (codigo, nombre, descripcion, codigo_barras, categoria_id,
                        stock_minimo, stock_maximo, unidad_medida_id, trazabilidad, metodo_picking,
                        peso_bruto, peso_neto, tenant_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (codigo, nombre, d.get('descripcion') or '',
                      barcode or None, categoria_id, stock_min, stock_max,
                      unidad_id, trazabilidad, metodo_picking, peso_bruto, peso_neto, tenant_id))

            cursor.execute("DELETE FROM material_proveedor WHERE id_material = %s", (current_id,))
            for p in proveedores:
                cursor.execute("""
                    INSERT INTO material_proveedor (id_material, id_proveedor, codigo_referencia_prov, es_habitual, tenant_id)
                    VALUES (%s, %s, %s, %s, %s)
                """, (current_id, p['id'], p['codigo'], p['habitual'], tenant_id))

            cursor.execute("DELETE FROM material_presentaciones WHERE id_material = %s", (current_id,))
            for p in presentaciones:
                cursor.execute("""
                    INSERT INTO material_presentaciones (id_material, nombre, codigo_barras, cantidad_unidades, peso_bruto, peso_neto, tenant_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (current_id, p['nombre'], p['gtin'] or None, p['cantidad'], p['peso_bruto'], p['peso_neto'],
                      tenant_id))

            conn.commit()
            flash("Material guardado correctamente", "success")
    except DatoInvalido as e:
        conn.rollback()
        flash(str(e), "danger")
    except Exception as e:
        conn.rollback()
        if is_duplicate_key_error(e):
            flash("No se pudo guardar: el código del material o un GTIN-14 ya existe.", "danger")
        else:
            flash(f"Error al guardar el material: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('materiales.listar'))


@materiales_bp.route('/materiales/importar', methods=['POST'])
def importar():
    file = request.files.get('archivo')
    if not file or file.filename == '':
        return jsonify({'error': 'No se proporcionó archivo'}), 400

    tenant_id = session.get('tenant_id')
    if not tenant_id:
        return jsonify({'error': 'No se encontró el tenant del usuario'}), 400

    filename = file.filename.lower()
    try:
        if filename.endswith(('.csv', '.json', '.xlsx')):
            rows = parse_file(file, request.form.get('hoja'))
        else:
            return jsonify({'error': 'Formato no soportado. Use CSV, JSON o XLSX'}), 400
    except Exception as e:
        return jsonify({'error': f'Error al leer el archivo: {e!s}'}), 400

    insertados = 0
    omitidos = []
    errores = []

    metodo_default = _get_picking_metodo_default(tenant_id)
    metodos_habilitados = _get_picking_metodos(tenant_id)

    conn = get_db_connection()
    try:
        for i, row in enumerate(rows, start=1):
            codigo = str(row.get('codigo', '') or '').strip()
            nombre = str(row.get('nombre', '') or '').strip()
            if not codigo or not nombre:
                errores.append({'fila': i, 'codigo': codigo or '(vacío)', 'razon': 'Código y Nombre son obligatorios'})
                continue
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id FROM materiales WHERE codigo = %s AND tenant_id = %s", (codigo, tenant_id))
                    if cursor.fetchone():
                        omitidos.append(codigo)
                        continue

                    traz = str(row.get('trazabilidad', '') or '').strip().lower()
                    if traz not in ('lote', 'serie', 'ninguna'):
                        traz = 'ninguna'

                    metodo_picking = _metodo_picking_valido(str(row.get('metodo_picking', '') or '').strip().lower(),
                                                            metodo_default, metodos_habilitados)
                    try:
                        categoria_id = _id_del_tenant(cursor, 'categorias', 'id_categoria',
                                                      int_or_none(row.get('categoria_id')), tenant_id, 'categoria_id')
                        unidad_id = _id_del_tenant(cursor, 'unidades_medida', 'id_unidad',
                                                   int_or_none(row.get('unidad_medida_id')), tenant_id,
                                                   'unidad_medida_id')
                    except DatoInvalido as e:
                        errores.append({'fila': i, 'codigo': codigo, 'razon': str(e)})
                        continue

                    barcode_import = str(row.get('codigo_barras', '') or '').strip()
                    valido_cb, error_cb = validar_ean(barcode_import)
                    if not valido_cb:
                        errores.append({'fila': i, 'codigo': codigo, 'razon': error_cb})
                        continue

                    if barcode_import:
                        cursor.execute("SELECT id FROM materiales WHERE codigo_barras = %s AND tenant_id = %s", (barcode_import, tenant_id))
                        if cursor.fetchone():
                            errores.append({'fila': i, 'codigo': codigo, 'razon': f'El código de barras {barcode_import} ya está asignado a otro material.'})
                            continue

                    material_id = execute_insert(cursor, """
                        INSERT INTO materiales
                            (codigo, nombre, descripcion, codigo_barras,
                             categoria_id, stock_minimo, stock_maximo,
                             unidad_medida_id, trazabilidad, metodo_picking,
                             peso_bruto, peso_neto,
                             tenant_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        codigo,
                        nombre,
                        str(row.get('descripcion', '') or '').strip() or None,
                        barcode_import or None,
                        categoria_id,
                        float_or_zero(row.get('stock_minimo')),
                        float_or_zero(row.get('stock_maximo')),
                        unidad_id,
                        traz,
                        metodo_picking,
                        float_or_zero(row.get('peso_bruto')) or None,
                        float_or_zero(row.get('peso_neto')) or None,
                        tenant_id,
                    ))

                    id_prov_hab = int_or_none(row.get('id_proveedor_habitual'))
                    if id_prov_hab:
                        cursor.execute("SELECT id FROM proveedores WHERE id = %s AND (%s IS NULL OR tenant_id = %s)", (id_prov_hab, tenant_id, tenant_id))
                        if cursor.fetchone():
                            cod_ref_prov = str(row.get('codigo_referencia_prov', '') or '').strip() or None
                            cursor.execute("""
                                INSERT INTO material_proveedor (id_material, id_proveedor, codigo_referencia_prov, es_habitual, tenant_id)
                                VALUES (%s, %s, %s, 1, %s)
                            """, (material_id, id_prov_hab, cod_ref_prov, tenant_id))

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


@materiales_bp.route('/materiales/exportar/<formato>')
def exportar(formato):
    tenant_id = get_tenant_filter()
    CAMPOS = ['codigo', 'nombre', 'descripcion', 'codigo_barras',
              'categoria_id', 'categoria_nombre', 'stock_minimo', 'stock_maximo',
              'unidad_medida_id', 'unidad_medida_nombre', 'trazabilidad', 'metodo_picking',
              'peso_bruto', 'peso_neto',
              'id_proveedor_habitual', 'proveedor_habitual_nombre', 'codigo_referencia_prov']

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT m.codigo, m.nombre, m.descripcion, m.codigo_barras,
                       m.categoria_id, c.nombre AS categoria_nombre,
                       m.stock_minimo, m.stock_maximo,
                       m.unidad_medida_id, u.nombre AS unidad_medida_nombre, m.trazabilidad,
                       m.metodo_picking,
                       m.peso_bruto, m.peso_neto,
                       mp.id_proveedor AS id_proveedor_habitual,
                       p.razonsocial AS proveedor_habitual_nombre,
                       mp.codigo_referencia_prov
                FROM materiales m
                LEFT JOIN categorias c ON m.categoria_id = c.id_categoria
                LEFT JOIN unidades_medida u ON m.unidad_medida_id = u.id_unidad
                LEFT JOIN material_proveedor mp ON mp.id_material = m.id AND mp.es_habitual = 1
                LEFT JOIN proveedores p ON p.id = mp.id_proveedor
                WHERE (%s IS NULL OR m.tenant_id = %s)
                ORDER BY m.codigo
            """, (tenant_id, tenant_id))
            rows = cursor.fetchall()
    finally:
        conn.close()

    if formato == 'csv':
        return export_csv(rows, CAMPOS, 'materiales.csv')
    elif formato == 'json':
        return export_json(rows, CAMPOS, 'materiales.json')
    elif formato == 'xlsx':
        return export_xlsx(rows, CAMPOS, 'materiales.xlsx')
    return 'Formato no válido', 400


@materiales_bp.route('/materiales/plantilla/<formato>')
def plantilla(formato):
    tenant_id = get_tenant_filter()
    HEADERS = ['codigo', 'nombre', 'descripcion', 'codigo_barras',
               'categoria_id', 'stock_minimo', 'stock_maximo', 'unidad_medida_id', 'trazabilidad',
               'metodo_picking', 'peso_bruto', 'peso_neto', 'id_proveedor_habitual', 'codigo_referencia_prov']
    EJEMPLO = ['MAT001', 'Ejemplo Material', 'Descripción opcional', '',
                '1', '0.00', '100.00', '1', 'ninguna', 'libre', '0.500', '0.450', '1', 'REF-PROV-001']

    # Obtener categorias, unidades y proveedores
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id_categoria, nombre FROM categorias WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s) ORDER BY nombre", (tenant_id, tenant_id))
            categorias = cursor.fetchall()
            cursor.execute("SELECT id_unidad, nombre, simbolo FROM unidades_medida WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s) ORDER BY nombre", (tenant_id, tenant_id))
            unidades = cursor.fetchall()
            cursor.execute("SELECT id, razonsocial FROM proveedores WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s) ORDER BY razonsocial", (tenant_id, tenant_id))
            proveedores = cursor.fetchall()
    finally:
        conn.close()

    if formato == 'csv':
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(['# PLANTILLA MATERIALES'])
        writer.writerow(HEADERS)
        writer.writerow(EJEMPLO)
        writer.writerow([])
        writer.writerow(['# REFERENCIAS'])
        writer.writerow(['# CATEGORIAS (categoria_id)'])
        writer.writerow(['id_categoria', 'nombre'])
        for c in categorias:
            writer.writerow([c['id_categoria'], c['nombre']])
        writer.writerow([])
        writer.writerow(['# UNIDADES DE MEDIDA (unidad_medida_id)'])
        writer.writerow(['id_unidad', 'nombre', 'simbolo'])
        for u in unidades:
            writer.writerow([u['id_unidad'], u['nombre'], u['simbolo']])
        writer.writerow([])
        writer.writerow(['# PROVEEDORES (id_proveedor_habitual)'])
        writer.writerow(['id', 'razonsocial'])
        for p in proveedores:
            writer.writerow([p['id'], p['razonsocial']])
        out = io.BytesIO(buf.getvalue().encode('utf-8-sig'))
        return send_file(out, mimetype='text/csv', as_attachment=True,
                         download_name='plantilla_materiales.csv')

    elif formato == 'json':
        data = {
            'materiales': [dict(zip(HEADERS, EJEMPLO, strict=False))],
            'categorias': [{'id_categoria': c['id_categoria'], 'nombre': c['nombre']} for c in categorias],
            'unidades': [{'id': u['id_unidad'], 'nombre': u['nombre'], 'abreviatura': u['simbolo']} for u in unidades],
            'proveedores': [{'id': p['id'], 'razonsocial': p['razonsocial']} for p in proveedores]
        }
        out = io.BytesIO(json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'))
        return send_file(out, mimetype='application/json', as_attachment=True,
                         download_name='plantilla_materiales.json')

    elif formato == 'xlsx':
        wb = openpyxl.Workbook()
        
        # Hoja de Materiales
        ws_mat = wb.active
        ws_mat.title = 'Materiales'
        ws_mat.append(HEADERS)
        ws_mat.append(EJEMPLO)
        
        # Estilo para cabecera
        from openpyxl.styles import Alignment, Font, PatternFill
        header_font = Font(bold=True, color='FFFFFF')
        header_fill = PatternFill(fill_type='solid', fgColor='2980B9')
        
        for cell in ws_mat[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')
        
        # Ancho de columnas
        for col in ws_mat.columns:
            ws_mat.column_dimensions[col[0].column_letter].width = 20
        
        # Hoja de Categorías
        ws_cat = wb.create_sheet('Categorias')
        ws_cat.append(['id_categoria', 'nombre'])
        for cell in ws_cat[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')
        for c in categorias:
            ws_cat.append([c['id_categoria'], c['nombre']])
        for col in ws_cat.columns:
            ws_cat.column_dimensions[col[0].column_letter].width = 15
        
        # Hoja de Unidades
        ws_uni = wb.create_sheet('Unidades')
        ws_uni.append(['id_unidad', 'nombre', 'simbolo'])
        for cell in ws_uni[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')
        for u in unidades:
            ws_uni.append([u['id_unidad'], u['nombre'], u['simbolo']])
        for col in ws_uni.columns:
            ws_uni.column_dimensions[col[0].column_letter].width = 15

        # Hoja de Proveedores
        ws_prov = wb.create_sheet('Proveedores')
        ws_prov.append(['id', 'razonsocial'])
        for cell in ws_prov[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')
        for p in proveedores:
            ws_prov.append([p['id'], p['razonsocial']])
        for col in ws_prov.columns:
            ws_prov.column_dimensions[col[0].column_letter].width = 20

        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        return send_file(out,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True, download_name='plantilla_materiales.xlsx')

    return 'Formato no válido', 400


@materiales_bp.route('/materiales/eliminar/<int:id>', methods=['POST'])
def eliminar(id):
    """Borra el material; si tiene stock o movimientos lo desactiva, para no perder su historial."""
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT codigo FROM materiales WHERE id = %s AND (%s IS NULL OR tenant_id = %s)",
                           (id, tenant_id, tenant_id))
            material = cursor.fetchone()
            if not material:
                flash("Material no encontrado.", "warning")
                return redirect(url_for('materiales.listar'))

            en_uso = False
            for tabla, columna in _USOS_MATERIAL:
                cursor.execute(f"SELECT COUNT(*) AS n FROM {tabla} WHERE {columna} = %s", (id,))
                if cursor.fetchone()['n']:
                    en_uso = True
                    break

            if en_uso:
                cursor.execute("UPDATE materiales SET activo = %s WHERE id = %s", (False, id))
                conn.commit()
                flash(f'El material "{material["codigo"]}" tiene stock o movimientos: no se borró, quedó inactivo. '
                      'Se puede reactivar desde su edición.', "warning")
            else:
                cursor.execute("DELETE FROM materiales WHERE id = %s", (id,))
                conn.commit()
                flash("Material eliminado", "success")
    except Exception as e:
        conn.rollback()
        flash(f"No se pudo eliminar el material: {e!s}", "danger")
    finally:
        conn.close()
    return redirect(url_for('materiales.listar'))
