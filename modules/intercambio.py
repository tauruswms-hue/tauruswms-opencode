"""
modules/intercambio.py — Base de datos de intercambio y sincronizacion WMS

El sistema de gestion externo inserta registros en las tablas de interfase
(taurus_intercambio.intercambio_*) y este modulo las lee y aplica sobre las
tablas operativas del WMS (taurus_wms).

Modulos soportados (ver MODULOS):
- materiales:   intercambio_materiales        -> wms.materiales
- rutas:        intercambio_rutas             -> wms.rutas
- transportes:  intercambio_transportes       -> wms.transportes
- transporte_rutas: intercambio_transporte_rutas -> wms.transporte_rutas (asignacion)
- clientes:     intercambio_clientes          -> wms.clientes
- pedidos:      intercambio_pedidos           -> wms.pedidos_cabecera + pedidos_detalle

- procesar_intercambio(): procesa todos los modulos en orden de dependencia
  (usado por la UI, el panel admin y el script procesar_intercambio.py).
- procesar_intercambio_<modulo>(): procesa un modulo individual.
- reintentar_intercambio(): vuelve a 'pendiente' registros en 'error'.
- reintentar_todo(): idem para todos los modulos.
- Blueprint `intercambio_bp`: pantalla del WMS (role con permiso en
  ROUTE_CATALOG -> /intercambio) para ver estado, procesar y recuperar.
"""

import datetime
import json
import logging

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from modules.db_config import (
    _get_admin_connection,
    get_db_connection,
    get_db_engine,
    get_intercambio_connection,
)
from modules.sql_dialect import execute_insert, in_clause_sql, set_engine

logger = logging.getLogger(__name__)

intercambio_bp = Blueprint('intercambio', __name__)

ERROR_LIMIT = 2000


def _now():
    return datetime.datetime.now()


def _valor_bool(v):
    if v is None:
        return True
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s not in ('0', 'false', 'no', '')


