-- engine: mysql
-- db: wms
-- Materiales: ruta de la imagen del producto (ruta en el servidor, ruta de red
-- o URL http/https). La DDL multi-engine ya se regeneró; esta migración cubre
-- las instalaciones MySQL existentes. La columna se agrega solo si no existe,
-- así que se puede correr más de una vez.

SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'materiales'
                  AND column_name = 'imagen_ruta') = 0,
               'ALTER TABLE materiales ADD COLUMN imagen_ruta varchar(500) NULL AFTER volumen_unidad_id',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
