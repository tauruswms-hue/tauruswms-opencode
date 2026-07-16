-- Renombrar columna NIT a CUIT en la tabla tenants

USE taurus_admin;

ALTER TABLE tenants CHANGE COLUMN nit cuit VARCHAR(50) NULL;
