import contextlib
import csv
import io
import json
import os
import re
from urllib.parse import urlparse

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
    bool_col,
    export_csv,
    export_json,
    export_xlsx,
    float_or_zero,
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


def _picking_del_tenant(tenant_id):
    """Métodos de picking habilitados para el tenant y su método por defecto.

    Salen de los parámetros del tenant (panel admin). Sin tenant (superadmin) o
    sin configuración, están todos habilitados. El método por defecto siempre es
    uno de los habilitados.
    """
    todos = list(PICKING_METODOS_LABELS)
    if not tenant_id:
        return todos, 'libre'
    conn = _get_admin_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT metodosdepicking, metodo_picking_default FROM tenants WHERE id = %s", (tenant_id,))
            row = cursor.fetchone()
    finally:
        conn.close()
    if not row:
        return todos, 'libre'

    metodos = row.get('metodosdepicking')
    if metodos:
        # Puede ser una lista en JSON o un valor suelto: en ese caso se deja como está
        with contextlib.suppress(Exception):
            metodos = json.loads(metodos)
    if isinstance(metodos, str):
        metodos = [metodos]
    metodos = [m for m in (metodos or []) if m in PICKING_METODOS_LABELS] or todos

    default = row.get('metodo_picking_default') or 'libre'
    if default not in metodos:
        default = metodos[0]
    return metodos, default


def _get_picking_metodos(tenant_id):
    """Devuelve la lista de métodos de picking habilitados para el tenant."""
    return _picking_del_tenant(tenant_id)[0]


def _get_picking_metodo_default(tenant_id):
    """Devuelve el método de picking por defecto configurado para el tenant."""
    return _picking_del_tenant(tenant_id)[1]


def _metodo_picking_valido(metodo, default='libre', habilitados=None):
    """Método de picking a guardar: el pedido si está habilitado para el tenant; si no, el default."""
    habilitados = habilitados or list(PICKING_METODOS_LABELS)
    if metodo in habilitados:
        return metodo
    return default if default in habilitados else habilitados[0]


TRAZABILIDADES = ('ninguna', 'lote', 'serie')


def _referencia(cursor, tabla, columna_id, columna_codigo, valor, tenant_id, rotulo):
    """Id de un registro de otra tabla indicado, en un archivo importado, por su id o por su código.

    Un valor numérico se busca primero como id y, si no existe, como código
    (hay códigos numéricos). Devuelve None si el valor está vacío.
    """
    valor = str(valor if valor is not None else '').strip()
    if not valor:
        return None
    filtro = "(%s IS NULL OR tenant_id = %s)"
    if re.fullmatch(r'\d+(\.0+)?', valor):
        cursor.execute(f"SELECT {columna_id} AS id FROM {tabla} WHERE {columna_id} = %s AND {filtro}",
                       (int(float(valor)), tenant_id, tenant_id))
        fila = cursor.fetchone()
        if fila:
            return fila['id']
    cursor.execute(f"SELECT {columna_id} AS id FROM {tabla} WHERE {columna_codigo} = %s AND {filtro}",
                   (valor, tenant_id, tenant_id))
    fila = cursor.fetchone()
    if not fila:
        raise DatoInvalido(f'{rotulo}: no existe "{valor}" (se puede indicar el id o el código).')
    return fila['id']


def _stocks(minimo, reposicion, maximo):
    """Stock mínimo, de reposición y máximo, verificados entre sí.

    Los tres son opcionales (0 = sin definir). Si están definidos tienen que
    quedar ordenados: mínimo <= reposición <= máximo.
    """
    minimo = _numero(minimo, 'Stock mínimo')
    reposicion = _numero(reposicion, 'Stock de reposición')
    maximo = _numero(maximo, 'Stock máximo')
    if maximo and minimo > maximo:
        raise DatoInvalido('El stock mínimo no puede ser mayor que el stock máximo.')
    if reposicion and reposicion < minimo:
        raise DatoInvalido('El stock de reposición no puede ser menor que el stock mínimo.')
    if reposicion and maximo and reposicion > maximo:
        raise DatoInvalido('El stock de reposición no puede ser mayor que el stock máximo.')
    return minimo, reposicion, maximo


