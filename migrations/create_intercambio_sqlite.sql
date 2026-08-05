-- SQLite schema for taurus_intercambio;
PRAGMA foreign_keys = ON;

-- TAURUS WMS - Schema para taurus_intercambio (interfaces con sistemas externos);
-- Engine: sqlite;
-- Generado por modules/schema_generator.py;

-- SQLite: database is a file, drop by deleting the file: taurus_intercambio.db;


-- --- intercambio_materiales ---;
CREATE TABLE IF NOT EXISTS "intercambio_materiales" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "tenant_codigo" TEXT NOT NULL,
    "codigo" TEXT NOT NULL,
    "codigo_barras" TEXT,
    "nombre" TEXT NOT NULL,
    "descripcion" text,
    "categoria_codigo" TEXT,
    "stock_minimo" REAL DEFAULT 0,
    "stock_maximo" REAL DEFAULT 0,
    "unidad_medida_codigo" TEXT,
    "trazabilidad" TEXT NOT NULL DEFAULT 'ninguna',
    "metodo_picking" TEXT NOT NULL DEFAULT 'libre',
    "peso_bruto" REAL,
    "peso_neto" REAL,
    "costo_promedio" REAL DEFAULT 0,
    "ultimo_costo" REAL DEFAULT 0,
    "activo" INTEGER NOT NULL DEFAULT 1,
    "accion" TEXT NOT NULL DEFAULT 'alta',
    "estado" TEXT NOT NULL DEFAULT 'pendiente',
    "intentos" INTEGER NOT NULL DEFAULT 0,
    "error_mensaje" text,
    "id_material_wms" INTEGER,
    "fecha_carga" TEXT NOT NULL DEFAULT (datetime('now')),
    "fecha_procesado" TEXT,
    "updated_at" TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS "idx_int_mat_tenant" ON "intercambio_materiales" ("tenant_codigo");
CREATE INDEX IF NOT EXISTS "idx_int_mat_estado" ON "intercambio_materiales" ("estado");
CREATE INDEX IF NOT EXISTS "idx_int_mat_codigo" ON "intercambio_materiales" ("codigo");

-- --- intercambio_rutas ---;
CREATE TABLE IF NOT EXISTS "intercambio_rutas" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "tenant_codigo" TEXT NOT NULL,
    "nombre_ruta" TEXT NOT NULL,
    "descripcion" text,
    "accion" TEXT NOT NULL DEFAULT 'alta',
    "estado" TEXT NOT NULL DEFAULT 'pendiente',
    "intentos" INTEGER NOT NULL DEFAULT 0,
    "error_mensaje" text,
    "id_ruta_wms" INTEGER,
    "fecha_carga" TEXT NOT NULL DEFAULT (datetime('now')),
    "fecha_procesado" TEXT,
    "updated_at" TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS "idx_int_rut_tenant" ON "intercambio_rutas" ("tenant_codigo");
CREATE INDEX IF NOT EXISTS "idx_int_rut_estado" ON "intercambio_rutas" ("estado");
CREATE INDEX IF NOT EXISTS "idx_int_rut_nombre" ON "intercambio_rutas" ("nombre_ruta");

-- --- intercambio_transportes ---;
CREATE TABLE IF NOT EXISTS "intercambio_transportes" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "tenant_codigo" TEXT NOT NULL,
    "codigo" TEXT NOT NULL,
    "razonsocial" TEXT NOT NULL,
    "cuit" TEXT,
    "telefono" TEXT,
    "email" TEXT,
    "muelle_codigo" TEXT,
    "activo" INTEGER NOT NULL DEFAULT 1,
    "accion" TEXT NOT NULL DEFAULT 'alta',
    "estado" TEXT NOT NULL DEFAULT 'pendiente',
    "intentos" INTEGER NOT NULL DEFAULT 0,
    "error_mensaje" text,
    "id_transporte_wms" INTEGER,
    "fecha_carga" TEXT NOT NULL DEFAULT (datetime('now')),
    "fecha_procesado" TEXT,
    "updated_at" TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS "idx_int_tra_tenant" ON "intercambio_transportes" ("tenant_codigo");
CREATE INDEX IF NOT EXISTS "idx_int_tra_estado" ON "intercambio_transportes" ("estado");
CREATE INDEX IF NOT EXISTS "idx_int_tra_codigo" ON "intercambio_transportes" ("codigo");

