-- Migración 007: Módulo de Inventario (conteo de existencias)
-- Fecha: 2026-03-18

CREATE TABLE IF NOT EXISTS inventarios_cabecera (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    numero           VARCHAR(20)  NOT NULL UNIQUE,
    descripcion      VARCHAR(200),
    estado           ENUM('Abierto','Cerrado') DEFAULT 'Abierto',
    fecha_creacion   DATETIME     DEFAULT CURRENT_TIMESTAMP,
    usuario_creacion VARCHAR(100),
    fecha_cierre     DATETIME     NULL,
    usuario_cierre   VARCHAR(100) NULL
);

CREATE TABLE IF NOT EXISTS inventarios_detalle (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    id_inventario  INT           NOT NULL,
    id_ubicacion   INT           NOT NULL,
    id_material    INT           NOT NULL,
    id_contenedor  VARCHAR(20)   DEFAULT '',
    lote           VARCHAR(100)  DEFAULT 'UNICO',
    tipo_stock     VARCHAR(50)   DEFAULT 'Libre Venta',
    stock_sistema  DECIMAL(15,3) DEFAULT 0,
    stock_contado  DECIMAL(15,3) NULL,
    fecha_conteo   DATETIME      NULL,
    usuario_conteo VARCHAR(100)  NULL,
    FOREIGN KEY (id_inventario) REFERENCES inventarios_cabecera(id)
);
