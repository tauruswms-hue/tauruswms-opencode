-- Agrega campo Cantidad_preparada a pedidos_detalle
-- Registra las unidades realmente preparadas (por picking o por OMC confirmada)
ALTER TABLE pedidos_detalle
    ADD COLUMN Cantidad_preparada DECIMAL(10,2) NOT NULL DEFAULT 0 AFTER cantidad;
