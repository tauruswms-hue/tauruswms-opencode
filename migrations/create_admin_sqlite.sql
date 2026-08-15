-- SQLite schema for taurus_admin;
PRAGMA foreign_keys = ON;

-- TAURUS WMS - Schema para taurus_admin;
-- Engine: sqlite;
-- Generado por modules/schema_generator.py;

-- SQLite: database is a file, drop by deleting the file: taurus_admin.db;


-- --- admin_usuarios ---;
CREATE TABLE IF NOT EXISTS "admin_usuarios" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "username" TEXT NOT NULL,
    "password_hash" TEXT NOT NULL,
    "nombre" TEXT NOT NULL,
    "email" TEXT,
    "rol" TEXT DEFAULT 'ADMIN',
    "activo" INTEGER DEFAULT 1,
    "ultimo_acceso" TEXT,
    "created_at" TEXT DEFAULT (datetime('now')),
    "updated_at" TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS "idx_username" ON "admin_usuarios" ("username");
CREATE INDEX IF NOT EXISTS "idx_rol" ON "admin_usuarios" ("rol");

-- --- roles ---;
CREATE TABLE IF NOT EXISTS "roles" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "nombre" TEXT NOT NULL,
    "descripcion" TEXT,
    "activo" INTEGER DEFAULT 1,
    "created_at" TEXT DEFAULT (datetime('now')),
    "updated_at" TEXT DEFAULT (datetime('now')),
    UNIQUE ("nombre")
);
CREATE INDEX IF NOT EXISTS "idx_roles_activo" ON "roles" ("activo");

-- --- tenants ---;
CREATE TABLE IF NOT EXISTS "tenants" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "codigo" TEXT NOT NULL,
    "nombre" TEXT NOT NULL,
    "razon_social" TEXT,
    "cuit" TEXT,
    "direccion" TEXT,
    "telefono" TEXT,
    "email" TEXT,
    "activo" INTEGER DEFAULT 1,
    "created_at" TEXT DEFAULT (datetime('now')),
    "updated_at" TEXT DEFAULT (datetime('now')),
    "nombredelalmacen" TEXT,
    "metodosdepicking" text,
    "metodo_picking_default" TEXT NOT NULL DEFAULT 'libre',
    "bajostock" REAL DEFAULT 0,
    "dias_filtro_fechas" INTEGER DEFAULT 30,
    "contexto" text,
    "prompt" text,
    "proveedor_api_ia" text,
    "modelo_api_ia" text,
    "api_key" text,
    "api_token" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_codigo" ON "tenants" ("codigo");
CREATE INDEX IF NOT EXISTS "idx_activo" ON "tenants" ("activo");

-- --- usuarios ---;
CREATE TABLE IF NOT EXISTS "usuarios" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "username" TEXT NOT NULL,
    "password_hash" TEXT NOT NULL,
    "nombre" TEXT NOT NULL,
    "email" TEXT,
    "rol" TEXT DEFAULT 'OPERADOR',
    "tenant_id" INTEGER NOT NULL,
    "activo" INTEGER DEFAULT 1,
    "ultimo_acceso" TEXT,
    "created_at" TEXT DEFAULT (datetime('now')),
    "updated_at" TEXT DEFAULT (datetime('now')),
    "sidebar_preferences" text,
    FOREIGN KEY ("tenant_id") REFERENCES "tenants" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_tenant" ON "usuarios" ("tenant_id");
CREATE INDEX IF NOT EXISTS "idx_rol" ON "usuarios" ("rol");

-- --- configuracion ---;
CREATE TABLE IF NOT EXISTS "configuracion" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "clave" TEXT NOT NULL,
    "valor" text,
    "descripcion" TEXT,
    "updated_at" TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS "idx_clave" ON "configuracion" ("clave");

-- --- audit_logs ---;
CREATE TABLE IF NOT EXISTS "audit_logs" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "usuario_id" INTEGER,
    "usuario_nombre" TEXT,
    "accion" TEXT NOT NULL,
    "modulo" TEXT NOT NULL,
    "detalle" text,
    "ip_address" TEXT,
    "user_agent" TEXT,
    "created_at" TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS "idx_usuario" ON "audit_logs" ("usuario_id");
