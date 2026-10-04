-- engine: mysql
-- db: wms
-- Unicidad de inventarios_cabecera.numero por tenant: el número es correlativo
-- por tenant (INV-<año>-<n>, modules/inventario.py), así que la clave es
-- (numero, tenant_id) y no numero solo. La DDL multi-engine ya se regeneró
-- (uk_inventarios_numero_tenant); esta migración cubre las instalaciones MySQL
-- existentes y no hace nada si el índice ya existe.
SET @sql := IF((SELECT COUNT(*) FROM information_schema.statistics
                WHERE table_schema = DATABASE() AND table_name = 'inventarios_cabecera'
                  AND index_name = 'uk_inventarios_numero_tenant') = 0,
               'CREATE UNIQUE INDEX uk_inventarios_numero_tenant ON inventarios_cabecera (numero, tenant_id)',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