def _valor_fecha(v):
    """Normaliza un valor de fecha a 'YYYY-MM-DD'. Acepta date/datetime o string."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return ''
    if isinstance(v, datetime.datetime):
        return v.strftime('%Y-%m-%d')
    if isinstance(v, datetime.date):
        return v.strftime('%Y-%m-%d')
    return str(v).strip()[:10]


def _obtener_tenant_id(tenant_codigo, cursor_admin):
    cursor_admin.execute("SELECT id FROM tenants WHERE codigo = %s", (tenant_codigo,))
    row = cursor_admin.fetchone()
    return row['id'] if row else None


def _obtener_tenant_codigo(tenant_id, cursor_admin):
    cursor_admin.execute("SELECT codigo FROM tenants WHERE id = %s", (tenant_id,))
    row = cursor_admin.fetchone()
    return row['codigo'] if row else None


# ============================================================================
# RESOLUCION DE REFERENCIAS
# ============================================================================

def _resolver_categoria(categoria_codigo, tenant_id, cursor_wms):
    if not categoria_codigo or not str(categoria_codigo).strip():
        return None
    cursor_wms.execute(
        "SELECT id_categoria FROM categorias WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)",
        (str(categoria_codigo).strip(), tenant_id, tenant_id))
    row = cursor_wms.fetchone()
    if not row:
        raise ValueError(f"Categoría '{categoria_codigo}' no encontrada en el WMS")
    return row['id_categoria']


def _resolver_unidad(unidad_codigo, tenant_id, cursor_wms):
    if not unidad_codigo or not str(unidad_codigo).strip():
        return None
    cursor_wms.execute(
        "SELECT id_unidad FROM unidades_medida WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)",
        (str(unidad_codigo).strip(), tenant_id, tenant_id))
    row = cursor_wms.fetchone()
    if not row:
        raise ValueError(f"Unidad de medida '{unidad_codigo}' no encontrada en el WMS")
    return row['id_unidad']


def _resolver_ruta_nombre(ruta_nombre, tenant_id, cursor_wms):
    """Resuelve id_ruta por nombre de ruta. Si se indica y no existe, error."""
    if not ruta_nombre or not str(ruta_nombre).strip():
        return None
    cursor_wms.execute(
        "SELECT id_ruta FROM rutas WHERE nombre_ruta = %s AND (%s IS NULL OR tenant_id = %s)",
        (str(ruta_nombre).strip(), tenant_id, tenant_id))
    row = cursor_wms.fetchone()
    if not row:
        raise ValueError(f"Ruta '{ruta_nombre}' no encontrada en el WMS")
    return row['id_ruta']


def _resolver_transporte_codigo(transporte_codigo, tenant_id, cursor_wms):
    """Resuelve id_transporte por codigo. Si se indica y no existe, error."""
    if not transporte_codigo or not str(transporte_codigo).strip():
        return None
    cursor_wms.execute(
        "SELECT id_transporte FROM transportes WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)",
        (str(transporte_codigo).strip(), tenant_id, tenant_id))
    row = cursor_wms.fetchone()
    if not row:
        raise ValueError(f"Transporte '{transporte_codigo}' no encontrado en el WMS")
    return row['id_transporte']


def _resolver_cliente_codigo(cliente_codigo, tenant_id, cursor_wms):
    """Resuelve id_cliente por codigo. Si se indica y no existe, error."""
    if not cliente_codigo or not str(cliente_codigo).strip():
        return None
    cursor_wms.execute(
        "SELECT id_cliente FROM clientes WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)",
        (str(cliente_codigo).strip(), tenant_id, tenant_id))
    row = cursor_wms.fetchone()
    if not row:
        raise ValueError(f"Cliente '{cliente_codigo}' no encontrado en el WMS")
    return row['id_cliente']


def _resolver_clase_nombre(clase_nombre, tenant_id, cursor_wms):
    """Resuelve id_clase de pedido por nombre. Si se indica y no existe, error."""
    if not clase_nombre or not str(clase_nombre).strip():
        return None
    cursor_wms.execute(
        "SELECT id_clase FROM clases_pedido WHERE nombre = %s AND (%s IS NULL OR tenant_id = %s)",
        (str(clase_nombre).strip(), tenant_id, tenant_id))
    row = cursor_wms.fetchone()
    if not row:
        raise ValueError(f"Clase de pedido '{clase_nombre}' no encontrada en el WMS")
    return row['id_clase']


def _resolver_muelle(muelle_codigo, tenant_id, cursor_wms):
    """Resuelve id de ubicacion (muelle de salida) por codigo. Si se indica y no existe, error."""
    if not muelle_codigo or not str(muelle_codigo).strip():
        return None
    cursor_wms.execute(
        "SELECT id FROM ubicaciones WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)",
        (str(muelle_codigo).strip(), tenant_id, tenant_id))
    row = cursor_wms.fetchone()
    if not row:
        raise ValueError(f"Muelle '{muelle_codigo}' no encontrado en el WMS")
    return row['id']


# ============================================================================
# APLICACION DE REGISTROS
# ============================================================================

def _aplicar_registro_material(reg, conn_wms, cursor_wms, cursor_admin):
    """Aplica un registro de intercambio_materiales sobre el WMS.

    Devuelve (ok, mensaje, id_material_wms). En caso de error lanza ValueError
    con el mensaje a guardar en el registro.
    """
    tenant_codigo = (reg.get('tenant_codigo') or '').strip()
    codigo = (reg.get('codigo') or '').strip()
    nombre = (reg.get('nombre') or '').strip()

    if not tenant_codigo:
        raise ValueError('Falta tenant_codigo')
    if not codigo:
        raise ValueError('Falta codigo del material')

    tenant_id = _obtener_tenant_id(tenant_codigo, cursor_admin)
    if not tenant_id:
        raise ValueError(f"Tenant '{tenant_codigo}' no encontrado en taurus_admin")

    accion = (reg.get('accion') or 'alta').strip().lower()

    # alta / modificacion resuelven referencias
    categoria_id = None
    unidad_id = None
    if accion != 'baja':
        categoria_id = _resolver_categoria(reg.get('categoria_codigo'), tenant_id, cursor_wms)
        unidad_id = _resolver_unidad(reg.get('unidad_medida_codigo'), tenant_id, cursor_wms)

    cursor_wms.execute(
        "SELECT id FROM materiales WHERE codigo = %s AND tenant_id = %s",
        (codigo, tenant_id))
    fila = cursor_wms.fetchone()
    material_id = fila['id'] if fila else None

    if accion == 'baja':
        if material_id:
            cursor_wms.execute(
                "UPDATE materiales SET activo = 0, updated_at = %s WHERE id = %s",
                (_now(), material_id))
        return True, 'baja aplicada', material_id

    trazabilidad = (reg.get('trazabilidad') or 'ninguna').strip().lower()
    if trazabilidad not in ('lote', 'serie', 'ninguna'):
        trazabilidad = 'ninguna'

    metodo_picking = (reg.get('metodo_picking') or 'libre').strip().lower()
    if metodo_picking not in ('fifo', 'lifo', 'fefo', 'libre'):
        metodo_picking = 'libre'

    campos = dict(
        codigo_barras=(str(reg.get('codigo_barras') or '').strip() or None),
        descripcion=(str(reg.get('descripcion') or '').strip() or None),
        categoria_id=categoria_id,
        stock_minimo=float(reg.get('stock_minimo') or 0) or 0,
        stock_maximo=float(reg.get('stock_maximo') or 0) or 0,
        unidad_medida_id=unidad_id,
        trazabilidad=trazabilidad,
        metodo_picking=metodo_picking,
        peso_bruto=float(reg.get('peso_bruto') or 0) or None,
        peso_neto=float(reg.get('peso_neto') or 0) or None,
        costo_promedio=float(reg.get('costo_promedio') or 0) or 0,
        ultimo_costo=float(reg.get('ultimo_costo') or 0) or 0,
        activo=1 if _valor_bool(reg.get('activo')) else 0,
    )

    if material_id:
        cursor_wms.execute("""
            UPDATE materiales SET
                codigo_barras = %s, descripcion = %s, categoria_id = %s,
                stock_minimo = %s, stock_maximo = %s, unidad_medida_id = %s,
                trazabilidad = %s, metodo_picking = %s, peso_bruto = %s, peso_neto = %s,
                costo_promedio = %s, ultimo_costo = %s, activo = %s,
                nombre = %s, updated_at = %s
            WHERE id = %s
        """, (campos['codigo_barras'], campos['descripcion'], campos['categoria_id'],
              campos['stock_minimo'], campos['stock_maximo'], campos['unidad_medida_id'],
              campos['trazabilidad'], campos['metodo_picking'], campos['peso_bruto'], campos['peso_neto'],
              campos['costo_promedio'], campos['ultimo_costo'], campos['activo'],
              nombre, _now(), material_id))
        return True, 'actualizado', material_id

    material_id = execute_insert(cursor_wms, """
        INSERT INTO materiales (codigo, codigo_barras, nombre, descripcion, categoria_id,
            stock_minimo, stock_maximo, unidad_medida_id, trazabilidad, metodo_picking,
            peso_bruto, peso_neto, costo_promedio, ultimo_costo, activo, tenant_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (codigo, campos['codigo_barras'], nombre, campos['descripcion'], campos['categoria_id'],
          campos['stock_minimo'], campos['stock_maximo'], campos['unidad_medida_id'],
          campos['trazabilidad'], campos['metodo_picking'], campos['peso_bruto'], campos['peso_neto'],
          campos['costo_promedio'], campos['ultimo_costo'], campos['activo'], tenant_id))
    return True, 'insertado', material_id


