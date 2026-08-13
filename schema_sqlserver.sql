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

-- SQL Server schema for taurus_wms;

-- TAURUS WMS - Schema para taurus_wms (datos operativos);
-- Engine: sqlserver;
-- Generado por modules/schema_generator.py;

IF EXISTS (SELECT name FROM sys.databases WHERE name = 'taurus_wms');
DROP DATABASE [taurus_wms];
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'taurus_wms');
CREATE DATABASE [taurus_wms];
USE [taurus_wms];


-- --- zonas ---;
CREATE TABLE [zonas] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [codigo] NVARCHAR(20) NOT NULL,
    [nombre] NVARCHAR(100) NOT NULL,
    [descripcion] NVARCHAR(MAX),
    [activo] BIT NOT NULL DEFAULT 1,
    [tenant_id] INT,
    [created_at] DATETIME2 NOT NULL DEFAULT GETDATE()
);
CREATE UNIQUE INDEX [uk_zonas_codigo_tenant] ON [zonas] ([codigo], [tenant_id]);
CREATE INDEX [idx_zona_activo] ON [zonas] ([activo]);
CREATE INDEX [idx_zonas_tenant] ON [zonas] ([tenant_id]);

-- --- tipoubicacion ---;
CREATE TABLE [tipoubicacion] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [descripcion] NVARCHAR(100) NOT NULL,
    [operacion] char(1),
    [soporte_picking] BIT NOT NULL DEFAULT 0,
    [tenant_id] INT
);
CREATE INDEX [idx_tipoubicacion_tenant] ON [tipoubicacion] ([tenant_id]);

-- --- categorias ---;
CREATE TABLE [categorias] (
    [id_categoria] INT IDENTITY(1,1) PRIMARY KEY,
    [codigo] NVARCHAR(50),
    [nombre] NVARCHAR(100) NOT NULL,
    [descripcion] NVARCHAR(MAX),
    [activo] BIT NOT NULL DEFAULT 1,
    [tenant_id] INT,
    [created_at] DATETIME2 NOT NULL DEFAULT GETDATE()
);
CREATE INDEX [idx_categorias_tenant] ON [categorias] ([tenant_id]);
CREATE UNIQUE INDEX [uk_categorias_codigo_tenant] ON [categorias] ([codigo], [tenant_id]);

-- --- proveedores ---;
CREATE TABLE [proveedores] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [codigo] NVARCHAR(50),
    [razonsocial] NVARCHAR(200) NOT NULL,
    [cuit] NVARCHAR(50),
    [direccion] NVARCHAR(255),
    [telefono] NVARCHAR(50),
    [email] NVARCHAR(100),
    [activo] BIT NOT NULL DEFAULT 1,
    [tenant_id] INT,
    [created_at] DATETIME2 NOT NULL DEFAULT GETDATE()
);
CREATE INDEX [idx_proveedores_tenant] ON [proveedores] ([tenant_id]);
CREATE UNIQUE INDEX [uk_proveedores_codigo_tenant] ON [proveedores] ([codigo], [tenant_id]);

-- --- rutas ---;
CREATE TABLE [rutas] (
    [id_ruta] INT IDENTITY(1,1) PRIMARY KEY,
    [nombre_ruta] NVARCHAR(100) NOT NULL,
    [descripcion] NVARCHAR(MAX),
    [tenant_id] INT
);
CREATE INDEX [idx_rutas_tenant] ON [rutas] ([tenant_id]);

-- --- unidades_medida ---;
CREATE TABLE [unidades_medida] (
    [id_unidad] INT IDENTITY(1,1) PRIMARY KEY,
    [codigo] NVARCHAR(50) NOT NULL,
    [nombre] NVARCHAR(100) NOT NULL,
    [simbolo] NVARCHAR(20),
    [tipo_magnitud] NVARCHAR(50) DEFAULT 'CANTIDAD',
    [conversion_a_base] decimal(12,4) DEFAULT 1.0,
    [unidad_base_referencia] NVARCHAR(10) DEFAULT 'U',
    [decimales_permitidos] INT DEFAULT 0,
    [activo] BIT NOT NULL DEFAULT 1,
    [tenant_id] INT
);
CREATE INDEX [idx_unidades_tenant] ON [unidades_medida] ([tenant_id]);

