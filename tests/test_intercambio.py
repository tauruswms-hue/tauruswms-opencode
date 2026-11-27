"""Tests de integración del módulo de intercambio (conexiones inyectables).

Requisito: MySQL con taurus_admin + taurus_wms + taurus_intercambio.
Se crean registros con codigo unico TEST-* y se limpian al final.
"""

import uuid

import pytest
from conftest import requires_db

from modules.db_config import (
    _get_admin_connection,
    get_db_connection,
    get_intercambio_connection,
)
from modules.intercambio import (
    procesar_intercambio_clientes,
    procesar_intercambio_materiales,
    procesar_intercambio_rutas,
)


@pytest.fixture(scope='module')
def tenant_id():
    """Devuelve un tenant_id real de taurus_admin.tenants."""
    conn = _get_admin_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, codigo FROM tenants WHERE activo = 1 ORDER BY id LIMIT 1")
        fila = cur.fetchone()
        assert fila, 'No hay tenants activos en taurus_admin'
        return fila['id']
    finally:
        conn.close()


@pytest.fixture
def conexiones():
    conn_int = get_intercambio_connection()
    conn_wms = get_db_connection()
    conn_admin = _get_admin_connection()
    yield conn_int, conn_wms, conn_admin
    conn_int.close()
    conn_wms.close()
    conn_admin.close()


def _limpiar(conn, cur, tablas, tenant_codigo, codigo):
    for tabla in tablas:
        cur.execute(f"DELETE FROM {tabla} WHERE tenant_codigo = %s AND codigo = %s",
                    (tenant_codigo, codigo))


def test_material_alta(conexiones, tenant_id):
    conn_int, conn_wms, conn_admin = conexiones
    codigo = 'TEST-INT-' + uuid.uuid4().hex[:8]
    nombre = 'Material test intercambio'

    conn_admin_cur = conn_admin.cursor()
    conn_admin_cur.execute("SELECT codigo FROM tenants WHERE id = %s", (tenant_id,))
    tenant_codigo = conn_admin_cur.fetchone()['codigo']
    conn_admin_cur.close()

    # insertar pendiente en intercambio_materiales
    cur = conn_int.cursor()
    cur.execute("""
        INSERT INTO intercambio_materiales
            (tenant_codigo, codigo, nombre, accion, estado)
        VALUES (%s, %s, %s, 'alta', 'pendiente')
    """, (tenant_codigo, codigo, nombre))
    conn_int.commit()
    cur.close()

    try:
        res = procesar_intercambio_materiales(
            tenant_id=tenant_id, conn_int=conn_int, conn_wms=conn_wms,
            conn_admin=conn_admin)
        assert res['procesados'] == 1, res['errores_detalle']
        assert res['errores'] == 0

        cur = conn_wms.cursor()
        cur.execute("SELECT id, nombre, tenant_id FROM materiales WHERE codigo = %s AND tenant_id = %s",
                    (codigo, tenant_id))
        mat = cur.fetchone()
        assert mat, 'El material no se creo en el WMS'
        assert mat['nombre'] == nombre
        cur.close()

        # el registro de intercambio debe quedar procesado con id_wms
        cur = conn_int.cursor()
        cur.execute("SELECT estado, id_material_wms FROM intercambio_materiales WHERE codigo = %s",
                    (codigo,))
        reg = cur.fetchone()
        assert reg['estado'].upper() == 'PROCESADO'
        assert reg['id_material_wms'] == mat['id']
        cur.close()
    finally:
        cur = conn_wms.cursor()
        cur.execute("DELETE FROM materiales WHERE codigo = %s AND tenant_id = %s", (codigo, tenant_id))
        conn_wms.commit()
        cur.close()
        cur = conn_int.cursor()
        _limpiar(conn_int, cur, ['intercambio_materiales'], tenant_codigo, codigo)
        conn_int.commit()
        cur.close()


def test_material_baja(conexiones, tenant_id):
    conn_int, conn_wms, conn_admin = conexiones
    codigo = 'TEST-INT-' + uuid.uuid4().hex[:8]
    nombre = 'Material test baja'

    conn_admin_cur = conn_admin.cursor()
    conn_admin_cur.execute("SELECT codigo FROM tenants WHERE id = %s", (tenant_id,))
    tenant_codigo = conn_admin_cur.fetchone()['codigo']
    conn_admin_cur.close()

    # crear material directamente en WMS
    cur = conn_wms.cursor()
    cur.execute("""
        INSERT INTO materiales (codigo, nombre, activo, tenant_id)
        VALUES (%s, %s, 1, %s)
    """, (codigo, nombre, tenant_id))
    conn_wms.commit()
    cur.close()

    # registrar baja en intercambio
    cur = conn_int.cursor()
    cur.execute("""
        INSERT INTO intercambio_materiales
            (tenant_codigo, codigo, nombre, accion, estado)
        VALUES (%s, %s, %s, 'baja', 'pendiente')
    """, (tenant_codigo, codigo, nombre))
    conn_int.commit()
    cur.close()

    try:
        res = procesar_intercambio_materiales(
            tenant_id=tenant_id, conn_int=conn_int, conn_wms=conn_wms,
            conn_admin=conn_admin)
        assert res['procesados'] == 1, res['errores_detalle']

        cur = conn_wms.cursor()
        cur.execute("SELECT activo FROM materiales WHERE codigo = %s AND tenant_id = %s",
                    (codigo, tenant_id))
        mat = cur.fetchone()
        assert mat and mat['activo'] == 0, 'La baja no desactivo el material'
        cur.close()
    finally:
        cur = conn_wms.cursor()
        cur.execute("DELETE FROM materiales WHERE codigo = %s AND tenant_id = %s", (codigo, tenant_id))
        conn_wms.commit()
        cur.close()
        cur = conn_int.cursor()
        _limpiar(conn_int, cur, ['intercambio_materiales'], tenant_codigo, codigo)
        conn_int.commit()
        cur.close()


