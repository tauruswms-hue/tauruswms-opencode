"""Test de integración de la importación de pedidos. Requiere MySQL. Crea y limpia los datos."""

import io
import uuid

from conftest import requires_db

from modules.db_config import get_db_connection


@requires_db
def test_importar_pedido_guarda_tenant_en_detalle(logged_client, usuario_wms):
    """Los ítems importados llevan el tenant del usuario (si no, el tenant no ve su detalle)."""
    tid = usuario_wms['tenant_id']
    sufijo = uuid.uuid4().hex[:8]
    cliente_cod, material_cod = 'TEST-IMP-CLI-' + sufijo, 'TEST-IMP-MAT-' + sufijo
    id_cliente = id_material = None

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO clientes (codigo, razonsocial, activo, tenant_id) VALUES (%s, %s, 1, %s)",
                    (cliente_cod, 'Cliente importacion', tid))
        id_cliente = cur.lastrowid
        cur.execute("""
            INSERT INTO materiales (codigo, nombre, trazabilidad, metodo_picking, activo, tenant_id)
            VALUES (%s, %s, 'lote', 'fifo', 1, %s)
        """, (material_cod, 'Material importacion', tid))
        id_material = cur.lastrowid
        conn.commit()

        csv = ("agrupador,cliente_codigo,fecha_pedido,observaciones,material_codigo,cantidad,tipo_stock\n"
               f"G1,{cliente_cod},2026-01-15,test,{material_cod},5,Libre Venta\n")
        resp = logged_client.post('/pedidos/importar', data={
            'archivo': (io.BytesIO(csv.encode('utf-8')), 'pedidos.csv'),
        }, content_type='multipart/form-data')
        assert resp.status_code == 200
        resultado = resp.get_json()
        assert resultado['insertados'] == 1, resultado
        conn.commit()

        cur.execute("""
            SELECT d.tenant_id, d.cantidad FROM pedidos_detalle d
            JOIN pedidos_cabecera p ON d.id_pedido = p.id_pedido
            WHERE p.id_cliente = %s
        """, (id_cliente,))
        filas = cur.fetchall()
        assert len(filas) == 1
        assert filas[0]['tenant_id'] == tid
        assert filas[0]['cantidad'] == 5
    finally:
        if id_cliente:
            cur.execute("""
                DELETE FROM pedidos_detalle
                WHERE id_pedido IN (SELECT id_pedido FROM pedidos_cabecera WHERE id_cliente = %s)
            """, (id_cliente,))
            cur.execute("DELETE FROM pedidos_cabecera WHERE id_cliente = %s", (id_cliente,))
            cur.execute("DELETE FROM clientes WHERE id_cliente = %s", (id_cliente,))
        if id_material:
            cur.execute("DELETE FROM materiales WHERE id = %s", (id_material,))
        conn.commit()
        cur.close()
        conn.close()


@requires_db
def test_importar_pedido_toma_clase_ruta_y_transporte(logged_client, usuario_wms):
    """La clase viene en el archivo; la ruta y el transporte salen del cliente."""
    tid = usuario_wms['tenant_id']
    sufijo = uuid.uuid4().hex[:8]
    cliente_cod = 'TEST-IMP-CLI-' + sufijo
    material_cod = 'TEST-IMP-MAT-' + sufijo
    ruta_nombre = 'TEST-IMP-RUTA-' + sufijo
    transporte_cod = 'TEST-IMP-TRA-' + sufijo
    clase_nombre = 'TEST-IMP-CLA-' + sufijo
    ids = {}

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO rutas (nombre_ruta, activo, tenant_id) VALUES (%s, 1, %s)", (ruta_nombre, tid))
        ids['ruta'] = cur.lastrowid
        cur.execute("""
            INSERT INTO transportes (codigo, razonsocial, activo, tenant_id)
            VALUES (%s, 'Transporte importacion', 1, %s)
        """, (transporte_cod, tid))
        ids['transporte'] = cur.lastrowid
        cur.execute("INSERT INTO clases_pedido (nombre, activo, tenant_id) VALUES (%s, 1, %s)", (clase_nombre, tid))
        ids['clase'] = cur.lastrowid
        cur.execute("""
            INSERT INTO clientes (codigo, razonsocial, activo, id_ruta, id_transporte_predeterminado, tenant_id)
            VALUES (%s, 'Cliente importacion', 1, %s, %s, %s)
        """, (cliente_cod, ids['ruta'], ids['transporte'], tid))
        ids['cliente'] = cur.lastrowid
        cur.execute("""
            INSERT INTO materiales (codigo, nombre, trazabilidad, metodo_picking, activo, tenant_id)
            VALUES (%s, 'Material importacion', 'lote', 'fifo', 1, %s)
        """, (material_cod, tid))
        ids['material'] = cur.lastrowid
        conn.commit()

        csv = ("agrupador,cliente_codigo,clase_nombre,fecha_pedido,observaciones,material_codigo,cantidad,tipo_stock\n"
               f"G2,{cliente_cod},{clase_nombre},2026-01-15,test,{material_cod},5,Libre Venta\n")
        resp = logged_client.post('/pedidos/importar', data={
            'archivo': (io.BytesIO(csv.encode('utf-8')), 'pedidos.csv'),
        }, content_type='multipart/form-data')
        assert resp.status_code == 200
        assert resp.get_json()['insertados'] == 1
        conn.commit()

        cur.execute("SELECT id_clase, id_ruta, id_transporte FROM pedidos_cabecera WHERE id_cliente = %s", (ids['cliente'],))
        fila = cur.fetchone()
        assert (fila['id_clase'], fila['id_ruta'], fila['id_transporte']) == (
            ids['clase'], ids['ruta'], ids['transporte'])

        csv_mal = csv.replace(clase_nombre, 'NOEXISTE').replace('G2,', 'G3,')
        resp = logged_client.post('/pedidos/importar', data={
            'archivo': (io.BytesIO(csv_mal.encode('utf-8')), 'pedidos.csv'),
        }, content_type='multipart/form-data')
        assert resp.status_code == 200
        resultado = resp.get_json()
        assert resultado['insertados'] == 0
        assert 'Clase de pedido "NOEXISTE" no encontrada' in resultado['errores'][0]['razon']
        cur.execute("SELECT COUNT(*) AS n FROM pedidos_cabecera WHERE id_cliente = %s", (ids['cliente'],))
        assert cur.fetchone()['n'] == 1
    finally:
        if ids.get('cliente'):
            cur.execute("""
                DELETE FROM pedidos_detalle
                WHERE id_pedido IN (SELECT id_pedido FROM pedidos_cabecera WHERE id_cliente = %s)
            """, (ids['cliente'],))
            cur.execute("DELETE FROM pedidos_cabecera WHERE id_cliente = %s", (ids['cliente'],))
            cur.execute("DELETE FROM clientes WHERE id_cliente = %s", (ids['cliente'],))
        if ids.get('material'):
            cur.execute("DELETE FROM materiales WHERE id = %s", (ids['material'],))
        if ids.get('transporte'):
            cur.execute("DELETE FROM transportes WHERE id_transporte = %s", (ids['transporte'],))
        if ids.get('clase'):
            cur.execute("DELETE FROM clases_pedido WHERE id_clase = %s", (ids['clase'],))
        if ids.get('ruta'):
            cur.execute("DELETE FROM rutas WHERE id_ruta = %s", (ids['ruta'],))
        conn.commit()
        cur.close()
        conn.close()
