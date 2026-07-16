-- ============================================================
-- Módulo: Ordenes de Movimiento de Contenedor (OMC)
-- Descripción: Registra el traslado de un contenedor entre
--   ubicaciones. Se genera automáticamente al cerrar una
--   recepción, o se puede crear manualmente.
--
-- Flujo de stock:
--   Al CREAR la OMC (desde cierre de recepción o manual):
--     - Origen:  stockcontable.StockSaliendo += cantidad  (ya hecho al cerrar recepción)
--     - Destino: stockcontable.StockEntrando += cantidad
--
--   Al CONFIRMAR la OMC:
--     - Origen:  StockSaliendo = 0
--     - Destino: StockTotal += StockEntrando, StockDisponible += StockEntrando, StockEntrando = 0
--
--   Al ANULAR la OMC:
--     - Destino: StockEntrando = 0
--     - Origen:  StockTotal += StockSaliendo, StockDisponible += StockSaliendo, StockSaliendo = 0
-- ============================================================

CREATE TABLE IF NOT EXISTS omc (
    id_omc               INT AUTO_INCREMENT PRIMARY KEY,
    numero               VARCHAR(20)  NOT NULL COMMENT 'Número único: OMC-YYYY-NNNNN',
    id_contenedor        VARCHAR(20)  NOT NULL COMMENT 'IDContenedor en stockcontable',
    id_ubicacion_origen  INT          NOT NULL COMMENT 'FK -> ubicaciones.id (tiene StockSaliendo)',
    id_ubicacion_destino INT          NOT NULL COMMENT 'FK -> ubicaciones.id (tiene StockEntrando)',
    id_recepcion         INT          NULL     COMMENT 'FK -> recepciones_cabecera.id_recepcion (si se originó de recepción)',
    estado               ENUM('Pendiente','Confirmada','Anulada') NOT NULL DEFAULT 'Pendiente',
    observaciones        TEXT         NULL,
    fecha_creacion       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_confirmacion   DATETIME     NULL,
    fecha_anulacion      DATETIME     NULL,
    usuario_creacion     VARCHAR(100) NOT NULL,
    usuario_confirmacion VARCHAR(100) NULL,
    usuario_anulacion    VARCHAR(100) NULL,
    created_at           TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_omc_numero (numero),

    INDEX idx_omc_contenedor (id_contenedor),
    INDEX idx_omc_origen     (id_ubicacion_origen),
    INDEX idx_omc_destino    (id_ubicacion_destino),
    INDEX idx_omc_estado     (estado),
    INDEX idx_omc_recepcion  (id_recepcion),

    CONSTRAINT fk_omc_origen FOREIGN KEY (id_ubicacion_origen)
        REFERENCES ubicaciones(id) ON DELETE RESTRICT ON UPDATE CASCADE,

    CONSTRAINT fk_omc_destino FOREIGN KEY (id_ubicacion_destino)
        REFERENCES ubicaciones(id) ON DELETE RESTRICT ON UPDATE CASCADE,

    CONSTRAINT fk_omc_recepcion FOREIGN KEY (id_recepcion)
        REFERENCES recepciones_cabecera(id_recepcion) ON DELETE SET NULL ON UPDATE CASCADE

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Ordenes de Movimiento de Contenedor entre ubicaciones';
