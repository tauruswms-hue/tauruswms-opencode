-- Eliminar tabla usuarios de taurus_wms
-- Ejecutar DESPUÉS de migrar los datos a taurus_admin

USE taurus_wms;

-- Desactivar foreign keys temporalmente
SET FOREIGN_KEY_CHECKS = 0;

-- Eliminar la tabla usuarios
DROP TABLE IF EXISTS usuarios;

-- Reactivar foreign keys
SET FOREIGN_KEY_CHECKS = 1;

-- Nota: Si hay otras tablas que referencian usuarios (roles_rutas, etc.)
-- esas referencias deben manejarse según la lógica del sistema
