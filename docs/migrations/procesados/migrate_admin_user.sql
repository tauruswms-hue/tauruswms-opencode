-- Migrar usuario admin de taurus_wms a taurus_admin

USE taurus_admin;

-- Migrar el admin de taurus_wms
INSERT INTO usuarios (username, password_hash, nombre, email, rol, tenant_id, activo)
SELECT 
    username,
    password_hash,
    COALESCE(nombre, username),
    email,
    'ADMIN',
    COALESCE(tenant_id, 1),
    activo
FROM taurus_wms.usuarios 
WHERE username = 'admin'
ON DUPLICATE KEY UPDATE 
    password_hash = VALUES(password_hash);
