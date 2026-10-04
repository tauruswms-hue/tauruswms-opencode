-- Agregar campo metodo_picking_default a la tabla tenants (taurus_admin)
-- Metodo de picking por defecto del tenant (fifo|lifo|fefo|libre)
ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS metodo_picking_default VARCHAR(20) NOT NULL DEFAULT 'libre'
        COMMENT 'Método de picking por defecto del tenant (fifo|lifo|fefo|libre)'
    AFTER metodosdepicking;
