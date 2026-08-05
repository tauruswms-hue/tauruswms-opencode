-- PostgreSQL schema for taurus_intercambio;

-- TAURUS WMS - Schema para taurus_intercambio (interfaces con sistemas externos);
-- Engine: postgresql;
-- Generado por modules/schema_generator.py;

DROP DATABASE IF EXISTS taurus_intercambio;
CREATE DATABASE taurus_intercambio;
\connect taurus_intercambio;


-- --- intercambio_materiales ---;
CREATE TABLE "intercambio_materiales" (
    "id" SERIAL,
    "tenant_codigo" VARCHAR(20) NOT NULL,
    "codigo" VARCHAR(100) NOT NULL,
    "codigo_barras" VARCHAR(100),
    "nombre" VARCHAR(255) NOT NULL,
    "descripcion" text,
    "categoria_codigo" VARCHAR(50),
    "stock_minimo" decimal(12,3) DEFAULT 0,
    "stock_maximo" decimal(12,3) DEFAULT 0,
    "unidad_medida_codigo" VARCHAR(50),
    "trazabilidad" VARCHAR(50) NOT NULL DEFAULT 'ninguna' CHECK ("trazabilidad" IN ('ninguna','lote','serie')),
    "metodo_picking" VARCHAR(20) NOT NULL DEFAULT 'libre',
    "peso_bruto" decimal(10,3),
    "peso_neto" decimal(10,3),
    "costo_promedio" decimal(12,4) DEFAULT 0,
    "ultimo_costo" decimal(12,4) DEFAULT 0,
    "activo" BOOLEAN NOT NULL DEFAULT TRUE,
    "accion" VARCHAR(20) NOT NULL DEFAULT 'alta',
    "estado" VARCHAR(50) NOT NULL DEFAULT 'pendiente' CHECK ("estado" IN ('pendiente','procesado','error')),
    "intentos" INTEGER NOT NULL DEFAULT 0,
    "error_mensaje" text,
    "id_material_wms" INTEGER,
    "fecha_carga" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "fecha_procesado" datetime,
    "updated_at" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX "idx_int_mat_tenant" ON "intercambio_materiales" ("tenant_codigo");
CREATE INDEX "idx_int_mat_estado" ON "intercambio_materiales" ("estado");
CREATE INDEX "idx_int_mat_codigo" ON "intercambio_materiales" ("codigo");

-- --- intercambio_rutas ---;
CREATE TABLE "intercambio_rutas" (
    "id" SERIAL,
    "tenant_codigo" VARCHAR(20) NOT NULL,
    "nombre_ruta" VARCHAR(100) NOT NULL,
    "descripcion" text,
    "accion" VARCHAR(20) NOT NULL DEFAULT 'alta',
    "estado" VARCHAR(50) NOT NULL DEFAULT 'pendiente' CHECK ("estado" IN ('pendiente','procesado','error')),
    "intentos" INTEGER NOT NULL DEFAULT 0,
    "error_mensaje" text,
    "id_ruta_wms" INTEGER,
    "fecha_carga" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "fecha_procesado" datetime,
    "updated_at" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX "idx_int_rut_tenant" ON "intercambio_rutas" ("tenant_codigo");
CREATE INDEX "idx_int_rut_estado" ON "intercambio_rutas" ("estado");
CREATE INDEX "idx_int_rut_nombre" ON "intercambio_rutas" ("nombre_ruta");

-- --- intercambio_transportes ---;
CREATE TABLE "intercambio_transportes" (
    "id" SERIAL,
    "tenant_codigo" VARCHAR(20) NOT NULL,
    "codigo" VARCHAR(100) NOT NULL,
    "razonsocial" VARCHAR(200) NOT NULL,
    "cuit" VARCHAR(50),
    "telefono" VARCHAR(50),
    "email" VARCHAR(100),
    "muelle_codigo" VARCHAR(50),
    "activo" BOOLEAN NOT NULL DEFAULT TRUE,
    "accion" VARCHAR(20) NOT NULL DEFAULT 'alta',
    "estado" VARCHAR(50) NOT NULL DEFAULT 'pendiente' CHECK ("estado" IN ('pendiente','procesado','error')),
    "intentos" INTEGER NOT NULL DEFAULT 0,
    "error_mensaje" text,
    "id_transporte_wms" INTEGER,
    "fecha_carga" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "fecha_procesado" datetime,
    "updated_at" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX "idx_int_tra_tenant" ON "intercambio_transportes" ("tenant_codigo");
CREATE INDEX "idx_int_tra_estado" ON "intercambio_transportes" ("estado");
CREATE INDEX "idx_int_tra_codigo" ON "intercambio_transportes" ("codigo");

-- --- intercambio_transporte_rutas ---;
CREATE TABLE "intercambio_transporte_rutas" (
    "id" SERIAL,
    "tenant_codigo" VARCHAR(20) NOT NULL,
    "transporte_codigo" VARCHAR(100) NOT NULL,
    "ruta_nombre" VARCHAR(100) NOT NULL,
    "observaciones" text,
    "accion" VARCHAR(20) NOT NULL DEFAULT 'alta',
    "estado" VARCHAR(50) NOT NULL DEFAULT 'pendiente' CHECK ("estado" IN ('pendiente','procesado','error')),
    "intentos" INTEGER NOT NULL DEFAULT 0,
    "error_mensaje" text,
    "fecha_carga" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "fecha_procesado" datetime,
    "updated_at" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX "idx_int_trr_tenant" ON "intercambio_transporte_rutas" ("tenant_codigo");
CREATE INDEX "idx_int_trr_estado" ON "intercambio_transporte_rutas" ("estado");
CREATE INDEX "idx_int_trr_transporte" ON "intercambio_transporte_rutas" ("transporte_codigo");
CREATE INDEX "idx_int_trr_ruta" ON "intercambio_transporte_rutas" ("ruta_nombre");

-- --- intercambio_clientes ---;
CREATE TABLE "intercambio_clientes" (
    "id" SERIAL,
    "tenant_codigo" VARCHAR(20) NOT NULL,
    "codigo" VARCHAR(100) NOT NULL,
    "razonsocial" VARCHAR(200) NOT NULL,
    "cuit" VARCHAR(50),
    "direccion" VARCHAR(255),
    "localidad" VARCHAR(100),
    "provincia" VARCHAR(100),
    "telefono" VARCHAR(50),
    "email" VARCHAR(100),
    "contacto_nombre" VARCHAR(100),
    "ruta_nombre" VARCHAR(100),
    "transporte_codigo" VARCHAR(100),
    "activo" BOOLEAN NOT NULL DEFAULT TRUE,
    "accion" VARCHAR(20) NOT NULL DEFAULT 'alta',
    "estado" VARCHAR(50) NOT NULL DEFAULT 'pendiente' CHECK ("estado" IN ('pendiente','procesado','error')),
    "intentos" INTEGER NOT NULL DEFAULT 0,
    "error_mensaje" text,
    "id_cliente_wms" INTEGER,
    "fecha_carga" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "fecha_procesado" datetime,
    "updated_at" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX "idx_int_cli_tenant" ON "intercambio_clientes" ("tenant_codigo");
CREATE INDEX "idx_int_cli_estado" ON "intercambio_clientes" ("estado");
CREATE INDEX "idx_int_cli_codigo" ON "intercambio_clientes" ("codigo");

-- --- intercambio_pedidos ---;
CREATE TABLE "intercambio_pedidos" (
    "id" SERIAL,
    "tenant_codigo" VARCHAR(20) NOT NULL,
    "nro_pedido" VARCHAR(20) NOT NULL,
    "cliente_codigo" VARCHAR(100) NOT NULL,
    "clase_nombre" VARCHAR(100),
    "fecha_pedido" date NOT NULL,
    "ruta_nombre" VARCHAR(100),
    "transporte_codigo" VARCHAR(100),
    "direccion_entrega" VARCHAR(255),
    "observaciones" text,
    "estado_pedido" VARCHAR(50) NOT NULL DEFAULT 'Pendiente',
    "items_json" text,
    "accion" VARCHAR(20) NOT NULL DEFAULT 'alta',
    "estado" VARCHAR(50) NOT NULL DEFAULT 'pendiente' CHECK ("estado" IN ('pendiente','procesado','error')),
    "intentos" INTEGER NOT NULL DEFAULT 0,
    "error_mensaje" text,
    "id_pedido_wms" INTEGER,
    "fecha_carga" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "fecha_procesado" datetime,
    "updated_at" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX "idx_int_ped_tenant" ON "intercambio_pedidos" ("tenant_codigo");
CREATE INDEX "idx_int_ped_estado" ON "intercambio_pedidos" ("estado");
CREATE INDEX "idx_int_ped_nro" ON "intercambio_pedidos" ("nro_pedido");

-- --- intercambio_log ---;
CREATE TABLE "intercambio_log" (
    "id" SERIAL,
    "modulo" VARCHAR(50) NOT NULL,
    "resultado" VARCHAR(20) NOT NULL DEFAULT 'ok',
    "registros_procesados" INTEGER NOT NULL DEFAULT 0,
    "registros_error" INTEGER NOT NULL DEFAULT 0,
    "detalle" text,
    "usuario" VARCHAR(100),
    "fecha" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX "idx_int_log_modulo" ON "intercambio_log" ("modulo");
CREATE INDEX "idx_int_log_fecha" ON "intercambio_log" ("fecha");

-- --- Datos iniciales ---;


-- === FIN DEL SCRIPT ===;
-- Schema generado para engine: postgresql;
-- Usuarios por defecto:;
--   SuperAdmin: admin / Admin@2024!;
--   Operador:   operador / Admin@2024!;
