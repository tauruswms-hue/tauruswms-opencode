-- Procedimiento almacenado para guardar material con todas sus relaciones
-- Valida EAN, GTIN-14, unicidad y maneja la transacción atómicamente
DROP PROCEDURE IF EXISTS sp_guardar_material;

DELIMITER //

CREATE PROCEDURE sp_guardar_material(
    IN p_id VARCHAR(255),                    -- NULL o vacío para INSERT, ID para UPDATE
    IN p_codigo VARCHAR(100),
    IN p_nombre VARCHAR(255),
    IN p_descripcion TEXT,
    IN p_codigo_barras VARCHAR(100),
    IN p_categoria_id INT,
    IN p_stock_minimo DECIMAL(12,3),
    IN p_stock_maximo DECIMAL(12,3),
    IN p_unidad_medida_id INT,
    IN p_trazabilidad VARCHAR(20),
    IN p_prov_ids TEXT,                      -- JSON array: ["id1", "id2", ...]
    IN p_prov_codigos TEXT,                  -- JSON array: ["cod1", "cod2", ...]
    IN p_prov_habitual INT,                  -- índice de la fila habitual
    IN p_pres_nombres TEXT,                  -- JSON array: ["nombre1", "nombre2", ...]
    IN p_pres_barcodes TEXT,                 -- JSON array: ["gtin1", "gtin2", ...]
    IN p_pres_cantidades TEXT,               -- JSON array: [1.0, 12.0, ...]
    OUT p_resultado VARCHAR(10),             -- 'OK' o 'ERROR'
    OUT p_mensaje VARCHAR(500),
    OUT p_id_material INT
)
BEGIN
    DECLARE v_current_id INT DEFAULT 0;
    DECLARE v_es_update BOOLEAN DEFAULT FALSE;
    DECLARE v_count INT DEFAULT 0;
    DECLARE v_i INT DEFAULT 0;
    DECLARE v_n INT DEFAULT 0;
    DECLARE v_prov_id VARCHAR(255);
    DECLARE v_prov_cod VARCHAR(255);
    DECLARE v_pres_nombre VARCHAR(255);
    DECLARE v_pres_barcode VARCHAR(255);
    DECLARE v_pres_cantidad DECIMAL(12,3);
    DECLARE v_es_habitual INT;
    DECLARE v_barcode VARCHAR(100);
    DECLARE v_digitos VARCHAR(100);
    DECLARE v_suma INT;
    DECLARE v_check_calc INT;
    DECLARE v_indicador INT;
    DECLARE v_gtin_exists INT DEFAULT 0;
    
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_resultado = 'ERROR';
        SET p_mensaje = CONCAT('Error en la transacción: ', GETSTACKEDDIAGNOSTICS_MESSAGE(1));
        SET p_id_material = 0;
    END;
    
    SET p_resultado = 'ERROR';
    SET p_mensaje = '';
    SET p_id_material = 0;
    
    START TRANSACTION;
    
    -- Validar código de barras EAN si se proporcionó
    IF p_codigo_barras IS NOT NULL AND p_codigo_barras != '' THEN
        SET v_barcode = TRIM(p_codigo_barras);
        IF LENGTH(v_barcode) NOT IN (8, 13) OR v_barcode NOT REGEXP '^[0-9]+$' THEN
            SET p_mensaje = 'El código de barras debe tener 8 (EAN-8) o 13 (EAN-13) dígitos numéricos.';
            ROLLBACK;
        ELSE
            -- Validar dígito verificador EAN
            SET v_digitos = v_barcode;
            SET v_suma = 0;
            SET v_i = 1;
            
            WHILE v_i <= LENGTH(v_digitos) - 1 DO
                IF LENGTH(v_barcode) = 8 THEN
                    -- EAN-8: pesos 3,1,3,1,...
                    SET v_suma = v_suma + (CAST(SUBSTRING(v_digitos, v_i, 1) AS UNSIGNED) * IF(v_i % 2 = 1, 3, 1));
                ELSE
                    -- EAN-13: pesos 1,3,1,3,...
                    SET v_suma = v_suma + (CAST(SUBSTRING(v_digitos, v_i, 1) AS UNSIGNED) * IF(v_i % 2 = 1, 1, 3));
                END IF;
                SET v_i = v_i + 1;
            END WHILE;
            
            SET v_check_calc = (10 - (v_suma % 10)) % 10;
            
            IF v_check_calc != CAST(SUBSTRING(v_digitos, LENGTH(v_digitos), 1) AS UNSIGNED) THEN
                SET p_mensaje = 'El código de barras tiene un dígito verificador inválido.';
                ROLLBACK;
            ELSE
                -- Verificar unicidad del código de barras
                SELECT COUNT(*) INTO v_count FROM materiales 
                WHERE codigo_barras = v_barcode AND (p_id IS NULL OR p_id = '' OR id != CAST(p_id AS UNSIGNED));
                
                IF v_count > 0 THEN
                    SET p_mensaje = CONCAT('El código de barras ', v_barcode, ' ya está asignado a otro material.');
                    ROLLBACK;
                END IF;
            END IF;
        END IF;
    END IF;
    
    IF p_mensaje != '' THEN
        SET p_resultado = 'ERROR';
    ELSE
        -- Determinar si es INSERT o UPDATE
        IF p_id IS NOT NULL AND p_id != '' THEN
            SET v_es_update = TRUE;
            SET v_current_id = CAST(p_id AS UNSIGNED);
            
            -- Verificar que existe el material
            SELECT COUNT(*) INTO v_count FROM materiales WHERE id = v_current_id;
            IF v_count = 0 THEN
                SET p_mensaje = 'El material a actualizar no existe.';
                ROLLBACK;
            ELSE
                UPDATE materiales SET
                    codigo = p_codigo,
                    nombre = p_nombre,
                    descripcion = p_descripcion,
                    codigo_barras = NULLIF(TRIM(p_codigo_barras), ''),
                    categoria_id = p_categoria_id,
                    stock_minimo = p_stock_minimo,
                    stock_maximo = p_stock_maximo,
                    unidad_medida_id = p_unidad_medida_id,
                    trazabilidad = p_trazabilidad
                WHERE id = v_current_id;
            END IF;
        ELSE
            INSERT INTO materiales (codigo, nombre, descripcion, codigo_barras, categoria_id, stock_minimo, stock_maximo, unidad_medida_id, trazabilidad)
            VALUES (p_codigo, p_nombre, p_descripcion, NULLIF(TRIM(p_codigo_barras), ''), p_categoria_id, p_stock_minimo, p_stock_maximo, p_unidad_medida_id, p_trazabilidad);
            
            SET v_current_id = LAST_INSERT_ID();
        END IF;
        
        IF p_mensaje = '' THEN
            -- Eliminar relaciones existentes de proveedores
            DELETE FROM material_proveedor WHERE id_material = v_current_id;
            
            -- Procesar proveedores
            IF p_prov_ids IS NOT NULL AND p_prov_ids != '' THEN
                SET v_i = 0;
                SET v_n = JSON_LENGTH(p_prov_ids);
                
                WHILE v_i < v_n DO
                    SET v_prov_id = JSON_UNQUOTE(JSON_EXTRACT(p_prov_ids, CONCAT('$[', v_i, ']')));
                    SET v_prov_cod = JSON_UNQUOTE(JSON_EXTRACT(p_prov_codigos, CONCAT('$[', v_i, ']')));
                    
                    IF v_prov_id IS NOT NULL AND v_prov_id != '' THEN
                        SET v_es_habitual = IF(v_prov_habitual IS NOT NULL AND v_prov_habitual = v_i, 1, 0);
                        
                        INSERT INTO material_proveedor (id_material, id_proveedor, codigo_referencia_prov, es_habitual)
                        VALUES (v_current_id, CAST(v_prov_id AS UNSIGNED), v_prov_cod, v_es_habitual);
                    END IF;
                    
                    SET v_i = v_i + 1;
                END WHILE;
            END IF;
            
            -- Eliminar presentaciones existentes
            DELETE FROM material_presentaciones WHERE id_material = v_current_id;
            
            -- Procesar presentaciones (validar GTIN-14)
            IF p_pres_nombres IS NOT NULL AND p_pres_nombres != '' THEN
                SET v_i = 0;
                SET v_n = JSON_LENGTH(p_pres_nombres);
                
                WHILE v_i < v_n DO
                    SET v_pres_nombre = JSON_UNQUOTE(JSON_EXTRACT(p_pres_nombres, CONCAT('$[', v_i, ']')));
                    
                    IF v_pres_nombre IS NOT NULL AND v_pres_nombre != '' THEN
                        SET v_pres_barcode = JSON_UNQUOTE(JSON_EXTRACT(p_pres_barcodes, CONCAT('$[', v_i, ']')));
                        SET v_pres_cantidad = CAST(JSON_UNQUOTE(JSON_EXTRACT(p_pres_cantidades, CONCAT('$[', v_i, ']'))) AS DECIMAL(12,3));
                        
                        -- Validar GTIN-14 si se proporcionó
                        IF v_pres_barcode IS NOT NULL AND v_pres_barcode != '' THEN
                            SET v_barcode = TRIM(v_pres_barcode);
                            
                            -- Verificar longitud y dígitos
                            IF LENGTH(v_barcode) != 14 OR v_barcode NOT REGEXP '^[0-9]+$' THEN
                                SET p_mensaje = CONCAT('Presentación "', v_pres_nombre, '": el GTIN-14 debe tener exactamente 14 dígitos numéricos.');
                                SET v_i = v_n; -- Salir del while
                            ELSE
                                -- Validar dígito verificador GTIN-14
                                SET v_suma = 0;
                                SET v_indicador = 1;
                                
                                -- Posiciones desde la derecha: 13=peso3, 12=peso1, 11=peso3, etc.
                                WHILE v_indicador <= 13 DO
                                    SET v_suma = v_suma + (CAST(SUBSTRING(v_barcode, v_indicador, 1) AS UNSIGNED) * IF((14 - v_indicador) % 2 = 0, 1, 3));
                                    SET v_indicador = v_indicador + 1;
                                END WHILE;
                                
                                SET v_check_calc = (10 - (v_suma % 10)) % 10;
                                
                                IF v_check_calc != CAST(SUBSTRING(v_barcode, 14, 1) AS UNSIGNED) THEN
                                    SET p_mensaje = CONCAT('Presentación "', v_pres_nombre, '": el GTIN-14 tiene un dígito verificador inválido.');
                                    SET v_i = v_n;
                                ELSE
                                    -- Verificar que el GTIN-14 no exista en otra presentación
                                    SELECT COUNT(*) INTO v_gtin_exists FROM material_presentaciones WHERE codigo_barras = v_barcode;
                                    IF v_gtin_exists > 0 THEN
                                        SET p_mensaje = CONCAT('El GTIN-14 ', v_barcode, ' ya está asignado a otra presentación.');
                                        SET v_i = v_n;
                                    END IF;
                                END IF;
                            END IF;
                        ELSE
                            SET v_barcode = NULL;
                        END IF;
                        
                        IF p_mensaje = '' THEN
                            INSERT INTO material_presentaciones (id_material, nombre, codigo_barras, cantidad_unidades)
                            VALUES (v_current_id, v_pres_nombre, v_barcode, COALESCE(v_pres_cantidad, 1.0));
                        END IF;
                    END IF;
                    
                    SET v_i = v_i + 1;
                END WHILE;
            END IF;
            
            IF p_mensaje = '' THEN
                COMMIT;
                SET p_resultado = 'OK';
                SET p_mensaje = 'Material guardado correctamente';
                SET p_id_material = v_current_id;
            ELSE
                ROLLBACK;
                SET p_resultado = 'ERROR';
            END IF;
        END IF;
    END IF;
END //

DELIMITER ;