CREATE INDEX IF NOT EXISTS "idx_accion" ON "audit_logs" ("accion");
CREATE INDEX IF NOT EXISTS "idx_modulo" ON "audit_logs" ("modulo");
CREATE INDEX IF NOT EXISTS "idx_fecha" ON "audit_logs" ("created_at");

-- --- roles_rutas ---;
CREATE TABLE IF NOT EXISTS "roles_rutas" (
    "rol" TEXT NOT NULL,
    "ruta" TEXT NOT NULL,
    PRIMARY KEY ("rol", "ruta")
);

-- --- Datos iniciales ---;

INSERT OR IGNORE INTO "tenants" ("id", "codigo", "nombre", "razon_social", "activo", "nombredelalmacen", "metodosdepicking", "bajostock", "dias_filtro_fechas") VALUES (1, 'DEFAULT', 'Empresa Principal', 'Empresa Principal S.A.', 1, 'Almacen Principal', '"fifo"', 0, 30);

-- Roles por defecto del sistema;
INSERT OR IGNORE INTO "roles" ("nombre", "descripcion", "activo") VALUES ('ADMIN', 'Acceso total a todas las rutas', 1);
INSERT OR IGNORE INTO "roles" ("nombre", "descripcion", "activo") VALUES ('OPERADOR', 'Rutas operativas del WMS', 1);
INSERT OR IGNORE INTO "roles" ("nombre", "descripcion", "activo") VALUES ('CONSULTA', 'Acceso de solo lectura', 1);

-- SuperAdmin password: Admin@2024!;
INSERT OR IGNORE INTO "admin_usuarios" ("username", "password_hash", "nombre", "email", "rol") VALUES ('admin', 'scrypt:32768:8:1$WQ6PhKOf81VV3FcH$ed1ca47fd1fd381583f0289acf9e839521b5e74a07adfc034382ea5342d608e393b7143fec95b3aef262f1946f95696e3e8acbfc867c91769d63142d4e4a5db2', 'Administrador', 'admin@taurus.local', 'SUPERADMIN');

-- Operador password: Admin@2024!;
INSERT OR IGNORE INTO "usuarios" ("username", "password_hash", "nombre", "email", "rol", "tenant_id", "activo") VALUES ('operador', 'scrypt:32768:8:1$WQ6PhKOf81VV3FcH$ed1ca47fd1fd381583f0289acf9e839521b5e74a07adfc034382ea5342d608e393b7143fec95b3aef262f1946f95696e3e8acbfc867c91769d63142d4e4a5db2', 'Operador General', 'operador@taurus.local', 'OPERADOR', 1, 1);

INSERT OR IGNORE INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('app_version', '1.0.0', 'Version actual de la aplicacion');
INSERT OR IGNORE INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('app_name', 'Taurus WMS', 'Nombre de la aplicacion');
INSERT OR IGNORE INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('mantenimiento', 'false', 'Modo mantenimiento (true/false)');
INSERT OR IGNORE INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('DB_HOST', 'localhost', 'Host del servidor de base de datos');
INSERT OR IGNORE INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('DB_PORT', '3306', 'Puerto del servidor MySQL');
INSERT OR IGNORE INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('DB_NAME', 'taurus_wms', 'Nombre de la base de datos principal');
INSERT OR IGNORE INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('DB_USER', 'taurus', 'Usuario de la base de datos');
INSERT OR IGNORE INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('DB_PASSWORD', 'Taurus_2001', 'Contrasena de la base de datos');
INSERT OR IGNORE INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('DB_CHAR_SET', 'utf8mb4', 'Charset de la base de datos');
INSERT OR IGNORE INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('DB_ENGINE', 'mysql', 'Motor de BD: mysql, postgresql, sqlite');
INSERT OR IGNORE INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('INTERCAMBIO_ENGINE', 'mysql', 'Motor de BD de intercambio (mysql, postgresql, sqlite, sqlserver)');
INSERT OR IGNORE INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('INTERCAMBIO_HOST', 'localhost', 'Host de la base de intercambio');
INSERT OR IGNORE INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('INTERCAMBIO_PORT', '3306', 'Puerto de la base de intercambio');
INSERT OR IGNORE INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('INTERCAMBIO_NAME', 'taurus_intercambio', 'Nombre de la base de intercambio');
INSERT OR IGNORE INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('INTERCAMBIO_USER', 'taurus', 'Usuario de la base de intercambio');
INSERT OR IGNORE INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('INTERCAMBIO_PASSWORD', 'Taurus_2001', 'Contrasena de la base de intercambio');
INSERT OR IGNORE INTO "configuracion" ("clave", "valor", "descripcion") VALUES ('INTERCAMBIO_CHAR_SET', 'utf8mb4', 'Charset de la base de intercambio');

