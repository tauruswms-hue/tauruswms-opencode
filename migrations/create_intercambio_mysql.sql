SET NAMES utf8mb4;

-- TAURUS WMS - Schema para taurus_intercambio (interfaces con sistemas externos);
-- Engine: mysql;
-- Generado por modules/schema_generator.py;

DROP DATABASE IF EXISTS taurus_intercambio;
CREATE DATABASE IF NOT EXISTS taurus_intercambio CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE taurus_intercambio;


-- --- intercambio_materiales ---;
CREATE TABLE `intercambio_materiales` (
    `id` int AUTO_INCREMENT PRIMARY KEY,
    `tenant_codigo` varchar(20) NOT NULL,
    `codigo` varchar(100) NOT NULL,
    `codigo_barras` varchar(100),
    `nombre` varchar(255) NOT NULL,
    `descripcion` text,
    `categoria_codigo` varchar(50),
    `stock_minimo` decimal(12,3) DEFAULT 0,
    `stock_maximo` decimal(12,3) DEFAULT 0,
    `unidad_medida_codigo` varchar(50),
    `trazabilidad` ENUM('NINGUNA','LOTE','SERIE') NOT NULL DEFAULT 'ninguna',
    `metodo_picking` varchar(20) NOT NULL DEFAULT 'libre',
    `peso_bruto` decimal(10,3),
    `peso_neto` decimal(10,3),
    `costo_promedio` decimal(12,4) DEFAULT 0,
    `ultimo_costo` decimal(12,4) DEFAULT 0,
    `activo` TINYINT(1) NOT NULL DEFAULT TRUE,
    `accion` varchar(20) NOT NULL DEFAULT 'alta',
    `estado` ENUM('PENDIENTE','PROCESADO','ERROR') NOT NULL DEFAULT 'pendiente',
    `intentos` int NOT NULL DEFAULT 0,
    `error_mensaje` text,
    `id_material_wms` int,
    `fecha_carga` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `fecha_procesado` datetime,
    `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_int_mat_tenant` ON `intercambio_materiales` (`tenant_codigo`);
CREATE INDEX `idx_int_mat_estado` ON `intercambio_materiales` (`estado`);
CREATE INDEX `idx_int_mat_codigo` ON `intercambio_materiales` (`codigo`);

-- --- intercambio_rutas ---;
CREATE TABLE `intercambio_rutas` (
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
CREATE TABLE `intercambio_transportes` (
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
CREATE TABLE `intercambio_transporte_rutas` (
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
CREATE TABLE `intercambio_clientes` (
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

-- --- intercambio_pedidos ---;
CREATE TABLE `intercambio_pedidos` (
    `id` int AUTO_INCREMENT PRIMARY KEY,
    `tenant_codigo` varchar(20) NOT NULL,
    `nro_pedido` varchar(20) NOT NULL,
    `cliente_codigo` varchar(100) NOT NULL,
    `clase_nombre` varchar(100),
    `fecha_pedido` date NOT NULL,
    `ruta_nombre` varchar(100),
    `transporte_codigo` varchar(100),
    `direccion_entrega` varchar(255),
    `observaciones` text,
    `estado_pedido` varchar(50) NOT NULL DEFAULT 'Pendiente',
    `items_json` text,
    `accion` varchar(20) NOT NULL DEFAULT 'alta',
    `estado` ENUM('PENDIENTE','PROCESADO','ERROR') NOT NULL DEFAULT 'pendiente',
    `intentos` int NOT NULL DEFAULT 0,
    `error_mensaje` text,
    `id_pedido_wms` int,
    `fecha_carga` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `fecha_procesado` datetime,
    `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_int_ped_tenant` ON `intercambio_pedidos` (`tenant_codigo`);
CREATE INDEX `idx_int_ped_estado` ON `intercambio_pedidos` (`estado`);
CREATE INDEX `idx_int_ped_nro` ON `intercambio_pedidos` (`nro_pedido`);

-- --- intercambio_log ---;
CREATE TABLE `intercambio_log` (
    `id` int AUTO_INCREMENT PRIMARY KEY,
    `modulo` varchar(50) NOT NULL,
    `resultado` varchar(20) NOT NULL DEFAULT 'ok',
    `registros_procesados` int NOT NULL DEFAULT 0,
    `registros_error` int NOT NULL DEFAULT 0,
    `detalle` text,
    `usuario` varchar(100),
    `fecha` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_int_log_modulo` ON `intercambio_log` (`modulo`);
CREATE INDEX `idx_int_log_fecha` ON `intercambio_log` (`fecha`);

-- --- Datos iniciales ---;


-- === FIN DEL SCRIPT ===;
-- Schema generado para engine: mysql;
-- Usuarios por defecto:;
--   SuperAdmin: admin / Admin@2024!;
--   Operador:   operador / Admin@2024!;
