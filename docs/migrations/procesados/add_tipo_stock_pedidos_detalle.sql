-- Agregar tipo_stock a pedidos_detalle
ALTER TABLE pedidos_detalle
    ADD COLUMN IF NOT EXISTS tipo_stock VARCHAR(20) NOT NULL DEFAULT 'Libre Venta'
        COMMENT 'Tipo de stock a consumir: Libre Venta, Calidad, Bloqueado, Mal Estado'
    AFTER cantidad;
