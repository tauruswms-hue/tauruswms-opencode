-- SQL Server schema for taurus_admin;

-- TAURUS WMS - Schema para taurus_admin;
-- Engine: sqlserver;
-- Generado por modules/schema_generator.py;

IF EXISTS (SELECT name FROM sys.databases WHERE name = 'taurus_admin');
DROP DATABASE [taurus_admin];
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'taurus_admin');
CREATE DATABASE [taurus_admin];
USE [taurus_admin];


-- --- admin_usuarios ---;
CREATE TABLE [admin_usuarios] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [username] NVARCHAR(50) NOT NULL,
    [password_hash] NVARCHAR(255) NOT NULL,
    [nombre] NVARCHAR(100) NOT NULL,
    [email] NVARCHAR(100),
    [rol] NVARCHAR(50) DEFAULT 'ADMIN',
    [activo] BIT DEFAULT 1,
    [ultimo_acceso] DATETIME2,
    [created_at] DATETIME2 DEFAULT GETDATE(),
    [updated_at] DATETIME2 DEFAULT GETDATE()
);
CREATE INDEX [idx_username] ON [admin_usuarios] ([username]);
CREATE INDEX [idx_rol] ON [admin_usuarios] ([rol]);

-- --- roles ---;
CREATE TABLE [roles] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [nombre] NVARCHAR(50) NOT NULL,
    [descripcion] NVARCHAR(255),
    [activo] BIT DEFAULT 1,
    [created_at] DATETIME2 DEFAULT GETDATE(),
    [updated_at] DATETIME2 DEFAULT GETDATE()
);
CREATE UNIQUE INDEX [uk_rol_nombre] ON [roles] ([nombre]);
CREATE INDEX [idx_roles_activo] ON [roles] ([activo]);

-- --- tenants ---;
CREATE TABLE [tenants] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [codigo] NVARCHAR(20) NOT NULL,
    [nombre] NVARCHAR(100) NOT NULL,
    [razon_social] NVARCHAR(200),
    [cuit] NVARCHAR(50),
    [direccion] NVARCHAR(255),
    [telefono] NVARCHAR(50),
    [email] NVARCHAR(100),
    [activo] BIT DEFAULT 1,
    [created_at] DATETIME2 DEFAULT GETDATE(),
    [updated_at] DATETIME2 DEFAULT GETDATE(),
    [nombredelalmacen] NVARCHAR(200),
    [metodosdepicking] NVARCHAR(MAX),
    [metodo_picking_default] NVARCHAR(20) NOT NULL DEFAULT 'libre',
    [bajostock] decimal(12,3) DEFAULT 0,
    [dias_filtro_fechas] INT DEFAULT 30,
    [contexto] NVARCHAR(MAX),
    [prompt] NVARCHAR(MAX),
    [proveedor_api_ia] NVARCHAR(MAX),
    [modelo_api_ia] NVARCHAR(MAX),
    [api_key] NVARCHAR(MAX)
);
CREATE INDEX [idx_codigo] ON [tenants] ([codigo]);
CREATE INDEX [idx_activo] ON [tenants] ([activo]);

-- --- usuarios ---;
CREATE TABLE [usuarios] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [username] NVARCHAR(50) NOT NULL,
    [password_hash] NVARCHAR(255) NOT NULL,
    [nombre] NVARCHAR(100) NOT NULL,
    [email] NVARCHAR(100),
    [rol] NVARCHAR(50) DEFAULT 'OPERADOR',
    [tenant_id] INT NOT NULL,
    [activo] BIT DEFAULT 1,
    [ultimo_acceso] DATETIME2,
    [created_at] DATETIME2 DEFAULT GETDATE(),
    [updated_at] DATETIME2 DEFAULT GETDATE(),
    [sidebar_preferences] NVARCHAR(MAX),
    CONSTRAINT [fk_usuarios_tenant_id] FOREIGN KEY ([tenant_id]) REFERENCES [tenants] ([id]) ON DELETE CASCADE
);
CREATE INDEX [idx_tenant] ON [usuarios] ([tenant_id]);
CREATE INDEX [idx_rol] ON [usuarios] ([rol]);

