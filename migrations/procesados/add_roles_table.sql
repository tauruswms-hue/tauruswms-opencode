-- ============================================================================
-- Taurus WMS — Migración: catálogo de roles + rol como varchar(50)
-- Base de datos: taurus_admin
-- Motor: MySQL
-- Ejecutar manualmente (no hay migration runner).
-- ============================================================================

USE taurus_admin;

-- 1) Catálogo de roles
CREATE TABLE IF NOT EXISTS roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL,
    descripcion VARCHAR(255) NULL,
    activo TINYINT(1) DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_rol_nombre (nombre),
    INDEX idx_roles_activo (activo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2) Permitir roles personalizados en usuarios (antes era enum)
ALTER TABLE usuarios MODIFY rol VARCHAR(50) NOT NULL DEFAULT 'OPERADOR';

-- 3) Roles por defecto
INSERT IGNORE INTO roles (nombre, descripcion, activo) VALUES
('ADMIN',    'Acceso total a todas las rutas', 1),
('OPERADOR', 'Rutas operativas del WMS',       1),
('CONSULTA', 'Acceso de solo lectura',         1);

-- 4) MOVER roles_rutas desde taurus_wms (instalaciones existentes).
--    En instalaciones nuevas la tabla ya se crea en taurus_admin y este paso no aplica.
--    Descomentar y ejecutar si la tabla existe todavía en taurus_wms.
-- USE taurus_wms;
-- CREATE TABLE IF NOT EXISTS roles_rutas (
--     rol  VARCHAR(50)  NOT NULL,
--     ruta VARCHAR(255) NOT NULL,
--     PRIMARY KEY (rol, ruta)
-- ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
--
-- USE taurus_admin;
-- INSERT IGNORE INTO roles_rutas (rol, ruta)
-- SELECT rol, ruta FROM taurus_wms.roles_rutas;

-- 5) Permisos por defecto actualizados (idempotente, no pisa lo ya asignado)
INSERT IGNORE INTO roles_rutas (rol, ruta) VALUES
('OPERADOR', '/sidebar-preferences'),
('CONSULTA', '/sidebar-preferences'),
('CONSULTA', '/pedidos/filtros/*'),
('CONSULTA', '/pedidos/buscar_contenedores'),
('CONSULTA', '/pedidos/contenedor_stock'),
('CONSULTA', '/recepciones/buscar_*'),
('CONSULTA', '/omc/buscar_*'),
('CONSULTA', '/inventario/*'),
('CONSULTA', '/stockcontable/exportar/*'),
('CONSULTA', '/stockcontable/plantilla/*'),
('CONSULTA', '/rentradas'),
('CONSULTA', '/rsalidas'),
('OPERADOR', '/omc/tipos_ubicacion');