def test_material_falta_codigo_queda_error(conexiones, tenant_id):
    """Registro sin codigo no debe romper el lote: queda en 'error'."""
    conn_int, conn_wms, conn_admin = conexiones

    conn_admin_cur = conn_admin.cursor()
    conn_admin_cur.execute("SELECT codigo FROM tenants WHERE id = %s", (tenant_id,))
    tenant_codigo = conn_admin_cur.fetchone()['codigo']
    conn_admin_cur.close()

    cur = conn_int.cursor()
    cur.execute("""
        INSERT INTO intercambio_materiales
            (tenant_codigo, codigo, nombre, accion, estado)
        VALUES (%s, %s, %s, 'alta', 'pendiente')
    """, (tenant_codigo, 'TEST-ERR-' + uuid.uuid4().hex[:6], 'Sin codigo'))
    conn_int.commit()
    cur.close()

    # insertar un registro valido que debe procesarse
    codigo_bueno = 'TEST-INT-' + uuid.uuid4().hex[:8]
    cur = conn_int.cursor()
    cur.execute("""
        INSERT INTO intercambio_materiales
            (tenant_codigo, codigo, nombre, accion, estado)
        VALUES (%s, %s, %s, 'alta', 'pendiente')
    """, (tenant_codigo, codigo_bueno, 'Material valido'))
    conn_int.commit()
    cur.close()

    try:
        # registro con codigo vacio (NOT NULL pero '' posible): debe quedar en error
        codigo_mal = ''
        cur = conn_int.cursor()
        cur.execute("""
            INSERT INTO intercambio_materiales
                (tenant_codigo, codigo, nombre, accion, estado)
            VALUES (%s, %s, %s, 'alta', 'pendiente')
        """, (tenant_codigo, codigo_mal, 'Sin codigo'))
        conn_int.commit()
        cur.close()

        procesar_intercambio_materiales(
            tenant_id=tenant_id, conn_int=conn_int, conn_wms=conn_wms,
            conn_admin=conn_admin)

        # el valido se proceso; el de codigo vacio quedo en error
        cur = conn_int.cursor()
        cur.execute("SELECT estado FROM intercambio_materiales WHERE codigo = %s", (codigo_bueno,))
        assert cur.fetchone()['estado'].upper() == 'PROCESADO'
        cur.execute("SELECT estado, error_mensaje FROM intercambio_materiales WHERE codigo = %s",
                    (codigo_mal,))
        fila = cur.fetchone()
        assert fila['estado'].upper() == 'ERROR'
        assert 'codigo' in (fila['error_mensaje'] or '').lower()
        cur.close()
    finally:
        cur = conn_wms.cursor()
        cur.execute("DELETE FROM materiales WHERE codigo LIKE 'TEST-%%' AND tenant_id = %s", (tenant_id,))
        conn_wms.commit()
        cur.close()
        cur = conn_int.cursor()
        cur.execute("DELETE FROM intercambio_materiales WHERE codigo LIKE 'TEST-%%'")
        conn_int.commit()
        cur.close()