-- --- configuracion ---;
CREATE TABLE [configuracion] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [clave] NVARCHAR(100) NOT NULL,
    [valor] NVARCHAR(MAX),
    [descripcion] NVARCHAR(255),
    [updated_at] DATETIME2 DEFAULT GETDATE()
);
CREATE INDEX [idx_clave] ON [configuracion] ([clave]);

-- --- audit_logs ---;
CREATE TABLE [audit_logs] (
    [id] BIGINT IDENTITY(1,1) PRIMARY KEY,
    [usuario_id] INT,
    [usuario_nombre] NVARCHAR(100),
    [accion] NVARCHAR(50) NOT NULL,
    [modulo] NVARCHAR(100) NOT NULL,
    [detalle] NVARCHAR(MAX),
    [ip_address] NVARCHAR(45),
    [user_agent] NVARCHAR(255),
    [created_at] DATETIME2 DEFAULT GETDATE()
);
CREATE INDEX [idx_usuario] ON [audit_logs] ([usuario_id]);
CREATE INDEX [idx_accion] ON [audit_logs] ([accion]);
CREATE INDEX [idx_modulo] ON [audit_logs] ([modulo]);
CREATE INDEX [idx_fecha] ON [audit_logs] ([created_at]);

-- --- roles_rutas ---;
CREATE TABLE [roles_rutas] (
    [rol] NVARCHAR(50) NOT NULL,
    [ruta] NVARCHAR(255) NOT NULL,
    PRIMARY KEY ([rol], [ruta])
);

-- --- Datos iniciales ---;

IF NOT EXISTS (SELECT 1 FROM [tenants] WHERE [id] = 1) INSERT INTO [tenants] ([id], [codigo], [nombre], [razon_social], [activo], [nombredelalmacen], [metodosdepicking], [bajostock], [dias_filtro_fechas]) VALUES (1, 'DEFAULT', 'Empresa Principal', 'Empresa Principal S.A.', 1, 'Almacen Principal', '"fifo"', 0, 30);

-- Roles por defecto del sistema;
IF NOT EXISTS (SELECT 1 FROM [roles] WHERE [nombre] = 'ADMIN') INSERT INTO [roles] ([nombre], [descripcion], [activo]) VALUES ('ADMIN', 'Acceso total a todas las rutas', 1);
IF NOT EXISTS (SELECT 1 FROM [roles] WHERE [nombre] = 'OPERADOR') INSERT INTO [roles] ([nombre], [descripcion], [activo]) VALUES ('OPERADOR', 'Rutas operativas del WMS', 1);
IF NOT EXISTS (SELECT 1 FROM [roles] WHERE [nombre] = 'CONSULTA') INSERT INTO [roles] ([nombre], [descripcion], [activo]) VALUES ('CONSULTA', 'Acceso de solo lectura', 1);

-- SuperAdmin password: Admin@2024!;
IF NOT EXISTS (SELECT 1 FROM [admin_usuarios] WHERE [username] = 'admin') INSERT INTO [admin_usuarios] ([username], [password_hash], [nombre], [email], [rol]) VALUES ('admin', 'scrypt:32768:8:1$WQ6PhKOf81VV3FcH$ed1ca47fd1fd381583f0289acf9e839521b5e74a07adfc034382ea5342d608e393b7143fec95b3aef262f1946f95696e3e8acbfc867c91769d63142d4e4a5db2', 'Administrador', 'admin@taurus.local', 'SUPERADMIN');

-- Operador password: Admin@2024!;
IF NOT EXISTS (SELECT 1 FROM [usuarios] WHERE [username] = 'operador') INSERT INTO [usuarios] ([username], [password_hash], [nombre], [email], [rol], [tenant_id], [activo]) VALUES ('operador', 'scrypt:32768:8:1$WQ6PhKOf81VV3FcH$ed1ca47fd1fd381583f0289acf9e839521b5e74a07adfc034382ea5342d608e393b7143fec95b3aef262f1946f95696e3e8acbfc867c91769d63142d4e4a5db2', 'Operador General', 'operador@taurus.local', 'OPERADOR', 1, 1);

