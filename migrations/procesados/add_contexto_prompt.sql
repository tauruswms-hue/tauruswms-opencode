-- Agrega los campos contexto y prompt a la tabla tenants
ALTER TABLE tenants ADD COLUMN contexto LONGTEXT NULL;
ALTER TABLE tenants ADD COLUMN prompt LONGTEXT NULL;
