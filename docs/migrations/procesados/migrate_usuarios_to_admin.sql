-- Migración: Mover usuarios de taurus_wms a taurus_admin
-- Ejecutar DESPUÉS de create_admin_db.sql

USE taurus_admin;

-- Insertar tenants que existan en taurus_wms
INSERT INTO tenants (id, codigo, nombre, razon_social, nit, direccion, telefono, email, activo)
SELECT id, codigo, nombre, COALESCE(razon_social, ''), COALESCE(nit, ''), 
       COALESCE(direccion, ''), COALESCE(telefono, ''), COALESCE(email, ''), COALESCE(activo, 1)
FROM taurus_wms.tenants
ON DUPLICATE KEY UPDATE 
    nombre = VALUES(nombre),
    razon_social = VALUES(razon_social),
    nit = VALUES(nit);

-- Si no hay tenants, crear uno por defecto
INSERT IGNORE INTO tenants (id, codigo, nombre, activo)
SELECT 1, 'DEFAULT', 'Empresa Principal', 1 
WHERE NOT EXISTS (SELECT 1 FROM tenants);

-- Insertar usuarios existentes de taurus_wms
INSERT INTO usuarios (username, password_hash, nombre, email, rol, tenant_id, activo)
SELECT 
    u.username,
    u.password_hash,
    COALESCE(u.nombre, u.username),
    u.email,
    CASE u.rol 
        WHEN 'ADMIN' THEN 'ADMIN'
        WHEN 'SUPERADMIN' THEN 'ADMIN'
        ELSE 'OPERADOR'
    END as rol,
    COALESCE(u.tenant_id, 1),
    u.activo
FROM taurus_wms.usuarios u
WHERE u.username != 'admin'
ON DUPLICATE KEY UPDATE 
    password_hash = VALUES(password_hash),
    nombre = VALUES(nombre);

-- Insertar usuario SUPERADMIN
INSERT IGNORE INTO admin_usuarios (username, password_hash, nombre, email, rol) VALUES 
('admin', 'scrypt:32768:8:1$WQ6PhKOf81VV3FcH$ed1ca47fd1fd381583f0289acf9e839521b5e74a07adfc034382ea5342d608e393b7143fec95b3aef262f1946f95696e3e8acbfc867c91769d63142d4e4a5db2', 'Administrador', 'admin@taurus.local', 'SUPERADMIN');