-- --- ubicaciones ---;
CREATE TABLE [ubicaciones] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [codigo] NVARCHAR(50) NOT NULL,
    [nombre] NVARCHAR(100),
    [descipcion] NVARCHAR(200),
    [tipoubicacion] INT,
    [zona] NVARCHAR(50),
    [id_zona] INT,
    [pasillo] NVARCHAR(20),
    [estante] NVARCHAR(20),
    [nivel] NVARCHAR(20),
    [posicion] NVARCHAR(20),
    [coordenadaA] NVARCHAR(20),
    [coordenadaB] NVARCHAR(20),
    [coordenadaC] NVARCHAR(20),
    [coordenadaD] NVARCHAR(20),
    [capacidad_maxima] INT NOT NULL DEFAULT 0,
    [ocupado] INT NOT NULL DEFAULT 0,
    [disponible_entrada] BIT NOT NULL DEFAULT 1,
    [disponible_salida] BIT NOT NULL DEFAULT 1,
    [orden_picking] INT NOT NULL DEFAULT 0,
    [activo] BIT NOT NULL DEFAULT 1,
    [tenant_id] INT,
    [created_at] DATETIME2 NOT NULL DEFAULT GETDATE(),
    CONSTRAINT [fk_ubicaciones_id_zona] FOREIGN KEY ([id_zona]) REFERENCES [zonas] ([id]) ON DELETE SET NULL ON UPDATE CASCADE
);
CREATE INDEX [idx_ubicaciones_tenant] ON [ubicaciones] ([tenant_id]);
CREATE UNIQUE INDEX [uk_ubicaciones_codigo_tenant] ON [ubicaciones] ([codigo], [tenant_id]);
CREATE INDEX [idx_ubi_zona] ON [ubicaciones] ([id_zona]);
CREATE INDEX [idx_ubi_tipo] ON [ubicaciones] ([tipoubicacion]);

-- --- transportes ---;
CREATE TABLE [transportes] (
    [id_transporte] INT IDENTITY(1,1) PRIMARY KEY,
    [codigo] NVARCHAR(100),
    [razonsocial] NVARCHAR(200) NOT NULL,
    [cuit] NVARCHAR(50),
    [telefono] NVARCHAR(50),
    [email] NVARCHAR(100),
    [activo] BIT NOT NULL DEFAULT 1,
    [id_muelle_salida] INT,
    [tenant_id] INT,
    CONSTRAINT [fk_transportes_id_muelle_salida] FOREIGN KEY ([id_muelle_salida]) REFERENCES [ubicaciones] ([id])
);
CREATE INDEX [idx_transportes_tenant] ON [transportes] ([tenant_id]);
CREATE UNIQUE INDEX [uk_transportes_codigo_tenant] ON [transportes] ([codigo], [tenant_id]);

-- --- transporte_rutas ---;
CREATE TABLE [transporte_rutas] (
    [id_transporte] INT NOT NULL,
    [id_ruta] INT NOT NULL,
    [observaciones] NVARCHAR(MAX),
    [tenant_id] INT,
    PRIMARY KEY ([id_transporte], [id_ruta]),
    CONSTRAINT [fk_transporte_rutas_id_transporte] FOREIGN KEY ([id_transporte]) REFERENCES [transportes] ([id_transporte]) ON DELETE CASCADE,
    CONSTRAINT [fk_transporte_rutas_id_ruta] FOREIGN KEY ([id_ruta]) REFERENCES [rutas] ([id_ruta]) ON DELETE CASCADE
);
CREATE INDEX [idx_transporte_rutas_tenant] ON [transporte_rutas] ([tenant_id]);

-- --- clientes ---;
CREATE TABLE [clientes] (
    [id_cliente] INT IDENTITY(1,1) PRIMARY KEY,
    [codigo] NVARCHAR(100),
    [razonsocial] NVARCHAR(200) NOT NULL,
    [cuit] NVARCHAR(50),
    [direccion] NVARCHAR(255),
    [localidad] NVARCHAR(100),
    [provincia] NVARCHAR(100),
    [telefono] NVARCHAR(50),
    [email] NVARCHAR(100),
    [contacto_nombre] NVARCHAR(100),
    [id_ruta] INT,
    [id_transporte_predeterminado] INT,
    [activo] BIT NOT NULL DEFAULT 1,
    [tenant_id] INT,
    CONSTRAINT [fk_clientes_id_ruta] FOREIGN KEY ([id_ruta]) REFERENCES [rutas] ([id_ruta]) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT [fk_clientes_id_transporte_predeterminado] FOREIGN KEY ([id_transporte_predeterminado]) REFERENCES [transportes] ([id_transporte]) ON DELETE SET NULL ON UPDATE CASCADE
);
CREATE INDEX [idx_clientes_tenant] ON [clientes] ([tenant_id]);
CREATE UNIQUE INDEX [uk_clientes_codigo_tenant] ON [clientes] ([codigo], [tenant_id]);

