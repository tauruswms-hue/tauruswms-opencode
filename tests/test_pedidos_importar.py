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
