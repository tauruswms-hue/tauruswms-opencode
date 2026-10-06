-- engine: mysql
-- db: wms
-- Materiales: código alternativo, código del proveedor y volumen con su unidad
-- de medida (volumen_unidad_id apunta a unidades_medida.id_unidad, una unidad
-- de magnitud VOLUMEN). La DDL multi-engine ya se regeneró; esta migración
-- cubre las instalaciones MySQL existentes. Cada columna se agrega solo si no
-- existe, así que se puede correr más de una vez.

SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'materiales'
                  AND column_name = 'codigo_alternativo') = 0,
               'ALTER TABLE materiales ADD COLUMN codigo_alternativo varchar(100) NULL AFTER codigo_barras',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'materiales'
                  AND column_name = 'codigo_proveedor') = 0,
               'ALTER TABLE materiales ADD COLUMN codigo_proveedor varchar(100) NULL AFTER codigo_alternativo',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'materiales'
                  AND column_name = 'volumen') = 0,
               'ALTER TABLE materiales ADD COLUMN volumen decimal(12,4) NULL AFTER peso_neto',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'materiales'
                  AND column_name = 'volumen_unidad_id') = 0,
               'ALTER TABLE materiales ADD COLUMN volumen_unidad_id int NULL AFTER volumen',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
