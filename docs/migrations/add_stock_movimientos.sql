-- engine: mysql
-- db: wms
-- Fase 5.4: tabla de auditoría de movimientos de stock (historial por posición).
-- Registra cada cambio de stock (recepciones, OMC, pedidos, ajustes, API).
-- La DDL multi-engine se regenera con schema_generator (WMS_TABLES); esta
-- migración cubre las instalaciones MySQL existentes.
CREATE TABLE IF NOT EXISTS stock_movimientos (
  id            BIGINT        NOT NULL AUTO_INCREMENT,
  tenant_id     INT           NULL,
  fecha         DATETIME      NOT NULL,
  usuario       VARCHAR(100)  NULL,
  accion        VARCHAR(60)   NOT NULL,
  modulo        VARCHAR(50)   NULL,
  id_ubicacion  INT           NULL,
  id_material   INT           NULL,
  id_contenedor VARCHAR(10)   NULL,
  lote          VARCHAR(100)  NULL,
  tipo_stock    VARCHAR(50)   NULL,
  cantidad      DECIMAL(15,4) NULL,
  detalle       VARCHAR(500)  NULL,
  PRIMARY KEY (id),
  KEY idx_stockmov_tenant (tenant_id),
  KEY idx_stockmov_fecha (fecha),
  KEY idx_stockmov_material (id_material),
  KEY idx_stockmov_ubicacion (id_ubicacion),
  KEY idx_stockmov_contenedor (id_contenedor)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
