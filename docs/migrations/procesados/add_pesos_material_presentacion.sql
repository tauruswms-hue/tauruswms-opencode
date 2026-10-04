-- Agregar campos de peso bruto y peso neto a materiales
ALTER TABLE materiales
    ADD COLUMN peso_bruto DECIMAL(10,3) NULL COMMENT 'Peso bruto del material (kg)',
    ADD COLUMN peso_neto  DECIMAL(10,3) NULL COMMENT 'Peso neto del material (kg)';

-- Agregar campos de peso bruto y peso neto a presentaciones
ALTER TABLE material_presentaciones
    ADD COLUMN peso_bruto DECIMAL(10,3) NULL COMMENT 'Peso bruto de la presentacion (kg)',
    ADD COLUMN peso_neto  DECIMAL(10,3) NULL COMMENT 'Peso neto de la presentacion (kg)';
