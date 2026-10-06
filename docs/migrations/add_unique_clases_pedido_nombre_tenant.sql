-- engine: mysql
-- db: wms
-- Unicidad de clases_pedido.nombre por tenant: el nombre identifica a la clase
-- (el Intercambio y la importación de pedidos la buscan por nombre). La pantalla
-- y la importación ya rechazan un nombre repetido (modules/clases_pedido.py);
-- este índice lo garantiza también en la base. La DDL multi-engine ya se
-- regeneró; esta migración cubre las instalaciones MySQL existentes y no hace
-- nada si el índice ya existe.
-- Si falla por "Duplicate entry": hay clases con el mismo nombre en un tenant.
-- Renombrar o borrar las repetidas y volver a correr la migración.
SET @sql := IF((SELECT COUNT(*) FROM information_schema.statistics
                WHERE table_schema = DATABASE() AND table_name = 'clases_pedido'
                  AND index_name = 'uk_clases_pedido_nombre_tenant') = 0,
               'CREATE UNIQUE INDEX uk_clases_pedido_nombre_tenant ON clases_pedido (nombre, tenant_id)',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
