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
    `username` varchar(50) NOT NULL,
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
    `codigo` varchar(20) NOT NULL,
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
    `api_key` text
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_codigo` ON `tenants` (`codigo`);
CREATE INDEX `idx_activo` ON `tenants` (`activo`);

-- --- usuarios ---;
CREATE TABLE `usuarios` (
    `id` int AUTO_INCREMENT PRIMARY KEY,
    `username` varchar(50) NOT NULL,
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
    `clave` varchar(100) NOT NULL,
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

INSERT IGNORE INTO `tenants` (`id`, `codigo`, `nombre`, `razon_social`, `activo`, `nombredelalmacen`, `metodosdepicking`, `bajostock`, `dias_filtro_fechas`) VALUES (1, 'DEFAULT', 'Empresa Principal', 'Empresa Principal S.A.', TRUE, 'Almacen Principal', '"fifo"', 0, 30);

-- Roles por defecto del sistema;
INSERT IGNORE INTO `roles` (`nombre`, `descripcion`, `activo`) VALUES ('ADMIN', 'Acceso total a todas las rutas', TRUE);
INSERT IGNORE INTO `roles` (`nombre`, `descripcion`, `activo`) VALUES ('OPERADOR', 'Rutas operativas del WMS', TRUE);
INSERT IGNORE INTO `roles` (`nombre`, `descripcion`, `activo`) VALUES ('CONSULTA', 'Acceso de solo lectura', TRUE);

-- SuperAdmin password: Admin@2024!;
INSERT IGNORE INTO `admin_usuarios` (`username`, `password_hash`, `nombre`, `email`, `rol`) VALUES ('admin', 'scrypt:32768:8:1$WQ6PhKOf81VV3FcH$ed1ca47fd1fd381583f0289acf9e839521b5e74a07adfc034382ea5342d608e393b7143fec95b3aef262f1946f95696e3e8acbfc867c91769d63142d4e4a5db2', 'Administrador', 'admin@taurus.local', 'SUPERADMIN');

-- Operador password: Admin@2024!;
INSERT IGNORE INTO `usuarios` (`username`, `password_hash`, `nombre`, `email`, `rol`, `tenant_id`, `activo`) VALUES ('operador', 'scrypt:32768:8:1$WQ6PhKOf81VV3FcH$ed1ca47fd1fd381583f0289acf9e839521b5e74a07adfc034382ea5342d608e393b7143fec95b3aef262f1946f95696e3e8acbfc867c91769d63142d4e4a5db2', 'Operador General', 'operador@taurus.local', 'OPERADOR', 1, TRUE);

INSERT IGNORE INTO `configuracion` (`clave`, `valor`, `descripcion`) VALUES ('app_version', '1.0.0', 'Version actual de la aplicacion');
INSERT IGNORE INTO `configuracion` (`clave`, `valor`, `descripcion`) VALUES ('app_name', 'Taurus WMS', 'Nombre de la aplicacion');
INSERT IGNORE INTO `configuracion` (`clave`, `valor`, `descripcion`) VALUES ('mantenimiento', 'false', 'Modo mantenimiento (true/false)');
INSERT IGNORE INTO `configuracion` (`clave`, `valor`, `descripcion`) VALUES ('DB_HOST', 'localhost', 'Host del servidor de base de datos');
INSERT IGNORE INTO `configuracion` (`clave`, `valor`, `descripcion`) VALUES ('DB_PORT', '3306', 'Puerto del servidor MySQL');
INSERT IGNORE INTO `configuracion` (`clave`, `valor`, `descripcion`) VALUES ('DB_NAME', 'taurus_wms', 'Nombre de la base de datos principal');
INSERT IGNORE INTO `configuracion` (`clave`, `valor`, `descripcion`) VALUES ('DB_USER', 'taurus', 'Usuario de la base de datos');
INSERT IGNORE INTO `configuracion` (`clave`, `valor`, `descripcion`) VALUES ('DB_PASSWORD', 'Taurus_2001', 'Contrasena de la base de datos');
INSERT IGNORE INTO `configuracion` (`clave`, `valor`, `descripcion`) VALUES ('DB_CHAR_SET', 'utf8mb4', 'Charset de la base de datos');
INSERT IGNORE INTO `configuracion` (`clave`, `valor`, `descripcion`) VALUES ('DB_ENGINE', 'mysql', 'Motor de BD: mysql, postgresql, sqlite');
INSERT IGNORE INTO `configuracion` (`clave`, `valor`, `descripcion`) VALUES ('INTERCAMBIO_ENGINE', 'mysql', 'Motor de BD de intercambio (mysql, postgresql, sqlite, sqlserver)');
INSERT IGNORE INTO `configuracion` (`clave`, `valor`, `descripcion`) VALUES ('INTERCAMBIO_HOST', 'localhost', 'Host de la base de intercambio');
INSERT IGNORE INTO `configuracion` (`clave`, `valor`, `descripcion`) VALUES ('INTERCAMBIO_PORT', '3306', 'Puerto de la base de intercambio');
INSERT IGNORE INTO `configuracion` (`clave`, `valor`, `descripcion`) VALUES ('INTERCAMBIO_NAME', 'taurus_intercambio', 'Nombre de la base de intercambio');
INSERT IGNORE INTO `configuracion` (`clave`, `valor`, `descripcion`) VALUES ('INTERCAMBIO_USER', 'taurus', 'Usuario de la base de intercambio');
INSERT IGNORE INTO `configuracion` (`clave`, `valor`, `descripcion`) VALUES ('INTERCAMBIO_PASSWORD', 'Taurus_2001', 'Contrasena de la base de intercambio');
INSERT IGNORE INTO `configuracion` (`clave`, `valor`, `descripcion`) VALUES ('INTERCAMBIO_CHAR_SET', 'utf8mb4', 'Charset de la base de intercambio');

-- Permisos de rutas por rol;
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('ADMIN', '*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/materiales');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/materiales/guardar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/materiales/importar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/materiales/exportar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/materiales/plantilla/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/materiales/eliminar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/ubicaciones');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/ubicaciones/guardar');
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
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/clientes/importar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/clientes/exportar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/clientes/plantilla/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/categorias');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/categorias/guardar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/categorias/eliminar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/unidades');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/unidades/guardar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/unidades/eliminar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/unidades/importar');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/unidades/exportar/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/unidades/plantilla/*');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/transportes');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/transportes/guardar');
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
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('OPERADOR', '/sidebar-preferences');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/materiales');
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
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/stock');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/entradas');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/salidas');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/movimientos');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/reportes');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/rentradas');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/rsalidas');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/dashboard');
INSERT IGNORE INTO `roles_rutas` (`rol`, `ruta`) VALUES ('CONSULTA', '/sidebar-preferences');


-- === FIN DEL SCRIPT ===;
-- Schema generado para engine: mysql;
-- Usuarios por defecto:;
--   SuperAdmin: admin / Admin@2024!;
--   Operador:   operador / Admin@2024!;

SET NAMES utf8mb4;

-- TAURUS WMS - Schema para taurus_wms (datos operativos);
-- Engine: mysql;
-- Generado por modules/schema_generator.py;

DROP DATABASE IF EXISTS taurus_wms;
CREATE DATABASE IF NOT EXISTS taurus_wms CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE taurus_wms;


-- --- zonas ---;
CREATE TABLE `zonas` (
    `id` int AUTO_INCREMENT PRIMARY KEY,
    `codigo` varchar(20) NOT NULL,
    `nombre` varchar(100) NOT NULL,
    `descripcion` text,
    `activo` TINYINT(1) NOT NULL DEFAULT TRUE,
    `tenant_id` int,
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_zonas_codigo_tenant` (`codigo`, `tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_zona_activo` ON `zonas` (`activo`);
CREATE INDEX `idx_zonas_tenant` ON `zonas` (`tenant_id`);

-- --- tipoubicacion ---;
CREATE TABLE `tipoubicacion` (
    `id` int AUTO_INCREMENT PRIMARY KEY,
    `descripcion` varchar(100) NOT NULL,
    `operacion` char(1),
    `soporte_picking` TINYINT(1) NOT NULL DEFAULT FALSE,
    `tenant_id` int
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_tipoubicacion_tenant` ON `tipoubicacion` (`tenant_id`);

-- --- categorias ---;
CREATE TABLE `categorias` (
    `id_categoria` int AUTO_INCREMENT PRIMARY KEY,
    `codigo` varchar(50),
    `nombre` varchar(100) NOT NULL,
    `descripcion` text,
    `activo` TINYINT(1) NOT NULL DEFAULT TRUE,
    `tenant_id` int,
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_categorias_codigo_tenant` (`codigo`, `tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_categorias_tenant` ON `categorias` (`tenant_id`);

-- --- proveedores ---;
CREATE TABLE `proveedores` (
    `id` int AUTO_INCREMENT PRIMARY KEY,
    `codigo` varchar(50),
    `razonsocial` varchar(200) NOT NULL,
    `cuit` varchar(50),
    `direccion` varchar(255),
    `telefono` varchar(50),
    `email` varchar(100),
    `activo` TINYINT(1) NOT NULL DEFAULT TRUE,
    `tenant_id` int,
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_proveedores_codigo_tenant` (`codigo`, `tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_proveedores_tenant` ON `proveedores` (`tenant_id`);

-- --- rutas ---;
CREATE TABLE `rutas` (
    `id_ruta` int AUTO_INCREMENT PRIMARY KEY,
    `nombre_ruta` varchar(100) NOT NULL,
    `descripcion` text,
    `tenant_id` int
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_rutas_tenant` ON `rutas` (`tenant_id`);

-- --- unidades_medida ---;
CREATE TABLE `unidades_medida` (
    `id_unidad` int AUTO_INCREMENT PRIMARY KEY,
    `codigo` varchar(50) NOT NULL,
    `nombre` varchar(100) NOT NULL,
    `simbolo` varchar(20),
    `tipo_magnitud` varchar(50) DEFAULT 'CANTIDAD',
    `conversion_a_base` decimal(12,4) DEFAULT 1.0,
    `unidad_base_referencia` varchar(10) DEFAULT 'U',
    `decimales_permitidos` int DEFAULT 0,
    `activo` TINYINT(1) NOT NULL DEFAULT TRUE,
    `tenant_id` int
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_unidades_tenant` ON `unidades_medida` (`tenant_id`);

-- --- ubicaciones ---;
CREATE TABLE `ubicaciones` (
    `id` int AUTO_INCREMENT PRIMARY KEY,
    `codigo` varchar(50) NOT NULL,
    `nombre` varchar(100),
    `descipcion` varchar(200),
    `tipoubicacion` int,
    `zona` varchar(50),
    `id_zona` int,
    `pasillo` varchar(20),
    `estante` varchar(20),
    `nivel` varchar(20),
    `posicion` varchar(20),
    `coordenadaA` varchar(20),
    `coordenadaB` varchar(20),
    `coordenadaC` varchar(20),
    `coordenadaD` varchar(20),
    `capacidad_maxima` int NOT NULL DEFAULT 0,
    `ocupado` int NOT NULL DEFAULT 0,
    `disponible_entrada` TINYINT(1) NOT NULL DEFAULT TRUE,
    `disponible_salida` TINYINT(1) NOT NULL DEFAULT TRUE,
    `orden_picking` int NOT NULL DEFAULT 0,
    `activo` TINYINT(1) NOT NULL DEFAULT TRUE,
    `tenant_id` int,
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_ubicaciones_codigo_tenant` (`codigo`, `tenant_id`),
    CONSTRAINT `fk_ubicaciones_id_zona` FOREIGN KEY (`id_zona`) REFERENCES `zonas` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_ubicaciones_tenant` ON `ubicaciones` (`tenant_id`);
CREATE INDEX `idx_ubi_zona` ON `ubicaciones` (`id_zona`);
CREATE INDEX `idx_ubi_tipo` ON `ubicaciones` (`tipoubicacion`);

-- --- transportes ---;
CREATE TABLE `transportes` (
    `id_transporte` int AUTO_INCREMENT PRIMARY KEY,
    `codigo` varchar(100),
    `razonsocial` varchar(200) NOT NULL,
    `cuit` varchar(50),
    `telefono` varchar(50),
    `email` varchar(100),
    `activo` TINYINT(1) NOT NULL DEFAULT TRUE,
    `id_muelle_salida` int,
    `tenant_id` int,
    UNIQUE KEY `uk_transportes_codigo_tenant` (`codigo`, `tenant_id`),
    CONSTRAINT `fk_transportes_id_muelle_salida` FOREIGN KEY (`id_muelle_salida`) REFERENCES `ubicaciones` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_transportes_tenant` ON `transportes` (`tenant_id`);

-- --- transporte_rutas ---;
CREATE TABLE `transporte_rutas` (
    `id_transporte` int NOT NULL,
    `id_ruta` int NOT NULL,
    `observaciones` text,
    PRIMARY KEY (`id_transporte`, `id_ruta`),
    CONSTRAINT `fk_transporte_rutas_id_transporte` FOREIGN KEY (`id_transporte`) REFERENCES `transportes` (`id_transporte`) ON DELETE CASCADE,
    CONSTRAINT `fk_transporte_rutas_id_ruta` FOREIGN KEY (`id_ruta`) REFERENCES `rutas` (`id_ruta`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --- clientes ---;
CREATE TABLE `clientes` (
    `id_cliente` int AUTO_INCREMENT PRIMARY KEY,
    `codigo` varchar(100),
    `razonsocial` varchar(200) NOT NULL,
    `cuit` varchar(50),
    `direccion` varchar(255),
    `localidad` varchar(100),
    `provincia` varchar(100),
    `telefono` varchar(50),
    `email` varchar(100),
    `contacto_nombre` varchar(100),
    `id_ruta` int,
    `id_transporte_predeterminado` int,
    `activo` TINYINT(1) NOT NULL DEFAULT TRUE,
    `tenant_id` int,
    UNIQUE KEY `uk_clientes_codigo_tenant` (`codigo`, `tenant_id`),
    CONSTRAINT `fk_clientes_id_ruta` FOREIGN KEY (`id_ruta`) REFERENCES `rutas` (`id_ruta`) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT `fk_clientes_id_transporte_predeterminado` FOREIGN KEY (`id_transporte_predeterminado`) REFERENCES `transportes` (`id_transporte`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_clientes_tenant` ON `clientes` (`tenant_id`);

-- --- materiales ---;
CREATE TABLE `materiales` (
    `id` int AUTO_INCREMENT PRIMARY KEY,
    `codigo` varchar(100) NOT NULL,
    `codigo_barras` varchar(100),
    `nombre` varchar(255) NOT NULL,
    `descripcion` text,
    `categoria_id` int,
    `stock_minimo` decimal(12,3) DEFAULT 0,
    `stock_maximo` decimal(12,3) DEFAULT 0,
    `unidad_medida_id` int,
    `trazabilidad` ENUM('NINGUNA','LOTE','SERIE') NOT NULL DEFAULT 'ninguna',
    `metodo_picking` varchar(20) NOT NULL DEFAULT 'libre',
    `peso_bruto` decimal(10,3),
    `peso_neto` decimal(10,3),
    `costo_promedio` decimal(12,4) DEFAULT 0,
    `ultimo_costo` decimal(12,4) DEFAULT 0,
    `activo` TINYINT(1) NOT NULL DEFAULT TRUE,
    `tenant_id` int,
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_materiales_codigo_tenant` (`codigo`, `tenant_id`),
    CONSTRAINT `fk_materiales_categoria_id` FOREIGN KEY (`categoria_id`) REFERENCES `categorias` (`id_categoria`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_materiales_tenant` ON `materiales` (`tenant_id`);
CREATE INDEX `idx_mat_categoria` ON `materiales` (`categoria_id`);
CREATE INDEX `idx_mat_codigo_barras` ON `materiales` (`codigo_barras`);

-- --- material_proveedor ---;
CREATE TABLE `material_proveedor` (
    `id_material` int NOT NULL,
    `id_proveedor` int NOT NULL,
    `codigo_referencia_prov` varchar(100),
    `es_habitual` TINYINT(1) NOT NULL DEFAULT FALSE,
    `tenant_id` int,
    PRIMARY KEY (`id_material`, `id_proveedor`),
    CONSTRAINT `fk_material_proveedor_id_material` FOREIGN KEY (`id_material`) REFERENCES `materiales` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_material_proveedor_id_proveedor` FOREIGN KEY (`id_proveedor`) REFERENCES `proveedores` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_matprov_tenant` ON `material_proveedor` (`tenant_id`);

-- --- material_presentaciones ---;
CREATE TABLE `material_presentaciones` (
    `id` int AUTO_INCREMENT PRIMARY KEY,
    `id_material` int NOT NULL,
    `nombre` varchar(100) NOT NULL,
    `codigo_barras` varchar(20),
    `cantidad_unidades` decimal(10,3) NOT NULL DEFAULT 1.0,
    `peso_bruto` decimal(10,3),
    `peso_neto` decimal(10,3),
    `activo` TINYINT(1) NOT NULL DEFAULT TRUE,
    `tenant_id` int,
    UNIQUE KEY `uk_pres_barcode_tenant` (`codigo_barras`, `tenant_id`),
    CONSTRAINT `fk_material_presentaciones_id_material` FOREIGN KEY (`id_material`) REFERENCES `materiales` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_matpres_tenant` ON `material_presentaciones` (`tenant_id`);

-- --- stockcontable ---;
CREATE TABLE `stockcontable` (
    `ID` int AUTO_INCREMENT PRIMARY KEY,
    `Ubicacion` int NOT NULL,
    `Material` int NOT NULL,
    `Lote` varchar(100) NOT NULL DEFAULT 'UNICO',
    `TipoStock` ENUM('LIBRE VENTA','CALIDAD','BLOQUEADO','MAL ESTADO') NOT NULL DEFAULT 'Libre Venta',
    `UltimaEntrada` datetime,
    `UltimaSalida` datetime,
    `UltimoMovimiento` datetime,
    `UsuarioUltimoMov` varchar(100),
    `FechaVencimiento` date,
    `StockTotal` decimal(15,4) NOT NULL DEFAULT 0,
    `StockDisponible` decimal(15,4) NOT NULL DEFAULT 0,
    `StockEntrando` decimal(15,4) NOT NULL DEFAULT 0,
    `StockSaliendo` decimal(15,4) NOT NULL DEFAULT 0,
    `IDContenedor` varchar(10) NOT NULL,
    `tenant_id` int,
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uq_stock_pos` (`Ubicacion`, `Material`, `IDContenedor`),
    CONSTRAINT `fk_stockcontable_Ubicacion` FOREIGN KEY (`Ubicacion`) REFERENCES `ubicaciones` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT `fk_stockcontable_Material` FOREIGN KEY (`Material`) REFERENCES `materiales` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_material` ON `stockcontable` (`Material`);
CREATE INDEX `idx_ubicacion` ON `stockcontable` (`Ubicacion`);
CREATE INDEX `idx_lote` ON `stockcontable` (`Lote`);
CREATE INDEX `idx_tipo_stock` ON `stockcontable` (`TipoStock`);
CREATE INDEX `idx_contenedor` ON `stockcontable` (`IDContenedor`);
CREATE INDEX `idx_stockcontable_tenant` ON `stockcontable` (`tenant_id`);

-- --- clases_pedido ---;
CREATE TABLE `clases_pedido` (
    `id_clase` int AUTO_INCREMENT PRIMARY KEY,
    `nombre` varchar(100) NOT NULL,
    `activo` TINYINT(1) NOT NULL DEFAULT TRUE,
    `tenant_id` int
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_clases_pedido_tenant` ON `clases_pedido` (`tenant_id`);

-- --- recepciones_cabecera ---;
CREATE TABLE `recepciones_cabecera` (
    `id_recepcion` int AUTO_INCREMENT PRIMARY KEY,
    `numero` varchar(20) NOT NULL,
    `id_proveedor` int NOT NULL,
    `estado` ENUM('ABIERTA','CERRADA','CONFIRMADA','ANULADA') NOT NULL DEFAULT 'Abierta',
    `id_contenedor` varchar(10) NOT NULL,
    `id_ubicacion_recep` int NOT NULL,
    `id_ubicacion_destino` int,
    `observaciones` text,
    `fecha_recepcion` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `fecha_cierre` datetime,
    `usuario_creacion` varchar(100) NOT NULL,
    `usuario_cierre` varchar(100),
    `tenant_id` int,
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uq_recepcion_numero` (`numero`),
    CONSTRAINT `fk_recepciones_cabecera_id_proveedor` FOREIGN KEY (`id_proveedor`) REFERENCES `proveedores` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT `fk_recepciones_cabecera_id_ubicacion_recep` FOREIGN KEY (`id_ubicacion_recep`) REFERENCES `ubicaciones` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT `fk_recepciones_cabecera_id_ubicacion_destino` FOREIGN KEY (`id_ubicacion_destino`) REFERENCES `ubicaciones` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_rec_proveedor` ON `recepciones_cabecera` (`id_proveedor`);
CREATE INDEX `idx_rec_estado` ON `recepciones_cabecera` (`estado`);
CREATE INDEX `idx_rec_contenedor` ON `recepciones_cabecera` (`id_contenedor`);
CREATE INDEX `idx_rec_ubicrec` ON `recepciones_cabecera` (`id_ubicacion_recep`);
CREATE INDEX `idx_rec_ubicdest` ON `recepciones_cabecera` (`id_ubicacion_destino`);
CREATE INDEX `idx_rec_fecha` ON `recepciones_cabecera` (`fecha_recepcion`);
CREATE INDEX `idx_recepciones_cab_tenant` ON `recepciones_cabecera` (`tenant_id`);

-- --- recepciones_detalle ---;
CREATE TABLE `recepciones_detalle` (
    `id_detalle` int AUTO_INCREMENT PRIMARY KEY,
    `id_recepcion` int NOT NULL,
    `id_material` int NOT NULL,
    `lote` varchar(100) NOT NULL DEFAULT 'UNICO',
    `fecha_vencimiento` date,
    `cantidad_esperada` decimal(15,4) NOT NULL DEFAULT 0,
    `cantidad_recibida` decimal(15,4) NOT NULL DEFAULT 0,
    `tipo_stock` ENUM('LIBRE VENTA','CALIDAD','BLOQUEADO','MAL ESTADO') NOT NULL DEFAULT 'Libre Venta',
    `observaciones` text,
    `tenant_id` int,
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uq_det_recep_mat_lote` (`id_recepcion`, `id_material`, `lote`, `tipo_stock`),
    CONSTRAINT `fk_recepciones_detalle_id_recepcion` FOREIGN KEY (`id_recepcion`) REFERENCES `recepciones_cabecera` (`id_recepcion`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_recepciones_detalle_id_material` FOREIGN KEY (`id_material`) REFERENCES `materiales` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_det_recepcion` ON `recepciones_detalle` (`id_recepcion`);
CREATE INDEX `idx_det_material` ON `recepciones_detalle` (`id_material`);
CREATE INDEX `idx_det_lote` ON `recepciones_detalle` (`lote`);
CREATE INDEX `idx_recepciones_det_tenant` ON `recepciones_detalle` (`tenant_id`);

-- --- pedidos_cabecera ---;
CREATE TABLE `pedidos_cabecera` (
    `id_pedido` int AUTO_INCREMENT PRIMARY KEY,
    `nro_pedido` varchar(20) NOT NULL,
    `id_cliente` int NOT NULL,
    `id_clase` int,
    `fecha_pedido` date NOT NULL,
    `id_ruta` int,
    `id_transporte` int,
    `direccion_entrega` varchar(255),
    `observaciones` text,
    `estado` varchar(50) NOT NULL DEFAULT 'Pendiente',
    `fecha_despacho` datetime,
    `tenant_id` int,
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uq_pedido_nro` (`nro_pedido`),
    CONSTRAINT `fk_pedidos_cabecera_id_cliente` FOREIGN KEY (`id_cliente`) REFERENCES `clientes` (`id_cliente`) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT `fk_pedidos_cabecera_id_clase` FOREIGN KEY (`id_clase`) REFERENCES `clases_pedido` (`id_clase`) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT `fk_pedidos_cabecera_id_ruta` FOREIGN KEY (`id_ruta`) REFERENCES `rutas` (`id_ruta`) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT `fk_pedidos_cabecera_id_transporte` FOREIGN KEY (`id_transporte`) REFERENCES `transportes` (`id_transporte`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_pedido_cliente` ON `pedidos_cabecera` (`id_cliente`);
CREATE INDEX `idx_pedido_estado` ON `pedidos_cabecera` (`estado`);
CREATE INDEX `idx_pedido_fecha` ON `pedidos_cabecera` (`fecha_pedido`);
CREATE INDEX `idx_pedidos_cab_tenant` ON `pedidos_cabecera` (`tenant_id`);

-- --- pedidos_detalle ---;
CREATE TABLE `pedidos_detalle` (
    `id_detalle` int AUTO_INCREMENT PRIMARY KEY,
    `id_pedido` int NOT NULL,
    `id_material` int NOT NULL,
    `cantidad` decimal(15,4) NOT NULL DEFAULT 0,
    `Cantidad_preparada` decimal(10,2) NOT NULL DEFAULT 0,
    `tipo_stock` varchar(20) NOT NULL DEFAULT 'Libre Venta',
    `tenant_id` int,
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_pedidos_detalle_id_pedido` FOREIGN KEY (`id_pedido`) REFERENCES `pedidos_cabecera` (`id_pedido`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_pedidos_detalle_id_material` FOREIGN KEY (`id_material`) REFERENCES `materiales` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_pd_pedido` ON `pedidos_detalle` (`id_pedido`);
CREATE INDEX `idx_pd_material` ON `pedidos_detalle` (`id_material`);
CREATE INDEX `idx_pedidos_det_tenant` ON `pedidos_detalle` (`tenant_id`);

-- --- omc ---;
CREATE TABLE `omc` (
    `id_omc` int AUTO_INCREMENT PRIMARY KEY,
    `numero` varchar(20) NOT NULL,
    `id_contenedor` varchar(20),
    `id_contenedor_destino` varchar(20),
    `id_ubicacion_origen` int,
    `id_ubicacion_destino` int NOT NULL,
    `id_recepcion` int,
    `id_pedido` int,
    `estado` ENUM('PENDIENTE','CONFIRMADA','ANULADA') NOT NULL DEFAULT 'Pendiente',
    `observaciones` text,
    `fecha_creacion` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `fecha_confirmacion` datetime,
    `fecha_anulacion` datetime,
    `usuario_creacion` varchar(100) NOT NULL,
    `usuario_confirmacion` varchar(100),
    `usuario_anulacion` varchar(100),
    `tenant_id` int,
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uq_omc_numero` (`numero`),
    CONSTRAINT `fk_omc_id_ubicacion_origen` FOREIGN KEY (`id_ubicacion_origen`) REFERENCES `ubicaciones` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT `fk_omc_id_ubicacion_destino` FOREIGN KEY (`id_ubicacion_destino`) REFERENCES `ubicaciones` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT `fk_omc_id_recepcion` FOREIGN KEY (`id_recepcion`) REFERENCES `recepciones_cabecera` (`id_recepcion`) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT `fk_omc_id_pedido` FOREIGN KEY (`id_pedido`) REFERENCES `pedidos_cabecera` (`id_pedido`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_omc_contenedor` ON `omc` (`id_contenedor`);
CREATE INDEX `idx_omc_origen` ON `omc` (`id_ubicacion_origen`);
CREATE INDEX `idx_omc_destino` ON `omc` (`id_ubicacion_destino`);
CREATE INDEX `idx_omc_estado` ON `omc` (`estado`);
CREATE INDEX `idx_omc_recepcion` ON `omc` (`id_recepcion`);
CREATE INDEX `idx_omc_pedido` ON `omc` (`id_pedido`);
CREATE INDEX `idx_omc_tenant` ON `omc` (`tenant_id`);

-- --- omc_contenedores ---;
CREATE TABLE `omc_contenedores` (
    `id` int AUTO_INCREMENT PRIMARY KEY,
    `id_omc` int NOT NULL,
    `id_contenedor` varchar(20) NOT NULL,
    `id_contenedor_destino` varchar(20),
    `id_ubicacion_origen` int NOT NULL,
    `tenant_id` int,
    CONSTRAINT `fk_omc_contenedores_id_omc` FOREIGN KEY (`id_omc`) REFERENCES `omc` (`id_omc`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_omc_contenedores_id_ubicacion_origen` FOREIGN KEY (`id_ubicacion_origen`) REFERENCES `ubicaciones` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_omc_cont_tenant` ON `omc_contenedores` (`tenant_id`);

-- --- inventarios_cabecera ---;
CREATE TABLE `inventarios_cabecera` (
    `id` int AUTO_INCREMENT PRIMARY KEY,
    `numero` varchar(20) NOT NULL,
    `descripcion` varchar(200),
    `estado` ENUM('ABIERTO','CERRADO','ANULADO') DEFAULT 'Abierto',
    `fecha_creacion` datetime DEFAULT CURRENT_TIMESTAMP,
    `usuario_creacion` varchar(100),
    `fecha_cierre` datetime,
    `usuario_cierre` varchar(100),
    `fecha_anulacion` datetime,
    `usuario_anulacion` varchar(100),
    `tenant_id` int
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_inventarios_cab_tenant` ON `inventarios_cabecera` (`tenant_id`);

-- --- inventarios_detalle ---;
CREATE TABLE `inventarios_detalle` (
    `id` int AUTO_INCREMENT PRIMARY KEY,
    `id_inventario` int NOT NULL,
    `id_ubicacion` int NOT NULL,
    `id_material` int NOT NULL,
    `id_contenedor` varchar(20) DEFAULT '',
    `lote` varchar(100) DEFAULT 'UNICO',
    `tipo_stock` varchar(50) DEFAULT 'Libre Venta',
    `stock_sistema` decimal(15,3) DEFAULT 0,
    `stock_contado` decimal(15,3),
    `fecha_conteo` datetime,
    `usuario_conteo` varchar(100),
    `tenant_id` int,
    CONSTRAINT `fk_inventarios_detalle_id_inventario` FOREIGN KEY (`id_inventario`) REFERENCES `inventarios_cabecera` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX `idx_inventarios_det_tenant` ON `inventarios_detalle` (`tenant_id`);

-- --- Datos iniciales ---;

INSERT IGNORE INTO `clases_pedido` (`nombre`, `activo`) VALUES ('Venta', TRUE);
INSERT IGNORE INTO `clases_pedido` (`nombre`, `activo`) VALUES ('Reposicion', TRUE);
INSERT IGNORE INTO `clases_pedido` (`nombre`, `activo`) VALUES ('Muestra', TRUE);
INSERT IGNORE INTO `clases_pedido` (`nombre`, `activo`) VALUES ('Devolucion', TRUE);


-- === FIN DEL SCRIPT ===;
-- Schema generado para engine: mysql;
-- Usuarios por defecto:;
--   SuperAdmin: admin / Admin@2024!;
--   Operador:   operador / Admin@2024!;

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
