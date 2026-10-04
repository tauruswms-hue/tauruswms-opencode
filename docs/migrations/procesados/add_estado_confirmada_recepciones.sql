-- ============================================================
-- Migración: agrega estado 'Confirmada' a recepciones_cabecera
-- Representa una recepción cerrada cuyo stock ya fue confirmado
-- (StockEntrando → StockDisponible + StockTotal).
-- ============================================================

ALTER TABLE recepciones_cabecera
    MODIFY COLUMN estado
        ENUM('Abierta','Cerrada','Confirmada','Anulada')
        NOT NULL DEFAULT 'Abierta';