-- Permisos de rutas por rol;
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('ADMIN', '*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/materiales');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/materiales/guardar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/materiales/importar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/materiales/exportar/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/materiales/plantilla/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/materiales/eliminar/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/ubicaciones');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/ubicaciones/guardar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/ubicaciones/eliminar/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/ubicaciones/importar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/ubicaciones/exportar/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/ubicaciones/plantilla/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/tipoubicacion');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/tipoubicacion/guardar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/tipoubicacion/eliminar/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/tipoubicacion/importar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/tipoubicacion/exportar/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/tipoubicacion/plantilla/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/proveedores');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/proveedores/guardar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/proveedores/eliminar/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/proveedores/importar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/proveedores/exportar/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/proveedores/plantilla/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/clientes');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/clientes/guardar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/clientes/eliminar/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/clientes/importar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/clientes/exportar/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/clientes/plantilla/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/categorias');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/categorias/guardar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/categorias/eliminar/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/unidades');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/unidades/guardar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/unidades/eliminar/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/unidades/importar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/unidades/exportar/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/unidades/plantilla/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/transportes');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/transportes/guardar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/transportes/eliminar/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/transportes/importar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/transportes/exportar/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/transportes/plantilla/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/rutas');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/rutas/guardar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/rutas/eliminar/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/rutas/importar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/rutas/exportar/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/rutas/plantilla/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/nuevo');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/ver/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/editar/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/guardar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/eliminar/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/importar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/plantilla/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/picking_json');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/preparar_masivo');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/resumen_preparar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/cambiar_ruta_transporte');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/filtros/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/contenedor_stock');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/nueva');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/guardar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/ver/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/buscar_*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/guardar_item');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/eliminar_item/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/cerrar/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/eliminar/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/confirmar_stock/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/anular/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/importar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/plantilla/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/omc');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/omc/nueva');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/omc/guardar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/omc/ver/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/omc/confirmar/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/omc/modificar/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/omc/anular/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/omc/buscar_*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/omc/tipos_ubicacion');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/despacho');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/despacho/despachar/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/despacho/despachar_masivo');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/stockcontable');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/stockcontable/editar/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/stockcontable/importar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/stockcontable/exportar/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/stockcontable/plantilla/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/inventario');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/inventario/crear');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/inventario/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/parametros');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/actualizar_parametros');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/movil');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/movil/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/sidebar-preferences');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/materiales');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/ubicaciones');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/tipoubicacion');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/proveedores');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/clientes');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/categorias');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/unidades');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/transportes');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/rutas');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/zonas');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/clases-pedido');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/pedidos');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/pedidos/ver/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/pedidos/filtros/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/pedidos/buscar_contenedores');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/pedidos/contenedor_stock');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/recepciones');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/recepciones/ver/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/recepciones/buscar_*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/omc');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/omc/ver/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/omc/buscar_*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/despacho');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/stockcontable');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/stockcontable/exportar/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/stockcontable/plantilla/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/inventario');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/inventario/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/parametros');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/stock');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/entradas');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/salidas');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/reportes');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/reportes/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/sidebar-preferences');


-- === FIN DEL SCRIPT ===;
-- Schema generado para engine: sqlite;
-- Usuarios por defecto:;
--   SuperAdmin: admin / Admin@2024!;
--   Operador:   operador / Admin@2024!;