-- --- intercambio_transporte_rutas ---;
CREATE TABLE IF NOT EXISTS "intercambio_transporte_rutas" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "tenant_codigo" TEXT NOT NULL,
    "transporte_codigo" TEXT NOT NULL,
    "ruta_nombre" TEXT NOT NULL,
    "observaciones" text,
    "accion" TEXT NOT NULL DEFAULT 'alta',
    "estado" TEXT NOT NULL DEFAULT 'pendiente',
    "intentos" INTEGER NOT NULL DEFAULT 0,
    "error_mensaje" text,
    "fecha_carga" TEXT NOT NULL DEFAULT (datetime('now')),
    "fecha_procesado" TEXT,
    "updated_at" TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS "idx_int_trr_tenant" ON "intercambio_transporte_rutas" ("tenant_codigo");
CREATE INDEX IF NOT EXISTS "idx_int_trr_estado" ON "intercambio_transporte_rutas" ("estado");
CREATE INDEX IF NOT EXISTS "idx_int_trr_transporte" ON "intercambio_transporte_rutas" ("transporte_codigo");
CREATE INDEX IF NOT EXISTS "idx_int_trr_ruta" ON "intercambio_transporte_rutas" ("ruta_nombre");

-- --- intercambio_clientes ---;
CREATE TABLE IF NOT EXISTS "intercambio_clientes" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "tenant_codigo" TEXT NOT NULL,
    "codigo" TEXT NOT NULL,
    "razonsocial" TEXT NOT NULL,
    "cuit" TEXT,
    "direccion" TEXT,
    "localidad" TEXT,
    "provincia" TEXT,
    "telefono" TEXT,
    "email" TEXT,
    "contacto_nombre" TEXT,
    "ruta_nombre" TEXT,
    "transporte_codigo" TEXT,
    "activo" INTEGER NOT NULL DEFAULT 1,
    "accion" TEXT NOT NULL DEFAULT 'alta',
    "estado" TEXT NOT NULL DEFAULT 'pendiente',
    "intentos" INTEGER NOT NULL DEFAULT 0,
    "error_mensaje" text,
    "id_cliente_wms" INTEGER,
    "fecha_carga" TEXT NOT NULL DEFAULT (datetime('now')),
    "fecha_procesado" TEXT,
    "updated_at" TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS "idx_int_cli_tenant" ON "intercambio_clientes" ("tenant_codigo");
CREATE INDEX IF NOT EXISTS "idx_int_cli_estado" ON "intercambio_clientes" ("estado");
CREATE INDEX IF NOT EXISTS "idx_int_cli_codigo" ON "intercambio_clientes" ("codigo");

-- --- intercambio_pedidos ---;
CREATE TABLE IF NOT EXISTS "intercambio_pedidos" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "tenant_codigo" TEXT NOT NULL,
    "nro_pedido" TEXT NOT NULL,
    "cliente_codigo" TEXT NOT NULL,
    "clase_nombre" TEXT,
    "fecha_pedido" TEXT NOT NULL,
    "ruta_nombre" TEXT,
    "transporte_codigo" TEXT,
    "direccion_entrega" TEXT,
    "observaciones" text,
    "estado_pedido" TEXT NOT NULL DEFAULT 'Pendiente',
    "items_json" text,
    "accion" TEXT NOT NULL DEFAULT 'alta',
    "estado" TEXT NOT NULL DEFAULT 'pendiente',
    "intentos" INTEGER NOT NULL DEFAULT 0,
    "error_mensaje" text,
    "id_pedido_wms" INTEGER,
    "fecha_carga" TEXT NOT NULL DEFAULT (datetime('now')),
    "fecha_procesado" TEXT,
    "updated_at" TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS "idx_int_ped_tenant" ON "intercambio_pedidos" ("tenant_codigo");
CREATE INDEX IF NOT EXISTS "idx_int_ped_estado" ON "intercambio_pedidos" ("estado");
CREATE INDEX IF NOT EXISTS "idx_int_ped_nro" ON "intercambio_pedidos" ("nro_pedido");

-- --- intercambio_log ---;
CREATE TABLE IF NOT EXISTS "intercambio_log" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "modulo" TEXT NOT NULL,
    "resultado" TEXT NOT NULL DEFAULT 'ok',
    "registros_procesados" INTEGER NOT NULL DEFAULT 0,
    "registros_error" INTEGER NOT NULL DEFAULT 0,
    "detalle" text,
    "usuario" TEXT,
    "fecha" TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS "idx_int_log_modulo" ON "intercambio_log" ("modulo");
CREATE INDEX IF NOT EXISTS "idx_int_log_fecha" ON "intercambio_log" ("fecha");

-- --- Datos iniciales ---;


-- === FIN DEL SCRIPT ===;
-- Schema generado para engine: sqlite;
-- Usuarios por defecto:;
--   SuperAdmin: admin / Admin@2024!;
--   Operador:   operador / Admin@2024!;
