-- db: wms
-- Completa pedidos_detalle.tenant_id en los ítems de pedidos importados.
-- La importación de pedidos (/pedidos/importar) insertaba el detalle sin
-- tenant_id, así que el tenant no veía los ítems de sus pedidos importados
-- (las consultas filtran por d.tenant_id). El código ya se corrigió; esta
-- migración cubre los registros existentes copiando el tenant de la cabecera.
-- Idempotente: solo toca filas con tenant_id NULL. SQL estándar, válido en
-- los 4 engines.

UPDATE pedidos_detalle
SET tenant_id = (SELECT p.tenant_id
                 FROM pedidos_cabecera p
                 WHERE p.id_pedido = pedidos_detalle.id_pedido)
WHERE tenant_id IS NULL;
