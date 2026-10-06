-- engine: mysql
-- db: wms
-- Clientes: nombre de fantasía y sitio web. La DDL multi-engine ya se regeneró;
-- esta migración cubre las instalaciones MySQL existentes. Cada columna se
-- agrega solo si no existe, así que se puede correr más de una vez.

SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'clientes'
                  AND column_name = 'nombre_fantasia') = 0,
               'ALTER TABLE clientes ADD COLUMN nombre_fantasia varchar(200) NULL AFTER razonsocial',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'clientes'
                  AND column_name = 'sitio_web') = 0,
               'ALTER TABLE clientes ADD COLUMN sitio_web varchar(255) NULL AFTER contacto_nombre',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
