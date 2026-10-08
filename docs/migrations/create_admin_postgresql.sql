-- PostgreSQL schema for taurus_admin;

-- TAURUS WMS - Schema para taurus_admin;
-- Engine: postgresql;
-- Generado por modules/schema_generator.py;

DROP DATABASE IF EXISTS taurus_admin;
CREATE DATABASE taurus_admin;
\connect taurus_admin;


-- --- admin_usuarios ---;
CREATE TABLE "admin_usuarios" (
    "id" SERIAL,
    "username" VARCHAR(50) NOT NULL UNIQUE,
    "password_hash" VARCHAR(255) NOT NULL,
    "nombre" VARCHAR(100) NOT NULL,
    "email" VARCHAR(100),
    "rol" VARCHAR(50) DEFAULT 'ADMIN' CHECK ("rol" IN ('SUPERADMIN','ADMIN')),
    "activo" BOOLEAN DEFAULT TRUE,
    "ultimo_acceso" datetime,
    "created_at" datetime DEFAULT CURRENT_TIMESTAMP,
    "updated_at" datetime DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX "idx_username" ON "admin_usuarios" ("username");
CREATE INDEX "idx_rol" ON "admin_usuarios" ("rol");

-- --- roles ---;
CREATE TABLE "roles" (
    "id" SERIAL,
    "nombre" VARCHAR(50) NOT NULL,
    "descripcion" VARCHAR(255),
    "activo" BOOLEAN DEFAULT TRUE,
    "created_at" datetime DEFAULT CURRENT_TIMESTAMP,
    "updated_at" datetime DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX "uk_rol_nombre" ON "roles" ("nombre");
CREATE INDEX "idx_roles_activo" ON "roles" ("activo");

-- --- tenants ---;
CREATE TABLE "tenants" (
    "id" SERIAL,
    "codigo" VARCHAR(20) NOT NULL UNIQUE,
    "nombre" VARCHAR(100) NOT NULL,
    "razon_social" VARCHAR(200),
    "cuit" VARCHAR(50),
    "direccion" VARCHAR(255),
    "telefono" VARCHAR(50),
    "email" VARCHAR(100),
    "activo" BOOLEAN DEFAULT TRUE,
    "created_at" datetime DEFAULT CURRENT_TIMESTAMP,
    "updated_at" datetime DEFAULT CURRENT_TIMESTAMP,
    "nombredelalmacen" VARCHAR(200),
    "metodosdepicking" text,
    "metodo_picking_default" VARCHAR(20) NOT NULL DEFAULT 'libre',
    "bajostock" decimal(12,3) DEFAULT 0,
    "dias_filtro_fechas" INTEGER DEFAULT 30,
    "contexto" text,
    "prompt" text,
    "proveedor_api_ia" text,
    "modelo_api_ia" text,
    "api_key" text,
    "api_token" VARCHAR(255)
);
CREATE INDEX "idx_codigo" ON "tenants" ("codigo");
CREATE INDEX "idx_activo" ON "tenants" ("activo");

-- --- usuarios ---;
CREATE TABLE "usuarios" (
    "id" SERIAL,
    "username" VARCHAR(50) NOT NULL UNIQUE,
    "password_hash" VARCHAR(255) NOT NULL,
    "nombre" VARCHAR(100) NOT NULL,
    "email" VARCHAR(100),
    "rol" VARCHAR(50) DEFAULT 'OPERADOR',
    "tenant_id" INTEGER NOT NULL,
    "activo" BOOLEAN DEFAULT TRUE,
    "ultimo_acceso" datetime,
    "created_at" datetime DEFAULT CURRENT_TIMESTAMP,
    "updated_at" datetime DEFAULT CURRENT_TIMESTAMP,
    "sidebar_preferences" text,
    CONSTRAINT "fk_usuarios_tenant_id" FOREIGN KEY ("tenant_id") REFERENCES "tenants" ("id") ON DELETE CASCADE
);
CREATE INDEX "idx_tenant" ON "usuarios" ("tenant_id");
CREATE INDEX "idx_rol" ON "usuarios" ("rol");

-- --- configuracion ---;
CREATE TABLE "configuracion" (
    "id" SERIAL,
    "clave" VARCHAR(100) NOT NULL UNIQUE,
    "valor" text,
    "descripcion" VARCHAR(255),
    "updated_at" datetime DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX "idx_clave" ON "configuracion" ("clave");

-- --- audit_logs ---;
CREATE TABLE "audit_logs" (
    "id" BIGSERIAL,
    "usuario_id" INTEGER,
    "usuario_nombre" VARCHAR(100),
    "accion" VARCHAR(50) NOT NULL,
    "modulo" VARCHAR(100) NOT NULL,
    "detalle" text,
    "ip_address" VARCHAR(45),
    "user_agent" VARCHAR(255),
    "created_at" datetime DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX "idx_usuario" ON "audit_logs" ("usuario_id");
CREATE INDEX "idx_accion" ON "audit_logs" ("accion");
CREATE INDEX "idx_modulo" ON "audit_logs" ("modulo");
CREATE INDEX "idx_fecha" ON "audit_logs" ("created_at");

-- --- roles_rutas ---;
CREATE TABLE "roles_rutas" (
    "rol" VARCHAR(50) NOT NULL,
    "ruta" VARCHAR(255) NOT NULL,
    PRIMARY KEY ("rol", "ruta")
);

-- --- Datos iniciales ---;

-- Roles por defecto del sistema;
INSERT INTO "roles" ("nombre", "descripcion", "activo") VALUES ('ADMIN', 'Acceso total a todas las rutas', TRUE) ON CONFLICT DO NOTHING;
INSERT INTO "roles" ("nombre", "descripcion", "activo") VALUES ('OPERADOR', 'Rutas operativas del WMS', TRUE) ON CONFLICT DO NOTHING;
INSERT INTO "roles" ("nombre", "descripcion", "activo") VALUES ('CONSULTA', 'Acceso de solo lectura', TRUE) ON CONFLICT DO NOTHING;

INSERT INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('app_version', '1.0.0', 'Version actual de la aplicacion') ON CONFLICT DO NOTHING;
INSERT INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('app_name', 'Taurus WMS', 'Nombre de la aplicacion') ON CONFLICT DO NOTHING;
INSERT INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('mantenimiento', 'false', 'Modo mantenimiento (true/false)') ON CONFLICT DO NOTHING;

-- Permisos de rutas por rol;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('ADMIN', '*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/materiales') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/materiales/guardar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/materiales/importar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/materiales/exportar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/materiales/plantilla/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/materiales/eliminar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/materiales/imagen/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/materiales/distribucion/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/ubicaciones') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/ubicaciones/guardar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/ubicaciones/eliminar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/ubicaciones/importar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/ubicaciones/exportar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/ubicaciones/plantilla/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/tipoubicacion') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/tipoubicacion/guardar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/tipoubicacion/eliminar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/tipoubicacion/importar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/tipoubicacion/exportar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/tipoubicacion/plantilla/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/proveedores') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/proveedores/guardar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/proveedores/eliminar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/proveedores/importar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/proveedores/exportar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/proveedores/plantilla/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/clientes') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/clientes/guardar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/clientes/eliminar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/clientes/importar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/clientes/exportar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/clientes/plantilla/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/categorias') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/categorias/guardar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/categorias/eliminar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/categorias/importar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/categorias/exportar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/categorias/plantilla/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/unidades') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/unidades/guardar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/unidades/eliminar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/unidades/importar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/unidades/exportar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/unidades/plantilla/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/transportes') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/transportes/guardar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/transportes/eliminar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/transportes/importar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/transportes/exportar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/transportes/plantilla/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/rutas') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/rutas/guardar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/rutas/eliminar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/rutas/importar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/rutas/exportar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/rutas/plantilla/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/nuevo') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/ver/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/editar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/guardar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/eliminar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/importar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/plantilla/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/picking_json') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/preparar_masivo') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/resumen_preparar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/cambiar_ruta_transporte') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/filtros/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/contenedor_stock') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/nueva') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/guardar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/ver/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/buscar_*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/guardar_item') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/eliminar_item/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/cerrar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/eliminar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/confirmar_stock/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/anular/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/importar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/plantilla/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/omc') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/omc/nueva') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/omc/guardar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/omc/ver/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/omc/confirmar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/omc/modificar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/omc/anular/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/omc/buscar_*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/omc/tipos_ubicacion') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/despacho') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/despacho/despachar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/despacho/despachar_masivo') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/stockcontable') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/stockcontable/editar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/stockcontable/importar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/stockcontable/exportar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/stockcontable/plantilla/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/inventario') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/inventario/crear') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/inventario/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/parametros') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/actualizar_parametros') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/movil') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/movil/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/sidebar-preferences') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/materiales') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/materiales/imagen/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/materiales/distribucion/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/ubicaciones') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/tipoubicacion') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/proveedores') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/clientes') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/categorias') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/unidades') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/transportes') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/rutas') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/zonas') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/clases-pedido') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/pedidos') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/pedidos/ver/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/pedidos/filtros/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/pedidos/buscar_contenedores') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/pedidos/contenedor_stock') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/recepciones') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/recepciones/ver/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/recepciones/buscar_*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/omc') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/omc/ver/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/omc/buscar_*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/despacho') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/stockcontable') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/stockcontable/exportar/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/stockcontable/plantilla/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/inventario') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/inventario/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/parametros') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/reportes') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/reportes/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/sidebar-preferences') ON CONFLICT DO NOTHING;


-- === FIN DEL SCRIPT ===;
-- Schema generado para engine: postgresql;
