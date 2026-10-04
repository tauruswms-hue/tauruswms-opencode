-- Scoping de transporte_rutas por tenant.
-- La tabla de asignacion ruta<->transporte no tenia tenant_id; se agrega
-- para aplicar el patron WHERE (%s IS NULL OR tenant_id = %s) en todas las
-- consultas (pedidos, transportes, clientes) e intercambio.
-- MySQL: aplicar manualmente contra taurus_wms.
-- (Para los demas engines, ALTER equivalente o regenerar desde schema_generator.)

ALTER TABLE `transporte_rutas`
    ADD COLUMN `tenant_id` INT NULL AFTER `observaciones`;

-- Backfill: cada transporte pertenece a un tenant, y la asignacion hereda su tenant
UPDATE `transporte_rutas` tr
JOIN `transportes` t ON tr.id_transporte = t.id_transporte
SET tr.tenant_id = t.tenant_id
WHERE tr.tenant_id IS NULL;

ALTER TABLE `transporte_rutas`
    ADD INDEX `idx_transporte_rutas_tenant` (`tenant_id`);
