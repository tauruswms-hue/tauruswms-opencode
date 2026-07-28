-- Fix: Agregar AUTO_INCREMENT a tenants.id
-- Ejecutar manualmente en MySQL

-- 1. Drop FK
ALTER TABLE usuarios DROP FOREIGN KEY usuarios_ibfk_1;

-- 2. Alter
ALTER TABLE tenants MODIFY id INT NOT NULL AUTO_INCREMENT;

-- 3. Re-crear FK
ALTER TABLE usuarios ADD CONSTRAINT usuarios_ibfk_1 FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