@requires_db
def test_cliente_modificacion_completa_pedidos_pendientes(conexiones, tenant_id):
    """Al completar ruta/transporte del maestro por intercambio se rellenan los pedidos Pendientes."""
    conn_int, conn_wms, conn_admin = conexiones
    sufijo = uuid.uuid4().hex[:8]
    codigo, nombre_ruta = 'TEST-INT-' + sufijo, 'Ruta ' + sufijo
    codigo_transporte, nro_pedido = 'TRANS-' + sufijo, 'PED-' + sufijo

    cur_admin = conn_admin.cursor()
    cur_admin.execute("SELECT codigo FROM tenants WHERE id = %s", (tenant_id,))
    tenant_codigo = cur_admin.fetchone()['codigo']
    cur_admin.close()

    cur = conn_wms.cursor()
    cur.execute("INSERT INTO rutas (nombre_ruta, tenant_id, activo) VALUES (%s, %s, 1)", (nombre_ruta, tenant_id))
    cur.execute("INSERT INTO transportes (codigo, razonsocial, tenant_id, activo) VALUES (%s, %s, %s, 1)",
                (codigo_transporte, 'Transporte test', tenant_id))
    cur.execute("""INSERT INTO clientes (codigo, razonsocial, tenant_id)
                   VALUES (%s, %s, %s)""", (codigo, 'Cliente test', tenant_id))
    cur.execute("SELECT id_cliente FROM clientes WHERE codigo = %s AND tenant_id = %s", (codigo, tenant_id))
    cliente_id = cur.fetchone()['id_cliente']
    cur.execute("""INSERT INTO pedidos_cabecera (nro_pedido, id_cliente, fecha_pedido, estado, tenant_id)
                   VALUES (%s, %s, CURRENT_DATE, 'Pendiente', %s)""", (nro_pedido, cliente_id, tenant_id))
    conn_wms.commit()

    try:
        cur = conn_int.cursor()
        cur.execute("""INSERT INTO intercambio_clientes
                       (tenant_codigo, codigo, razonsocial, ruta_nombre, transporte_codigo, accion, estado)
                       VALUES (%s, %s, 'Cliente test', %s, %s, 'modificacion', 'pendiente')""",
                    (tenant_codigo, codigo, nombre_ruta, codigo_transporte))
        conn_int.commit()
        cur.close()

        res = procesar_intercambio_clientes(
            tenant_id=tenant_id, conn_int=conn_int, conn_wms=conn_wms, conn_admin=conn_admin)
        assert res['procesados'] == 1 and res['errores'] == 0, res['errores_detalle']

        cur = conn_wms.cursor()
        cur.execute("SELECT id_ruta, id_transporte FROM pedidos_cabecera WHERE nro_pedido = %s", (nro_pedido,))
        pedido = cur.fetchone()
        cur.execute("SELECT id_ruta FROM rutas WHERE nombre_ruta = %s AND tenant_id = %s", (nombre_ruta, tenant_id))
        id_ruta = cur.fetchone()['id_ruta']
        cur.execute("SELECT id_transporte FROM transportes WHERE codigo = %s AND tenant_id = %s",
                    (codigo_transporte, tenant_id))
        id_transporte = cur.fetchone()['id_transporte']
        assert (pedido['id_ruta'], pedido['id_transporte']) == (id_ruta, id_transporte)
    finally:
        cur = conn_wms.cursor()
        cur.execute("DELETE FROM pedidos_cabecera WHERE nro_pedido = %s", (nro_pedido,))
        cur.execute("DELETE FROM clientes WHERE codigo = %s AND tenant_id = %s", (codigo, tenant_id))
        cur.execute("DELETE FROM transportes WHERE codigo = %s AND tenant_id = %s", (codigo_transporte, tenant_id))
        cur.execute("DELETE FROM rutas WHERE nombre_ruta = %s AND tenant_id = %s", (nombre_ruta, tenant_id))
        conn_wms.commit()
        cur.close()
        cur = conn_int.cursor()
        _limpiar(conn_int, cur, ['intercambio_clientes'], tenant_codigo, codigo)
        conn_int.commit()
        cur.close()


def test_rutas_upsert(conexiones, tenant_id):
    """Alta de ruta via intercambio crea/actualiza wms.rutas."""
    conn_int, conn_wms, conn_admin = conexiones
    nombre_ruta = 'TEST-RUTA-' + uuid.uuid4().hex[:8]

    conn_admin_cur = conn_admin.cursor()
    conn_admin_cur.execute("SELECT codigo FROM tenants WHERE id = %s", (tenant_id,))
    tenant_codigo = conn_admin_cur.fetchone()['codigo']
    conn_admin_cur.close()

    cur = conn_int.cursor()
    cur.execute("""
        INSERT INTO intercambio_rutas
            (tenant_codigo, nombre_ruta, descripcion, accion, estado)
        VALUES (%s, %s, 'ruta de prueba', 'alta', 'pendiente')
    """, (tenant_codigo, nombre_ruta))
    conn_int.commit()
    cur.close()

    try:
        res = procesar_intercambio_rutas(
            tenant_id=tenant_id, conn_int=conn_int, conn_wms=conn_wms,
            conn_admin=conn_admin)
        assert res['procesados'] == 1, res['errores_detalle']

        cur = conn_wms.cursor()
        cur.execute("SELECT id_ruta FROM rutas WHERE nombre_ruta = %s AND tenant_id = %s",
                    (nombre_ruta, tenant_id))
        ruta = cur.fetchone()
        assert ruta, 'La ruta no se creo en el WMS'
        cur.close()
    finally:
        cur = conn_wms.cursor()
        cur.execute("DELETE FROM rutas WHERE nombre_ruta = %s AND tenant_id = %s",
                    (nombre_ruta, tenant_id))
        conn_wms.commit()
        cur.close()
        cur = conn_int.cursor()
        cur.execute("DELETE FROM intercambio_rutas WHERE nombre_ruta = %s", (nombre_ruta,))
        conn_int.commit()
        cur.close()
