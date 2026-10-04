-- Eliminar columna codigo de la tabla tenants
-- El identificador de un tenant será el campo id

USE taurus_admin;

ALTER TABLE tenants DROP COLUMN codigo;
