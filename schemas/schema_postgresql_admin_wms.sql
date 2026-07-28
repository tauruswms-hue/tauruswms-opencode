-- PostgreSQL schema for taurus_admin;

-- TAURUS WMS - Schema para taurus_admin;
-- Engine: postgresql;
-- Generado por modules/schema_generator.py;

DROP DATABASE IF EXISTS taurus_admin;
CREATE DATABASE taurus_admin;
\connect taurus_admin;


-- --- admin_usuarios ---;
CREATE TABLE "admin_usuarios" (
    "id" INTEGER,
    "username" VARCHAR(50) NOT NULL,
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

-- --- tenants ---;
CREATE TABLE "tenants" (
    "id" INTEGER,
    "codigo" VARCHAR(20) NOT NULL,
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
    "bajostock" decimal(12,3) DEFAULT 0,
    "dias_filtro_fechas" INTEGER DEFAULT 30,
    "contexto" text,
    "prompt" text,
    "proveedor_api_ia" text,
    "modelo_api_ia" text,
    "api_key" text
);
CREATE INDEX "idx_codigo" ON "tenants" ("codigo");
CREATE INDEX "idx_activo" ON "tenants" ("activo");

-- --- usuarios ---;
CREATE TABLE "usuarios" (
    "id" INTEGER,
    "username" VARCHAR(50) NOT NULL,
    "password_hash" VARCHAR(255) NOT NULL,
    "nombre" VARCHAR(100) NOT NULL,
    "email" VARCHAR(100),
    "rol" VARCHAR(50) DEFAULT 'OPERADOR' CHECK ("rol" IN ('ADMIN','OPERADOR','CONSULTA')),
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
    "id" INTEGER,
    "clave" VARCHAR(100) NOT NULL,
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

INSERT INTO "tenants" ("id", "codigo", "nombre", "razon_social", "activo", "nombredelalmacen", "metodosdepicking", "bajostock", "dias_filtro_fechas") VALUES (1, 'DEFAULT', 'Empresa Principal', 'Empresa Principal S.A.', TRUE, 'Almacen Principal', '"fifo"', 0, 30) ON CONFLICT DO NOTHING;

-- SuperAdmin password: Admin@2024!;
INSERT INTO "admin_usuarios" ("username", "password_hash", "nombre", "email", "rol") VALUES ('admin', 'scrypt:32768:8:1$WQ6PhKOf81VV3FcH$ed1ca47fd1fd381583f0289acf9e839521b5e74a07adfc034382ea5342d608e393b7143fec95b3aef262f1946f95696e3e8acbfc867c91769d63142d4e4a5db2', 'Administrador', 'admin@taurus.local', 'SUPERADMIN') ON CONFLICT DO NOTHING;

-- Operador password: Admin@2024!;
INSERT INTO "usuarios" ("username", "password_hash", "nombre", "email", "rol", "tenant_id", "activo") VALUES ('operador', 'scrypt:32768:8:1$WQ6PhKOf81VV3FcH$ed1ca47fd1fd381583f0289acf9e839521b5e74a07adfc034382ea5342d608e393b7143fec95b3aef262f1946f95696e3e8acbfc867c91769d63142d4e4a5db2', 'Operador General', 'operador@taurus.local', 'OPERADOR', 1, TRUE) ON CONFLICT DO NOTHING;

INSERT INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('app_version', '1.0.0', 'Version actual de la aplicacion') ON CONFLICT DO NOTHING;
INSERT INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('app_name', 'Taurus WMS', 'Nombre de la aplicacion') ON CONFLICT DO NOTHING;
INSERT INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('mantenimiento', 'false', 'Modo mantenimiento (true/false)') ON CONFLICT DO NOTHING;
INSERT INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('DB_HOST', 'localhost', 'Host del servidor de base de datos') ON CONFLICT DO NOTHING;
INSERT INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('DB_PORT', '3306', 'Puerto del servidor MySQL') ON CONFLICT DO NOTHING;
INSERT INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('DB_NAME', 'taurus_wms', 'Nombre de la base de datos principal') ON CONFLICT DO NOTHING;
INSERT INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('DB_USER', 'taurus', 'Usuario de la base de datos') ON CONFLICT DO NOTHING;
INSERT INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('DB_PASSWORD', 'Taurus_2001', 'Contrasena de la base de datos') ON CONFLICT DO NOTHING;
INSERT INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('DB_CHAR_SET', 'utf8mb4', 'Charset de la base de datos') ON CONFLICT DO NOTHING;
INSERT INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('DB_ENGINE', 'mysql', 'Motor de BD: mysql, postgresql, sqlite') ON CONFLICT DO NOTHING;

-- Permisos de rutas por rol;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('ADMIN', '*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/materiales') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/materiales/guardar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/materiales/eliminar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/materiales/importar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/materiales/exportar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/materiales/plantilla') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/ubicaciones') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/ubicaciones/guardar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/ubicaciones/importar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/ubicaciones/exportar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/ubicaciones/plantilla') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/tipoubicacion') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/tipoubicacion/guardar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/tipoubicacion/eliminar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/tipoubicacion/importar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/tipoubicacion/exportar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/tipoubicacion/plantilla') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/proveedores') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/proveedores/guardar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/proveedores/eliminar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/proveedores/importar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/proveedores/exportar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/proveedores/plantilla') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/clientes') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/clientes/guardar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/clientes/importar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/clientes/exportar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/clientes/plantilla') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/categorias') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/categorias/guardar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/categorias/eliminar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/unidades') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/unidades/guardar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/unidades/eliminar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/unidades/importar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/unidades/exportar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/unidades/plantilla') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/transportes') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/transportes/guardar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/transportes/importar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/transportes/exportar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/transportes/plantilla') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/rutas') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/rutas/guardar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/rutas/eliminar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/rutas/importar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/rutas/exportar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/rutas/plantilla') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/nuevo') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/editar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/guardar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/eliminar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/importar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/plantilla') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/picking_json') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/nueva') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/guardar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/ver') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/cerrar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/eliminar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/importar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/plantilla') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/guardar_item') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/eliminar_item') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/confirmar_stock') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/anular') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/omc') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/omc/nueva') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/omc/guardar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/omc/ver') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/despacho') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/despacho/despachar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/despacho/despachar_masivo') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/stockcontable') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/stockcontable/editar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/stockcontable/importar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/stockcontable/exportar') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/stockcontable/plantilla') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/inventario') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/inventario/crear') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/inventario/*') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/parametros') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/actualizar_parametros') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/materiales') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/ubicaciones') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/tipoubicacion') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/proveedores') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/clientes') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/categorias') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/unidades') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/transportes') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/rutas') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/pedidos') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/recepciones') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/omc') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/despacho') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/stockcontable') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/inventario') ON CONFLICT DO NOTHING;
INSERT INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/parametros') ON CONFLICT DO NOTHING;


-- PostgreSQL schema for taurus_wms;

-- TAURUS WMS - Schema para taurus_wms (datos operativos);
-- Engine: postgresql;
-- Generado por modules/schema_generator.py;

DROP DATABASE IF EXISTS taurus_wms;
CREATE DATABASE taurus_wms;
\connect taurus_wms;


-- --- zonas ---;
CREATE TABLE "zonas" (
    "id" INTEGER,
    "codigo" VARCHAR(20) NOT NULL,
    "nombre" VARCHAR(100) NOT NULL,
    "descripcion" text,
    "activo" BOOLEAN NOT NULL DEFAULT TRUE,
    "tenant_id" INTEGER,
    "created_at" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX "uk_zona_codigo" ON "zonas" ("codigo");
CREATE INDEX "idx_zona_activo" ON "zonas" ("activo");
CREATE INDEX "idx_zonas_tenant" ON "zonas" ("tenant_id");

-- --- tipoubicacion ---;
CREATE TABLE "tipoubicacion" (
    "id" INTEGER,
    "descripcion" VARCHAR(100) NOT NULL,
    "operacion" char(1),
    "soporte_picking" BOOLEAN NOT NULL DEFAULT FALSE,
    "tenant_id" INTEGER
);
CREATE INDEX "idx_tipoubicacion_tenant" ON "tipoubicacion" ("tenant_id");

-- --- categorias ---;
CREATE TABLE "categorias" (
    "id_categoria" INTEGER,
    "codigo" VARCHAR(50),
    "nombre" VARCHAR(100) NOT NULL,
    "descripcion" text,
    "activo" BOOLEAN NOT NULL DEFAULT TRUE,
    "tenant_id" INTEGER,
    "created_at" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX "idx_categorias_tenant" ON "categorias" ("tenant_id");

-- --- proveedores ---;
CREATE TABLE "proveedores" (
    "id" INTEGER,
    "codigo" VARCHAR(50),
    "razonsocial" VARCHAR(200) NOT NULL,
    "cuit" VARCHAR(50),
    "direccion" VARCHAR(255),
    "telefono" VARCHAR(50),
    "email" VARCHAR(100),
    "activo" BOOLEAN NOT NULL DEFAULT TRUE,
    "tenant_id" INTEGER,
    "created_at" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX "idx_proveedores_tenant" ON "proveedores" ("tenant_id");

-- --- rutas ---;
CREATE TABLE "rutas" (
    "id_ruta" INTEGER,
    "nombre_ruta" VARCHAR(100) NOT NULL,
    "descripcion" text,
    "tenant_id" INTEGER
);
CREATE INDEX "idx_rutas_tenant" ON "rutas" ("tenant_id");

-- --- unidades_medida ---;
CREATE TABLE "unidades_medida" (
    "id_unidad" INTEGER,
    "codigo" VARCHAR(50) NOT NULL,
    "nombre" VARCHAR(100) NOT NULL,
    "simbolo" VARCHAR(20),
    "tipo_magnitud" VARCHAR(50) DEFAULT 'CANTIDAD',
    "conversion_a_base" decimal(12,4) DEFAULT 1.0,
    "unidad_base_referencia" VARCHAR(10) DEFAULT 'U',
    "decimales_permitidos" INTEGER DEFAULT 0,
    "activo" BOOLEAN NOT NULL DEFAULT TRUE,
    "tenant_id" INTEGER
);
CREATE INDEX "idx_unidades_tenant" ON "unidades_medida" ("tenant_id");

-- --- ubicaciones ---;
CREATE TABLE "ubicaciones" (
    "id" INTEGER,
    "codigo" VARCHAR(50) NOT NULL,
    "nombre" VARCHAR(100),
    "descipcion" VARCHAR(200),
    "tipoubicacion" INTEGER,
    "zona" VARCHAR(50),
    "id_zona" INTEGER,
    "pasillo" VARCHAR(20),
    "estante" VARCHAR(20),
    "nivel" VARCHAR(20),
    "posicion" VARCHAR(20),
    "coordenadaA" VARCHAR(20),
    "coordenadaB" VARCHAR(20),
    "coordenadaC" VARCHAR(20),
    "coordenadaD" VARCHAR(20),
    "capacidad_maxima" INTEGER NOT NULL DEFAULT 0,
    "ocupado" INTEGER NOT NULL DEFAULT 0,
    "disponible_entrada" BOOLEAN NOT NULL DEFAULT TRUE,
    "disponible_salida" BOOLEAN NOT NULL DEFAULT TRUE,
    "orden_picking" INTEGER NOT NULL DEFAULT 0,
    "activo" BOOLEAN NOT NULL DEFAULT TRUE,
    "tenant_id" INTEGER,
    "created_at" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "fk_ubicaciones_id_zona" FOREIGN KEY ("id_zona") REFERENCES "zonas" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);
CREATE INDEX "idx_ubicaciones_tenant" ON "ubicaciones" ("tenant_id");
CREATE INDEX "idx_ubi_zona" ON "ubicaciones" ("id_zona");
CREATE INDEX "idx_ubi_tipo" ON "ubicaciones" ("tipoubicacion");

-- --- transportes ---;
CREATE TABLE "transportes" (
    "id_transporte" INTEGER,
    "codigo" VARCHAR(100),
    "razonsocial" VARCHAR(200) NOT NULL,
    "cuit" VARCHAR(50),
    "telefono" VARCHAR(50),
    "email" VARCHAR(100),
    "activo" BOOLEAN NOT NULL DEFAULT TRUE,
    "id_muelle_salida" INTEGER,
    "tenant_id" INTEGER,
    CONSTRAINT "fk_transportes_id_muelle_salida" FOREIGN KEY ("id_muelle_salida") REFERENCES "ubicaciones" ("id")
);
CREATE INDEX "idx_transportes_tenant" ON "transportes" ("tenant_id");

-- --- transporte_rutas ---;
CREATE TABLE "transporte_rutas" (
    "id_transporte" INTEGER NOT NULL,
    "id_ruta" INTEGER NOT NULL,
    "observaciones" text,
    PRIMARY KEY ("id_transporte", "id_ruta"),
    CONSTRAINT "fk_transporte_rutas_id_transporte" FOREIGN KEY ("id_transporte") REFERENCES "transportes" ("id_transporte") ON DELETE CASCADE,
    CONSTRAINT "fk_transporte_rutas_id_ruta" FOREIGN KEY ("id_ruta") REFERENCES "rutas" ("id_ruta") ON DELETE CASCADE
);

-- --- clientes ---;
CREATE TABLE "clientes" (
    "id_cliente" INTEGER,
    "codigo" VARCHAR(100),
    "razonsocial" VARCHAR(200) NOT NULL,
    "cuit" VARCHAR(50),
    "direccion" VARCHAR(255),
    "localidad" VARCHAR(100),
    "provincia" VARCHAR(100),
    "telefono" VARCHAR(50),
    "email" VARCHAR(100),
    "contacto_nombre" VARCHAR(100),
    "id_ruta" INTEGER,
    "id_transporte_predeterminado" INTEGER,
    "activo" BOOLEAN NOT NULL DEFAULT TRUE,
    "tenant_id" INTEGER,
    CONSTRAINT "fk_clientes_id_ruta" FOREIGN KEY ("id_ruta") REFERENCES "rutas" ("id_ruta") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "fk_clientes_id_transporte_predeterminado" FOREIGN KEY ("id_transporte_predeterminado") REFERENCES "transportes" ("id_transporte") ON DELETE SET NULL ON UPDATE CASCADE
);
CREATE INDEX "idx_clientes_tenant" ON "clientes" ("tenant_id");

-- --- materiales ---;
CREATE TABLE "materiales" (
    "id" INTEGER,
    "codigo" VARCHAR(100) NOT NULL,
    "codigo_barras" VARCHAR(100),
    "nombre" VARCHAR(255) NOT NULL,
    "descripcion" text,
    "categoria_id" INTEGER,
    "stock_minimo" decimal(12,3) DEFAULT 0,
    "stock_maximo" decimal(12,3) DEFAULT 0,
    "unidad_medida_id" INTEGER,
    "trazabilidad" VARCHAR(50) NOT NULL DEFAULT 'ninguna' CHECK ("trazabilidad" IN ('ninguna','lote','serie')),
    "peso_bruto" decimal(10,3),
    "peso_neto" decimal(10,3),
    "costo_promedio" decimal(12,4) DEFAULT 0,
    "ultimo_costo" decimal(12,4) DEFAULT 0,
    "activo" BOOLEAN NOT NULL DEFAULT TRUE,
    "tenant_id" INTEGER,
    "created_at" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "fk_materiales_categoria_id" FOREIGN KEY ("categoria_id") REFERENCES "categorias" ("id_categoria") ON DELETE SET NULL ON UPDATE CASCADE
);
CREATE INDEX "idx_materiales_tenant" ON "materiales" ("tenant_id");
CREATE INDEX "idx_mat_categoria" ON "materiales" ("categoria_id");
CREATE INDEX "idx_mat_codigo_barras" ON "materiales" ("codigo_barras");

-- --- material_proveedor ---;
CREATE TABLE "material_proveedor" (
    "id_material" INTEGER NOT NULL,
    "id_proveedor" INTEGER NOT NULL,
    "codigo_referencia_prov" VARCHAR(100),
    "es_habitual" BOOLEAN NOT NULL DEFAULT FALSE,
    "tenant_id" INTEGER,
    PRIMARY KEY ("id_material", "id_proveedor"),
    CONSTRAINT "fk_material_proveedor_id_material" FOREIGN KEY ("id_material") REFERENCES "materiales" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "fk_material_proveedor_id_proveedor" FOREIGN KEY ("id_proveedor") REFERENCES "proveedores" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);
CREATE INDEX "idx_matprov_tenant" ON "material_proveedor" ("tenant_id");

-- --- material_presentaciones ---;
CREATE TABLE "material_presentaciones" (
    "id" INTEGER,
    "id_material" INTEGER NOT NULL,
    "nombre" VARCHAR(100) NOT NULL,
    "codigo_barras" VARCHAR(20),
    "cantidad_unidades" decimal(10,3) NOT NULL DEFAULT 1.0,
    "peso_bruto" decimal(10,3),
    "peso_neto" decimal(10,3),
    "activo" BOOLEAN NOT NULL DEFAULT TRUE,
    "tenant_id" INTEGER,
    CONSTRAINT "fk_material_presentaciones_id_material" FOREIGN KEY ("id_material") REFERENCES "materiales" ("id") ON DELETE CASCADE
);
CREATE UNIQUE INDEX "uq_pres_barcode" ON "material_presentaciones" ("codigo_barras");
CREATE INDEX "idx_matpres_tenant" ON "material_presentaciones" ("tenant_id");

-- --- stockcontable ---;
CREATE TABLE "stockcontable" (
    "ID" INTEGER,
    "Ubicacion" INTEGER NOT NULL,
    "Material" INTEGER NOT NULL,
    "Lote" VARCHAR(100) NOT NULL DEFAULT 'UNICO',
    "TipoStock" VARCHAR(50) NOT NULL DEFAULT 'Libre Venta' CHECK ("TipoStock" IN ('Libre Venta','Calidad','Bloqueado','Mal Estado')),
    "UltimaEntrada" datetime,
    "UltimaSalida" datetime,
    "UltimoMovimiento" datetime,
    "UsuarioUltimoMov" VARCHAR(100),
    "FechaVencimiento" date,
    "StockTotal" decimal(15,4) NOT NULL DEFAULT 0,
    "StockDisponible" decimal(15,4) NOT NULL DEFAULT 0,
    "StockEntrando" decimal(15,4) NOT NULL DEFAULT 0,
    "StockSaliendo" decimal(15,4) NOT NULL DEFAULT 0,
    "IDContenedor" VARCHAR(10) NOT NULL,
    "tenant_id" INTEGER,
    "created_at" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "fk_stockcontable_Ubicacion" FOREIGN KEY ("Ubicacion") REFERENCES "ubicaciones" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "fk_stockcontable_Material" FOREIGN KEY ("Material") REFERENCES "materiales" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE UNIQUE INDEX "uq_stock_pos" ON "stockcontable" ("Ubicacion", "Material", "IDContenedor");
CREATE INDEX "idx_material" ON "stockcontable" ("Material");
CREATE INDEX "idx_ubicacion" ON "stockcontable" ("Ubicacion");
CREATE INDEX "idx_lote" ON "stockcontable" ("Lote");
CREATE INDEX "idx_tipo_stock" ON "stockcontable" ("TipoStock");
CREATE INDEX "idx_contenedor" ON "stockcontable" ("IDContenedor");
CREATE INDEX "idx_stockcontable_tenant" ON "stockcontable" ("tenant_id");

-- --- clases_pedido ---;
CREATE TABLE "clases_pedido" (
    "id_clase" INTEGER,
    "nombre" VARCHAR(100) NOT NULL,
    "activo" BOOLEAN NOT NULL DEFAULT TRUE,
    "tenant_id" INTEGER
);
CREATE INDEX "idx_clases_pedido_tenant" ON "clases_pedido" ("tenant_id");

-- --- recepciones_cabecera ---;
CREATE TABLE "recepciones_cabecera" (
    "id_recepcion" INTEGER,
    "numero" VARCHAR(20) NOT NULL,
    "id_proveedor" INTEGER NOT NULL,
    "estado" VARCHAR(50) NOT NULL DEFAULT 'Abierta' CHECK ("estado" IN ('Abierta','Cerrada','Confirmada','Anulada')),
    "id_contenedor" VARCHAR(10) NOT NULL,
    "id_ubicacion_recep" INTEGER NOT NULL,
    "id_ubicacion_destino" INTEGER,
    "observaciones" text,
    "fecha_recepcion" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "fecha_cierre" datetime,
    "usuario_creacion" VARCHAR(100) NOT NULL,
    "usuario_cierre" VARCHAR(100),
    "tenant_id" INTEGER,
    "created_at" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "fk_recepciones_cabecera_id_proveedor" FOREIGN KEY ("id_proveedor") REFERENCES "proveedores" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "fk_recepciones_cabecera_id_ubicacion_recep" FOREIGN KEY ("id_ubicacion_recep") REFERENCES "ubicaciones" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "fk_recepciones_cabecera_id_ubicacion_destino" FOREIGN KEY ("id_ubicacion_destino") REFERENCES "ubicaciones" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE UNIQUE INDEX "uq_recepcion_numero" ON "recepciones_cabecera" ("numero");
CREATE INDEX "idx_rec_proveedor" ON "recepciones_cabecera" ("id_proveedor");
CREATE INDEX "idx_rec_estado" ON "recepciones_cabecera" ("estado");
CREATE INDEX "idx_rec_contenedor" ON "recepciones_cabecera" ("id_contenedor");
CREATE INDEX "idx_rec_ubicrec" ON "recepciones_cabecera" ("id_ubicacion_recep");
CREATE INDEX "idx_rec_ubicdest" ON "recepciones_cabecera" ("id_ubicacion_destino");
CREATE INDEX "idx_rec_fecha" ON "recepciones_cabecera" ("fecha_recepcion");
CREATE INDEX "idx_recepciones_cab_tenant" ON "recepciones_cabecera" ("tenant_id");

-- --- recepciones_detalle ---;
CREATE TABLE "recepciones_detalle" (
    "id_detalle" INTEGER,
    "id_recepcion" INTEGER NOT NULL,
    "id_material" INTEGER NOT NULL,
    "lote" VARCHAR(100) NOT NULL DEFAULT 'UNICO',
    "fecha_vencimiento" date,
    "cantidad_esperada" decimal(15,4) NOT NULL DEFAULT 0,
    "cantidad_recibida" decimal(15,4) NOT NULL DEFAULT 0,
    "tipo_stock" VARCHAR(50) NOT NULL DEFAULT 'Libre Venta' CHECK ("tipo_stock" IN ('Libre Venta','Calidad','Bloqueado','Mal Estado')),
    "observaciones" text,
    "tenant_id" INTEGER,
    "created_at" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "fk_recepciones_detalle_id_recepcion" FOREIGN KEY ("id_recepcion") REFERENCES "recepciones_cabecera" ("id_recepcion") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "fk_recepciones_detalle_id_material" FOREIGN KEY ("id_material") REFERENCES "materiales" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE UNIQUE INDEX "uq_det_recep_mat_lote" ON "recepciones_detalle" ("id_recepcion", "id_material", "lote", "tipo_stock");
CREATE INDEX "idx_det_recepcion" ON "recepciones_detalle" ("id_recepcion");
CREATE INDEX "idx_det_material" ON "recepciones_detalle" ("id_material");
CREATE INDEX "idx_det_lote" ON "recepciones_detalle" ("lote");
CREATE INDEX "idx_recepciones_det_tenant" ON "recepciones_detalle" ("tenant_id");

-- --- pedidos_cabecera ---;
CREATE TABLE "pedidos_cabecera" (
    "id_pedido" INTEGER,
    "nro_pedido" VARCHAR(20) NOT NULL,
    "id_cliente" INTEGER NOT NULL,
    "id_clase" INTEGER,
    "fecha_pedido" date NOT NULL,
    "id_ruta" INTEGER,
    "id_transporte" INTEGER,
    "direccion_entrega" VARCHAR(255),
    "observaciones" text,
    "estado" VARCHAR(50) NOT NULL DEFAULT 'Pendiente',
    "fecha_despacho" datetime,
    "tenant_id" INTEGER,
    "created_at" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "fk_pedidos_cabecera_id_cliente" FOREIGN KEY ("id_cliente") REFERENCES "clientes" ("id_cliente") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "fk_pedidos_cabecera_id_clase" FOREIGN KEY ("id_clase") REFERENCES "clases_pedido" ("id_clase") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "fk_pedidos_cabecera_id_ruta" FOREIGN KEY ("id_ruta") REFERENCES "rutas" ("id_ruta") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "fk_pedidos_cabecera_id_transporte" FOREIGN KEY ("id_transporte") REFERENCES "transportes" ("id_transporte") ON DELETE SET NULL ON UPDATE CASCADE
);
CREATE UNIQUE INDEX "uq_pedido_nro" ON "pedidos_cabecera" ("nro_pedido");
CREATE INDEX "idx_pedido_cliente" ON "pedidos_cabecera" ("id_cliente");
CREATE INDEX "idx_pedido_estado" ON "pedidos_cabecera" ("estado");
CREATE INDEX "idx_pedido_fecha" ON "pedidos_cabecera" ("fecha_pedido");
CREATE INDEX "idx_pedidos_cab_tenant" ON "pedidos_cabecera" ("tenant_id");

-- --- pedidos_detalle ---;
CREATE TABLE "pedidos_detalle" (
    "id_detalle" INTEGER,
    "id_pedido" INTEGER NOT NULL,
    "id_material" INTEGER NOT NULL,
    "cantidad" decimal(15,4) NOT NULL DEFAULT 0,
    "Cantidad_preparada" decimal(10,2) NOT NULL DEFAULT 0,
    "tipo_stock" VARCHAR(20) NOT NULL DEFAULT 'Libre Venta',
    "tenant_id" INTEGER,
    "created_at" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "fk_pedidos_detalle_id_pedido" FOREIGN KEY ("id_pedido") REFERENCES "pedidos_cabecera" ("id_pedido") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "fk_pedidos_detalle_id_material" FOREIGN KEY ("id_material") REFERENCES "materiales" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE INDEX "idx_pd_pedido" ON "pedidos_detalle" ("id_pedido");
CREATE INDEX "idx_pd_material" ON "pedidos_detalle" ("id_material");
CREATE INDEX "idx_pedidos_det_tenant" ON "pedidos_detalle" ("tenant_id");

-- --- omc ---;
CREATE TABLE "omc" (
    "id_omc" INTEGER,
    "numero" VARCHAR(20) NOT NULL,
    "id_contenedor" VARCHAR(20),
    "id_contenedor_destino" VARCHAR(20),
    "id_ubicacion_origen" INTEGER,
    "id_ubicacion_destino" INTEGER NOT NULL,
    "id_recepcion" INTEGER,
    "id_pedido" INTEGER,
    "estado" VARCHAR(50) NOT NULL DEFAULT 'Pendiente' CHECK ("estado" IN ('Pendiente','Confirmada','Anulada')),
    "observaciones" text,
    "fecha_creacion" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "fecha_confirmacion" datetime,
    "fecha_anulacion" datetime,
    "usuario_creacion" VARCHAR(100) NOT NULL,
    "usuario_confirmacion" VARCHAR(100),
    "usuario_anulacion" VARCHAR(100),
    "tenant_id" INTEGER,
    "created_at" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "fk_omc_id_ubicacion_origen" FOREIGN KEY ("id_ubicacion_origen") REFERENCES "ubicaciones" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "fk_omc_id_ubicacion_destino" FOREIGN KEY ("id_ubicacion_destino") REFERENCES "ubicaciones" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "fk_omc_id_recepcion" FOREIGN KEY ("id_recepcion") REFERENCES "recepciones_cabecera" ("id_recepcion") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "fk_omc_id_pedido" FOREIGN KEY ("id_pedido") REFERENCES "pedidos_cabecera" ("id_pedido") ON DELETE SET NULL ON UPDATE CASCADE
);
CREATE UNIQUE INDEX "uq_omc_numero" ON "omc" ("numero");
CREATE INDEX "idx_omc_contenedor" ON "omc" ("id_contenedor");
CREATE INDEX "idx_omc_origen" ON "omc" ("id_ubicacion_origen");
CREATE INDEX "idx_omc_destino" ON "omc" ("id_ubicacion_destino");
CREATE INDEX "idx_omc_estado" ON "omc" ("estado");
CREATE INDEX "idx_omc_recepcion" ON "omc" ("id_recepcion");
CREATE INDEX "idx_omc_pedido" ON "omc" ("id_pedido");
CREATE INDEX "idx_omc_tenant" ON "omc" ("tenant_id");

-- --- omc_contenedores ---;
CREATE TABLE "omc_contenedores" (
    "id" INTEGER,
    "id_omc" INTEGER NOT NULL,
    "id_contenedor" VARCHAR(20) NOT NULL,
    "id_contenedor_destino" VARCHAR(20),
    "id_ubicacion_origen" INTEGER NOT NULL,
    "tenant_id" INTEGER,
    CONSTRAINT "fk_omc_contenedores_id_omc" FOREIGN KEY ("id_omc") REFERENCES "omc" ("id_omc") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "fk_omc_contenedores_id_ubicacion_origen" FOREIGN KEY ("id_ubicacion_origen") REFERENCES "ubicaciones" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE INDEX "idx_omc_cont_tenant" ON "omc_contenedores" ("tenant_id");

-- --- inventarios_cabecera ---;
CREATE TABLE "inventarios_cabecera" (
    "id" INTEGER,
    "numero" VARCHAR(20) NOT NULL,
    "descripcion" VARCHAR(200),
    "estado" VARCHAR(50) DEFAULT 'Abierto' CHECK ("estado" IN ('Abierto','Cerrado','Anulado')),
    "fecha_creacion" datetime DEFAULT CURRENT_TIMESTAMP,
    "usuario_creacion" VARCHAR(100),
    "fecha_cierre" datetime,
    "usuario_cierre" VARCHAR(100),
    "fecha_anulacion" datetime,
    "usuario_anulacion" VARCHAR(100),
    "tenant_id" INTEGER
);
CREATE INDEX "idx_inventarios_cab_tenant" ON "inventarios_cabecera" ("tenant_id");

-- --- inventarios_detalle ---;
CREATE TABLE "inventarios_detalle" (
    "id" INTEGER,
    "id_inventario" INTEGER NOT NULL,
    "id_ubicacion" INTEGER NOT NULL,
    "id_material" INTEGER NOT NULL,
    "id_contenedor" VARCHAR(20) DEFAULT '',
    "lote" VARCHAR(100) DEFAULT 'UNICO',
    "tipo_stock" VARCHAR(50) DEFAULT 'Libre Venta',
    "stock_sistema" decimal(15,3) DEFAULT 0,
    "stock_contado" decimal(15,3),
    "fecha_conteo" datetime,
    "usuario_conteo" VARCHAR(100),
    "tenant_id" INTEGER,
    CONSTRAINT "fk_inventarios_detalle_id_inventario" FOREIGN KEY ("id_inventario") REFERENCES "inventarios_cabecera" ("id") ON DELETE CASCADE
);
CREATE INDEX "idx_inventarios_det_tenant" ON "inventarios_detalle" ("tenant_id");

-- --- Datos iniciales ---;

INSERT INTO "clases_pedido" ("nombre", "activo") VALUES ('Venta', TRUE) ON CONFLICT DO NOTHING;
INSERT INTO "clases_pedido" ("nombre", "activo") VALUES ('Reposicion', TRUE) ON CONFLICT DO NOTHING;
INSERT INTO "clases_pedido" ("nombre", "activo") VALUES ('Muestra', TRUE) ON CONFLICT DO NOTHING;
INSERT INTO "clases_pedido" ("nombre", "activo") VALUES ('Devolucion', TRUE) ON CONFLICT DO NOTHING;


-- === FIN DEL SCRIPT ===;
-- Schema generado para engine: postgresql;
-- Usuarios por defecto:;
--   SuperAdmin: admin / Admin@2024!;
--   Operador:   operador / Admin@2024!;
