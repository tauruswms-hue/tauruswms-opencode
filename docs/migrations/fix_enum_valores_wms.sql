-- engine: mysql
-- db: wms
-- El generador de esquemas pasaba a mayúsculas los valores de las columnas ENUM de MySQL
-- ('ABIERTA', 'PENDIENTE', 'LIBRE VENTA'), pero el código y las pantallas trabajan con los
-- valores tal como están definidos ('Abierta', 'Pendiente', 'Libre Venta'). La base devolvía
-- entonces un texto que las pantallas no reconocían: la ficha de una recepción no ofrecía cerrarla, y lo mismo en OMC e Inventario.
-- Esta migración redefine cada columna con los valores del esquema. Los datos se conservan:
-- MySQL los reasigna por su valor, sin distinguir mayúsculas. Cada paso se aplica solo si la
-- columna todavía no coincide, así que se puede correr más de una vez.

SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'materiales' AND column_name = 'trazabilidad'
                  AND BINARY column_type <> 'enum(''ninguna'',''lote'',''serie'')') > 0,
               'ALTER TABLE materiales MODIFY COLUMN trazabilidad ENUM(''ninguna'',''lote'',''serie'') NOT NULL DEFAULT ''ninguna''',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'stockcontable' AND column_name = 'TipoStock'
                  AND BINARY column_type <> 'enum(''Libre Venta'',''Calidad'',''Bloqueado'',''Mal Estado'')') > 0,
               'ALTER TABLE stockcontable MODIFY COLUMN TipoStock ENUM(''Libre Venta'',''Calidad'',''Bloqueado'',''Mal Estado'') NOT NULL DEFAULT ''Libre Venta''',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'recepciones_cabecera' AND column_name = 'estado'
                  AND BINARY column_type <> 'enum(''Abierta'',''Cerrada'',''Confirmada'',''Anulada'')') > 0,
               'ALTER TABLE recepciones_cabecera MODIFY COLUMN estado ENUM(''Abierta'',''Cerrada'',''Confirmada'',''Anulada'') NOT NULL DEFAULT ''Abierta''',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'recepciones_detalle' AND column_name = 'tipo_stock'
                  AND BINARY column_type <> 'enum(''Libre Venta'',''Calidad'',''Bloqueado'',''Mal Estado'')') > 0,
               'ALTER TABLE recepciones_detalle MODIFY COLUMN tipo_stock ENUM(''Libre Venta'',''Calidad'',''Bloqueado'',''Mal Estado'') NOT NULL DEFAULT ''Libre Venta''',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'omc' AND column_name = 'estado'
                  AND BINARY column_type <> 'enum(''Pendiente'',''Confirmada'',''Anulada'')') > 0,
               'ALTER TABLE omc MODIFY COLUMN estado ENUM(''Pendiente'',''Confirmada'',''Anulada'') NOT NULL DEFAULT ''Pendiente''',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'inventarios_cabecera' AND column_name = 'estado'
                  AND BINARY column_type <> 'enum(''Abierto'',''Cerrado'',''Anulado'')') > 0,
               'ALTER TABLE inventarios_cabecera MODIFY COLUMN estado ENUM(''Abierto'',''Cerrado'',''Anulado'') NULL DEFAULT ''Abierto''',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
