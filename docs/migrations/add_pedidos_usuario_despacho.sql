-- engine: mysql
-- db: wms
-- Pedidos: usuario que despachó. Hasta ahora solo quedaba la fecha del despacho.
-- La DDL multi-engine ya se regeneró; esta migración cubre las instalaciones
-- MySQL existentes. Se aplica solo si la columna falta, así que se puede correr
-- más de una vez.

SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'pedidos_cabecera'
                  AND column_name = 'usuario_despacho') = 0,
               'ALTER TABLE pedidos_cabecera ADD COLUMN usuario_despacho varchar(100) NULL AFTER fecha_despacho',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