def _aplicar_registro_ruta(reg, conn_wms, cursor_wms, cursor_admin):
    """Aplica un registro de intercambio_rutas sobre el WMS (upsert por nombre_ruta)."""
    tenant_codigo = (reg.get('tenant_codigo') or '').strip()
    nombre_ruta = (reg.get('nombre_ruta') or '').strip()

    if not tenant_codigo:
        raise ValueError('Falta tenant_codigo')
    if not nombre_ruta:
        raise ValueError('Falta nombre_ruta')

    tenant_id = _obtener_tenant_id(tenant_codigo, cursor_admin)
    if not tenant_id:
        raise ValueError(f"Tenant '{tenant_codigo}' no encontrado en taurus_admin")

    accion = (reg.get('accion') or 'alta').strip().lower()

    cursor_wms.execute(
        "SELECT id_ruta FROM rutas WHERE nombre_ruta = %s AND tenant_id = %s",
        (nombre_ruta, tenant_id))
    fila = cursor_wms.fetchone()
    ruta_id = fila['id_ruta'] if fila else None

    if accion == 'baja':
        if ruta_id:
            cursor_wms.execute("DELETE FROM rutas WHERE id_ruta = %s", (ruta_id,))
        return True, 'baja aplicada', ruta_id

    descripcion = (reg.get('descripcion') or '').strip() or None
    if ruta_id:
        cursor_wms.execute(
            "UPDATE rutas SET descripcion = %s WHERE id_ruta = %s",
            (descripcion, ruta_id))
        return True, 'actualizado', ruta_id

    ruta_id = execute_insert(cursor_wms, """
        INSERT INTO rutas (nombre_ruta, descripcion, tenant_id)
        VALUES (%s, %s, %s)
    """, (nombre_ruta, descripcion, tenant_id))
    return True, 'insertado', ruta_id