# --- Imagen del producto ---------------------------------------------------
# Se guarda dónde está la imagen, no la imagen: una ruta del servidor, una ruta
# de red (UNC) o una URL. Las rutas las lee el servidor y las entrega por
# /materiales/imagen/<id>; el navegador no puede abrir rutas de disco o de red.
IMAGEN_MAX = 500                       # largo de materiales.imagen_ruta
IMAGEN_PESO_MAX = 15 * 1024 * 1024     # bytes
IMAGEN_TIPOS = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
                '.gif': 'image/gif', '.webp': 'image/webp', '.bmp': 'image/bmp'}


def _es_url(ruta):
    partes = urlparse(ruta)
    return partes.scheme in ('http', 'https') and bool(partes.netloc)


def _imagen_ruta(valor):
    """Ruta de la imagen, verificada: URL http(s) o ruta a un archivo de imagen. None si está vacía."""
    valor = str(valor or '').strip().strip('"')
    if not valor:
        return None
    if len(valor) > IMAGEN_MAX:
        raise DatoInvalido(f'Imagen: la ruta admite hasta {IMAGEN_MAX} caracteres.')
    if _es_url(valor):
        return valor
    if '://' in valor or valor.lower().startswith(('javascript:', 'data:', 'file:')):
        raise DatoInvalido('Imagen: como dirección web solo se admiten URL http o https.')
    if os.path.splitext(valor)[1].lower() not in IMAGEN_TIPOS:
        raise DatoInvalido('Imagen: el archivo tiene que ser una imagen (' + ', '.join(sorted(IMAGEN_TIPOS)) + ').')
    return valor


def _tipo_de_imagen(cabecera):
    """Tipo de imagen según los primeros bytes del archivo, o None si no es una imagen admitida."""
    if cabecera.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if cabecera.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if cabecera[:6] in (b'GIF87a', b'GIF89a'):
        return 'image/gif'
    if cabecera[:4] == b'RIFF' and cabecera[8:12] == b'WEBP':
        return 'image/webp'
    if cabecera[:2] == b'BM':
        return 'image/bmp'
    return None


CODIGO_MAX = 100   # largo de materiales.codigo_alternativo y codigo_proveedor


def _codigo_secundario(valor, rotulo, codigo):
    """Código alternativo o del proveedor: si no se indica, es el mismo que el código del material."""
    valor = str(valor or '').strip()
    if len(valor) > CODIGO_MAX:
        raise DatoInvalido(f'{rotulo}: admite hasta {CODIGO_MAX} caracteres.')
    return valor or codigo


def _volumen(cursor, valor, unidad, tenant_id):
    """Volumen del material y su unidad, verificados: (volumen, id de la unidad) o (None, None).

    El volumen se guarda siempre con su unidad, que tiene que ser una unidad de
    medida del tenant de magnitud VOLUMEN.
    """
    volumen = _numero(valor, 'Volumen') or None
    if volumen is None:
        return None, None
    try:
        unidad = int(unidad or 0)
    except (TypeError, ValueError):
        unidad = 0
    if not unidad:
        raise DatoInvalido('Volumen: falta indicar la unidad de medida.')
    cursor.execute("""SELECT tipo_magnitud FROM unidades_medida
                      WHERE id_unidad = %s AND (%s IS NULL OR tenant_id = %s)""", (unidad, tenant_id, tenant_id))
    fila = cursor.fetchone()
    if not fila:
        raise DatoInvalido('Volumen: la unidad de medida elegida no existe.')
    if str(fila['tipo_magnitud'] or '').upper() != 'VOLUMEN':
        raise DatoInvalido('Volumen: la unidad de medida tiene que ser de magnitud Volumen.')
    return volumen, unidad