IF NOT EXISTS (SELECT 1 FROM [configuracion] WHERE [clave] = 'app_version') INSERT INTO [configuracion] ([clave], [valor], [descripcion]) VALUES ('app_version', '1.0.0', 'Version actual de la aplicacion');
IF NOT EXISTS (SELECT 1 FROM [configuracion] WHERE [clave] = 'app_name') INSERT INTO [configuracion] ([clave], [valor], [descripcion]) VALUES ('app_name', 'Taurus WMS', 'Nombre de la aplicacion');
IF NOT EXISTS (SELECT 1 FROM [configuracion] WHERE [clave] = 'mantenimiento') INSERT INTO [configuracion] ([clave], [valor], [descripcion]) VALUES ('mantenimiento', 'false', 'Modo mantenimiento (true/false)');
IF NOT EXISTS (SELECT 1 FROM [configuracion] WHERE [clave] = 'DB_HOST') INSERT INTO [configuracion] ([clave], [valor], [descripcion]) VALUES ('DB_HOST', 'localhost', 'Host del servidor de base de datos');
IF NOT EXISTS (SELECT 1 FROM [configuracion] WHERE [clave] = 'DB_PORT') INSERT INTO [configuracion] ([clave], [valor], [descripcion]) VALUES ('DB_PORT', '3306', 'Puerto del servidor MySQL');
IF NOT EXISTS (SELECT 1 FROM [configuracion] WHERE [clave] = 'DB_NAME') INSERT INTO [configuracion] ([clave], [valor], [descripcion]) VALUES ('DB_NAME', 'taurus_wms', 'Nombre de la base de datos principal');
IF NOT EXISTS (SELECT 1 FROM [configuracion] WHERE [clave] = 'DB_USER') INSERT INTO [configuracion] ([clave], [valor], [descripcion]) VALUES ('DB_USER', 'taurus', 'Usuario de la base de datos');
IF NOT EXISTS (SELECT 1 FROM [configuracion] WHERE [clave] = 'DB_PASSWORD') INSERT INTO [configuracion] ([clave], [valor], [descripcion]) VALUES ('DB_PASSWORD', 'Taurus_2001', 'Contrasena de la base de datos');
IF NOT EXISTS (SELECT 1 FROM [configuracion] WHERE [clave] = 'DB_CHAR_SET') INSERT INTO [configuracion] ([clave], [valor], [descripcion]) VALUES ('DB_CHAR_SET', 'utf8mb4', 'Charset de la base de datos');
IF NOT EXISTS (SELECT 1 FROM [configuracion] WHERE [clave] = 'DB_ENGINE') INSERT INTO [configuracion] ([clave], [valor], [descripcion]) VALUES ('DB_ENGINE', 'mysql', 'Motor de BD: mysql, postgresql, sqlite');
IF NOT EXISTS (SELECT 1 FROM [configuracion] WHERE [clave] = 'INTERCAMBIO_ENGINE') INSERT INTO [configuracion] ([clave], [valor], [descripcion]) VALUES ('INTERCAMBIO_ENGINE', 'mysql', 'Motor de BD de intercambio (mysql, postgresql, sqlite, sqlserver)');
IF NOT EXISTS (SELECT 1 FROM [configuracion] WHERE [clave] = 'INTERCAMBIO_HOST') INSERT INTO [configuracion] ([clave], [valor], [descripcion]) VALUES ('INTERCAMBIO_HOST', 'localhost', 'Host de la base de intercambio');
IF NOT EXISTS (SELECT 1 FROM [configuracion] WHERE [clave] = 'INTERCAMBIO_PORT') INSERT INTO [configuracion] ([clave], [valor], [descripcion]) VALUES ('INTERCAMBIO_PORT', '3306', 'Puerto de la base de intercambio');
IF NOT EXISTS (SELECT 1 FROM [configuracion] WHERE [clave] = 'INTERCAMBIO_NAME') INSERT INTO [configuracion] ([clave], [valor], [descripcion]) VALUES ('INTERCAMBIO_NAME', 'taurus_intercambio', 'Nombre de la base de intercambio');
IF NOT EXISTS (SELECT 1 FROM [configuracion] WHERE [clave] = 'INTERCAMBIO_USER') INSERT INTO [configuracion] ([clave], [valor], [descripcion]) VALUES ('INTERCAMBIO_USER', 'taurus', 'Usuario de la base de intercambio');
IF NOT EXISTS (SELECT 1 FROM [configuracion] WHERE [clave] = 'INTERCAMBIO_PASSWORD') INSERT INTO [configuracion] ([clave], [valor], [descripcion]) VALUES ('INTERCAMBIO_PASSWORD', 'Taurus_2001', 'Contrasena de la base de intercambio');
IF NOT EXISTS (SELECT 1 FROM [configuracion] WHERE [clave] = 'INTERCAMBIO_CHAR_SET') INSERT INTO [configuracion] ([clave], [valor], [descripcion]) VALUES ('INTERCAMBIO_CHAR_SET', 'utf8mb4', 'Charset de la base de intercambio');

