-- Migración 003: agregar campo es_habitual en material_proveedor
ALTER TABLE material_proveedor
    ADD COLUMN es_habitual TINYINT(1) NOT NULL DEFAULT 0
        COMMENT '1 = proveedor habitual del material';
