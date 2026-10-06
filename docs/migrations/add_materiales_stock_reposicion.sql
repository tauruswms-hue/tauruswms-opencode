-- engine: mysql
-- db: wms
-- Materiales: stock de reposición (punto de pedido), entre el stock mínimo y el
-- máximo. La DDL multi-engine ya se regeneró; esta migración cubre las
-- instalaciones MySQL existentes. La columna se agrega solo si no existe, así
-- que se puede correr más de una vez.

SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'materiales'
                  AND column_name = 'stock_reposicion') = 0,
               'ALTER TABLE materiales ADD COLUMN stock_reposicion decimal(12,3) DEFAULT 0 AFTER stock_maximo',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
