-- Add intercambio_pedidos table (pedidos sincronizados desde el sistema externo al WMS)
-- Run manually against taurus_intercambio (MySQL). Movido a procesados/ una vez aplicado.

SET NAMES utf8mb4;

-- --- intercambio_pedidos ---;
CREATE TABLE IF NOT EXISTS `intercambio_pedidos` (
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
