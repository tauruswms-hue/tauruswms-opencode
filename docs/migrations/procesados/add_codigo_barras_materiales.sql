-- Agregar campo codigo_barras a la tabla materiales
-- Nota: el índice único uk_codigo_barras ya existe en la BD
ALTER TABLE materiales
    ADD COLUMN IF NOT EXISTS codigo_barras VARCHAR(100) NULL DEFAULT NULL
        COMMENT 'Código de barras EAN/UPC del material (único, índice uk_codigo_barras)'
    AFTER codigo;