def _cantidad(valor):
    """Cantidad para mostrar, sin ceros de relleno: 100.000 -> '100', 0.500 -> '0.5'."""
    texto = f'{float(valor or 0):.3f}'.rstrip('0').rstrip('.')
    return texto or '0'

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
                       u.nombre as unidad_medida_nombre, u.simbolo as unidad_medida_simbolo,
                       uv.simbolo as volumen_unidad_simbolo
                FROM materiales m
                LEFT JOIN unidades_medida uv ON m.volumen_unidad_id = uv.id_unidad
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
                m['stock_minimo_txt'] = _cantidad(m.get('stock_minimo'))
                m['stock_maximo_txt'] = _cantidad(m.get('stock_maximo'))
                m['stock_reposicion_txt'] = _cantidad(m.get('stock_reposicion'))
                m['volumen_txt'] = _cantidad(m.get('volumen')) if m.get('volumen') else ''
                m['imagen_es_url'] = bool(m.get('imagen_ruta')) and _es_url(m['imagen_ruta'])

            # Con las inactivas: el formulario las oculta, salvo la que el material ya tiene
            cursor.execute("SELECT * FROM categorias WHERE (%s IS NULL OR tenant_id = %s) ORDER BY nombre", (tenant_id, tenant_id))
            categorias = cursor.fetchall()

            # Todos: el formulario ofrece los activos, y el inactivo solo en la fila del material que ya lo tiene
            cursor.execute("SELECT id, razonsocial, activo FROM proveedores WHERE (%s IS NULL OR tenant_id = %s) ORDER BY razonsocial", (tenant_id, tenant_id))
            proveedores = cursor.fetchall()

            # Todas: el formulario oculta las inactivas, salvo la que el material ya tiene
            cursor.execute("""
                SELECT id_unidad, codigo, nombre, simbolo, tipo_magnitud, activo FROM unidades_medida
                WHERE (%s IS NULL OR tenant_id = %s)
                ORDER BY nombre
            """, (tenant_id, tenant_id))
            unidades = cursor.fetchall()
            # Unidades en que se puede expresar el volumen: las de magnitud VOLUMEN
            unidades_volumen = [u for u in unidades if str(u['tipo_magnitud'] or '').upper() == 'VOLUMEN']

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

        metodos_habilitados, metodo_default = _picking_del_tenant(tenant_id)
        return render_template('materiales.html',
                               materiales=materiales,
                               categorias=categorias,
                               proveedores=proveedores,
                               relaciones=relaciones,
                               presentaciones=presentaciones,
                               unidades=unidades,
                               unidades_volumen=unidades_volumen,
                               codigo_max=CODIGO_MAX,
                               imagen_max=IMAGEN_MAX,
                               picking_metodos=[{'value': m, 'label': PICKING_METODOS_LABELS[m]} for m in metodos_habilitados],
                               picking_habilitados=metodos_habilitados,
                               picking_metodo_default=metodo_default,
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

            stock_min, stock_repo, stock_max = _stocks(d.get('stock_minimo'), d.get('stock_reposicion'),
                                                       d.get('stock_maximo'))
            peso_bruto = _numero(d.get('peso_bruto'), 'Peso bruto') or None
            peso_neto = _numero(d.get('peso_neto'), 'Peso neto') or None
            codigo_alternativo = _codigo_secundario(d.get('codigo_alternativo'), 'Código alternativo', codigo)
            codigo_proveedor = _codigo_secundario(d.get('codigo_proveedor'), 'Código proveedor', codigo)
            volumen, volumen_unidad_id = _volumen(cursor, d.get('volumen'), d.get('volumen_unidad_id'), tenant_id)
            imagen_ruta = _imagen_ruta(d.get('imagen_ruta'))
            # Estado: "1" activo, "0" inactivo. Sin el campo: un alta nace activa y una edición no lo cambia
            estados = request.form.getlist('activo')
            estado = (estados[-1] == '1') if estados else None
            categoria_id = _id_del_tenant(cursor, 'categorias', 'id_categoria', d.get('categoria_id'),
                                          tenant_id, 'Categoría')
            unidad_id = _id_del_tenant(cursor, 'unidades_medida', 'id_unidad', d.get('unidad_medida_id'),
                                       tenant_id, 'Unidad de medida')
            trazabilidad = d.get('trazabilidad') or 'ninguna'
            if trazabilidad not in TRAZABILIDADES:
                raise DatoInvalido('Trazabilidad inválida.')
            metodos_habilitados, metodo_default = _picking_del_tenant(tenant_id)
            metodo_picking = _metodo_picking_valido((d.get('metodo_picking') or '').strip().lower(),
                                                    metodo_default, metodos_habilitados)

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
                        peso_bruto = %s, peso_neto = %s,
                        codigo_alternativo = %s, codigo_proveedor = %s, volumen = %s, volumen_unidad_id = %s,
                        stock_reposicion = %s, imagen_ruta = %s
                    WHERE id = %s AND (%s IS NULL OR tenant_id = %s)
                """, (codigo, nombre, d.get('descripcion') or '',
                      barcode or None, categoria_id, stock_min, stock_max,
                      unidad_id, trazabilidad, metodo_picking, peso_bruto, peso_neto,
                      codigo_alternativo, codigo_proveedor, volumen, volumen_unidad_id, stock_repo, imagen_ruta,
                      m_id, tenant_id, tenant_id))
                # Estado (Activo / Inactivo): si el formulario no lo manda, no se toca
                if estado is not None:
                    cursor.execute("UPDATE materiales SET activo = %s WHERE id = %s", (estado, m_id))
                current_id = m_id
            else:
                current_id = execute_insert(cursor, """
                    INSERT INTO materiales (codigo, nombre, descripcion, codigo_barras, categoria_id,
                        stock_minimo, stock_maximo, unidad_medida_id, trazabilidad, metodo_picking,
                        peso_bruto, peso_neto,
                        codigo_alternativo, codigo_proveedor, volumen, volumen_unidad_id, stock_reposicion,
                        imagen_ruta, activo, tenant_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (codigo, nombre, d.get('descripcion') or '',
                      barcode or None, categoria_id, stock_min, stock_max,
                      unidad_id, trazabilidad, metodo_picking, peso_bruto, peso_neto,
                      codigo_alternativo, codigo_proveedor, volumen, volumen_unidad_id, stock_repo, imagen_ruta,
                      True if estado is None else estado, tenant_id))

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
            if imagen_ruta and not _es_url(imagen_ruta) and not os.path.isfile(imagen_ruta):
                flash(f'El material se guardó, pero el servidor no encuentra la imagen "{imagen_ruta}". '
                      'Revisar que la ruta exista y que el servidor pueda leerla.', "warning")
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

    metodos_habilitados, metodo_default = _picking_del_tenant(tenant_id)

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
                        # Las referencias a otros maestros se pueden indicar por id o por código
                        categoria_id = _referencia(cursor, 'categorias', 'id_categoria', 'codigo',
                                                   row.get('categoria_id'), tenant_id, 'categoria_id')
                        unidad_id = _referencia(cursor, 'unidades_medida', 'id_unidad', 'codigo',
                                                row.get('unidad_medida_id'), tenant_id, 'unidad_medida_id')
                        id_prov_hab = _referencia(cursor, 'proveedores', 'id', 'codigo',
                                                  row.get('id_proveedor_habitual'), tenant_id, 'id_proveedor_habitual')
                        codigo_alternativo = _codigo_secundario(row.get('codigo_alternativo'), 'codigo_alternativo',
                                                                codigo)
                        codigo_proveedor = _codigo_secundario(row.get('codigo_proveedor'), 'codigo_proveedor', codigo)
                        volumen, volumen_unidad_id = _volumen(
                            cursor, str(row.get('volumen') or '').replace(',', '.'),
                            _referencia(cursor, 'unidades_medida', 'id_unidad', 'codigo',
                                        row.get('volumen_unidad_id'), tenant_id, 'volumen_unidad_id'), tenant_id)
                        imagen_ruta = _imagen_ruta(row.get('imagen_ruta'))
                        stock_min, stock_repo, stock_max = _stocks(
                            *(str(row.get(c) or '').replace(',', '.')
                              for c in ('stock_minimo', 'stock_reposicion', 'stock_maximo')))
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
                             codigo_alternativo, codigo_proveedor, volumen, volumen_unidad_id,
                             stock_reposicion, imagen_ruta, activo, tenant_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        codigo,
                        nombre,
                        str(row.get('descripcion', '') or '').strip() or None,
                        barcode_import or None,
                        categoria_id,
                        stock_min,
                        stock_max,
                        unidad_id,
                        traz,
                        metodo_picking,
                        float_or_zero(row.get('peso_bruto')) or None,
                        float_or_zero(row.get('peso_neto')) or None,
                        codigo_alternativo, codigo_proveedor, volumen, volumen_unidad_id,
                        stock_repo, imagen_ruta,
                        bool(bool_col(row.get('activo') if str(row.get('activo') or '').strip() else '1')),
                        tenant_id,
                    ))

                    if id_prov_hab:
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
    CAMPOS = ['codigo', 'nombre', 'descripcion', 'codigo_barras', 'codigo_alternativo', 'codigo_proveedor',
              'categoria_id', 'categoria_nombre', 'stock_minimo', 'stock_reposicion', 'stock_maximo',
              'unidad_medida_id', 'unidad_medida_nombre', 'trazabilidad', 'metodo_picking',
              'peso_bruto', 'peso_neto', 'volumen', 'volumen_unidad_id', 'volumen_unidad_nombre', 'imagen_ruta', 'activo',
              'id_proveedor_habitual', 'proveedor_habitual_nombre', 'codigo_referencia_prov']

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT m.codigo, m.nombre, m.descripcion, m.codigo_barras,
                       m.codigo_alternativo, m.codigo_proveedor,
                       m.volumen, m.volumen_unidad_id, uv.nombre AS volumen_unidad_nombre, m.imagen_ruta, m.activo,
                       m.categoria_id, c.nombre AS categoria_nombre,
                       m.stock_minimo, m.stock_reposicion, m.stock_maximo,
                       m.unidad_medida_id, u.nombre AS unidad_medida_nombre, m.trazabilidad,
                       m.metodo_picking,
                       m.peso_bruto, m.peso_neto,
                       mp.id_proveedor AS id_proveedor_habitual,
                       p.razonsocial AS proveedor_habitual_nombre,
                       mp.codigo_referencia_prov
                FROM materiales m
                LEFT JOIN categorias c ON m.categoria_id = c.id_categoria
                LEFT JOIN unidades_medida u ON m.unidad_medida_id = u.id_unidad
                LEFT JOIN unidades_medida uv ON m.volumen_unidad_id = uv.id_unidad
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
    HEADERS = ['codigo', 'nombre', 'descripcion', 'codigo_barras', 'codigo_alternativo', 'codigo_proveedor',
               'categoria_id', 'stock_minimo', 'stock_reposicion', 'stock_maximo', 'unidad_medida_id', 'trazabilidad',
               'metodo_picking', 'peso_bruto', 'peso_neto', 'volumen', 'volumen_unidad_id', 'imagen_ruta', 'activo',
               'id_proveedor_habitual', 'codigo_referencia_prov']
    # El volumen del ejemplo va vacío: necesita el id de una unidad de volumen, que depende de la instalación
    # Los códigos alternativo y del proveedor van vacíos: por defecto toman el código del material
    EJEMPLO = ['MAT001', 'Ejemplo Material', 'Descripción opcional', '', '', '',
               '1', '10', '30', '100', '1', 'ninguna', _get_picking_metodo_default(tenant_id),
               '0.500', '0.450', '', '', '', '1', '1', 'REF-PROV-001']

    # Obtener categorias, unidades y proveedores
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id_categoria, nombre FROM categorias WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s) ORDER BY nombre", (tenant_id, tenant_id))
            categorias = cursor.fetchall()
            cursor.execute("SELECT id_unidad, nombre, simbolo, tipo_magnitud FROM unidades_medida WHERE activo = 1 AND (%s IS NULL OR tenant_id = %s) ORDER BY nombre", (tenant_id, tenant_id))
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
        writer.writerow(['# UNIDADES DE MEDIDA (unidad_medida_id; para volumen_unidad_id, las de magnitud VOLUMEN)'])
        writer.writerow(['id_unidad', 'nombre', 'simbolo', 'tipo_magnitud'])
        for u in unidades:
            writer.writerow([u['id_unidad'], u['nombre'], u['simbolo'], u['tipo_magnitud']])
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
            'unidades': [{'id': u['id_unidad'], 'nombre': u['nombre'], 'abreviatura': u['simbolo'],
                          'tipo_magnitud': u['tipo_magnitud']} for u in unidades],
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
        ws_uni.append(['id_unidad', 'nombre', 'simbolo', 'tipo_magnitud'])
        for cell in ws_uni[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')
        for u in unidades:
            ws_uni.append([u['id_unidad'], u['nombre'], u['simbolo'], u['tipo_magnitud']])
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


@materiales_bp.route('/materiales/distribucion/<int:id>')
def distribucion(id):
    """Stock de un material en cada posición donde tiene existencias (JSON para la grilla de Distribución).

    Una posición es una combinación de ubicación, contenedor, lote y tipo de
    stock (una fila de stockcontable). No se listan las que quedaron en cero.
    """
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT m.id, m.codigo, m.nombre, u.simbolo AS unidad
                FROM materiales m
                LEFT JOIN unidades_medida u ON m.unidad_medida_id = u.id_unidad
                WHERE m.id = %s AND (%s IS NULL OR m.tenant_id = %s)
            """, (id, tenant_id, tenant_id))
            material = cursor.fetchone()
            if not material:
                return jsonify({'error': 'Material no encontrado'}), 404

            cursor.execute("""
                SELECT ub.codigo AS ubicacion, ub.descipcion AS ubicacion_descripcion,
                       z.nombre AS zona, tu.descripcion AS tipo_ubicacion,
                       sc.IDContenedor AS contenedor, sc.Lote AS lote, sc.TipoStock AS tipo_stock,
                       sc.FechaVencimiento AS vencimiento,
                       sc.StockTotal AS total, sc.StockDisponible AS disponible,
                       sc.StockEntrando AS entrando, sc.StockSaliendo AS saliendo
                FROM stockcontable sc
                JOIN ubicaciones ub ON sc.Ubicacion = ub.id
                LEFT JOIN zonas z ON ub.id_zona = z.id
                LEFT JOIN tipoubicacion tu ON ub.tipoubicacion = tu.id
                WHERE sc.Material = %s AND (%s IS NULL OR sc.tenant_id = %s)
                  AND (sc.StockTotal <> 0 OR sc.StockDisponible <> 0
                       OR sc.StockEntrando <> 0 OR sc.StockSaliendo <> 0)
                ORDER BY ub.codigo, sc.IDContenedor, sc.TipoStock, sc.Lote
            """, (id, tenant_id, tenant_id))
            filas = cursor.fetchall()
    finally:
        conn.close()

    cantidades = ('total', 'disponible', 'entrando', 'saliendo')
    posiciones = []
    totales = dict.fromkeys(cantidades, 0.0)
    for f in filas:
        posicion = {
            'ubicacion': f['ubicacion'],
            'ubicacion_descripcion': f['ubicacion_descripcion'] or '',
            'zona': f['zona'] or '',
            'tipo_ubicacion': f['tipo_ubicacion'] or '',
            'contenedor': f['contenedor'] or '',
            'lote': f['lote'] or '',
            'tipo_stock': f['tipo_stock'] or '',
            'vencimiento': f['vencimiento'].strftime('%d/%m/%Y') if f['vencimiento'] else '',
        }
        for c in cantidades:
            posicion[c] = float(f[c] or 0)
            totales[c] += posicion[c]
        posiciones.append(posicion)

    return jsonify({
        'material': {'id': material['id'], 'codigo': material['codigo'], 'nombre': material['nombre'],
                     'unidad': material['unidad'] or ''},
        'posiciones': posiciones,
        'ubicaciones': len({p['ubicacion'] for p in posiciones}),
        'totales': {c: round(v, 4) for c, v in totales.items()},
    })


@materiales_bp.route('/materiales/imagen/<int:id>')
def imagen(id):
    """Entrega la imagen de un material del tenant.

    Si la imagen es una URL, redirige a ella. Si es una ruta (del servidor o de
    red), la lee el servidor: solo se entrega si es de verdad una imagen (por
    extensión y por contenido), para que esta ruta no sirva para leer otros archivos.
    """
    tenant_id = get_tenant_filter()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT imagen_ruta FROM materiales WHERE id = %s AND (%s IS NULL OR tenant_id = %s)",
                           (id, tenant_id, tenant_id))
            fila = cursor.fetchone()
    finally:
        conn.close()
    ruta = (fila or {}).get('imagen_ruta')
    if not ruta:
        return 'El material no tiene imagen', 404
    if _es_url(ruta):
        return redirect(ruta)
    if os.path.splitext(ruta)[1].lower() not in IMAGEN_TIPOS:
        return 'El archivo no es una imagen', 404
    try:
        if not os.path.isfile(ruta) or os.path.getsize(ruta) > IMAGEN_PESO_MAX:
            return 'No se encuentra la imagen o es demasiado grande', 404
        with open(ruta, 'rb') as fh:
            tipo = _tipo_de_imagen(fh.read(16))
    except OSError:
        return 'El servidor no puede leer la imagen', 404
    if not tipo:
        return 'El archivo no es una imagen', 404
    respuesta = send_file(ruta, mimetype=tipo, max_age=300)
    respuesta.headers['X-Content-Type-Options'] = 'nosniff'
    return respuesta


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
