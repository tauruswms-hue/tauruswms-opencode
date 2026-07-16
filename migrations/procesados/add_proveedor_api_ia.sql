-- Agrega el campo proveedor_api_ia a la tabla tenants (antes de modelo_api_ia)
ALTER TABLE tenants ADD COLUMN proveedor_api_ia LONGTEXT NULL AFTER dias_filtro_fechas;