-- --- materiales ---;
CREATE TABLE [materiales] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [codigo] NVARCHAR(100) NOT NULL,
    [codigo_barras] NVARCHAR(100),
    [nombre] NVARCHAR(255) NOT NULL,
    [descripcion] NVARCHAR(MAX),
    [categoria_id] INT,
    [stock_minimo] decimal(12,3) DEFAULT 0,
    [stock_maximo] decimal(12,3) DEFAULT 0,
    [unidad_medida_id] INT,
    [trazabilidad] NVARCHAR(50) NOT NULL DEFAULT 'ninguna',
    [metodo_picking] NVARCHAR(20) NOT NULL DEFAULT 'libre',
    [peso_bruto] decimal(10,3),
    [peso_neto] decimal(10,3),
    [costo_promedio] decimal(12,4) DEFAULT 0,
    [ultimo_costo] decimal(12,4) DEFAULT 0,
    [activo] BIT NOT NULL DEFAULT 1,
    [tenant_id] INT,
    [created_at] DATETIME2 NOT NULL DEFAULT GETDATE(),
    [updated_at] DATETIME2 NOT NULL DEFAULT GETDATE(),
    CONSTRAINT [fk_materiales_categoria_id] FOREIGN KEY ([categoria_id]) REFERENCES [categorias] ([id_categoria]) ON DELETE SET NULL ON UPDATE CASCADE
);
CREATE INDEX [idx_materiales_tenant] ON [materiales] ([tenant_id]);
CREATE INDEX [idx_mat_categoria] ON [materiales] ([categoria_id]);
CREATE INDEX [idx_mat_codigo_barras] ON [materiales] ([codigo_barras]);
CREATE UNIQUE INDEX [uk_materiales_codigo_tenant] ON [materiales] ([codigo], [tenant_id]);

-- --- material_proveedor ---;
CREATE TABLE [material_proveedor] (
    [id_material] INT NOT NULL,
    [id_proveedor] INT NOT NULL,
    [codigo_referencia_prov] NVARCHAR(100),
    [es_habitual] BIT NOT NULL DEFAULT 0,
    [tenant_id] INT,
    PRIMARY KEY ([id_material], [id_proveedor]),
    CONSTRAINT [fk_material_proveedor_id_material] FOREIGN KEY ([id_material]) REFERENCES [materiales] ([id]) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT [fk_material_proveedor_id_proveedor] FOREIGN KEY ([id_proveedor]) REFERENCES [proveedores] ([id]) ON DELETE CASCADE ON UPDATE CASCADE
);
CREATE INDEX [idx_matprov_tenant] ON [material_proveedor] ([tenant_id]);

-- --- material_presentaciones ---;
CREATE TABLE [material_presentaciones] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [id_material] INT NOT NULL,
    [nombre] NVARCHAR(100) NOT NULL,
    [codigo_barras] NVARCHAR(20),
    [cantidad_unidades] decimal(10,3) NOT NULL DEFAULT 1.0,
    [peso_bruto] decimal(10,3),
    [peso_neto] decimal(10,3),
    [activo] BIT NOT NULL DEFAULT 1,
    [tenant_id] INT,
    CONSTRAINT [fk_material_presentaciones_id_material] FOREIGN KEY ([id_material]) REFERENCES [materiales] ([id]) ON DELETE CASCADE
);
CREATE UNIQUE INDEX [uk_pres_barcode_tenant] ON [material_presentaciones] ([codigo_barras], [tenant_id]);
CREATE INDEX [idx_matpres_tenant] ON [material_presentaciones] ([tenant_id]);

