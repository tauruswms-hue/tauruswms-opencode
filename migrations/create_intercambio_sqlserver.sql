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
