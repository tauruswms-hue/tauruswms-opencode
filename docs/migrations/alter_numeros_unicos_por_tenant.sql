-- engine: mysql
-- db: wms
-- El número de las recepciones (REC-año-secuencia), de las OMC (OMC-...) y de los
-- pedidos (PED-...) se arma por empresa, pero su índice único abarcaba a todas:
-- cuando otra empresa ya tenía ese número, crear el documento fallaba con
-- "Duplicate entry". Los tres pasan a ser únicos por tenant.
-- La DDL multi-engine ya se regeneró; esta migración cubre las instalaciones
-- MySQL existentes. Cada paso se aplica solo si falta, así que se puede correr
-- más de una vez. Primero se crea el índice nuevo y después se quita el viejo.

SET @sql := IF((SELECT COUNT(*) FROM information_schema.statistics
                WHERE table_schema = DATABASE() AND table_name = 'recepciones_cabecera'
                  AND index_name = 'uk_recepciones_numero_tenant') = 0,
               'CREATE UNIQUE INDEX uk_recepciones_numero_tenant ON recepciones_cabecera (numero, tenant_id)',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF((SELECT COUNT(*) FROM information_schema.statistics
                WHERE table_schema = DATABASE() AND table_name = 'recepciones_cabecera'
                  AND index_name = 'uq_recepcion_numero') > 0,
               'DROP INDEX uq_recepcion_numero ON recepciones_cabecera',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF((SELECT COUNT(*) FROM information_schema.statistics
                WHERE table_schema = DATABASE() AND table_name = 'omc'
                  AND index_name = 'uk_omc_numero_tenant') = 0,
               'CREATE UNIQUE INDEX uk_omc_numero_tenant ON omc (numero, tenant_id)',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF((SELECT COUNT(*) FROM information_schema.statistics
                WHERE table_schema = DATABASE() AND table_name = 'omc'
                  AND index_name = 'uq_omc_numero') > 0,
               'DROP INDEX uq_omc_numero ON omc',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF((SELECT COUNT(*) FROM information_schema.statistics
                WHERE table_schema = DATABASE() AND table_name = 'pedidos_cabecera'
                  AND index_name = 'uk_pedidos_nro_tenant') = 0,
               'CREATE UNIQUE INDEX uk_pedidos_nro_tenant ON pedidos_cabecera (nro_pedido, tenant_id)',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF((SELECT COUNT(*) FROM information_schema.statistics
                WHERE table_schema = DATABASE() AND table_name = 'pedidos_cabecera'
                  AND index_name = 'uq_pedido_nro') > 0,
               'DROP INDEX uq_pedido_nro ON pedidos_cabecera',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