-- --- stockcontable ---;
CREATE TABLE [stockcontable] (
    [ID] INT IDENTITY(1,1) PRIMARY KEY,
    [Ubicacion] INT NOT NULL,
    [Material] INT NOT NULL,
    [Lote] NVARCHAR(100) NOT NULL DEFAULT 'UNICO',
    [TipoStock] NVARCHAR(50) NOT NULL DEFAULT 'Libre Venta',
    [UltimaEntrada] DATETIME2,
    [UltimaSalida] DATETIME2,
    [UltimoMovimiento] DATETIME2,
    [UsuarioUltimoMov] NVARCHAR(100),
    [FechaVencimiento] DATE,
    [StockTotal] decimal(15,4) NOT NULL DEFAULT 0,
    [StockDisponible] decimal(15,4) NOT NULL DEFAULT 0,
    [StockEntrando] decimal(15,4) NOT NULL DEFAULT 0,
    [StockSaliendo] decimal(15,4) NOT NULL DEFAULT 0,
    [IDContenedor] NVARCHAR(10) NOT NULL,
    [tenant_id] INT,
    [created_at] DATETIME2 NOT NULL DEFAULT GETDATE(),
    [updated_at] DATETIME2 NOT NULL DEFAULT GETDATE(),
    CONSTRAINT [fk_stockcontable_Ubicacion] FOREIGN KEY ([Ubicacion]) REFERENCES [ubicaciones] ([id]) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT [fk_stockcontable_Material] FOREIGN KEY ([Material]) REFERENCES [materiales] ([id]) ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE UNIQUE INDEX [uq_stock_pos] ON [stockcontable] ([Ubicacion], [Material], [IDContenedor]);
CREATE INDEX [idx_material] ON [stockcontable] ([Material]);
CREATE INDEX [idx_ubicacion] ON [stockcontable] ([Ubicacion]);
CREATE INDEX [idx_lote] ON [stockcontable] ([Lote]);
CREATE INDEX [idx_tipo_stock] ON [stockcontable] ([TipoStock]);
CREATE INDEX [idx_contenedor] ON [stockcontable] ([IDContenedor]);
CREATE INDEX [idx_stockcontable_tenant] ON [stockcontable] ([tenant_id]);

-- --- clases_pedido ---;
CREATE TABLE [clases_pedido] (
    [id_clase] INT IDENTITY(1,1) PRIMARY KEY,
    [nombre] NVARCHAR(100) NOT NULL,
    [activo] BIT NOT NULL DEFAULT 1,
    [tenant_id] INT
);
CREATE INDEX [idx_clases_pedido_tenant] ON [clases_pedido] ([tenant_id]);

-- --- recepciones_cabecera ---;
CREATE TABLE [recepciones_cabecera] (
    [id_recepcion] INT IDENTITY(1,1) PRIMARY KEY,
    [numero] NVARCHAR(20) NOT NULL,
    [id_proveedor] INT NOT NULL,
    [estado] NVARCHAR(50) NOT NULL DEFAULT 'Abierta',
    [id_contenedor] NVARCHAR(10) NOT NULL,
    [id_ubicacion_recep] INT NOT NULL,
    [id_ubicacion_destino] INT,
    [observaciones] NVARCHAR(MAX),
    [fecha_recepcion] DATETIME2 NOT NULL DEFAULT GETDATE(),
    [fecha_cierre] DATETIME2,
    [usuario_creacion] NVARCHAR(100) NOT NULL,
    [usuario_cierre] NVARCHAR(100),
    [tenant_id] INT,
    [created_at] DATETIME2 NOT NULL DEFAULT GETDATE(),
    [updated_at] DATETIME2 NOT NULL DEFAULT GETDATE(),
    CONSTRAINT [fk_recepciones_cabecera_id_proveedor] FOREIGN KEY ([id_proveedor]) REFERENCES [proveedores] ([id]) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT [fk_recepciones_cabecera_id_ubicacion_recep] FOREIGN KEY ([id_ubicacion_recep]) REFERENCES [ubicaciones] ([id]) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT [fk_recepciones_cabecera_id_ubicacion_destino] FOREIGN KEY ([id_ubicacion_destino]) REFERENCES [ubicaciones] ([id]) ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE UNIQUE INDEX [uq_recepcion_numero] ON [recepciones_cabecera] ([numero]);
CREATE INDEX [idx_rec_proveedor] ON [recepciones_cabecera] ([id_proveedor]);
CREATE INDEX [idx_rec_estado] ON [recepciones_cabecera] ([estado]);
CREATE INDEX [idx_rec_contenedor] ON [recepciones_cabecera] ([id_contenedor]);
CREATE INDEX [idx_rec_ubicrec] ON [recepciones_cabecera] ([id_ubicacion_recep]);
CREATE INDEX [idx_rec_ubicdest] ON [recepciones_cabecera] ([id_ubicacion_destino]);
CREATE INDEX [idx_rec_fecha] ON [recepciones_cabecera] ([fecha_recepcion]);
CREATE INDEX [idx_recepciones_cab_tenant] ON [recepciones_cabecera] ([tenant_id]);

-- --- recepciones_detalle ---;
CREATE TABLE [recepciones_detalle] (
    [id_detalle] INT IDENTITY(1,1) PRIMARY KEY,
    [id_recepcion] INT NOT NULL,
    [id_material] INT NOT NULL,
    [lote] NVARCHAR(100) NOT NULL DEFAULT 'UNICO',
    [fecha_vencimiento] DATE,
    [cantidad_esperada] decimal(15,4) NOT NULL DEFAULT 0,
    [cantidad_recibida] decimal(15,4) NOT NULL DEFAULT 0,
    [tipo_stock] NVARCHAR(50) NOT NULL DEFAULT 'Libre Venta',
    [observaciones] NVARCHAR(MAX),
    [tenant_id] INT,
    [created_at] DATETIME2 NOT NULL DEFAULT GETDATE(),
    [updated_at] DATETIME2 NOT NULL DEFAULT GETDATE(),
    CONSTRAINT [fk_recepciones_detalle_id_recepcion] FOREIGN KEY ([id_recepcion]) REFERENCES [recepciones_cabecera] ([id_recepcion]) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT [fk_recepciones_detalle_id_material] FOREIGN KEY ([id_material]) REFERENCES [materiales] ([id]) ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE UNIQUE INDEX [uq_det_recep_mat_lote] ON [recepciones_detalle] ([id_recepcion], [id_material], [lote], [tipo_stock]);
CREATE INDEX [idx_det_recepcion] ON [recepciones_detalle] ([id_recepcion]);
CREATE INDEX [idx_det_material] ON [recepciones_detalle] ([id_material]);
CREATE INDEX [idx_det_lote] ON [recepciones_detalle] ([lote]);
CREATE INDEX [idx_recepciones_det_tenant] ON [recepciones_detalle] ([tenant_id]);

-- --- pedidos_cabecera ---;
CREATE TABLE [pedidos_cabecera] (
    [id_pedido] INT IDENTITY(1,1) PRIMARY KEY,
    [nro_pedido] NVARCHAR(20) NOT NULL,
    [id_cliente] INT NOT NULL,
    [id_clase] INT,
    [fecha_pedido] DATE NOT NULL,
    [id_ruta] INT,
    [id_transporte] INT,
    [direccion_entrega] NVARCHAR(255),
    [observaciones] NVARCHAR(MAX),
    [estado] NVARCHAR(50) NOT NULL DEFAULT 'Pendiente',
    [fecha_despacho] DATETIME2,
    [tenant_id] INT,
    [created_at] DATETIME2 NOT NULL DEFAULT GETDATE(),
    [updated_at] DATETIME2 NOT NULL DEFAULT GETDATE(),
    CONSTRAINT [fk_pedidos_cabecera_id_cliente] FOREIGN KEY ([id_cliente]) REFERENCES [clientes] ([id_cliente]) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT [fk_pedidos_cabecera_id_clase] FOREIGN KEY ([id_clase]) REFERENCES [clases_pedido] ([id_clase]) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT [fk_pedidos_cabecera_id_ruta] FOREIGN KEY ([id_ruta]) REFERENCES [rutas] ([id_ruta]) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT [fk_pedidos_cabecera_id_transporte] FOREIGN KEY ([id_transporte]) REFERENCES [transportes] ([id_transporte]) ON DELETE SET NULL ON UPDATE CASCADE
);
CREATE UNIQUE INDEX [uq_pedido_nro] ON [pedidos_cabecera] ([nro_pedido]);
CREATE INDEX [idx_pedido_cliente] ON [pedidos_cabecera] ([id_cliente]);
CREATE INDEX [idx_pedido_estado] ON [pedidos_cabecera] ([estado]);
CREATE INDEX [idx_pedido_fecha] ON [pedidos_cabecera] ([fecha_pedido]);
CREATE INDEX [idx_pedidos_cab_tenant] ON [pedidos_cabecera] ([tenant_id]);

-- --- pedidos_detalle ---;
CREATE TABLE [pedidos_detalle] (
    [id_detalle] INT IDENTITY(1,1) PRIMARY KEY,
    [id_pedido] INT NOT NULL,
    [id_material] INT NOT NULL,
    [cantidad] decimal(15,4) NOT NULL DEFAULT 0,
    [Cantidad_preparada] decimal(10,2) NOT NULL DEFAULT 0,
    [tipo_stock] NVARCHAR(20) NOT NULL DEFAULT 'Libre Venta',
    [tenant_id] INT,
    [created_at] DATETIME2 NOT NULL DEFAULT GETDATE(),
    [updated_at] DATETIME2 NOT NULL DEFAULT GETDATE(),
    CONSTRAINT [fk_pedidos_detalle_id_pedido] FOREIGN KEY ([id_pedido]) REFERENCES [pedidos_cabecera] ([id_pedido]) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT [fk_pedidos_detalle_id_material] FOREIGN KEY ([id_material]) REFERENCES [materiales] ([id]) ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE INDEX [idx_pd_pedido] ON [pedidos_detalle] ([id_pedido]);
CREATE INDEX [idx_pd_material] ON [pedidos_detalle] ([id_material]);
CREATE INDEX [idx_pedidos_det_tenant] ON [pedidos_detalle] ([tenant_id]);

-- --- omc ---;
CREATE TABLE [omc] (
    [id_omc] INT IDENTITY(1,1) PRIMARY KEY,
    [numero] NVARCHAR(20) NOT NULL,
    [id_contenedor] NVARCHAR(20),
    [id_contenedor_destino] NVARCHAR(20),
    [id_ubicacion_origen] INT,
    [id_ubicacion_destino] INT NOT NULL,
    [id_recepcion] INT,
    [id_pedido] INT,
    [estado] NVARCHAR(50) NOT NULL DEFAULT 'Pendiente',
    [observaciones] NVARCHAR(MAX),
    [fecha_creacion] DATETIME2 NOT NULL DEFAULT GETDATE(),
    [fecha_confirmacion] DATETIME2,
    [fecha_anulacion] DATETIME2,
    [usuario_creacion] NVARCHAR(100) NOT NULL,
    [usuario_confirmacion] NVARCHAR(100),
    [usuario_anulacion] NVARCHAR(100),
    [tenant_id] INT,
    [created_at] DATETIME2 NOT NULL DEFAULT GETDATE(),
    [updated_at] DATETIME2 NOT NULL DEFAULT GETDATE(),
    CONSTRAINT [fk_omc_id_ubicacion_origen] FOREIGN KEY ([id_ubicacion_origen]) REFERENCES [ubicaciones] ([id]) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT [fk_omc_id_ubicacion_destino] FOREIGN KEY ([id_ubicacion_destino]) REFERENCES [ubicaciones] ([id]) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT [fk_omc_id_recepcion] FOREIGN KEY ([id_recepcion]) REFERENCES [recepciones_cabecera] ([id_recepcion]) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT [fk_omc_id_pedido] FOREIGN KEY ([id_pedido]) REFERENCES [pedidos_cabecera] ([id_pedido]) ON DELETE SET NULL ON UPDATE CASCADE
);
CREATE UNIQUE INDEX [uq_omc_numero] ON [omc] ([numero]);
CREATE INDEX [idx_omc_contenedor] ON [omc] ([id_contenedor]);
CREATE INDEX [idx_omc_origen] ON [omc] ([id_ubicacion_origen]);
CREATE INDEX [idx_omc_destino] ON [omc] ([id_ubicacion_destino]);
CREATE INDEX [idx_omc_estado] ON [omc] ([estado]);
CREATE INDEX [idx_omc_recepcion] ON [omc] ([id_recepcion]);
CREATE INDEX [idx_omc_pedido] ON [omc] ([id_pedido]);
CREATE INDEX [idx_omc_tenant] ON [omc] ([tenant_id]);

-- --- omc_contenedores ---;
CREATE TABLE [omc_contenedores] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [id_omc] INT NOT NULL,
    [id_contenedor] NVARCHAR(20) NOT NULL,
    [id_contenedor_destino] NVARCHAR(20),
    [id_ubicacion_origen] INT NOT NULL,
    [tenant_id] INT,
    CONSTRAINT [fk_omc_contenedores_id_omc] FOREIGN KEY ([id_omc]) REFERENCES [omc] ([id_omc]) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT [fk_omc_contenedores_id_ubicacion_origen] FOREIGN KEY ([id_ubicacion_origen]) REFERENCES [ubicaciones] ([id]) ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE INDEX [idx_omc_cont_tenant] ON [omc_contenedores] ([tenant_id]);

-- --- inventarios_cabecera ---;
CREATE TABLE [inventarios_cabecera] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [numero] NVARCHAR(20) NOT NULL,
    [descripcion] NVARCHAR(200),
    [estado] NVARCHAR(50) DEFAULT 'Abierto',
    [fecha_creacion] DATETIME2 DEFAULT GETDATE(),
    [usuario_creacion] NVARCHAR(100),
    [fecha_cierre] DATETIME2,
    [usuario_cierre] NVARCHAR(100),
    [fecha_anulacion] DATETIME2,
    [usuario_anulacion] NVARCHAR(100),
    [tenant_id] INT
);
CREATE INDEX [idx_inventarios_cab_tenant] ON [inventarios_cabecera] ([tenant_id]);

-- --- inventarios_detalle ---;
CREATE TABLE [inventarios_detalle] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [id_inventario] INT NOT NULL,
    [id_ubicacion] INT NOT NULL,
    [id_material] INT NOT NULL,
    [id_contenedor] NVARCHAR(20) DEFAULT '',
    [lote] NVARCHAR(100) DEFAULT 'UNICO',
    [tipo_stock] NVARCHAR(50) DEFAULT 'Libre Venta',
    [stock_sistema] decimal(15,3) DEFAULT 0,
    [stock_contado] decimal(15,3),
    [fecha_conteo] DATETIME2,
    [usuario_conteo] NVARCHAR(100),
    [tenant_id] INT,
    CONSTRAINT [fk_inventarios_detalle_id_inventario] FOREIGN KEY ([id_inventario]) REFERENCES [inventarios_cabecera] ([id]) ON DELETE CASCADE
);
CREATE INDEX [idx_inventarios_det_tenant] ON [inventarios_detalle] ([tenant_id]);

-- --- Datos iniciales ---;

IF NOT EXISTS (SELECT 1 FROM [clases_pedido] WHERE [nombre] = 'Venta') INSERT INTO [clases_pedido] ([nombre], [activo]) VALUES ('Venta', 1);
IF NOT EXISTS (SELECT 1 FROM [clases_pedido] WHERE [nombre] = 'Reposicion') INSERT INTO [clases_pedido] ([nombre], [activo]) VALUES ('Reposicion', 1);
IF NOT EXISTS (SELECT 1 FROM [clases_pedido] WHERE [nombre] = 'Muestra') INSERT INTO [clases_pedido] ([nombre], [activo]) VALUES ('Muestra', 1);
IF NOT EXISTS (SELECT 1 FROM [clases_pedido] WHERE [nombre] = 'Devolucion') INSERT INTO [clases_pedido] ([nombre], [activo]) VALUES ('Devolucion', 1);


-- === FIN DEL SCRIPT ===;
-- Schema generado para engine: sqlserver;
-- Usuarios por defecto:;
--   SuperAdmin: admin / Admin@2024!;
--   Operador:   operador / Admin@2024!;

-- SQL Server schema for taurus_intercambio;

-- TAURUS WMS - Schema para taurus_intercambio (interfaces con sistemas externos);
-- Engine: sqlserver;
-- Generado por modules/schema_generator.py;

IF EXISTS (SELECT name FROM sys.databases WHERE name = 'taurus_intercambio');
DROP DATABASE [taurus_intercambio];
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'taurus_intercambio');
CREATE DATABASE [taurus_intercambio];
USE [taurus_intercambio];


-- --- intercambio_materiales ---;
CREATE TABLE [intercambio_materiales] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [tenant_codigo] NVARCHAR(20) NOT NULL,
    [codigo] NVARCHAR(100) NOT NULL,
    [codigo_barras] NVARCHAR(100),
    [nombre] NVARCHAR(255) NOT NULL,
    [descripcion] NVARCHAR(MAX),
    [categoria_codigo] NVARCHAR(50),
    [stock_minimo] decimal(12,3) DEFAULT 0,
    [stock_maximo] decimal(12,3) DEFAULT 0,
    [unidad_medida_codigo] NVARCHAR(50),
    [trazabilidad] NVARCHAR(50) NOT NULL DEFAULT 'ninguna',
    [metodo_picking] NVARCHAR(20) NOT NULL DEFAULT 'libre',
    [peso_bruto] decimal(10,3),
    [peso_neto] decimal(10,3),
    [costo_promedio] decimal(12,4) DEFAULT 0,
    [ultimo_costo] decimal(12,4) DEFAULT 0,
    [activo] BIT NOT NULL DEFAULT 1,
    [accion] NVARCHAR(20) NOT NULL DEFAULT 'alta',
    [estado] NVARCHAR(50) NOT NULL DEFAULT 'pendiente',
    [intentos] INT NOT NULL DEFAULT 0,
    [error_mensaje] NVARCHAR(MAX),
    [id_material_wms] INT,
    [fecha_carga] DATETIME2 NOT NULL DEFAULT GETDATE(),
    [fecha_procesado] DATETIME2,
    [updated_at] DATETIME2 NOT NULL DEFAULT GETDATE()
);
CREATE INDEX [idx_int_mat_tenant] ON [intercambio_materiales] ([tenant_codigo]);
CREATE INDEX [idx_int_mat_estado] ON [intercambio_materiales] ([estado]);
CREATE INDEX [idx_int_mat_codigo] ON [intercambio_materiales] ([codigo]);

