-- Agrega campo soporte_picking a tipoubicacion
-- Indica si ese tipo de ubicación permite operaciones de picking/preparación de pedidos
ALTER TABLE tipoubicacion
    ADD COLUMN soporte_picking TINYINT(1) NOT NULL DEFAULT 0;
