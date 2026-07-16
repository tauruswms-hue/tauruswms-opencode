-- ============================================================
-- Módulo: Recepciones de Materiales
-- Descripción: Registra la recepción de materiales de un proveedor.
--   - Una recepción pertenece a un proveedor.
--   - Los materiales del detalle deben estar asignados a ese
--     proveedor en material_proveedor.
--   - La recepción se opera sobre un contenedor ubicado en una
--     ubicación de tipo "Recepción Material nuevo".
--   - Al cerrar la recepción, el contenedor se mueve a la
--     ubicación destino y el stock pasa de StockEntrando a
--     StockTotal/StockDisponible en stockcontable.
-- ============================================================


-- ============================================================
-- 1. CABECERA DE RECEPCION
-- ============================================================

CREATE TABLE IF NOT EXISTS recepciones_cabecera (
    id_recepcion        INT AUTO_INCREMENT PRIMARY KEY,
    numero              VARCHAR(20)  NOT NULL COMMENT 'Número único: REC-YYYY-NNNNN',
    id_proveedor        INT          NOT NULL COMMENT 'FK -> proveedores.id',
    estado              ENUM('Abierta','Cerrada','Anulada')
                            NOT NULL DEFAULT 'Abierta',
    id_contenedor       VARCHAR(10)  NOT NULL COMMENT 'Contenedor asignado (mismo IDContenedor de stockcontable)',
    id_ubicacion_recep  INT          NOT NULL COMMENT 'FK -> ubicaciones.id (tipo Recepcion Material nuevo)',
    id_ubicacion_destino INT         NULL     COMMENT 'FK -> ubicaciones.id destino al cerrar',
    observaciones       TEXT         NULL,
    fecha_recepcion     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_cierre        DATETIME     NULL,
    usuario_creacion    VARCHAR(100) NOT NULL,
    usuario_cierre      VARCHAR(100) NULL,
    created_at          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
                            ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_recepcion_numero (numero),

    INDEX idx_rec_proveedor  (id_proveedor),
    INDEX idx_rec_estado     (estado),
    INDEX idx_rec_contenedor (id_contenedor),
    INDEX idx_rec_ubicrec    (id_ubicacion_recep),
    INDEX idx_rec_ubicdest   (id_ubicacion_destino),
    INDEX idx_rec_fecha      (fecha_recepcion),

    CONSTRAINT fk_reccab_proveedor  FOREIGN KEY (id_proveedor)
        REFERENCES proveedores(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,

    CONSTRAINT fk_reccab_ubic_recep FOREIGN KEY (id_ubicacion_recep)
        REFERENCES ubicaciones(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,

    CONSTRAINT fk_reccab_ubic_dest  FOREIGN KEY (id_ubicacion_destino)
        REFERENCES ubicaciones(id)
        ON DELETE RESTRICT ON UPDATE CASCADE

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Cabecera de recepciones de materiales por proveedor';


-- ============================================================
-- 2. DETALLE DE RECEPCION
-- ============================================================

CREATE TABLE IF NOT EXISTS recepciones_detalle (
    id_detalle          INT AUTO_INCREMENT PRIMARY KEY,
    id_recepcion        INT          NOT NULL COMMENT 'FK -> recepciones_cabecera.id_recepcion',
    id_material         INT          NOT NULL COMMENT 'FK -> materiales.id (debe estar en material_proveedor)',
    lote                VARCHAR(100) NOT NULL DEFAULT 'UNICO'
                            COMMENT 'Lote del material; UNICO si no maneja lotes',
    fecha_vencimiento   DATE         NULL     COMMENT 'Vencimiento del lote (si aplica)',
    cantidad_esperada   DECIMAL(15,4) NOT NULL DEFAULT 0
                            COMMENT 'Cantidad en orden de compra / remito esperado',
    cantidad_recibida   DECIMAL(15,4) NOT NULL DEFAULT 0
                            COMMENT 'Cantidad efectivamente recibida y verificada',
    tipo_stock          ENUM('Libre Venta','Calidad','Bloqueado','Mal Estado')
                            NOT NULL DEFAULT 'Libre Venta',
    observaciones       TEXT         NULL,
    created_at          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
                            ON UPDATE CURRENT_TIMESTAMP,

    -- Un material/lote/tipo_stock no se repite en la misma recepción
    UNIQUE KEY uq_det_recep_mat_lote (id_recepcion, id_material, lote, tipo_stock),

    INDEX idx_det_recepcion (id_recepcion),
    INDEX idx_det_material  (id_material),
    INDEX idx_det_lote      (lote),

    CONSTRAINT fk_recdet_cabecera FOREIGN KEY (id_recepcion)
        REFERENCES recepciones_cabecera(id_recepcion)
        ON DELETE CASCADE ON UPDATE CASCADE,

    CONSTRAINT fk_recdet_material FOREIGN KEY (id_material)
        REFERENCES materiales(id)
        ON DELETE RESTRICT ON UPDATE CASCADE

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Detalle de materiales por recepción (lote, cantidad esperada vs recibida)';


-- ============================================================
-- NOTAS DE INTEGRACIÓN CON stockcontable
-- ============================================================
-- Al ABRIR una recepción (o al agregar/modificar un ítem):
--   INSERT INTO stockcontable ... SET StockEntrando = cantidad_recibida
--   (Ubicacion = id_ubicacion_recep, IDContenedor = id_contenedor)
--   Si ya existe el registro, UPDATE StockEntrando.
--
-- Al CERRAR una recepción:
--   Para cada detalle con cantidad_recibida > 0:
--     1. UPDATE stockcontable
--           SET StockTotal      = StockTotal + cantidad_recibida,
--               StockDisponible = StockDisponible + cantidad_recibida,
--               StockEntrando   = 0,
--               Ubicacion       = id_ubicacion_destino,
--               UltimaEntrada   = NOW()
--        WHERE Ubicacion = id_ubicacion_recep
--          AND IDContenedor = id_contenedor
--          AND Material = id_material
--          AND Lote = lote
--          AND TipoStock = tipo_stock;
--     2. UPDATE recepciones_cabecera
--           SET estado='Cerrada', fecha_cierre=NOW(), usuario_cierre=...
--        WHERE id_recepcion = ...;
--
-- Al ANULAR una recepción (solo si está Abierta):
--   Eliminar o poner a 0 los StockEntrando en stockcontable del contenedor.
--   UPDATE recepciones_cabecera SET estado='Anulada' WHERE ...;
-- ============================================================