-- --- intercambio_rutas ---;
CREATE TABLE [intercambio_rutas] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [tenant_codigo] NVARCHAR(20) NOT NULL,
    [nombre_ruta] NVARCHAR(100) NOT NULL,
    [descripcion] NVARCHAR(MAX),
    [accion] NVARCHAR(20) NOT NULL DEFAULT 'alta',
    [estado] NVARCHAR(50) NOT NULL DEFAULT 'pendiente',
    [intentos] INT NOT NULL DEFAULT 0,
    [error_mensaje] NVARCHAR(MAX),
    [id_ruta_wms] INT,
    [fecha_carga] DATETIME2 NOT NULL DEFAULT GETDATE(),
    [fecha_procesado] DATETIME2,
    [updated_at] DATETIME2 NOT NULL DEFAULT GETDATE()
);
CREATE INDEX [idx_int_rut_tenant] ON [intercambio_rutas] ([tenant_codigo]);
CREATE INDEX [idx_int_rut_estado] ON [intercambio_rutas] ([estado]);
CREATE INDEX [idx_int_rut_nombre] ON [intercambio_rutas] ([nombre_ruta]);

-- --- intercambio_transportes ---;
CREATE TABLE [intercambio_transportes] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [tenant_codigo] NVARCHAR(20) NOT NULL,
    [codigo] NVARCHAR(100) NOT NULL,
    [razonsocial] NVARCHAR(200) NOT NULL,
    [cuit] NVARCHAR(50),
    [telefono] NVARCHAR(50),
    [email] NVARCHAR(100),
    [muelle_codigo] NVARCHAR(50),
    [activo] BIT NOT NULL DEFAULT 1,
    [accion] NVARCHAR(20) NOT NULL DEFAULT 'alta',
    [estado] NVARCHAR(50) NOT NULL DEFAULT 'pendiente',
    [intentos] INT NOT NULL DEFAULT 0,
    [error_mensaje] NVARCHAR(MAX),
    [id_transporte_wms] INT,
    [fecha_carga] DATETIME2 NOT NULL DEFAULT GETDATE(),
    [fecha_procesado] DATETIME2,
    [updated_at] DATETIME2 NOT NULL DEFAULT GETDATE()
);
CREATE INDEX [idx_int_tra_tenant] ON [intercambio_transportes] ([tenant_codigo]);
CREATE INDEX [idx_int_tra_estado] ON [intercambio_transportes] ([estado]);
CREATE INDEX [idx_int_tra_codigo] ON [intercambio_transportes] ([codigo]);