-- Permisos de rutas por rol;
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'ADMIN') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('ADMIN', '*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/materiales');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/materiales/guardar');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/materiales/importar');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/materiales/exportar/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/materiales/plantilla/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/materiales/eliminar/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/ubicaciones');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/ubicaciones/guardar');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/ubicaciones/importar');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/ubicaciones/exportar/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/ubicaciones/plantilla/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/tipoubicacion');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/tipoubicacion/guardar');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/tipoubicacion/eliminar/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/tipoubicacion/importar');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/tipoubicacion/exportar/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/tipoubicacion/plantilla/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/proveedores');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/proveedores/guardar');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/proveedores/eliminar/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/proveedores/importar');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/proveedores/exportar/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/proveedores/plantilla/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/clientes');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/clientes/guardar');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/clientes/importar');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/clientes/exportar/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/clientes/plantilla/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/categorias');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/categorias/guardar');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/categorias/eliminar/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/unidades');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/unidades/guardar');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/unidades/eliminar/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/unidades/importar');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/unidades/exportar/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/unidades/plantilla/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/transportes');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/transportes/guardar');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/transportes/importar');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/transportes/exportar/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/transportes/plantilla/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/rutas');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/rutas/guardar');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/rutas/eliminar/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/rutas/importar');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/rutas/exportar/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/rutas/plantilla/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/pedidos');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/pedidos/nuevo');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/pedidos/ver/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/pedidos/editar/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/pedidos/guardar');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/pedidos/eliminar/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/pedidos/importar');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/pedidos/plantilla/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/pedidos/picking_json');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/pedidos/preparar_masivo');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/pedidos/resumen_preparar');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/pedidos/cambiar_ruta_transporte');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/pedidos/filtros/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/pedidos/contenedor_stock');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/recepciones');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/recepciones/nueva');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/recepciones/guardar');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/recepciones/ver/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/recepciones/buscar_*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/recepciones/guardar_item');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/recepciones/eliminar_item/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/recepciones/cerrar/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/recepciones/eliminar/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/recepciones/confirmar_stock/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/recepciones/anular/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/recepciones/importar');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/recepciones/plantilla/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/omc');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/omc/nueva');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/omc/guardar');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/omc/ver/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/omc/confirmar/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/omc/modificar/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/omc/anular/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/omc/buscar_*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/omc/tipos_ubicacion');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/despacho');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/despacho/despachar/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/despacho/despachar_masivo');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/stockcontable');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/stockcontable/editar/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/stockcontable/importar');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/stockcontable/exportar/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/stockcontable/plantilla/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/inventario');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/inventario/crear');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/inventario/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/parametros');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/actualizar_parametros');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'OPERADOR') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('OPERADOR', '/sidebar-preferences');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/materiales');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/ubicaciones');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/tipoubicacion');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/proveedores');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/clientes');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/categorias');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/unidades');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/transportes');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/rutas');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/zonas');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/clases-pedido');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/pedidos');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/pedidos/ver/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/pedidos/filtros/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/pedidos/buscar_contenedores');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/pedidos/contenedor_stock');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/recepciones');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/recepciones/ver/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/recepciones/buscar_*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/omc');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/omc/ver/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/omc/buscar_*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/despacho');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/stockcontable');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/stockcontable/exportar/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/stockcontable/plantilla/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/inventario');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/inventario/*');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/parametros');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/stock');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/entradas');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/salidas');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/movimientos');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/reportes');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/rentradas');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/rsalidas');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/dashboard');
IF NOT EXISTS (SELECT 1 FROM [roles_rutas] WHERE [rol] = 'CONSULTA') INSERT INTO [roles_rutas] ([rol], [ruta]) VALUES ('CONSULTA', '/sidebar-preferences');


-- === FIN DEL SCRIPT ===;
-- Schema generado para engine: sqlserver;
-- Usuarios por defecto:;
--   SuperAdmin: admin / Admin@2024!;
--   Operador:   operador / Admin@2024!;
