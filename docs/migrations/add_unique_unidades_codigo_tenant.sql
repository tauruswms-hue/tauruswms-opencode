-- engine: mysql
-- db: wms
-- Unicidad de unidades_medida.codigo por tenant: la pantalla y la importación ya
-- rechazan un código repetido (modules/unidades.py); este índice lo garantiza
-- también en la base. La DDL multi-engine ya se regeneró (uk_unidades_codigo_tenant);
-- esta migración cubre las instalaciones MySQL existentes y no hace nada si el
-- índice ya existe.
-- Si falla por "Duplicate entry": hay unidades con el mismo código en un tenant.
-- Renombrar o borrar las repetidas y volver a correr la migración.
SET @sql := IF((SELECT COUNT(*) FROM information_schema.statistics
                WHERE table_schema = DATABASE() AND table_name = 'unidades_medida'
                  AND index_name = 'uk_unidades_codigo_tenant') = 0,
               'CREATE UNIQUE INDEX uk_unidades_codigo_tenant ON unidades_medida (codigo, tenant_id)',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
