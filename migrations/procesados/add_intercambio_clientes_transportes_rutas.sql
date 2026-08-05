-- Add intercambio tables for clientes, transportes, rutas y asignaciones ruta<->transporte
-- Run manually against taurus_intercambio (MySQL). Movido a procesados/ una vez aplicado.

SET NAMES utf8mb4;

-- --- intercambio_rutas ---;
CREATE TABLE IF NOT EXISTS `intercambio_rutas` (
    `id` int AUTO_INCREMENT PRIMARY KEY,
    `tenant_codigo` varchar(20) NOT NULL,
    `nombre_ruta` varchar(100) NOT NULL,
    `descripcion` text,
    `accion` varchar(20) NOT NULL DEFAULT 'alta',
    `estado` ENUM('PENDIENTE','PROCESADO','ERROR') NOT NULL DEFAULT 'pendiente',
    `intentos` int NOT NULL DEFAULT 0,
    `error_mensaje` text,
    `id_ruta_wms` int,
    `fecha_carga` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `fecha_procesado` datetime,
    `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_int_rut_tenant` ON `intercambio_rutas` (`tenant_codigo`);
CREATE INDEX `idx_int_rut_estado` ON `intercambio_rutas` (`estado`);
CREATE INDEX `idx_int_rut_nombre` ON `intercambio_rutas` (`nombre_ruta`);

-- --- intercambio_transportes ---;
CREATE TABLE IF NOT EXISTS `intercambio_transportes` (
    `id` int AUTO_INCREMENT PRIMARY KEY,
    `tenant_codigo` varchar(20) NOT NULL,
    `codigo` varchar(100) NOT NULL,
    `razonsocial` varchar(200) NOT NULL,
    `cuit` varchar(50),
    `telefono` varchar(50),
    `email` varchar(100),
    `muelle_codigo` varchar(50),
    `activo` TINYINT(1) NOT NULL DEFAULT TRUE,
    `accion` varchar(20) NOT NULL DEFAULT 'alta',
    `estado` ENUM('PENDIENTE','PROCESADO','ERROR') NOT NULL DEFAULT 'pendiente',
    `intentos` int NOT NULL DEFAULT 0,
    `error_mensaje` text,
    `id_transporte_wms` int,
    `fecha_carga` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `fecha_procesado` datetime,
    `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_int_tra_tenant` ON `intercambio_transportes` (`tenant_codigo`);
CREATE INDEX `idx_int_tra_estado` ON `intercambio_transportes` (`estado`);
CREATE INDEX `idx_int_tra_codigo` ON `intercambio_transportes` (`codigo`);

-- --- intercambio_transporte_rutas ---;
CREATE TABLE IF NOT EXISTS `intercambio_transporte_rutas` (
    `id` int AUTO_INCREMENT PRIMARY KEY,
    `tenant_codigo` varchar(20) NOT NULL,
    `transporte_codigo` varchar(100) NOT NULL,
    `ruta_nombre` varchar(100) NOT NULL,
    `observaciones` text,
    `accion` varchar(20) NOT NULL DEFAULT 'alta',
    `estado` ENUM('PENDIENTE','PROCESADO','ERROR') NOT NULL DEFAULT 'pendiente',
    `intentos` int NOT NULL DEFAULT 0,
    `error_mensaje` text,
    `fecha_carga` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `fecha_procesado` datetime,
    `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_int_trr_tenant` ON `intercambio_transporte_rutas` (`tenant_codigo`);
CREATE INDEX `idx_int_trr_estado` ON `intercambio_transporte_rutas` (`estado`);
CREATE INDEX `idx_int_trr_transporte` ON `intercambio_transporte_rutas` (`transporte_codigo`);
CREATE INDEX `idx_int_trr_ruta` ON `intercambio_transporte_rutas` (`ruta_nombre`);

-- --- intercambio_clientes ---;
CREATE TABLE IF NOT EXISTS `intercambio_clientes` (
    `id` int AUTO_INCREMENT PRIMARY KEY,
    `tenant_codigo` varchar(20) NOT NULL,
    `codigo` varchar(100) NOT NULL,
    `razonsocial` varchar(200) NOT NULL,
    `cuit` varchar(50),
    `direccion` varchar(255),
    `localidad` varchar(100),
    `provincia` varchar(100),
    `telefono` varchar(50),
    `email` varchar(100),
    `contacto_nombre` varchar(100),
    `ruta_nombre` varchar(100),
    `transporte_codigo` varchar(100),
    `activo` TINYINT(1) NOT NULL DEFAULT TRUE,
    `accion` varchar(20) NOT NULL DEFAULT 'alta',
    `estado` ENUM('PENDIENTE','PROCESADO','ERROR') NOT NULL DEFAULT 'pendiente',
    `intentos` int NOT NULL DEFAULT 0,
    `error_mensaje` text,
    `id_cliente_wms` int,
    `fecha_carga` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `fecha_procesado` datetime,
    `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_int_cli_tenant` ON `intercambio_clientes` (`tenant_codigo`);
CREATE INDEX `idx_int_cli_estado` ON `intercambio_clientes` (`estado`);
CREATE INDEX `idx_int_cli_codigo` ON `intercambio_clientes` (`codigo`);
