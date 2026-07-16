-- Presentaciones / embalajes de un material
-- Permite definir múltiples unidades de empaque (caja, pallet, display, etc.)
-- con su propio código de barras (GTIN-14 u otro) y la cantidad de unidades base que contiene.

CREATE TABLE material_presentaciones (
    id                INT          NOT NULL AUTO_INCREMENT,
    id_material       INT          NOT NULL,
    nombre            VARCHAR(100) NOT NULL,          -- ej: "Caja x12", "Palet x120"
    codigo_barras     VARCHAR(20)  NULL,               -- GTIN-14 u otro; único globalmente
    cantidad_unidades DECIMAL(10,3) NOT NULL DEFAULT 1.000, -- unidades base por presentación
    activo            TINYINT(1)   NOT NULL DEFAULT 1,
    PRIMARY KEY (id),
    UNIQUE  KEY uq_pres_barcode (codigo_barras),
    FOREIGN KEY (id_material) REFERENCES materiales(id) ON DELETE CASCADE
);
