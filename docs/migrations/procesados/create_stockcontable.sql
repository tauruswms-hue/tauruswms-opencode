-- ============================================================
-- Tabla: stockcontable
-- Descripción: Stock contable por ubicación, material, lote
--              tipo de stock y contenedor.
-- ============================================================

CREATE TABLE IF NOT EXISTS stockcontable (
    ID              INT AUTO_INCREMENT PRIMARY KEY,
    Ubicacion       INT NOT NULL COMMENT 'FK -> ubicaciones.id',
    Material        INT NOT NULL COMMENT 'FK -> materiales.id',
    Lote            VARCHAR(100) NOT NULL DEFAULT 'UNICO'
                        COMMENT 'Lote del material; UNICO si no maneja lotes',
    TipoStock       ENUM('Libre Venta','Calidad','Bloqueado','Mal Estado')
                        NOT NULL DEFAULT 'Libre Venta',
    UltimaEntrada   DATETIME NULL COMMENT 'Fecha/hora del último ingreso a la ubicación',
    UltimaSalida    DATETIME NULL COMMENT 'Fecha/hora del último egreso de la ubicación',
    UltimoMovimiento DATETIME NULL COMMENT 'Fecha/hora del último movimiento interno',
    FechaVencimiento DATE NULL COMMENT 'Fecha de vencimiento del lote (si aplica)',
    StockTotal      DECIMAL(15,4) NOT NULL DEFAULT 0 COMMENT 'Total de unidades',
    StockDisponible DECIMAL(15,4) NOT NULL DEFAULT 0 COMMENT 'Unidades disponibles para afectar',
    StockEntrando   DECIMAL(15,4) NOT NULL DEFAULT 0 COMMENT 'Unidades en proceso de recepción',
    StockSaliendo   DECIMAL(15,4) NOT NULL DEFAULT 0 COMMENT 'Unidades en proceso de pedido',
    IDContenedor    VARCHAR(10)   NOT NULL COMMENT 'Identificador del contenedor (mínimo 1 por ubicación)',
    created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP,

    -- Unicidad: un contenedor sólo puede tener un material en una ubicación.
    -- No se puede mezclar distintos tipos de stock en el mismo contenedor.
    UNIQUE KEY uq_stock_pos (Ubicacion, Material, IDContenedor),

    INDEX idx_material    (Material),
    INDEX idx_ubicacion   (Ubicacion),
    INDEX idx_lote        (Lote),
    INDEX idx_tipo_stock  (TipoStock),
    INDEX idx_contenedor  (IDContenedor),

    CONSTRAINT fk_sc_ubicacion FOREIGN KEY (Ubicacion)
        REFERENCES ubicaciones(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,

    CONSTRAINT fk_sc_material  FOREIGN KEY (Material)
        REFERENCES materiales(id)
        ON DELETE RESTRICT ON UPDATE CASCADE

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Stock contable por posición (ubicación + material + lote + tipo + contenedor)';
