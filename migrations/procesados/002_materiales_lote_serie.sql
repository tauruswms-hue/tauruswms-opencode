-- Migración 002: agregar atributo de trazabilidad a materiales (lote o serie, excluyentes)
ALTER TABLE materiales
    ADD COLUMN trazabilidad ENUM('ninguna', 'lote', 'serie') NOT NULL DEFAULT 'ninguna'
        COMMENT 'Tipo de trazabilidad: ninguna, por lote o por número de serie';
