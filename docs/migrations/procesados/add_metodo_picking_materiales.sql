-- Agregar campo metodo_picking a la tabla materiales
-- Metodo de picking por defecto del material (fifo|lifo|fefo|libre)
ALTER TABLE materiales
    ADD COLUMN IF NOT EXISTS metodo_picking VARCHAR(20) NOT NULL DEFAULT 'libre'
        COMMENT 'Método de picking usado para el material (fifo|lifo|fefo|libre)'
    AFTER trazabilidad;

-- Agregar campo metodo_picking a la tabla intercambio_materiales
ALTER TABLE intercambio_materiales
    ADD COLUMN IF NOT EXISTS metodo_picking VARCHAR(20) NOT NULL DEFAULT 'libre'
        COMMENT 'Método de picking del material (fifo|lifo|fefo|libre)'
    AFTER trazabilidad;