def _aplicar_registro_transporte(reg, conn_wms, cursor_wms, cursor_admin):
    """Aplica un registro de intercambio_transportes sobre el WMS (upsert por codigo)."""
    tenant_codigo = (reg.get('tenant_codigo') or '').strip()
    codigo = (reg.get('codigo') or '').strip()
    razonsocial = (reg.get('razonsocial') or '').strip()

    if not tenant_codigo:
        raise ValueError('Falta tenant_codigo')
    if not codigo:
        raise ValueError('Falta codigo del transporte')
    if not razonsocial:
        raise ValueError('Falta razonsocial del transporte')

    tenant_id = _obtener_tenant_id(tenant_codigo, cursor_admin)
    if not tenant_id:
        raise ValueError(f"Tenant '{tenant_codigo}' no encontrado en taurus_admin")

    accion = (reg.get('accion') or 'alta').strip().lower()

    muelle_id = None
    if accion != 'baja':
        muelle_id = _resolver_muelle(reg.get('muelle_codigo'), tenant_id, cursor_wms)

    cursor_wms.execute(
        "SELECT id_transporte FROM transportes WHERE codigo = %s AND tenant_id = %s",
        (codigo, tenant_id))
    fila = cursor_wms.fetchone()
    transporte_id = fila['id_transporte'] if fila else None

    if accion == 'baja':
        if transporte_id:
            cursor_wms.execute(
                "UPDATE transportes SET activo = 0 WHERE id_transporte = %s",
                (transporte_id,))
        return True, 'baja aplicada', transporte_id

    campos = dict(
        razonsocial=razonsocial,
        cuit=(str(reg.get('cuit') or '').strip() or None),
        telefono=(str(reg.get('telefono') or '').strip() or None),
        email=(str(reg.get('email') or '').strip() or None),
        id_muelle_salida=muelle_id,
        activo=1 if _valor_bool(reg.get('activo')) else 0,
    )

    if transporte_id:
        cursor_wms.execute("""
            UPDATE transportes SET razonsocial = %s, cuit = %s, telefono = %s,
                email = %s, id_muelle_salida = %s, activo = %s
            WHERE id_transporte = %s
        """, (campos['razonsocial'], campos['cuit'], campos['telefono'],
              campos['email'], campos['id_muelle_salida'], campos['activo'],
              transporte_id))
        return True, 'actualizado', transporte_id

    transporte_id = execute_insert(cursor_wms, """
        INSERT INTO transportes (codigo, razonsocial, cuit, telefono, email,
            id_muelle_salida, activo, tenant_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (codigo, campos['razonsocial'], campos['cuit'], campos['telefono'],
          campos['email'], campos['id_muelle_salida'], campos['activo'], tenant_id))
    return True, 'insertado', transporte_id


def _aplicar_registro_transporte_ruta(reg, conn_wms, cursor_wms, cursor_admin):
    """Aplica un registro de intercambio_transporte_rutas (asignacion ruta<->transporte).

    accion 'baja' elimina la asignacion; 'alta'/'modificacion' hace upsert.
    """
    tenant_codigo = (reg.get('tenant_codigo') or '').strip()
    transporte_codigo = (reg.get('transporte_codigo') or '').strip()
    ruta_nombre = (reg.get('ruta_nombre') or '').strip()

    if not tenant_codigo:
        raise ValueError('Falta tenant_codigo')
    if not transporte_codigo:
        raise ValueError('Falta transporte_codigo')
    if not ruta_nombre:
        raise ValueError('Falta ruta_nombre')

    tenant_id = _obtener_tenant_id(tenant_codigo, cursor_admin)
    if not tenant_id:
        raise ValueError(f"Tenant '{tenant_codigo}' no encontrado en taurus_admin")

    accion = (reg.get('accion') or 'alta').strip().lower()

    transporte_id = _resolver_transporte_codigo(transporte_codigo, tenant_id, cursor_wms)
    ruta_id = _resolver_ruta_nombre(ruta_nombre, tenant_id, cursor_wms)

    if accion == 'baja':
        cursor_wms.execute(
            "DELETE FROM transporte_rutas WHERE id_transporte = %s AND id_ruta = %s "
            "AND tenant_id = %s",
            (transporte_id, ruta_id, tenant_id))
        return True, 'baja aplicada', None

    observaciones = (reg.get('observaciones') or '').strip() or None
    cursor_wms.execute(
        "SELECT 1 FROM transporte_rutas WHERE id_transporte = %s AND id_ruta = %s "
        "AND tenant_id = %s",
        (transporte_id, ruta_id, tenant_id))
    if cursor_wms.fetchone():
        cursor_wms.execute(
            "UPDATE transporte_rutas SET observaciones = %s "
            "WHERE id_transporte = %s AND id_ruta = %s AND tenant_id = %s",
            (observaciones, transporte_id, ruta_id, tenant_id))
        return True, 'actualizado', None

    cursor_wms.execute(
        "INSERT INTO transporte_rutas (id_transporte, id_ruta, observaciones, tenant_id) "
        "VALUES (%s, %s, %s, %s)",
        (transporte_id, ruta_id, observaciones, tenant_id))
    return True, 'insertado', None


def _aplicar_registro_cliente(reg, conn_wms, cursor_wms, cursor_admin):
    """Aplica un registro de intercambio_clientes sobre el WMS (upsert por codigo)."""
    tenant_codigo = (reg.get('tenant_codigo') or '').strip()
    codigo = (reg.get('codigo') or '').strip()
    razonsocial = (reg.get('razonsocial') or '').strip()

    if not tenant_codigo:
        raise ValueError('Falta tenant_codigo')
    if not codigo:
        raise ValueError('Falta codigo del cliente')
    if not razonsocial:
        raise ValueError('Falta razonsocial del cliente')

    tenant_id = _obtener_tenant_id(tenant_codigo, cursor_admin)
    if not tenant_id:
        raise ValueError(f"Tenant '{tenant_codigo}' no encontrado en taurus_admin")

    accion = (reg.get('accion') or 'alta').strip().lower()

    id_ruta = None
    id_transporte = None
    if accion != 'baja':
        id_ruta = _resolver_ruta_nombre(reg.get('ruta_nombre'), tenant_id, cursor_wms)
        id_transporte = _resolver_transporte_codigo(reg.get('transporte_codigo'), tenant_id, cursor_wms)

    cursor_wms.execute(
        "SELECT id_cliente FROM clientes WHERE codigo = %s AND tenant_id = %s",
        (codigo, tenant_id))
    fila = cursor_wms.fetchone()
    cliente_id = fila['id_cliente'] if fila else None

    if accion == 'baja':
        if cliente_id:
            cursor_wms.execute(
                "UPDATE clientes SET activo = 0 WHERE id_cliente = %s",
                (cliente_id,))
        return True, 'baja aplicada', cliente_id

    campos = dict(
        razonsocial=razonsocial,
        cuit=(str(reg.get('cuit') or '').strip() or None),
        direccion=(str(reg.get('direccion') or '').strip() or None),
        localidad=(str(reg.get('localidad') or '').strip() or None),
        provincia=(str(reg.get('provincia') or '').strip() or None),
        telefono=(str(reg.get('telefono') or '').strip() or None),
        email=(str(reg.get('email') or '').strip() or None),
        contacto_nombre=(str(reg.get('contacto_nombre') or '').strip() or None),
        id_ruta=id_ruta,
        id_transporte_predeterminado=id_transporte,
        activo=1 if _valor_bool(reg.get('activo')) else 0,
    )

    if cliente_id:
        cursor_wms.execute("""
            UPDATE clientes SET razonsocial = %s, cuit = %s, direccion = %s,
                localidad = %s, provincia = %s, telefono = %s, email = %s,
                contacto_nombre = %s, id_ruta = %s, id_transporte_predeterminado = %s,
                activo = %s
            WHERE id_cliente = %s
        """, (campos['razonsocial'], campos['cuit'], campos['direccion'],
              campos['localidad'], campos['provincia'], campos['telefono'],
              campos['email'], campos['contacto_nombre'], campos['id_ruta'],
              campos['id_transporte_predeterminado'], campos['activo'], cliente_id))
        return True, 'actualizado', cliente_id

    cliente_id = execute_insert(cursor_wms, """
        INSERT INTO clientes (codigo, razonsocial, cuit, direccion, localidad,
            provincia, telefono, email, contacto_nombre,
            id_ruta, id_transporte_predeterminado, activo, tenant_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (codigo, campos['razonsocial'], campos['cuit'], campos['direccion'],
          campos['localidad'], campos['provincia'], campos['telefono'],
          campos['email'], campos['contacto_nombre'], campos['id_ruta'],
          campos['id_transporte_predeterminado'], campos['activo'], tenant_id))
    return True, 'insertado', cliente_id


def _parse_items_pedido(items_json, tenant_id, cursor_wms):
    """Parsea items_json de un pedido y resuelve cada material a su id en el WMS.

    items_json: lista JSON de {material_codigo, cantidad, tipo_stock}.
    Devuelve lista de dicts {id_material, cantidad, tipo_stock}. Lanza ValueError
    si el JSON es invalido, falta material_codigo o el material no existe.
    """
    if not items_json or not str(items_json).strip():
        return []
    try:
        data = json.loads(str(items_json).strip())
    except Exception as e:
        raise ValueError(f"items_json no es JSON valido: {str(items_json)[:200]}") from e
    if not isinstance(data, list):
        raise ValueError('items_json debe ser una lista')

    items = []
    for i, it in enumerate(data):
        if not isinstance(it, dict):
            raise ValueError(f"Item {i}: debe ser un objeto")
        material_codigo = (str(it.get('material_codigo') or '').strip())
        if not material_codigo:
            raise ValueError(f"Item {i}: falta material_codigo")
        cursor_wms.execute(
            "SELECT id FROM materiales WHERE codigo = %s AND (%s IS NULL OR tenant_id = %s)",
            (material_codigo, tenant_id, tenant_id))
        row = cursor_wms.fetchone()
        if not row:
            raise ValueError(f"Material '{material_codigo}' no encontrado en el WMS")
        try:
            cantidad = float(it.get('cantidad') or 0)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Item {i}: cantidad '{it.get('cantidad')}' invalida") from e
        tipo_stock = (str(it.get('tipo_stock') or 'Libre Venta').strip() or 'Libre Venta')
        items.append({'id_material': row['id'], 'cantidad': cantidad,
                      'tipo_stock': tipo_stock})
    return items


def _aplicar_registro_pedido(reg, conn_wms, cursor_wms, cursor_admin):
    """Aplica un registro de intercambio_pedidos sobre el WMS (upsert por nro_pedido).

    Cabecera en columnas del registro; items en items_json:
    [{"material_codigo": "...", "cantidad": 5, "tipo_stock": "Libre Venta"}].
    Referencias resueltas por nombre/codigo: cliente_codigo -> clientes.codigo,
    ruta_nombre -> rutas.nombre_ruta, transporte_codigo -> transportes.codigo,
    clase_nombre -> clases_pedido.nombre.
    accion 'baja' elimina el pedido (solo si aun no fue procesado).
    """
    tenant_codigo = (reg.get('tenant_codigo') or '').strip()
    nro_pedido = (reg.get('nro_pedido') or '').strip()
    cliente_codigo = (reg.get('cliente_codigo') or '').strip()
    fecha_pedido = _valor_fecha(reg.get('fecha_pedido'))

    if not tenant_codigo:
        raise ValueError('Falta tenant_codigo')
    if not nro_pedido:
        raise ValueError('Falta nro_pedido')
    if not cliente_codigo:
        raise ValueError('Falta cliente_codigo')
    if not fecha_pedido:
        raise ValueError('Falta fecha_pedido')

    try:
        datetime.datetime.strptime(fecha_pedido, '%Y-%m-%d')
    except ValueError as e:
        raise ValueError(f"fecha_pedido '{reg.get('fecha_pedido')}' no es una fecha valida (YYYY-MM-DD)") from e

    tenant_id = _obtener_tenant_id(tenant_codigo, cursor_admin)
    if not tenant_id:
        raise ValueError(f"Tenant '{tenant_codigo}' no encontrado en taurus_admin")

    accion = (reg.get('accion') or 'alta').strip().lower()

    cliente_id = _resolver_cliente_codigo(cliente_codigo, tenant_id, cursor_wms)

    cursor_wms.execute(
        "SELECT id_pedido, estado FROM pedidos_cabecera "
        "WHERE nro_pedido = %s AND tenant_id = %s",
        (nro_pedido, tenant_id))
    fila = cursor_wms.fetchone()
    pedido_id = fila['id_pedido'] if fila else None

    if accion == 'baja':
        if pedido_id:
            if fila['estado'] != 'Pendiente':
                raise ValueError(
                    f"Pedido '{nro_pedido}' no se puede dar de baja: estado '{fila['estado']}'")
            cursor_wms.execute(
                "DELETE FROM pedidos_cabecera WHERE id_pedido = %s", (pedido_id,))
        return True, 'baja aplicada', pedido_id

    id_clase = _resolver_clase_nombre(reg.get('clase_nombre'), tenant_id, cursor_wms)
    id_ruta = _resolver_ruta_nombre(reg.get('ruta_nombre'), tenant_id, cursor_wms)
    id_transporte = _resolver_transporte_codigo(reg.get('transporte_codigo'), tenant_id, cursor_wms)

    direccion = (reg.get('direccion_entrega') or '').strip() or None
    observaciones = (reg.get('observaciones') or '').strip() or None

    items = _parse_items_pedido(reg.get('items_json'), tenant_id, cursor_wms)

    if pedido_id:
        if fila['estado'] != 'Pendiente':
            raise ValueError(
                f"Pedido '{nro_pedido}' ya esta procesado, no se puede modificar")
        cursor_wms.execute("""
            UPDATE pedidos_cabecera SET id_cliente = %s, id_clase = %s, fecha_pedido = %s,
                id_ruta = %s, id_transporte = %s, direccion_entrega = %s,
                observaciones = %s, updated_at = %s
            WHERE id_pedido = %s
        """, (cliente_id, id_clase, fecha_pedido, id_ruta, id_transporte,
              direccion, observaciones, _now(), pedido_id))
        cursor_wms.execute(
            "DELETE FROM pedidos_detalle WHERE id_pedido = %s", (pedido_id,))
        mensaje = 'actualizado'
    else:
        estado_pedido = (reg.get('estado_pedido') or 'Pendiente').strip() or 'Pendiente'
        pedido_id = execute_insert(cursor_wms, """
            INSERT INTO pedidos_cabecera (nro_pedido, id_cliente, id_clase, fecha_pedido,
                id_ruta, id_transporte, direccion_entrega, observaciones, estado, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (nro_pedido, cliente_id, id_clase, fecha_pedido, id_ruta, id_transporte,
              direccion, observaciones, estado_pedido, tenant_id))
        mensaje = 'insertado'

    for it in items:
        cursor_wms.execute("""
            INSERT INTO pedidos_detalle (id_pedido, id_material, cantidad, tipo_stock, tenant_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (pedido_id, it['id_material'], it['cantidad'], it['tipo_stock'], tenant_id))

    return True, mensaje, pedido_id


# ============================================================================
# CATALOGO DE MODULOS
# ============================================================================

MODULOS = {
    'rutas': {
        'nombre': 'Rutas',
        'tabla': 'intercambio_rutas',
        'id_wms': 'id_ruta_wms',
        'aplicar': _aplicar_registro_ruta,
    },
    'transportes': {
        'nombre': 'Transportes',
        'tabla': 'intercambio_transportes',
        'id_wms': 'id_transporte_wms',
        'aplicar': _aplicar_registro_transporte,
    },
    'transporte_rutas': {
        'nombre': 'Asignaciones Ruta-Transporte',
        'tabla': 'intercambio_transporte_rutas',
        'id_wms': None,
        'aplicar': _aplicar_registro_transporte_ruta,
    },
    'clientes': {
        'nombre': 'Clientes',
        'tabla': 'intercambio_clientes',
        'id_wms': 'id_cliente_wms',
        'aplicar': _aplicar_registro_cliente,
    },
    'materiales': {
        'nombre': 'Materiales',
        'tabla': 'intercambio_materiales',
        'id_wms': 'id_material_wms',
        'aplicar': _aplicar_registro_material,
    },
    'pedidos': {
        'nombre': 'Pedidos',
        'tabla': 'intercambio_pedidos',
        'id_wms': 'id_pedido_wms',
        'aplicar': _aplicar_registro_pedido,
    },
}

# Orden de procesamiento: primero lo que otros modulos referencian.
ORDEN_PROCESO = ['rutas', 'transportes', 'transporte_rutas', 'clientes', 'materiales', 'pedidos']


def _referencia_registro(modulo, reg):
    """Devuelve una referencia corta del registro para la lista de errores."""
    if modulo == 'transporte_rutas':
        return f"{reg.get('transporte_codigo')} -> {reg.get('ruta_nombre')}"
    if modulo == 'pedidos':
        return (reg.get('nro_pedido') or '')
    return (reg.get('codigo') or reg.get('nombre_ruta') or reg.get('nombre')
            or reg.get('razonsocial') or '')


# ============================================================================
# REGISTRO DE LOG
# ============================================================================

def _registrar_log(modulo, procesados, errores, errores_detalle, usuario=None):
    try:
        conn = get_intercambio_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO intercambio_log
                    (modulo, resultado, registros_procesados, registros_error, detalle, usuario, fecha)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (modulo, 'ok' if errores == 0 else 'error', procesados, errores,
                  json.dumps(errores_detalle, ensure_ascii=False) if errores_detalle else None,
                  usuario, _now()))
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.error("No se pudo registrar log de intercambio: %s", e)


# ============================================================================
# PROCESAMIENTO (nucleo)
# ============================================================================

def _procesar_tabla_intercambio(tabla, id_wms_col, aplicar_func, modulo,
                                tenant_id=None, conn_int=None, conn_wms=None,
                                conn_admin=None, usuario=None):
    """Lee registros 'pendiente' de una tabla de intercambio y los aplica en el WMS.

    - tabla: nombre de la tabla en taurus_intercambio.
    - id_wms_col: columna de la tabla que guarda el id resultante en el WMS (o None).
    - aplicar_func: funcion (reg, conn_wms, cursor_wms, cursor_admin) -> (ok, mensaje, wms_id).
      Debe lanzar ValueError ante error (el mensaje se guarda en el registro).
    - conn_int/conn_wms/conn_admin: conexiones inyectables para testing.
    Devuelve dict {procesados, errores, errores_detalle, aviso}.
    """
    cerrar_int = conn_int is None
    cerrar_wms = conn_wms is None
    cerrar_admin = conn_admin is None

    if conn_int is None:
        conn_int = get_intercambio_connection()
    if conn_wms is None:
        conn_wms = get_db_connection()
    if conn_admin is None:
        conn_admin = _get_admin_connection()

    set_engine(get_db_engine())

    procesados = 0
    errores = 0
    errores_detalle = []

    try:
        cursor_int = conn_int.cursor()
        cursor_wms = conn_wms.cursor()
        cursor_admin = conn_admin.cursor()

        where = "estado = 'pendiente'"
        params = []
        if tenant_id is not None:
            tenant_codigo = _obtener_tenant_codigo(tenant_id, cursor_admin)
            if not tenant_codigo:
                return {'procesados': 0, 'errores': 0, 'errores_detalle': [],
                        'aviso': 'Tenant no encontrado'}
            where += " AND tenant_codigo = %s"
            params.append(tenant_codigo)

        cursor_int.execute(f"SELECT * FROM {tabla} WHERE {where} ORDER BY id ASC", params)
        registros = cursor_int.fetchall()

        for reg in registros:
            reg = dict(reg)
            rid = reg['id']
            try:
                ok, mensaje, wms_id = aplicar_func(reg, conn_wms, cursor_wms, cursor_admin)
                conn_wms.commit()
            except Exception as e:
                conn_wms.rollback()
                ok, mensaje, wms_id = False, str(e), None

            ahora = _now()
            if ok:
                procesados += 1
                if id_wms_col:
                    cursor_int.execute(f"""
                        UPDATE {tabla}
                        SET estado = 'procesado', error_mensaje = NULL,
                            {id_wms_col} = %s, intentos = intentos + 1,
                            fecha_procesado = %s, updated_at = %s
                        WHERE id = %s
                    """, (wms_id, ahora, ahora, rid))
                else:
                    cursor_int.execute(f"""
                        UPDATE {tabla}
                        SET estado = 'procesado', error_mensaje = NULL,
                            intentos = intentos + 1,
                            fecha_procesado = %s, updated_at = %s
                        WHERE id = %s
                    """, (ahora, ahora, rid))
            else:
                errores += 1
                mensaje_trunc = (mensaje or '')[:ERROR_LIMIT]
                errores_detalle.append({'id': rid, 'codigo': _referencia_registro(modulo, reg),
                                        'error': mensaje_trunc})
                cursor_int.execute(f"""
                    UPDATE {tabla}
                    SET estado = 'error', error_mensaje = %s,
                        intentos = intentos + 1, updated_at = %s
                    WHERE id = %s
                """, (mensaje_trunc, ahora, rid))
            conn_int.commit()
    finally:
        if cerrar_int:
            conn_int.close()
        if cerrar_wms:
            conn_wms.close()
        if cerrar_admin:
            conn_admin.close()

    _registrar_log(modulo, procesados, errores, errores_detalle, usuario)
    return {'procesados': procesados, 'errores': errores,
            'errores_detalle': errores_detalle}


def procesar_intercambio_materiales(tenant_id=None, conn_int=None, conn_wms=None,
                                   conn_admin=None, usuario=None):
    """Lee registros 'pendiente' de intercambio_materiales y los aplica en el WMS."""
    return _procesar_tabla_intercambio(
        'intercambio_materiales', 'id_material_wms', _aplicar_registro_material,
        'materiales', tenant_id, conn_int, conn_wms, conn_admin, usuario)


def procesar_intercambio_rutas(tenant_id=None, conn_int=None, conn_wms=None,
                               conn_admin=None, usuario=None):
    """Lee registros 'pendiente' de intercambio_rutas y los aplica en el WMS."""
    return _procesar_tabla_intercambio(
        'intercambio_rutas', 'id_ruta_wms', _aplicar_registro_ruta,
        'rutas', tenant_id, conn_int, conn_wms, conn_admin, usuario)


def procesar_intercambio_transportes(tenant_id=None, conn_int=None, conn_wms=None,
                                     conn_admin=None, usuario=None):
    """Lee registros 'pendiente' de intercambio_transportes y los aplica en el WMS."""
    return _procesar_tabla_intercambio(
        'intercambio_transportes', 'id_transporte_wms', _aplicar_registro_transporte,
        'transportes', tenant_id, conn_int, conn_wms, conn_admin, usuario)


def procesar_intercambio_transporte_rutas(tenant_id=None, conn_int=None, conn_wms=None,
                                          conn_admin=None, usuario=None):
    """Lee registros 'pendiente' de intercambio_transporte_rutas y los aplica en el WMS."""
    return _procesar_tabla_intercambio(
        'intercambio_transporte_rutas', None, _aplicar_registro_transporte_ruta,
        'transporte_rutas', tenant_id, conn_int, conn_wms, conn_admin, usuario)


def procesar_intercambio_clientes(tenant_id=None, conn_int=None, conn_wms=None,
                                  conn_admin=None, usuario=None):
    """Lee registros 'pendiente' de intercambio_clientes y los aplica en el WMS."""
    return _procesar_tabla_intercambio(
        'intercambio_clientes', 'id_cliente_wms', _aplicar_registro_cliente,
        'clientes', tenant_id, conn_int, conn_wms, conn_admin, usuario)


def procesar_intercambio_pedidos(tenant_id=None, conn_int=None, conn_wms=None,
                                 conn_admin=None, usuario=None):
    """Lee registros 'pendiente' de intercambio_pedidos y los aplica en el WMS."""
    return _procesar_tabla_intercambio(
        'intercambio_pedidos', 'id_pedido_wms', _aplicar_registro_pedido,
        'pedidos', tenant_id, conn_int, conn_wms, conn_admin, usuario)


def procesar_intercambio(tenant_id=None, conn_int=None, conn_wms=None,
                         conn_admin=None, usuario=None, modulos=None):
    """Procesa todos los modulos de intercambio en orden de dependencia.

    Orden por defecto: rutas -> transportes -> transporte_rutas -> clientes -> materiales.
    Devuelve dict {procesados, errores, errores_detalle, aviso}.
    """
    if modulos is None:
        modulos = ORDEN_PROCESO

    cerrar_int = conn_int is None
    cerrar_wms = conn_wms is None
    cerrar_admin = conn_admin is None

    if conn_int is None:
        conn_int = get_intercambio_connection()
    if conn_wms is None:
        conn_wms = get_db_connection()
    if conn_admin is None:
        conn_admin = _get_admin_connection()

    total = {'procesados': 0, 'errores': 0, 'errores_detalle': [], 'aviso': None}
    try:
        for modulo in modulos:
            conf = MODULOS.get(modulo)
            if not conf:
                continue
            res = _procesar_tabla_intercambio(
                conf['tabla'], conf['id_wms'], conf['aplicar'], modulo,
                tenant_id, conn_int, conn_wms, conn_admin, usuario)
            total['procesados'] += res['procesados']
            total['errores'] += res['errores']
            total['errores_detalle'].extend(res['errores_detalle'])
            if res.get('aviso'):
                total['aviso'] = res['aviso']
    finally:
        if cerrar_int:
            conn_int.close()
        if cerrar_wms:
            conn_wms.close()
        if cerrar_admin:
            conn_admin.close()

    return total


def reintentar_intercambio(ids=None, tenant_id=None, tabla='intercambio_materiales',
                           conn_int=None, conn_admin=None):
    """Devuelve a 'pendiente' registros en 'error' de la tabla indicada."""
    cerrar_int = conn_int is None
    cerrar_admin = conn_admin is None

    if conn_int is None:
        conn_int = get_intercambio_connection()
    if conn_admin is None:
        conn_admin = _get_admin_connection()

    try:
        cursor = conn_int.cursor()
        where = "estado = 'error'"
        params = []
        if ids:
            placeholders = in_clause_sql(ids)
            where += f" AND id IN ({placeholders})"
            params.extend(ids)
        if tenant_id is not None:
            cursor_admin = conn_admin.cursor()
            try:
                tenant_codigo = _obtener_tenant_codigo(tenant_id, cursor_admin)
            finally:
                cursor_admin.close()
            if not tenant_codigo:
                return 0
            where += " AND tenant_codigo = %s"
            params.append(tenant_codigo)
        cursor.execute(
            f"UPDATE {tabla} SET estado = 'pendiente', "
            f"error_mensaje = NULL, updated_at = %s WHERE {where}",
            [_now(), *params])
        conn_int.commit()
        return cursor.rowcount
    finally:
        if cerrar_int:
            conn_int.close()
        if cerrar_admin:
            conn_admin.close()


def reintentar_todo(tenant_id=None, conn_int=None, conn_admin=None):
    """Devuelve a 'pendiente' los errores de todas las tablas de intercambio."""
    total = 0
    for conf in MODULOS.values():
        total += reintentar_intercambio(tenant_id=tenant_id, tabla=conf['tabla'],
                                        conn_int=conn_int, conn_admin=conn_admin)
    return total


# ============================================================================
# BLUEPRINT WMS
# ============================================================================

def _condicion_tenant(cursor_admin, tenant_id):
    """Devuelve (where_sql, params) para filtrar registros por tenant."""
    if tenant_id is None:
        return "1=1", []
    tenant_codigo = _obtener_tenant_codigo(tenant_id, cursor_admin)
    if not tenant_codigo:
        return "1=1", []
    return "tenant_codigo = %s", [tenant_codigo]


def _normalizar_registro(modulo, reg):
    """Convierte una fila de una tabla de intercambio a una vista comun para la UI."""
    if modulo == 'transporte_rutas':
        referencia = (reg.get('transporte_codigo') or '') + ' -> ' + (reg.get('ruta_nombre') or '')
        nombre = (reg.get('observaciones') or '') or None
    elif modulo == 'rutas':
        referencia = reg.get('nombre_ruta')
        nombre = reg.get('descripcion')
    elif modulo == 'pedidos':
        referencia = reg.get('nro_pedido')
        nombre = reg.get('cliente_codigo')
    else:
        referencia = reg.get('codigo')
        nombre = reg.get('nombre') or reg.get('razonsocial')
    return {
        'modulo': modulo,
        'modulo_nombre': MODULOS.get(modulo, {}).get('nombre', modulo),
        'id': reg.get('id'),
        'tenant_codigo': reg.get('tenant_codigo'),
        'referencia': referencia,
        'nombre': nombre,
        'accion': reg.get('accion'),
        'estado': reg.get('estado'),
        'intentos': reg.get('intentos'),
        'error_mensaje': reg.get('error_mensaje'),
        'fecha_carga': reg.get('fecha_carga'),
        'fecha_procesado': reg.get('fecha_procesado'),
    }


@intercambio_bp.route('/intercambio')
def listar():
    conn_int = get_intercambio_connection()
    conn_admin = None
    try:
        cursor_int = conn_int.cursor()
        tenant_id = session.get('tenant_id')
        try:
            conn_admin = _get_admin_connection()
            cursor_admin = conn_admin.cursor()
            where_tenant, params_tenant = _condicion_tenant(cursor_admin, tenant_id)
        except Exception:
            where_tenant, params_tenant = "1=1", []

        filtro = request.args.get('estado', '')
        if filtro not in ('pendiente', 'procesado', 'error'):
            filtro = ''

        modulo = request.args.get('modulo', '')
        if modulo not in MODULOS:
            modulo = ''

        conteo = {'pendiente': 0, 'procesado': 0, 'error': 0}
        registros = []
        for m, conf in MODULOS.items():
            if modulo and modulo != m:
                continue

            cursor_int.execute(
                f"SELECT estado, COUNT(*) AS total FROM {conf['tabla']} "
                f"WHERE {where_tenant} GROUP BY estado", params_tenant)
            for r in cursor_int.fetchall():
                conteo[r['estado']] = conteo.get(r['estado'], 0) + r['total']

            where = where_tenant
            params = list(params_tenant)
            if filtro:
                where += " AND estado = %s"
                params.append(filtro)
            params.append(300)
            cursor_int.execute(
                f"SELECT * FROM {conf['tabla']} WHERE {where} "
                f"ORDER BY id DESC LIMIT %s", params)
            for row in cursor_int.fetchall():
                registros.append(_normalizar_registro(m, dict(row)))

        registros.sort(key=lambda r: r['fecha_carga'] or datetime.datetime.min, reverse=True)
        registros = registros[:300]

        cursor_int.execute(
            "SELECT * FROM intercambio_log ORDER BY id DESC LIMIT 20")
        logs = cursor_int.fetchall()
    finally:
        if conn_admin is not None:
            conn_admin.close()
        conn_int.close()

    return render_template('intercambio.html',
                           conteo=conteo,
                           registros=registros,
                           logs=logs,
                           filtro=filtro,
                           modulo=modulo,
                           modulos=MODULOS,
                           tenant_id=session.get('tenant_id'))


@intercambio_bp.route('/intercambio/procesar', methods=['POST'])
def procesar():
    try:
        resultado = procesar_intercambio(
            tenant_id=session.get('tenant_id'), usuario=session.get('username'))
        if resultado.get('aviso'):
            flash(resultado['aviso'], 'warning')
        elif resultado['errores'] == 0:
            flash(f"Intercambio procesado: {resultado['procesados']} registro(s) aplicados.", 'success')
        else:
            flash(f"Intercambio procesado: {resultado['procesados']} aplicados, "
                  f"{resultado['errores']} con error. Revise la lista de errores.", 'warning')
    except Exception as e:
        flash(f"Error al procesar el intercambio: {e!s}", 'danger')
    return redirect(url_for('intercambio.listar'))


@intercambio_bp.route('/intercambio/reintentar', methods=['POST'])
def reintentar_todos():
    try:
        n = reintentar_todo(tenant_id=session.get('tenant_id'))
        flash(f"{n} registro(s) en error devuelto(s) a pendiente. Ejecute Procesar para aplicarlos.", 'info')
    except Exception as e:
        flash(f"Error: {e!s}", 'danger')
    return redirect(url_for('intercambio.listar'))


@intercambio_bp.route('/intercambio/reintentar/<modulo>/<int:rid>', methods=['POST'])
def reintentar_uno(modulo, rid):
    conf = MODULOS.get(modulo)
    if not conf:
        flash('Módulo no válido', 'danger')
        return redirect(url_for('intercambio.listar'))
    try:
        reintentar_intercambio(ids=[rid], tenant_id=session.get('tenant_id'),
                               tabla=conf['tabla'])
        flash("Registro devuelto a pendiente. Ejecute Procesar para aplicarlo.", 'info')
    except Exception as e:
        flash(f"Error: {e!s}", 'danger')
    return redirect(url_for('intercambio.listar'))
