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
    "bajostock" REAL DEFAULT 0,
    "dias_filtro_fechas" INTEGER DEFAULT 30,
    "contexto" text,
    "prompt" text,
    "proveedor_api_ia" text,
    "modelo_api_ia" text,
    "api_key" text
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

-- Permisos de rutas por rol;
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('ADMIN', '*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/materiales');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/materiales/guardar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/materiales/eliminar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/materiales/importar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/materiales/exportar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/materiales/plantilla');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/ubicaciones');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/ubicaciones/guardar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/ubicaciones/importar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/ubicaciones/exportar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/ubicaciones/plantilla');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/tipoubicacion');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/tipoubicacion/guardar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/tipoubicacion/eliminar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/tipoubicacion/importar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/tipoubicacion/exportar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/tipoubicacion/plantilla');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/proveedores');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/proveedores/guardar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/proveedores/eliminar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/proveedores/importar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/proveedores/exportar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/proveedores/plantilla');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/clientes');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/clientes/guardar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/clientes/importar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/clientes/exportar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/clientes/plantilla');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/categorias');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/categorias/guardar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/categorias/eliminar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/unidades');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/unidades/guardar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/unidades/eliminar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/unidades/importar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/unidades/exportar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/unidades/plantilla');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/transportes');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/transportes/guardar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/transportes/importar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/transportes/exportar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/transportes/plantilla');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/rutas');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/rutas/guardar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/rutas/eliminar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/rutas/importar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/rutas/exportar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/rutas/plantilla');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/nuevo');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/editar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/guardar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/eliminar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/importar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/plantilla');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/pedidos/picking_json');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/nueva');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/guardar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/ver');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/cerrar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/eliminar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/importar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/plantilla');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/guardar_item');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/eliminar_item');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/confirmar_stock');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/recepciones/anular');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/omc');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/omc/nueva');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/omc/guardar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/omc/ver');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/despacho');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/despacho/despachar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/despacho/despachar_masivo');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/stockcontable');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/stockcontable/editar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/stockcontable/importar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/stockcontable/exportar');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/stockcontable/plantilla');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/inventario');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/inventario/crear');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/inventario/*');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/parametros');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('OPERADOR', '/actualizar_parametros');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/materiales');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/ubicaciones');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/tipoubicacion');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/proveedores');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/clientes');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/categorias');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/unidades');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/transportes');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/rutas');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/pedidos');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/recepciones');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/omc');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/despacho');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/stockcontable');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/inventario');
INSERT OR IGNORE INTO "roles_rutas" ("rol", "ruta") VALUES ('CONSULTA', '/parametros');


-- SQLite schema for taurus_wms;
PRAGMA foreign_keys = ON;

-- TAURUS WMS - Schema para taurus_wms (datos operativos);
-- Engine: sqlite;
-- Generado por modules/schema_generator.py;

-- SQLite: database is a file, drop by deleting the file: taurus_wms.db;


-- --- zonas ---;
CREATE TABLE IF NOT EXISTS "zonas" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "codigo" TEXT NOT NULL,
    "nombre" TEXT NOT NULL,
    "descripcion" text,
    "activo" INTEGER NOT NULL DEFAULT 1,
    "tenant_id" INTEGER,
    "created_at" TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE ("codigo")
);
CREATE INDEX IF NOT EXISTS "idx_zona_activo" ON "zonas" ("activo");
CREATE INDEX IF NOT EXISTS "idx_zonas_tenant" ON "zonas" ("tenant_id");

-- --- tipoubicacion ---;
CREATE TABLE IF NOT EXISTS "tipoubicacion" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "descripcion" TEXT NOT NULL,
    "operacion" char(1),
    "soporte_picking" INTEGER NOT NULL DEFAULT 0,
    "tenant_id" INTEGER
);
CREATE INDEX IF NOT EXISTS "idx_tipoubicacion_tenant" ON "tipoubicacion" ("tenant_id");

-- --- categorias ---;
CREATE TABLE IF NOT EXISTS "categorias" (
    "id_categoria" INTEGER PRIMARY KEY AUTOINCREMENT,
    "codigo" TEXT,
    "nombre" TEXT NOT NULL,
    "descripcion" text,
    "activo" INTEGER NOT NULL DEFAULT 1,
    "tenant_id" INTEGER,
    "created_at" TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS "idx_categorias_tenant" ON "categorias" ("tenant_id");

-- --- proveedores ---;
CREATE TABLE IF NOT EXISTS "proveedores" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "codigo" TEXT,
    "razonsocial" TEXT NOT NULL,
    "cuit" TEXT,
    "direccion" TEXT,
    "telefono" TEXT,
    "email" TEXT,
    "activo" INTEGER NOT NULL DEFAULT 1,
    "tenant_id" INTEGER,
    "created_at" TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS "idx_proveedores_tenant" ON "proveedores" ("tenant_id");

-- --- rutas ---;
CREATE TABLE IF NOT EXISTS "rutas" (
    "id_ruta" INTEGER PRIMARY KEY AUTOINCREMENT,
    "nombre_ruta" TEXT NOT NULL,
    "descripcion" text,
    "tenant_id" INTEGER
);
CREATE INDEX IF NOT EXISTS "idx_rutas_tenant" ON "rutas" ("tenant_id");

-- --- unidades_medida ---;
CREATE TABLE IF NOT EXISTS "unidades_medida" (
    "id_unidad" INTEGER PRIMARY KEY AUTOINCREMENT,
    "codigo" TEXT NOT NULL,
    "nombre" TEXT NOT NULL,
    "simbolo" TEXT,
    "tipo_magnitud" TEXT DEFAULT 'CANTIDAD',
    "conversion_a_base" REAL DEFAULT 1.0,
    "unidad_base_referencia" TEXT DEFAULT 'U',
    "decimales_permitidos" INTEGER DEFAULT 0,
    "activo" INTEGER NOT NULL DEFAULT 1,
    "tenant_id" INTEGER
);
CREATE INDEX IF NOT EXISTS "idx_unidades_tenant" ON "unidades_medida" ("tenant_id");

-- --- ubicaciones ---;
CREATE TABLE IF NOT EXISTS "ubicaciones" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "codigo" TEXT NOT NULL,
    "nombre" TEXT,
    "descipcion" TEXT,
    "tipoubicacion" INTEGER,
    "zona" TEXT,
    "id_zona" INTEGER,
    "pasillo" TEXT,
    "estante" TEXT,
    "nivel" TEXT,
    "posicion" TEXT,
    "coordenadaA" TEXT,
    "coordenadaB" TEXT,
    "coordenadaC" TEXT,
    "coordenadaD" TEXT,
    "capacidad_maxima" INTEGER NOT NULL DEFAULT 0,
    "ocupado" INTEGER NOT NULL DEFAULT 0,
    "disponible_entrada" INTEGER NOT NULL DEFAULT 1,
    "disponible_salida" INTEGER NOT NULL DEFAULT 1,
    "orden_picking" INTEGER NOT NULL DEFAULT 0,
    "activo" INTEGER NOT NULL DEFAULT 1,
    "tenant_id" INTEGER,
    "created_at" TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY ("id_zona") REFERENCES "zonas" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_ubicaciones_tenant" ON "ubicaciones" ("tenant_id");
CREATE INDEX IF NOT EXISTS "idx_ubi_zona" ON "ubicaciones" ("id_zona");
CREATE INDEX IF NOT EXISTS "idx_ubi_tipo" ON "ubicaciones" ("tipoubicacion");

-- --- transportes ---;
CREATE TABLE IF NOT EXISTS "transportes" (
    "id_transporte" INTEGER PRIMARY KEY AUTOINCREMENT,
    "codigo" TEXT,
    "razonsocial" TEXT NOT NULL,
    "cuit" TEXT,
    "telefono" TEXT,
    "email" TEXT,
    "activo" INTEGER NOT NULL DEFAULT 1,
    "id_muelle_salida" INTEGER,
    "tenant_id" INTEGER,
    FOREIGN KEY ("id_muelle_salida") REFERENCES "ubicaciones" ("id")
);
CREATE INDEX IF NOT EXISTS "idx_transportes_tenant" ON "transportes" ("tenant_id");

-- --- transporte_rutas ---;
CREATE TABLE IF NOT EXISTS "transporte_rutas" (
    "id_transporte" INTEGER NOT NULL,
    "id_ruta" INTEGER NOT NULL,
    "observaciones" text,
    PRIMARY KEY ("id_transporte", "id_ruta"),
    FOREIGN KEY ("id_transporte") REFERENCES "transportes" ("id_transporte") ON DELETE CASCADE,
    FOREIGN KEY ("id_ruta") REFERENCES "rutas" ("id_ruta") ON DELETE CASCADE
);

-- --- clientes ---;
CREATE TABLE IF NOT EXISTS "clientes" (
    "id_cliente" INTEGER PRIMARY KEY AUTOINCREMENT,
    "codigo" TEXT,
    "razonsocial" TEXT NOT NULL,
    "cuit" TEXT,
    "direccion" TEXT,
    "localidad" TEXT,
    "provincia" TEXT,
    "telefono" TEXT,
    "email" TEXT,
    "contacto_nombre" TEXT,
    "id_ruta" INTEGER,
    "id_transporte_predeterminado" INTEGER,
    "activo" INTEGER NOT NULL DEFAULT 1,
    "tenant_id" INTEGER,
    FOREIGN KEY ("id_ruta") REFERENCES "rutas" ("id_ruta") ON DELETE SET NULL ON UPDATE CASCADE,
    FOREIGN KEY ("id_transporte_predeterminado") REFERENCES "transportes" ("id_transporte") ON DELETE SET NULL ON UPDATE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_clientes_tenant" ON "clientes" ("tenant_id");

-- --- materiales ---;
CREATE TABLE IF NOT EXISTS "materiales" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "codigo" TEXT NOT NULL,
    "codigo_barras" TEXT,
    "nombre" TEXT NOT NULL,
    "descripcion" text,
    "categoria_id" INTEGER,
    "stock_minimo" REAL DEFAULT 0,
    "stock_maximo" REAL DEFAULT 0,
    "unidad_medida_id" INTEGER,
    "trazabilidad" TEXT NOT NULL DEFAULT 'ninguna',
    "peso_bruto" REAL,
    "peso_neto" REAL,
    "costo_promedio" REAL DEFAULT 0,
    "ultimo_costo" REAL DEFAULT 0,
    "activo" INTEGER NOT NULL DEFAULT 1,
    "tenant_id" INTEGER,
    "created_at" TEXT NOT NULL DEFAULT (datetime('now')),
    "updated_at" TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY ("categoria_id") REFERENCES "categorias" ("id_categoria") ON DELETE SET NULL ON UPDATE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_materiales_tenant" ON "materiales" ("tenant_id");
CREATE INDEX IF NOT EXISTS "idx_mat_categoria" ON "materiales" ("categoria_id");
CREATE INDEX IF NOT EXISTS "idx_mat_codigo_barras" ON "materiales" ("codigo_barras");

-- --- material_proveedor ---;
CREATE TABLE IF NOT EXISTS "material_proveedor" (
    "id_material" INTEGER NOT NULL,
    "id_proveedor" INTEGER NOT NULL,
    "codigo_referencia_prov" TEXT,
    "es_habitual" INTEGER NOT NULL DEFAULT 0,
    "tenant_id" INTEGER,
    PRIMARY KEY ("id_material", "id_proveedor"),
    FOREIGN KEY ("id_material") REFERENCES "materiales" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY ("id_proveedor") REFERENCES "proveedores" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_matprov_tenant" ON "material_proveedor" ("tenant_id");

-- --- material_presentaciones ---;
CREATE TABLE IF NOT EXISTS "material_presentaciones" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "id_material" INTEGER NOT NULL,
    "nombre" TEXT NOT NULL,
    "codigo_barras" TEXT,
    "cantidad_unidades" REAL NOT NULL DEFAULT 1.0,
    "peso_bruto" REAL,
    "peso_neto" REAL,
    "activo" INTEGER NOT NULL DEFAULT 1,
    "tenant_id" INTEGER,
    UNIQUE ("codigo_barras"),
    FOREIGN KEY ("id_material") REFERENCES "materiales" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_matpres_tenant" ON "material_presentaciones" ("tenant_id");

-- --- stockcontable ---;
CREATE TABLE IF NOT EXISTS "stockcontable" (
    "ID" INTEGER PRIMARY KEY AUTOINCREMENT,
    "Ubicacion" INTEGER NOT NULL,
    "Material" INTEGER NOT NULL,
    "Lote" TEXT NOT NULL DEFAULT 'UNICO',
    "TipoStock" TEXT NOT NULL DEFAULT 'Libre Venta',
    "UltimaEntrada" TEXT,
    "UltimaSalida" TEXT,
    "UltimoMovimiento" TEXT,
    "UsuarioUltimoMov" TEXT,
    "FechaVencimiento" TEXT,
    "StockTotal" REAL NOT NULL DEFAULT 0,
    "StockDisponible" REAL NOT NULL DEFAULT 0,
    "StockEntrando" REAL NOT NULL DEFAULT 0,
    "StockSaliendo" REAL NOT NULL DEFAULT 0,
    "IDContenedor" TEXT NOT NULL,
    "tenant_id" INTEGER,
    "created_at" TEXT NOT NULL DEFAULT (datetime('now')),
    "updated_at" TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE ("Ubicacion", "Material", "IDContenedor"),
    FOREIGN KEY ("Ubicacion") REFERENCES "ubicaciones" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY ("Material") REFERENCES "materiales" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_material" ON "stockcontable" ("Material");
CREATE INDEX IF NOT EXISTS "idx_ubicacion" ON "stockcontable" ("Ubicacion");
CREATE INDEX IF NOT EXISTS "idx_lote" ON "stockcontable" ("Lote");
CREATE INDEX IF NOT EXISTS "idx_tipo_stock" ON "stockcontable" ("TipoStock");
CREATE INDEX IF NOT EXISTS "idx_contenedor" ON "stockcontable" ("IDContenedor");
CREATE INDEX IF NOT EXISTS "idx_stockcontable_tenant" ON "stockcontable" ("tenant_id");

-- --- clases_pedido ---;
CREATE TABLE IF NOT EXISTS "clases_pedido" (
    "id_clase" INTEGER PRIMARY KEY AUTOINCREMENT,
    "nombre" TEXT NOT NULL,
    "activo" INTEGER NOT NULL DEFAULT 1,
    "tenant_id" INTEGER
);
CREATE INDEX IF NOT EXISTS "idx_clases_pedido_tenant" ON "clases_pedido" ("tenant_id");

-- --- recepciones_cabecera ---;
CREATE TABLE IF NOT EXISTS "recepciones_cabecera" (
    "id_recepcion" INTEGER PRIMARY KEY AUTOINCREMENT,
    "numero" TEXT NOT NULL,
    "id_proveedor" INTEGER NOT NULL,
    "estado" TEXT NOT NULL DEFAULT 'Abierta',
    "id_contenedor" TEXT NOT NULL,
    "id_ubicacion_recep" INTEGER NOT NULL,
    "id_ubicacion_destino" INTEGER,
    "observaciones" text,
    "fecha_recepcion" TEXT NOT NULL DEFAULT (datetime('now')),
    "fecha_cierre" TEXT,
    "usuario_creacion" TEXT NOT NULL,
    "usuario_cierre" TEXT,
    "tenant_id" INTEGER,
    "created_at" TEXT NOT NULL DEFAULT (datetime('now')),
    "updated_at" TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE ("numero"),
    FOREIGN KEY ("id_proveedor") REFERENCES "proveedores" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY ("id_ubicacion_recep") REFERENCES "ubicaciones" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY ("id_ubicacion_destino") REFERENCES "ubicaciones" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_rec_proveedor" ON "recepciones_cabecera" ("id_proveedor");
CREATE INDEX IF NOT EXISTS "idx_rec_estado" ON "recepciones_cabecera" ("estado");
CREATE INDEX IF NOT EXISTS "idx_rec_contenedor" ON "recepciones_cabecera" ("id_contenedor");
CREATE INDEX IF NOT EXISTS "idx_rec_ubicrec" ON "recepciones_cabecera" ("id_ubicacion_recep");
CREATE INDEX IF NOT EXISTS "idx_rec_ubicdest" ON "recepciones_cabecera" ("id_ubicacion_destino");
CREATE INDEX IF NOT EXISTS "idx_rec_fecha" ON "recepciones_cabecera" ("fecha_recepcion");
CREATE INDEX IF NOT EXISTS "idx_recepciones_cab_tenant" ON "recepciones_cabecera" ("tenant_id");

-- --- recepciones_detalle ---;
CREATE TABLE IF NOT EXISTS "recepciones_detalle" (
    "id_detalle" INTEGER PRIMARY KEY AUTOINCREMENT,
    "id_recepcion" INTEGER NOT NULL,
    "id_material" INTEGER NOT NULL,
    "lote" TEXT NOT NULL DEFAULT 'UNICO',
    "fecha_vencimiento" TEXT,
    "cantidad_esperada" REAL NOT NULL DEFAULT 0,
    "cantidad_recibida" REAL NOT NULL DEFAULT 0,
    "tipo_stock" TEXT NOT NULL DEFAULT 'Libre Venta',
    "observaciones" text,
    "tenant_id" INTEGER,
    "created_at" TEXT NOT NULL DEFAULT (datetime('now')),
    "updated_at" TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE ("id_recepcion", "id_material", "lote", "tipo_stock"),
    FOREIGN KEY ("id_recepcion") REFERENCES "recepciones_cabecera" ("id_recepcion") ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY ("id_material") REFERENCES "materiales" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_det_recepcion" ON "recepciones_detalle" ("id_recepcion");
CREATE INDEX IF NOT EXISTS "idx_det_material" ON "recepciones_detalle" ("id_material");
CREATE INDEX IF NOT EXISTS "idx_det_lote" ON "recepciones_detalle" ("lote");
CREATE INDEX IF NOT EXISTS "idx_recepciones_det_tenant" ON "recepciones_detalle" ("tenant_id");

-- --- pedidos_cabecera ---;
CREATE TABLE IF NOT EXISTS "pedidos_cabecera" (
    "id_pedido" INTEGER PRIMARY KEY AUTOINCREMENT,
    "nro_pedido" TEXT NOT NULL,
    "id_cliente" INTEGER NOT NULL,
    "id_clase" INTEGER,
    "fecha_pedido" TEXT NOT NULL,
    "id_ruta" INTEGER,
    "id_transporte" INTEGER,
    "direccion_entrega" TEXT,
    "observaciones" text,
    "estado" TEXT NOT NULL DEFAULT 'Pendiente',
    "fecha_despacho" TEXT,
    "tenant_id" INTEGER,
    "created_at" TEXT NOT NULL DEFAULT (datetime('now')),
    "updated_at" TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE ("nro_pedido"),
    FOREIGN KEY ("id_cliente") REFERENCES "clientes" ("id_cliente") ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY ("id_clase") REFERENCES "clases_pedido" ("id_clase") ON DELETE SET NULL ON UPDATE CASCADE,
    FOREIGN KEY ("id_ruta") REFERENCES "rutas" ("id_ruta") ON DELETE SET NULL ON UPDATE CASCADE,
    FOREIGN KEY ("id_transporte") REFERENCES "transportes" ("id_transporte") ON DELETE SET NULL ON UPDATE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_pedido_cliente" ON "pedidos_cabecera" ("id_cliente");
CREATE INDEX IF NOT EXISTS "idx_pedido_estado" ON "pedidos_cabecera" ("estado");
CREATE INDEX IF NOT EXISTS "idx_pedido_fecha" ON "pedidos_cabecera" ("fecha_pedido");
CREATE INDEX IF NOT EXISTS "idx_pedidos_cab_tenant" ON "pedidos_cabecera" ("tenant_id");

-- --- pedidos_detalle ---;
CREATE TABLE IF NOT EXISTS "pedidos_detalle" (
    "id_detalle" INTEGER PRIMARY KEY AUTOINCREMENT,
    "id_pedido" INTEGER NOT NULL,
    "id_material" INTEGER NOT NULL,
    "cantidad" REAL NOT NULL DEFAULT 0,
    "Cantidad_preparada" REAL NOT NULL DEFAULT 0,
    "tipo_stock" TEXT NOT NULL DEFAULT 'Libre Venta',
    "tenant_id" INTEGER,
    "created_at" TEXT NOT NULL DEFAULT (datetime('now')),
    "updated_at" TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY ("id_pedido") REFERENCES "pedidos_cabecera" ("id_pedido") ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY ("id_material") REFERENCES "materiales" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_pd_pedido" ON "pedidos_detalle" ("id_pedido");
CREATE INDEX IF NOT EXISTS "idx_pd_material" ON "pedidos_detalle" ("id_material");
CREATE INDEX IF NOT EXISTS "idx_pedidos_det_tenant" ON "pedidos_detalle" ("tenant_id");

-- --- omc ---;
CREATE TABLE IF NOT EXISTS "omc" (
    "id_omc" INTEGER PRIMARY KEY AUTOINCREMENT,
    "numero" TEXT NOT NULL,
    "id_contenedor" TEXT,
    "id_contenedor_destino" TEXT,
    "id_ubicacion_origen" INTEGER,
    "id_ubicacion_destino" INTEGER NOT NULL,
    "id_recepcion" INTEGER,
    "id_pedido" INTEGER,
    "estado" TEXT NOT NULL DEFAULT 'Pendiente',
    "observaciones" text,
    "fecha_creacion" TEXT NOT NULL DEFAULT (datetime('now')),
    "fecha_confirmacion" TEXT,
    "fecha_anulacion" TEXT,
    "usuario_creacion" TEXT NOT NULL,
    "usuario_confirmacion" TEXT,
    "usuario_anulacion" TEXT,
    "tenant_id" INTEGER,
    "created_at" TEXT NOT NULL DEFAULT (datetime('now')),
    "updated_at" TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE ("numero"),
    FOREIGN KEY ("id_ubicacion_origen") REFERENCES "ubicaciones" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY ("id_ubicacion_destino") REFERENCES "ubicaciones" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY ("id_recepcion") REFERENCES "recepciones_cabecera" ("id_recepcion") ON DELETE SET NULL ON UPDATE CASCADE,
    FOREIGN KEY ("id_pedido") REFERENCES "pedidos_cabecera" ("id_pedido") ON DELETE SET NULL ON UPDATE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_omc_contenedor" ON "omc" ("id_contenedor");
CREATE INDEX IF NOT EXISTS "idx_omc_origen" ON "omc" ("id_ubicacion_origen");
CREATE INDEX IF NOT EXISTS "idx_omc_destino" ON "omc" ("id_ubicacion_destino");
CREATE INDEX IF NOT EXISTS "idx_omc_estado" ON "omc" ("estado");
CREATE INDEX IF NOT EXISTS "idx_omc_recepcion" ON "omc" ("id_recepcion");
CREATE INDEX IF NOT EXISTS "idx_omc_pedido" ON "omc" ("id_pedido");
CREATE INDEX IF NOT EXISTS "idx_omc_tenant" ON "omc" ("tenant_id");

-- --- omc_contenedores ---;
CREATE TABLE IF NOT EXISTS "omc_contenedores" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "id_omc" INTEGER NOT NULL,
    "id_contenedor" TEXT NOT NULL,
    "id_contenedor_destino" TEXT,
    "id_ubicacion_origen" INTEGER NOT NULL,
    "tenant_id" INTEGER,
    FOREIGN KEY ("id_omc") REFERENCES "omc" ("id_omc") ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY ("id_ubicacion_origen") REFERENCES "ubicaciones" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_omc_cont_tenant" ON "omc_contenedores" ("tenant_id");

-- --- inventarios_cabecera ---;
CREATE TABLE IF NOT EXISTS "inventarios_cabecera" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "numero" TEXT NOT NULL,
    "descripcion" TEXT,
    "estado" TEXT DEFAULT 'Abierto',
    "fecha_creacion" TEXT DEFAULT (datetime('now')),
    "usuario_creacion" TEXT,
    "fecha_cierre" TEXT,
    "usuario_cierre" TEXT,
    "fecha_anulacion" TEXT,
    "usuario_anulacion" TEXT,
    "tenant_id" INTEGER
);
CREATE INDEX IF NOT EXISTS "idx_inventarios_cab_tenant" ON "inventarios_cabecera" ("tenant_id");

-- --- inventarios_detalle ---;
CREATE TABLE IF NOT EXISTS "inventarios_detalle" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "id_inventario" INTEGER NOT NULL,
    "id_ubicacion" INTEGER NOT NULL,
    "id_material" INTEGER NOT NULL,
    "id_contenedor" TEXT DEFAULT '',
    "lote" TEXT DEFAULT 'UNICO',
    "tipo_stock" TEXT DEFAULT 'Libre Venta',
    "stock_sistema" REAL DEFAULT 0,
    "stock_contado" REAL,
    "fecha_conteo" TEXT,
    "usuario_conteo" TEXT,
    "tenant_id" INTEGER,
    FOREIGN KEY ("id_inventario") REFERENCES "inventarios_cabecera" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_inventarios_det_tenant" ON "inventarios_detalle" ("tenant_id");

-- --- Datos iniciales ---;

INSERT OR IGNORE INTO "clases_pedido" ("nombre", "activo") VALUES ('Venta', 1);
INSERT OR IGNORE INTO "clases_pedido" ("nombre", "activo") VALUES ('Reposicion', 1);
INSERT OR IGNORE INTO "clases_pedido" ("nombre", "activo") VALUES ('Muestra', 1);
INSERT OR IGNORE INTO "clases_pedido" ("nombre", "activo") VALUES ('Devolucion', 1);


-- === FIN DEL SCRIPT ===;
-- Schema generado para engine: sqlite;
-- Usuarios por defecto:;
--   SuperAdmin: admin / Admin@2024!;
--   Operador:   operador / Admin@2024!;
