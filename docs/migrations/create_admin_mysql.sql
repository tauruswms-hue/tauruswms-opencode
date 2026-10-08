SET NAMES utf8mb4;

-- TAURUS WMS - Schema para taurus_admin;
-- Engine: mysql;
-- Generado por modules/schema_generator.py;

DROP DATABASE IF EXISTS taurus_admin;
CREATE DATABASE IF NOT EXISTS taurus_admin CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE taurus_admin;


-- --- admin_usuarios ---;
CREATE TABLE `admin_usuarios` (
    `id` int AUTO_INCREMENT PRIMARY KEY,
    `username` varchar(50) NOT NULL UNIQUE,
    `password_hash` varchar(255) NOT NULL,
    `nombre` varchar(100) NOT NULL,
    `email` varchar(100),
    `rol` ENUM('SUPERADMIN','ADMIN') DEFAULT 'ADMIN',
    `activo` TINYINT(1) DEFAULT TRUE,
    `ultimo_acceso` datetime,
    `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
    `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_username` ON `admin_usuarios` (`username`);
CREATE INDEX `idx_rol` ON `admin_usuarios` (`rol`);

-- --- roles ---;
CREATE TABLE `roles` (
    `id` int AUTO_INCREMENT PRIMARY KEY,
    `nombre` varchar(50) NOT NULL,
    `descripcion` varchar(255),
    `activo` TINYINT(1) DEFAULT TRUE,
    `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
    `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_rol_nombre` (`nombre`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_roles_activo` ON `roles` (`activo`);

-- --- tenants ---;
CREATE TABLE `tenants` (
    `id` int AUTO_INCREMENT PRIMARY KEY,
    `codigo` varchar(20) NOT NULL UNIQUE,
    `nombre` varchar(100) NOT NULL,
    `razon_social` varchar(200),
    `cuit` varchar(50),
    `direccion` varchar(255),
    `telefono` varchar(50),
    `email` varchar(100),
    `activo` TINYINT(1) DEFAULT TRUE,
    `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
    `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `nombredelalmacen` varchar(200),
    `metodosdepicking` text,
    `metodo_picking_default` varchar(20) NOT NULL DEFAULT 'libre',
    `bajostock` decimal(12,3) DEFAULT 0,
    `dias_filtro_fechas` int DEFAULT 30,
    `contexto` text,
    `prompt` text,
    `proveedor_api_ia` text,
    `modelo_api_ia` text,
    `api_key` text,
    `api_token` varchar(255)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_codigo` ON `tenants` (`codigo`);
CREATE INDEX `idx_activo` ON `tenants` (`activo`);

-- --- usuarios ---;
CREATE TABLE `usuarios` (
    `id` int AUTO_INCREMENT PRIMARY KEY,
    `username` varchar(50) NOT NULL UNIQUE,
    `password_hash` varchar(255) NOT NULL,
    `nombre` varchar(100) NOT NULL,
    `email` varchar(100),
    `rol` varchar(50) DEFAULT 'OPERADOR',
    `tenant_id` int NOT NULL,
    `activo` TINYINT(1) DEFAULT TRUE,
    `ultimo_acceso` datetime,
    `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
    `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `sidebar_preferences` text,
    CONSTRAINT `fk_usuarios_tenant_id` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_tenant` ON `usuarios` (`tenant_id`);
CREATE INDEX `idx_rol` ON `usuarios` (`rol`);

-- --- configuracion ---;
CREATE TABLE `configuracion` (
    `id` int AUTO_INCREMENT PRIMARY KEY,
    `clave` varchar(100) NOT NULL UNIQUE,
    `valor` text,
    `descripcion` varchar(255),
    `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_clave` ON `configuracion` (`clave`);

-- --- audit_logs ---;
CREATE TABLE `audit_logs` (
    `id` bigint AUTO_INCREMENT PRIMARY KEY,
    `usuario_id` int,
    `usuario_nombre` varchar(100),
    `accion` varchar(50) NOT NULL,
    `modulo` varchar(100) NOT NULL,
    `detalle` text,
    `ip_address` varchar(45),
    `user_agent` varchar(255),
    `created_at` datetime DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_usuario` ON `audit_logs` (`usuario_id`);
CREATE INDEX `idx_accion` ON `audit_logs` (`accion`);
CREATE INDEX `idx_modulo` ON `audit_logs` (`modulo`);
CREATE INDEX `idx_fecha` ON `audit_logs` (`created_at`);

-- --- roles_rutas ---;
CREATE TABLE `roles_rutas` (
    `rol` varchar(50) NOT NULL,
    `ruta` varchar(255) NOT NULL,
    PRIMARY KEY (`rol`, `ruta`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --- Datos iniciales ---;

-- Roles por defecto del sistema;
INSERT IGNORE INTO `roles` (`nombre`, `descripcion`, `activo`) VALUES ('ADMIN', 'Acceso total a todas las rutas', TRUE);
INSERT IGNORE INTO `roles` (`nombre`, `descripcion`, `activo`) VALUES ('OPERADOR', 'Rutas operativas del WMS', TRUE);
INSERT IGNORE INTO `roles` (`nombre`, `descripcion`, `activo`) VALUES ('CONSULTA', 'Acceso de solo lectura', TRUE);

INSERT IGNORE INTO `configuracion` (`clave`, `valor`, `descripcion`) VALUES ('app_version', '1.0.0', 'Version actual de la aplicacion');
INSERT IGNORE INTO `configuracion` (`clave`, `valor`, `descripcion`) VALUES ('app_name', 'Taurus WMS', 'Nombre de la aplicacion');
INSERT IGNORE INTO `configuracion` (`clave`, `valor`, `descripcion`) VALUES ('mantenimiento', 'false', 'Modo mantenimiento (true/false)');

-- Permisos de rutas por rol;
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('ADMIN', '*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/materiales');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/materiales/guardar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/materiales/importar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/materiales/exportar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/materiales/plantilla/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/materiales/eliminar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/materiales/imagen/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/materiales/distribucion/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/ubicaciones');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/ubicaciones/guardar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/ubicaciones/eliminar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/ubicaciones/importar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/ubicaciones/exportar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/ubicaciones/plantilla/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/tipoubicacion');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/tipoubicacion/guardar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/tipoubicacion/eliminar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/tipoubicacion/importar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/tipoubicacion/exportar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/tipoubicacion/plantilla/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/proveedores');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/proveedores/guardar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/proveedores/eliminar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/proveedores/importar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/proveedores/exportar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/proveedores/plantilla/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/clientes');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/clientes/guardar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/clientes/eliminar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/clientes/importar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/clientes/exportar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/clientes/plantilla/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/categorias');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/categorias/guardar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/categorias/eliminar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/categorias/importar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/categorias/exportar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/categorias/plantilla/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/unidades');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/unidades/guardar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/unidades/eliminar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/unidades/importar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/unidades/exportar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/unidades/plantilla/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/transportes');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/transportes/guardar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/transportes/eliminar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/transportes/importar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/transportes/exportar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/transportes/plantilla/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/rutas');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/rutas/guardar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/rutas/eliminar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/rutas/importar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/rutas/exportar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/rutas/plantilla/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/pedidos');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/pedidos/nuevo');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/pedidos/ver/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/pedidos/editar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/pedidos/guardar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/pedidos/eliminar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/pedidos/importar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/pedidos/plantilla/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/pedidos/picking_json');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/pedidos/preparar_masivo');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/pedidos/resumen_preparar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/pedidos/cambiar_ruta_transporte');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/pedidos/filtros/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/pedidos/contenedor_stock');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/recepciones');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/recepciones/nueva');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/recepciones/guardar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/recepciones/ver/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/recepciones/buscar_*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/recepciones/guardar_item');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/recepciones/eliminar_item/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/recepciones/cerrar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/recepciones/eliminar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/recepciones/confirmar_stock/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/recepciones/anular/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/recepciones/importar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/recepciones/plantilla/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/omc');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/omc/nueva');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/omc/guardar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/omc/ver/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/omc/confirmar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/omc/modificar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/omc/anular/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/omc/buscar_*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/omc/tipos_ubicacion');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/despacho');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/despacho/despachar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/despacho/despachar_masivo');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/stockcontable');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/stockcontable/editar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/stockcontable/importar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/stockcontable/exportar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/stockcontable/plantilla/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/inventario');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/inventario/crear');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/inventario/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/parametros');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/actualizar_parametros');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/movil');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/movil/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/sidebar-preferences');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/materiales');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/materiales/imagen/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/materiales/distribucion/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/ubicaciones');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/tipoubicacion');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/proveedores');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/clientes');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/categorias');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/unidades');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/transportes');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/rutas');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/zonas');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/clases-pedido');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/pedidos');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/pedidos/ver/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/pedidos/filtros/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/pedidos/buscar_contenedores');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/pedidos/contenedor_stock');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/recepciones');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/recepciones/ver/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/recepciones/buscar_*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/omc');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/omc/ver/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/omc/buscar_*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/despacho');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/stockcontable');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/stockcontable/exportar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/stockcontable/plantilla/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/inventario');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/inventario/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/parametros');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/reportes');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/reportes/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/sidebar-preferences');


-- === FIN DEL SCRIPT ===;
-- Schema generado para engine: mysql;
