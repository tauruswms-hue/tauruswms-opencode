-- Agrega el campo api_key a la tabla tenants (despues de proveedor_api_ia)
ALTER TABLE tenants ADD COLUMN api_key LONGTEXT NULL AFTER proveedor_api_ia;