-- --- intercambio_transporte_rutas ---;
CREATE TABLE [intercambio_transporte_rutas] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [tenant_codigo] NVARCHAR(20) NOT NULL,
    [transporte_codigo] NVARCHAR(100) NOT NULL,
    [ruta_nombre] NVARCHAR(100) NOT NULL,
    [observaciones] NVARCHAR(MAX),
    [accion] NVARCHAR(20) NOT NULL DEFAULT 'alta',
    [estado] NVARCHAR(50) NOT NULL DEFAULT 'pendiente',
    [intentos] INT NOT NULL DEFAULT 0,
    [error_mensaje] NVARCHAR(MAX),
    [fecha_carga] DATETIME2 NOT NULL DEFAULT GETDATE(),
    [fecha_procesado] DATETIME2,
    [updated_at] DATETIME2 NOT NULL DEFAULT GETDATE()
);
CREATE INDEX [idx_int_trr_tenant] ON [intercambio_transporte_rutas] ([tenant_codigo]);
CREATE INDEX [idx_int_trr_estado] ON [intercambio_transporte_rutas] ([estado]);
CREATE INDEX [idx_int_trr_transporte] ON [intercambio_transporte_rutas] ([transporte_codigo]);
CREATE INDEX [idx_int_trr_ruta] ON [intercambio_transporte_rutas] ([ruta_nombre]);

