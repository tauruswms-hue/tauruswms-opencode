-- engine: mysql
-- db: intercambio
-- El generador de esquemas pasaba a mayúsculas los valores de las columnas ENUM de MySQL
-- ('ABIERTA', 'PENDIENTE', 'LIBRE VENTA'), pero el código y las pantallas trabajan con los
-- valores tal como están definidos ('Abierta', 'Pendiente', 'Libre Venta'). La base devolvía
-- entonces un texto que las pantallas no reconocían: la pantalla de Intercambio no marcaba los registros procesados ni ofrecía reintentar los que dieron error.
-- Esta migración redefine cada columna con los valores del esquema. Los datos se conservan:
-- MySQL los reasigna por su valor, sin distinguir mayúsculas. Cada paso se aplica solo si la
-- columna todavía no coincide, así que se puede correr más de una vez.

SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'intercambio_materiales' AND column_name = 'trazabilidad'
                  AND BINARY column_type <> 'enum(''ninguna'',''lote'',''serie'')') > 0,
               'ALTER TABLE intercambio_materiales MODIFY COLUMN trazabilidad ENUM(''ninguna'',''lote'',''serie'') NOT NULL DEFAULT ''ninguna''',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'intercambio_materiales' AND column_name = 'estado'
                  AND BINARY column_type <> 'enum(''pendiente'',''procesado'',''error'')') > 0,
               'ALTER TABLE intercambio_materiales MODIFY COLUMN estado ENUM(''pendiente'',''procesado'',''error'') NOT NULL DEFAULT ''pendiente''',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'intercambio_rutas' AND column_name = 'estado'
                  AND BINARY column_type <> 'enum(''pendiente'',''procesado'',''error'')') > 0,
               'ALTER TABLE intercambio_rutas MODIFY COLUMN estado ENUM(''pendiente'',''procesado'',''error'') NOT NULL DEFAULT ''pendiente''',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'intercambio_transportes' AND column_name = 'estado'
                  AND BINARY column_type <> 'enum(''pendiente'',''procesado'',''error'')') > 0,
               'ALTER TABLE intercambio_transportes MODIFY COLUMN estado ENUM(''pendiente'',''procesado'',''error'') NOT NULL DEFAULT ''pendiente''',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'intercambio_transporte_rutas' AND column_name = 'estado'
                  AND BINARY column_type <> 'enum(''pendiente'',''procesado'',''error'')') > 0,
               'ALTER TABLE intercambio_transporte_rutas MODIFY COLUMN estado ENUM(''pendiente'',''procesado'',''error'') NOT NULL DEFAULT ''pendiente''',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'intercambio_clientes' AND column_name = 'estado'
                  AND BINARY column_type <> 'enum(''pendiente'',''procesado'',''error'')') > 0,
               'ALTER TABLE intercambio_clientes MODIFY COLUMN estado ENUM(''pendiente'',''procesado'',''error'') NOT NULL DEFAULT ''pendiente''',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'intercambio_pedidos' AND column_name = 'estado'
                  AND BINARY column_type <> 'enum(''pendiente'',''procesado'',''error'')') > 0,
               'ALTER TABLE intercambio_pedidos MODIFY COLUMN estado ENUM(''pendiente'',''procesado'',''error'') NOT NULL DEFAULT ''pendiente''',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
