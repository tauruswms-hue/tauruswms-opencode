-- Unicidad de codigo POR TENANT.
-- La clave unica global sobre `codigo`/`codigo_barras` impedía importar/crear el mismo codigo
-- en tenants distintos (el control de duplicados de la app ya filtra por tenant).
-- Se reemplaza por una clave unica compuesta (columna, tenant_id).

DROP PROCEDURE IF EXISTS __fix_unique_codigo_per_tenant;

DELIMITER $$
CREATE PROCEDURE __fix_unique_codigo_per_tenant(IN tbl VARCHAR(64), IN col VARCHAR(64), IN uk_name VARCHAR(64))
BEGIN
    DECLARE idx_name VARCHAR(64);
    DECLARE done INT DEFAULT 0;
    DECLARE cur CURSOR FOR
        SELECT DISTINCT INDEX_NAME
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = tbl
          AND COLUMN_NAME = col
          AND NON_UNIQUE = 0
          AND INDEX_NAME <> 'PRIMARY';
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1;

    OPEN cur;
    read_loop: LOOP
        FETCH cur INTO idx_name;
        IF done THEN LEAVE read_loop; END IF;
        SET @ddl = CONCAT('ALTER TABLE `', tbl, '` DROP INDEX `', idx_name, '`');
        PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;
    END LOOP;
    CLOSE cur;

    SET @ddl = CONCAT('ALTER TABLE `', tbl, '` ADD UNIQUE KEY `', uk_name, '` (`', col, '`, `tenant_id`)');
    PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;
END$$
DELIMITER ;

CALL __fix_unique_codigo_per_tenant('categorias', 'codigo', 'uk_categorias_codigo_tenant');
CALL __fix_unique_codigo_per_tenant('proveedores', 'codigo', 'uk_proveedores_codigo_tenant');
CALL __fix_unique_codigo_per_tenant('clientes', 'codigo', 'uk_clientes_codigo_tenant');
CALL __fix_unique_codigo_per_tenant('materiales', 'codigo', 'uk_materiales_codigo_tenant');
CALL __fix_unique_codigo_per_tenant('transportes', 'codigo', 'uk_transportes_codigo_tenant');
CALL __fix_unique_codigo_per_tenant('zonas', 'codigo', 'uk_zonas_codigo_tenant');
CALL __fix_unique_codigo_per_tenant('ubicaciones', 'codigo', 'uk_ubicaciones_codigo_tenant');
CALL __fix_unique_codigo_per_tenant('material_presentaciones', 'codigo_barras', 'uk_pres_barcode_tenant');

DROP PROCEDURE IF EXISTS __fix_unique_codigo_per_tenant;