-- --- intercambio_clientes ---;
CREATE TABLE [intercambio_clientes] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [tenant_codigo] NVARCHAR(20) NOT NULL,
    [codigo] NVARCHAR(100) NOT NULL,
    [razonsocial] NVARCHAR(200) NOT NULL,
    [cuit] NVARCHAR(50),
    [direccion] NVARCHAR(255),
    [localidad] NVARCHAR(100),
    [provincia] NVARCHAR(100),
    [telefono] NVARCHAR(50),
    [email] NVARCHAR(100),
    [contacto_nombre] NVARCHAR(100),
    [ruta_nombre] NVARCHAR(100),
    [transporte_codigo] NVARCHAR(100),
    [activo] BIT NOT NULL DEFAULT 1,
    [accion] NVARCHAR(20) NOT NULL DEFAULT 'alta',
    [estado] NVARCHAR(50) NOT NULL DEFAULT 'pendiente',
    [intentos] INT NOT NULL DEFAULT 0,
    [error_mensaje] NVARCHAR(MAX),
    [id_cliente_wms] INT,
    [fecha_carga] DATETIME2 NOT NULL DEFAULT GETDATE(),
    [fecha_procesado] DATETIME2,
    [updated_at] DATETIME2 NOT NULL DEFAULT GETDATE()
);
CREATE INDEX [idx_int_cli_tenant] ON [intercambio_clientes] ([tenant_codigo]);
CREATE INDEX [idx_int_cli_estado] ON [intercambio_clientes] ([estado]);
CREATE INDEX [idx_int_cli_codigo] ON [intercambio_clientes] ([codigo]);

