-- Encriptar códigos existentes de tenants

USE taurus_admin;

-- Actualizar códigos existentes con hash encriptado
UPDATE tenants 
SET codigo = SHA2(CONCAT(codigo, ':taurus-wms-salt-2024'), 256)
WHERE codigo IS NOT NULL AND LENGTH(codigo) < 32;
