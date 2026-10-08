-- engine: mysql
-- db: wms
-- Rutas: estado Activa / Inactiva y nombre único por tenant.
--   * activo: una ruta ya no se borra (el borrado la quitaba en silencio de
--     transportes, clientes y pedidos); se inactiva y deja de ofrecerse.
--     Las rutas existentes quedan activas.
--   * uk_rutas_nombre_tenant: el nombre identifica a la ruta (clientes,
--     transportes, importaciones e Intercambio la buscan por nombre).
-- La DDL multi-engine ya se regeneró; esta migración cubre las instalaciones
-- MySQL existentes. Cada paso se aplica solo si falta, así que se puede correr
-- más de una vez.
-- Si falla por "Duplicate entry": hay rutas con el mismo nombre en un tenant.
-- Renombrar las repetidas y volver a correr la migración.

SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'rutas'
                  AND column_name = 'activo') = 0,
               'ALTER TABLE rutas ADD COLUMN activo tinyint(1) DEFAULT 1 AFTER descripcion',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

UPDATE rutas SET activo = 1 WHERE activo IS NULL;

SET @sql := IF((SELECT COUNT(*) FROM information_schema.statistics
                WHERE table_schema = DATABASE() AND table_name = 'rutas'
                  AND index_name = 'uk_rutas_nombre_tenant') = 0,
               'CREATE UNIQUE INDEX uk_rutas_nombre_tenant ON rutas (nombre_ruta, tenant_id)',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