-- --- intercambio_pedidos ---;
CREATE TABLE [intercambio_pedidos] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [tenant_codigo] NVARCHAR(20) NOT NULL,
    [nro_pedido] NVARCHAR(20) NOT NULL,
    [cliente_codigo] NVARCHAR(100) NOT NULL,
    [clase_nombre] NVARCHAR(100),
    [fecha_pedido] DATE NOT NULL,
    [ruta_nombre] NVARCHAR(100),
    [transporte_codigo] NVARCHAR(100),
    [direccion_entrega] NVARCHAR(255),
    [observaciones] NVARCHAR(MAX),
    [estado_pedido] NVARCHAR(50) NOT NULL DEFAULT 'Pendiente',
    [items_json] NVARCHAR(MAX),
    [accion] NVARCHAR(20) NOT NULL DEFAULT 'alta',
    [estado] NVARCHAR(50) NOT NULL DEFAULT 'pendiente',
    [intentos] INT NOT NULL DEFAULT 0,
    [error_mensaje] NVARCHAR(MAX),
    [id_pedido_wms] INT,
    [fecha_carga] DATETIME2 NOT NULL DEFAULT GETDATE(),
    [fecha_procesado] DATETIME2,
    [updated_at] DATETIME2 NOT NULL DEFAULT GETDATE()
);
CREATE INDEX [idx_int_ped_tenant] ON [intercambio_pedidos] ([tenant_codigo]);
CREATE INDEX [idx_int_ped_estado] ON [intercambio_pedidos] ([estado]);
CREATE INDEX [idx_int_ped_nro] ON [intercambio_pedidos] ([nro_pedido]);

-- --- intercambio_log ---;
CREATE TABLE [intercambio_log] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [modulo] NVARCHAR(50) NOT NULL,
    [resultado] NVARCHAR(20) NOT NULL DEFAULT 'ok',
    [registros_procesados] INT NOT NULL DEFAULT 0,
    [registros_error] INT NOT NULL DEFAULT 0,
    [detalle] NVARCHAR(MAX),
    [usuario] NVARCHAR(100),
    [fecha] DATETIME2 NOT NULL DEFAULT GETDATE()
);
CREATE INDEX [idx_int_log_modulo] ON [intercambio_log] ([modulo]);
CREATE INDEX [idx_int_log_fecha] ON [intercambio_log] ([fecha]);

-- --- Datos iniciales ---;


-- === FIN DEL SCRIPT ===;
-- Schema generado para engine: sqlserver;
-- Usuarios por defecto:;
--   SuperAdmin: admin / Admin@2024!;
--   Operador:   operador / Admin@2024!;
