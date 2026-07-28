"""
schema_generator.py — Generador de DDL multi-engine para Taurus WMS

Uso:
    python schema_generator.py --engine mysql     > schema_mysql.sql
    python schema_generator.py --engine postgresql > schema_postgresql.sql
    python schema_generator.py --engine sqlite     > schema_sqlite.sql
    python schema_generator.py --all               (genera los 3 archivos)

Tambien se puede importar para uso programatico:
    from modules.schema_generator import generate_schema
    sql = generate_schema('postgresql')
"""

import argparse
import sys
import os

# ============================================================================
# DEFINICION DE COLUMNAS (tipos genericos, se traducen por engine)
# ============================================================================

# Tipos genericos soportados:
#   'int'          -> INT / SERIAL / INTEGER
#   'bigint'       -> BIGINT / BIGSERIAL / INTEGER
#   'varchar(N)'   -> VARCHAR(N)
#   'text'         -> TEXT
#   'decimal(P,S)' -> DECIMAL(P,S)
#   'boolean'      -> TINYINT(1) / BOOLEAN / INTEGER
#   'datetime'     -> DATETIME / TIMESTAMP / TEXT
#   'date'         -> DATE
#   'char(N)'      -> CHAR(N)
#   'enum(...)'    -> ENUM / VARCHAR + CHECK / TEXT + CHECK


# ============================================================================
# DEFINICION DE TABLAS — ADMIN DATABASE
# ============================================================================

ADMIN_TABLES = [
    {
        "name": "admin_usuarios",
        "columns": [
            {"name": "id",            "type": "int",     "pk": True, "autoincrement": True},
            {"name": "username",      "type": "varchar(50)",  "not_null": True, "unique": True},
            {"name": "password_hash", "type": "varchar(255)", "not_null": True},
            {"name": "nombre",        "type": "varchar(100)", "not_null": True},
            {"name": "email",         "type": "varchar(100)"},
            {"name": "rol",           "type": "enum('SUPERADMIN','ADMIN')", "default": "'ADMIN'"},
            {"name": "activo",        "type": "boolean", "default": True},
            {"name": "ultimo_acceso", "type": "datetime"},
            {"name": "created_at",    "type": "datetime", "default": "CURRENT_TIMESTAMP"},
            {"name": "updated_at",    "type": "datetime", "default": "CURRENT_TIMESTAMP_ON_UPDATE"},
        ],
        "indexes": [
            {"columns": ["username"], "name": "idx_username"},
            {"columns": ["rol"],      "name": "idx_rol"},
        ],
    },
    {
        "name": "tenants",
        "columns": [
            {"name": "id",                "type": "int",      "pk": True, "autoincrement": True},
            {"name": "codigo",            "type": "varchar(20)",  "not_null": True, "unique": True},
            {"name": "nombre",            "type": "varchar(100)", "not_null": True},
            {"name": "razon_social",      "type": "varchar(200)"},
            {"name": "cuit",              "type": "varchar(50)"},
            {"name": "direccion",         "type": "varchar(255)"},
            {"name": "telefono",          "type": "varchar(50)"},
            {"name": "email",             "type": "varchar(100)"},
            {"name": "activo",            "type": "boolean", "default": True},
            {"name": "created_at",        "type": "datetime", "default": "CURRENT_TIMESTAMP"},
            {"name": "updated_at",        "type": "datetime", "default": "CURRENT_TIMESTAMP_ON_UPDATE"},
            {"name": "nombredelalmacen",  "type": "varchar(200)"},
            {"name": "metodosdepicking",  "type": "text"},
            {"name": "bajostock",         "type": "decimal(12,3)", "default": 0},
            {"name": "dias_filtro_fechas","type": "int", "default": 30},
            {"name": "contexto",          "type": "text"},
            {"name": "prompt",            "type": "text"},
            {"name": "proveedor_api_ia",  "type": "text"},
            {"name": "modelo_api_ia",     "type": "text"},
            {"name": "api_key",           "type": "text"},
        ],
        "indexes": [
            {"columns": ["codigo"],  "name": "idx_codigo"},
            {"columns": ["activo"],  "name": "idx_activo"},
        ],
    },
    {
        "name": "usuarios",
        "columns": [
            {"name": "id",                  "type": "int",     "pk": True, "autoincrement": True},
            {"name": "username",            "type": "varchar(50)",  "not_null": True, "unique": True},
            {"name": "password_hash",       "type": "varchar(255)", "not_null": True},
            {"name": "nombre",              "type": "varchar(100)", "not_null": True},
            {"name": "email",               "type": "varchar(100)"},
            {"name": "rol",                 "type": "enum('ADMIN','OPERADOR','CONSULTA')", "default": "'OPERADOR'"},
            {"name": "tenant_id",           "type": "int", "not_null": True},
            {"name": "activo",              "type": "boolean", "default": True},
            {"name": "ultimo_acceso",       "type": "datetime"},
            {"name": "created_at",          "type": "datetime", "default": "CURRENT_TIMESTAMP"},
            {"name": "updated_at",          "type": "datetime", "default": "CURRENT_TIMESTAMP_ON_UPDATE"},
            {"name": "sidebar_preferences", "type": "text"},
        ],
        "indexes": [
            {"columns": ["tenant_id"], "name": "idx_tenant"},
            {"columns": ["rol"],       "name": "idx_rol"},
        ],
        "foreign_keys": [
            {"columns": ["tenant_id"], "ref_table": "tenants", "ref_columns": ["id"], "on_delete": "CASCADE"},
        ],
    },
    {
        "name": "configuracion",
        "columns": [
            {"name": "id",          "type": "int",          "pk": True, "autoincrement": True},
            {"name": "clave",       "type": "varchar(100)", "not_null": True, "unique": True},
            {"name": "valor",       "type": "text"},
            {"name": "descripcion", "type": "varchar(255)"},
            {"name": "updated_at",  "type": "datetime", "default": "CURRENT_TIMESTAMP_ON_UPDATE"},
        ],
        "indexes": [
            {"columns": ["clave"], "name": "idx_clave"},
        ],
    },
    {
        "name": "audit_logs",
        "columns": [
            {"name": "id",             "type": "bigint",      "pk": True, "autoincrement": True},
            {"name": "usuario_id",     "type": "int"},
            {"name": "usuario_nombre", "type": "varchar(100)"},
            {"name": "accion",         "type": "varchar(50)",  "not_null": True},
            {"name": "modulo",         "type": "varchar(100)", "not_null": True},
            {"name": "detalle",        "type": "text"},
            {"name": "ip_address",     "type": "varchar(45)"},
            {"name": "user_agent",     "type": "varchar(255)"},
            {"name": "created_at",     "type": "datetime", "default": "CURRENT_TIMESTAMP"},
        ],
        "indexes": [
            {"columns": ["usuario_id"], "name": "idx_usuario"},
            {"columns": ["accion"],     "name": "idx_accion"},
            {"columns": ["modulo"],     "name": "idx_modulo"},
            {"columns": ["created_at"], "name": "idx_fecha"},
        ],
    },
    {
        "name": "roles_rutas",
        "columns": [
            {"name": "rol",  "type": "varchar(50)",  "not_null": True},
            {"name": "ruta", "type": "varchar(255)", "not_null": True},
        ],
        "primary_key": ["rol", "ruta"],
    },
]


# ============================================================================
# DEFINICION DE TABLAS — WMS DATABASE
# ============================================================================

WMS_TABLES = [
    {
        "name": "zonas",
        "columns": [
            {"name": "id",         "type": "int",          "pk": True, "autoincrement": True},
            {"name": "codigo",     "type": "varchar(20)",  "not_null": True},
            {"name": "nombre",     "type": "varchar(100)", "not_null": True},
            {"name": "descripcion","type": "text"},
            {"name": "activo",     "type": "boolean", "not_null": True, "default": True},
            {"name": "tenant_id",  "type": "int"},
            {"name": "created_at", "type": "datetime", "not_null": True, "default": "CURRENT_TIMESTAMP"},
        ],
        "indexes": [
            {"columns": ["codigo"],    "name": "uk_zona_codigo", "unique": True},
            {"columns": ["activo"],    "name": "idx_zona_activo"},
            {"columns": ["tenant_id"], "name": "idx_zonas_tenant"},
        ],
    },
    {
        "name": "tipoubicacion",
        "columns": [
            {"name": "id",              "type": "int",          "pk": True, "autoincrement": True},
            {"name": "descripcion",     "type": "varchar(100)", "not_null": True},
            {"name": "operacion",       "type": "char(1)"},
            {"name": "soporte_picking", "type": "boolean", "not_null": True, "default": False},
            {"name": "tenant_id",       "type": "int"},
        ],
        "indexes": [
            {"columns": ["tenant_id"], "name": "idx_tipoubicacion_tenant"},
        ],
    },
    {
        "name": "categorias",
        "columns": [
            {"name": "id_categoria", "type": "int",          "pk": True, "autoincrement": True},
            {"name": "codigo",       "type": "varchar(50)",  "unique": True},
            {"name": "nombre",       "type": "varchar(100)", "not_null": True},
            {"name": "descripcion",  "type": "text"},
            {"name": "activo",       "type": "boolean", "not_null": True, "default": True},
            {"name": "tenant_id",    "type": "int"},
            {"name": "created_at",   "type": "datetime", "not_null": True, "default": "CURRENT_TIMESTAMP"},
        ],
        "indexes": [
            {"columns": ["tenant_id"], "name": "idx_categorias_tenant"},
        ],
    },
    {
        "name": "proveedores",
        "columns": [
            {"name": "id",          "type": "int",           "pk": True, "autoincrement": True},
            {"name": "codigo",      "type": "varchar(50)",   "unique": True},
            {"name": "razonsocial", "type": "varchar(200)",  "not_null": True},
            {"name": "cuit",        "type": "varchar(50)"},
            {"name": "direccion",   "type": "varchar(255)"},
            {"name": "telefono",    "type": "varchar(50)"},
            {"name": "email",       "type": "varchar(100)"},
            {"name": "activo",      "type": "boolean", "not_null": True, "default": True},
            {"name": "tenant_id",   "type": "int"},
            {"name": "created_at",  "type": "datetime", "not_null": True, "default": "CURRENT_TIMESTAMP"},
        ],
        "indexes": [
            {"columns": ["tenant_id"], "name": "idx_proveedores_tenant"},
        ],
    },
    {
        "name": "rutas",
        "columns": [
            {"name": "id_ruta",     "type": "int",          "pk": True, "autoincrement": True},
            {"name": "nombre_ruta", "type": "varchar(100)", "not_null": True},
            {"name": "descripcion", "type": "text"},
            {"name": "tenant_id",   "type": "int"},
        ],
        "indexes": [
            {"columns": ["tenant_id"], "name": "idx_rutas_tenant"},
        ],
    },
    {
        "name": "unidades_medida",
        "columns": [
            {"name": "id_unidad",              "type": "int",           "pk": True, "autoincrement": True},
            {"name": "codigo",                 "type": "varchar(50)",   "not_null": True},
            {"name": "nombre",                 "type": "varchar(100)",  "not_null": True},
            {"name": "simbolo",                "type": "varchar(20)"},
            {"name": "tipo_magnitud",          "type": "varchar(50)",   "default": "'CANTIDAD'"},
            {"name": "conversion_a_base",      "type": "decimal(12,4)", "default": 1.0},
            {"name": "unidad_base_referencia", "type": "varchar(10)",   "default": "'U'"},
            {"name": "decimales_permitidos",   "type": "int",           "default": 0},
            {"name": "activo",                 "type": "boolean", "not_null": True, "default": True},
            {"name": "tenant_id",              "type": "int"},
        ],
        "indexes": [
            {"columns": ["tenant_id"], "name": "idx_unidades_tenant"},
        ],
    },
    {
        "name": "ubicaciones",
        "columns": [
            {"name": "id",                 "type": "int",           "pk": True, "autoincrement": True},
            {"name": "codigo",             "type": "varchar(50)",   "not_null": True, "unique": True},
            {"name": "nombre",             "type": "varchar(100)"},
            {"name": "descipcion",         "type": "varchar(200)"},
            {"name": "tipoubicacion",      "type": "int"},
            {"name": "zona",               "type": "varchar(50)"},
            {"name": "id_zona",            "type": "int"},
            {"name": "pasillo",            "type": "varchar(20)"},
            {"name": "estante",            "type": "varchar(20)"},
            {"name": "nivel",              "type": "varchar(20)"},
            {"name": "posicion",           "type": "varchar(20)"},
            {"name": "coordenadaA",        "type": "varchar(20)"},
            {"name": "coordenadaB",        "type": "varchar(20)"},
            {"name": "coordenadaC",        "type": "varchar(20)"},
            {"name": "coordenadaD",        "type": "varchar(20)"},
            {"name": "capacidad_maxima",   "type": "int", "not_null": True, "default": 0},
            {"name": "ocupado",            "type": "int", "not_null": True, "default": 0},
            {"name": "disponible_entrada", "type": "boolean", "not_null": True, "default": True},
            {"name": "disponible_salida",  "type": "boolean", "not_null": True, "default": True},
            {"name": "orden_picking",      "type": "int", "not_null": True, "default": 0},
            {"name": "activo",             "type": "boolean", "not_null": True, "default": True},
            {"name": "tenant_id",          "type": "int"},
            {"name": "created_at",         "type": "datetime", "not_null": True, "default": "CURRENT_TIMESTAMP"},
        ],
        "indexes": [
            {"columns": ["tenant_id"],     "name": "idx_ubicaciones_tenant"},
            {"columns": ["id_zona"],       "name": "idx_ubi_zona"},
            {"columns": ["tipoubicacion"], "name": "idx_ubi_tipo"},
        ],
        "foreign_keys": [
            {"columns": ["id_zona"], "ref_table": "zonas", "ref_columns": ["id"],
             "on_update": "CASCADE", "on_delete": "SET NULL"},
        ],
    },
    {
        "name": "transportes",
        "columns": [
            {"name": "id_transporte",    "type": "int",          "pk": True, "autoincrement": True},
            {"name": "codigo",           "type": "varchar(100)", "unique": True},
            {"name": "razonsocial",      "type": "varchar(200)", "not_null": True},
            {"name": "cuit",             "type": "varchar(50)"},
            {"name": "telefono",         "type": "varchar(50)"},
            {"name": "email",            "type": "varchar(100)"},
            {"name": "activo",           "type": "boolean", "not_null": True, "default": True},
            {"name": "id_muelle_salida", "type": "int"},
            {"name": "tenant_id",        "type": "int"},
        ],
        "indexes": [
            {"columns": ["tenant_id"], "name": "idx_transportes_tenant"},
        ],
        "foreign_keys": [
            {"columns": ["id_muelle_salida"], "ref_table": "ubicaciones", "ref_columns": ["id"]},
        ],
    },
    {
        "name": "transporte_rutas",
        "columns": [
            {"name": "id_transporte", "type": "int",  "not_null": True},
            {"name": "id_ruta",       "type": "int",  "not_null": True},
            {"name": "observaciones", "type": "text"},
        ],
        "primary_key": ["id_transporte", "id_ruta"],
        "foreign_keys": [
            {"columns": ["id_transporte"], "ref_table": "transportes", "ref_columns": ["id_transporte"], "on_delete": "CASCADE"},
            {"columns": ["id_ruta"],       "ref_table": "rutas",       "ref_columns": ["id_ruta"],       "on_delete": "CASCADE"},
        ],
    },
    {
        "name": "clientes",
        "columns": [
            {"name": "id_cliente",                   "type": "int",          "pk": True, "autoincrement": True},
            {"name": "codigo",                       "type": "varchar(100)", "unique": True},
            {"name": "razonsocial",                  "type": "varchar(200)", "not_null": True},
            {"name": "cuit",                         "type": "varchar(50)"},
            {"name": "direccion",                    "type": "varchar(255)"},
            {"name": "localidad",                    "type": "varchar(100)"},
            {"name": "provincia",                    "type": "varchar(100)"},
            {"name": "telefono",                     "type": "varchar(50)"},
            {"name": "email",                        "type": "varchar(100)"},
            {"name": "contacto_nombre",              "type": "varchar(100)"},
            {"name": "id_ruta",                      "type": "int"},
            {"name": "id_transporte_predeterminado", "type": "int"},
            {"name": "activo",                       "type": "boolean", "not_null": True, "default": True},
            {"name": "tenant_id",                    "type": "int"},
        ],
        "indexes": [
            {"columns": ["tenant_id"], "name": "idx_clientes_tenant"},
        ],
        "foreign_keys": [
            {"columns": ["id_ruta"],                      "ref_table": "rutas",       "ref_columns": ["id_ruta"],       "on_delete": "SET NULL", "on_update": "CASCADE"},
            {"columns": ["id_transporte_predeterminado"], "ref_table": "transportes", "ref_columns": ["id_transporte"], "on_delete": "SET NULL", "on_update": "CASCADE"},
        ],
    },
    {
        "name": "materiales",
        "columns": [
            {"name": "id",               "type": "int",           "pk": True, "autoincrement": True},
            {"name": "codigo",           "type": "varchar(100)",  "not_null": True, "unique": True},
            {"name": "codigo_barras",    "type": "varchar(100)"},
            {"name": "nombre",           "type": "varchar(255)",  "not_null": True},
            {"name": "descripcion",      "type": "text"},
            {"name": "categoria_id",     "type": "int"},
            {"name": "stock_minimo",     "type": "decimal(12,3)", "default": 0},
            {"name": "stock_maximo",     "type": "decimal(12,3)", "default": 0},
            {"name": "unidad_medida_id", "type": "int"},
            {"name": "trazabilidad",     "type": "enum('ninguna','lote','serie')", "not_null": True, "default": "'ninguna'"},
            {"name": "peso_bruto",       "type": "decimal(10,3)"},
            {"name": "peso_neto",        "type": "decimal(10,3)"},
            {"name": "costo_promedio",   "type": "decimal(12,4)", "default": 0},
            {"name": "ultimo_costo",     "type": "decimal(12,4)", "default": 0},
            {"name": "activo",           "type": "boolean", "not_null": True, "default": True},
            {"name": "tenant_id",        "type": "int"},
            {"name": "created_at",       "type": "datetime", "not_null": True, "default": "CURRENT_TIMESTAMP"},
            {"name": "updated_at",       "type": "datetime", "not_null": True, "default": "CURRENT_TIMESTAMP_ON_UPDATE"},
        ],
        "indexes": [
            {"columns": ["tenant_id"],     "name": "idx_materiales_tenant"},
            {"columns": ["categoria_id"],  "name": "idx_mat_categoria"},
            {"columns": ["codigo_barras"], "name": "idx_mat_codigo_barras"},
        ],
        "foreign_keys": [
            {"columns": ["categoria_id"], "ref_table": "categorias", "ref_columns": ["id_categoria"],
             "on_delete": "SET NULL", "on_update": "CASCADE"},
        ],
    },
    {
        "name": "material_proveedor",
        "columns": [
            {"name": "id_material",            "type": "int",          "not_null": True},
            {"name": "id_proveedor",           "type": "int",          "not_null": True},
            {"name": "codigo_referencia_prov", "type": "varchar(100)"},
            {"name": "es_habitual",            "type": "boolean", "not_null": True, "default": False},
            {"name": "tenant_id",              "type": "int"},
        ],
        "primary_key": ["id_material", "id_proveedor"],
        "indexes": [
            {"columns": ["tenant_id"], "name": "idx_matprov_tenant"},
        ],
        "foreign_keys": [
            {"columns": ["id_material"],  "ref_table": "materiales",  "ref_columns": ["id"],         "on_delete": "CASCADE", "on_update": "CASCADE"},
            {"columns": ["id_proveedor"], "ref_table": "proveedores", "ref_columns": ["id"],         "on_delete": "CASCADE", "on_update": "CASCADE"},
        ],
    },
    {
        "name": "material_presentaciones",
        "columns": [
            {"name": "id",                "type": "int",           "pk": True, "autoincrement": True},
            {"name": "id_material",       "type": "int",           "not_null": True},
            {"name": "nombre",            "type": "varchar(100)",  "not_null": True},
            {"name": "codigo_barras",     "type": "varchar(20)"},
            {"name": "cantidad_unidades", "type": "decimal(10,3)", "not_null": True, "default": 1.0},
            {"name": "peso_bruto",        "type": "decimal(10,3)"},
            {"name": "peso_neto",         "type": "decimal(10,3)"},
            {"name": "activo",            "type": "boolean", "not_null": True, "default": True},
            {"name": "tenant_id",         "type": "int"},
        ],
        "indexes": [
            {"columns": ["codigo_barras"], "name": "uq_pres_barcode", "unique": True},
            {"columns": ["tenant_id"],     "name": "idx_matpres_tenant"},
        ],
        "foreign_keys": [
            {"columns": ["id_material"], "ref_table": "materiales", "ref_columns": ["id"], "on_delete": "CASCADE"},
        ],
    },
    {
        "name": "stockcontable",
        "columns": [
            {"name": "ID",               "type": "int",           "pk": True, "autoincrement": True},
            {"name": "Ubicacion",        "type": "int",           "not_null": True},
            {"name": "Material",         "type": "int",           "not_null": True},
            {"name": "Lote",             "type": "varchar(100)",  "not_null": True, "default": "'UNICO'"},
            {"name": "TipoStock",        "type": "enum('Libre Venta','Calidad','Bloqueado','Mal Estado')",
                                         "not_null": True, "default": "'Libre Venta'"},
            {"name": "UltimaEntrada",    "type": "datetime"},
            {"name": "UltimaSalida",     "type": "datetime"},
            {"name": "UltimoMovimiento", "type": "datetime"},
            {"name": "UsuarioUltimoMov", "type": "varchar(100)"},
            {"name": "FechaVencimiento", "type": "date"},
            {"name": "StockTotal",       "type": "decimal(15,4)", "not_null": True, "default": 0},
            {"name": "StockDisponible",  "type": "decimal(15,4)", "not_null": True, "default": 0},
            {"name": "StockEntrando",    "type": "decimal(15,4)", "not_null": True, "default": 0},
            {"name": "StockSaliendo",    "type": "decimal(15,4)", "not_null": True, "default": 0},
            {"name": "IDContenedor",     "type": "varchar(10)",   "not_null": True},
            {"name": "tenant_id",        "type": "int"},
            {"name": "created_at",       "type": "datetime", "not_null": True, "default": "CURRENT_TIMESTAMP"},
            {"name": "updated_at",       "type": "datetime", "not_null": True, "default": "CURRENT_TIMESTAMP_ON_UPDATE"},
        ],
        "indexes": [
            {"columns": ["Ubicacion", "Material", "IDContenedor"], "name": "uq_stock_pos", "unique": True},
            {"columns": ["Material"],      "name": "idx_material"},
            {"columns": ["Ubicacion"],     "name": "idx_ubicacion"},
            {"columns": ["Lote"],          "name": "idx_lote"},
            {"columns": ["TipoStock"],     "name": "idx_tipo_stock"},
            {"columns": ["IDContenedor"],  "name": "idx_contenedor"},
            {"columns": ["tenant_id"],     "name": "idx_stockcontable_tenant"},
        ],
        "foreign_keys": [
            {"columns": ["Ubicacion"], "ref_table": "ubicaciones", "ref_columns": ["id"],
             "on_delete": "RESTRICT", "on_update": "CASCADE"},
            {"columns": ["Material"],  "ref_table": "materiales",  "ref_columns": ["id"],
             "on_delete": "RESTRICT", "on_update": "CASCADE"},
        ],
    },
    {
        "name": "clases_pedido",
        "columns": [
            {"name": "id_clase", "type": "int",          "pk": True, "autoincrement": True},
            {"name": "nombre",   "type": "varchar(100)", "not_null": True},
            {"name": "activo",   "type": "boolean", "not_null": True, "default": True},
            {"name": "tenant_id","type": "int"},
        ],
        "indexes": [
            {"columns": ["tenant_id"], "name": "idx_clases_pedido_tenant"},
        ],
    },
    {
        "name": "recepciones_cabecera",
        "columns": [
            {"name": "id_recepcion",         "type": "int",          "pk": True, "autoincrement": True},
            {"name": "numero",               "type": "varchar(20)",  "not_null": True},
            {"name": "id_proveedor",         "type": "int",          "not_null": True},
            {"name": "estado",               "type": "enum('Abierta','Cerrada','Confirmada','Anulada')",
                                             "not_null": True, "default": "'Abierta'"},
            {"name": "id_contenedor",        "type": "varchar(10)",  "not_null": True},
            {"name": "id_ubicacion_recep",   "type": "int",          "not_null": True},
            {"name": "id_ubicacion_destino", "type": "int"},
            {"name": "observaciones",        "type": "text"},
            {"name": "fecha_recepcion",      "type": "datetime",     "not_null": True, "default": "CURRENT_TIMESTAMP"},
            {"name": "fecha_cierre",         "type": "datetime"},
            {"name": "usuario_creacion",     "type": "varchar(100)", "not_null": True},
            {"name": "usuario_cierre",       "type": "varchar(100)"},
            {"name": "tenant_id",            "type": "int"},
            {"name": "created_at",           "type": "datetime",     "not_null": True, "default": "CURRENT_TIMESTAMP"},
            {"name": "updated_at",           "type": "datetime",     "not_null": True, "default": "CURRENT_TIMESTAMP_ON_UPDATE"},
        ],
        "indexes": [
            {"columns": ["numero"],              "name": "uq_recepcion_numero", "unique": True},
            {"columns": ["id_proveedor"],        "name": "idx_rec_proveedor"},
            {"columns": ["estado"],              "name": "idx_rec_estado"},
            {"columns": ["id_contenedor"],       "name": "idx_rec_contenedor"},
            {"columns": ["id_ubicacion_recep"],  "name": "idx_rec_ubicrec"},
            {"columns": ["id_ubicacion_destino"],"name": "idx_rec_ubicdest"},
            {"columns": ["fecha_recepcion"],     "name": "idx_rec_fecha"},
            {"columns": ["tenant_id"],           "name": "idx_recepciones_cab_tenant"},
        ],
        "foreign_keys": [
            {"columns": ["id_proveedor"],         "ref_table": "proveedores",  "ref_columns": ["id"],
             "on_delete": "RESTRICT", "on_update": "CASCADE"},
            {"columns": ["id_ubicacion_recep"],   "ref_table": "ubicaciones",  "ref_columns": ["id"],
             "on_delete": "RESTRICT", "on_update": "CASCADE"},
            {"columns": ["id_ubicacion_destino"], "ref_table": "ubicaciones",  "ref_columns": ["id"],
             "on_delete": "RESTRICT", "on_update": "CASCADE"},
        ],
    },
    {
        "name": "recepciones_detalle",
        "columns": [
            {"name": "id_detalle",        "type": "int",           "pk": True, "autoincrement": True},
            {"name": "id_recepcion",      "type": "int",           "not_null": True},
            {"name": "id_material",       "type": "int",           "not_null": True},
            {"name": "lote",              "type": "varchar(100)",  "not_null": True, "default": "'UNICO'"},
            {"name": "fecha_vencimiento", "type": "date"},
            {"name": "cantidad_esperada", "type": "decimal(15,4)", "not_null": True, "default": 0},
            {"name": "cantidad_recibida", "type": "decimal(15,4)", "not_null": True, "default": 0},
            {"name": "tipo_stock",        "type": "enum('Libre Venta','Calidad','Bloqueado','Mal Estado')",
                                          "not_null": True, "default": "'Libre Venta'"},
            {"name": "observaciones",     "type": "text"},
            {"name": "tenant_id",         "type": "int"},
            {"name": "created_at",        "type": "datetime", "not_null": True, "default": "CURRENT_TIMESTAMP"},
            {"name": "updated_at",        "type": "datetime", "not_null": True, "default": "CURRENT_TIMESTAMP_ON_UPDATE"},
        ],
        "indexes": [
            {"columns": ["id_recepcion", "id_material", "lote", "tipo_stock"], "name": "uq_det_recep_mat_lote", "unique": True},
            {"columns": ["id_recepcion"], "name": "idx_det_recepcion"},
            {"columns": ["id_material"],  "name": "idx_det_material"},
            {"columns": ["lote"],         "name": "idx_det_lote"},
            {"columns": ["tenant_id"],    "name": "idx_recepciones_det_tenant"},
        ],
        "foreign_keys": [
            {"columns": ["id_recepcion"], "ref_table": "recepciones_cabecera", "ref_columns": ["id_recepcion"],
             "on_delete": "CASCADE", "on_update": "CASCADE"},
            {"columns": ["id_material"],  "ref_table": "materiales",           "ref_columns": ["id"],
             "on_delete": "RESTRICT", "on_update": "CASCADE"},
        ],
    },
    {
        "name": "pedidos_cabecera",
        "columns": [
            {"name": "id_pedido",         "type": "int",          "pk": True, "autoincrement": True},
            {"name": "nro_pedido",        "type": "varchar(20)",  "not_null": True},
            {"name": "id_cliente",        "type": "int",          "not_null": True},
            {"name": "id_clase",          "type": "int"},
            {"name": "fecha_pedido",      "type": "date",         "not_null": True},
            {"name": "id_ruta",           "type": "int"},
            {"name": "id_transporte",     "type": "int"},
            {"name": "direccion_entrega", "type": "varchar(255)"},
            {"name": "observaciones",     "type": "text"},
            {"name": "estado",            "type": "varchar(50)",  "not_null": True, "default": "'Pendiente'"},
            {"name": "fecha_despacho",    "type": "datetime"},
            {"name": "tenant_id",         "type": "int"},
            {"name": "created_at",        "type": "datetime", "not_null": True, "default": "CURRENT_TIMESTAMP"},
            {"name": "updated_at",        "type": "datetime", "not_null": True, "default": "CURRENT_TIMESTAMP_ON_UPDATE"},
        ],
        "indexes": [
            {"columns": ["nro_pedido"],  "name": "uq_pedido_nro", "unique": True},
            {"columns": ["id_cliente"],  "name": "idx_pedido_cliente"},
            {"columns": ["estado"],      "name": "idx_pedido_estado"},
            {"columns": ["fecha_pedido"],"name": "idx_pedido_fecha"},
            {"columns": ["tenant_id"],   "name": "idx_pedidos_cab_tenant"},
        ],
        "foreign_keys": [
            {"columns": ["id_cliente"],    "ref_table": "clientes",    "ref_columns": ["id_cliente"],
             "on_delete": "RESTRICT", "on_update": "CASCADE"},
            {"columns": ["id_clase"],      "ref_table": "clases_pedido","ref_columns": ["id_clase"],
             "on_delete": "SET NULL", "on_update": "CASCADE"},
            {"columns": ["id_ruta"],       "ref_table": "rutas",       "ref_columns": ["id_ruta"],
             "on_delete": "SET NULL", "on_update": "CASCADE"},
            {"columns": ["id_transporte"], "ref_table": "transportes", "ref_columns": ["id_transporte"],
             "on_delete": "SET NULL", "on_update": "CASCADE"},
        ],
    },
    {
        "name": "pedidos_detalle",
        "columns": [
            {"name": "id_detalle",        "type": "int",           "pk": True, "autoincrement": True},
            {"name": "id_pedido",         "type": "int",           "not_null": True},
            {"name": "id_material",       "type": "int",           "not_null": True},
            {"name": "cantidad",          "type": "decimal(15,4)", "not_null": True, "default": 0},
            {"name": "Cantidad_preparada","type": "decimal(10,2)", "not_null": True, "default": 0},
            {"name": "tipo_stock",        "type": "varchar(20)",   "not_null": True, "default": "'Libre Venta'"},
            {"name": "tenant_id",         "type": "int"},
            {"name": "created_at",        "type": "datetime", "not_null": True, "default": "CURRENT_TIMESTAMP"},
            {"name": "updated_at",        "type": "datetime", "not_null": True, "default": "CURRENT_TIMESTAMP_ON_UPDATE"},
        ],
        "indexes": [
            {"columns": ["id_pedido"],  "name": "idx_pd_pedido"},
            {"columns": ["id_material"], "name": "idx_pd_material"},
            {"columns": ["tenant_id"],  "name": "idx_pedidos_det_tenant"},
        ],
        "foreign_keys": [
            {"columns": ["id_pedido"],   "ref_table": "pedidos_cabecera", "ref_columns": ["id_pedido"],
             "on_delete": "CASCADE", "on_update": "CASCADE"},
            {"columns": ["id_material"], "ref_table": "materiales",       "ref_columns": ["id"],
             "on_delete": "RESTRICT", "on_update": "CASCADE"},
        ],
    },
    {
        "name": "omc",
        "columns": [
            {"name": "id_omc",                "type": "int",          "pk": True, "autoincrement": True},
            {"name": "numero",                "type": "varchar(20)",  "not_null": True},
            {"name": "id_contenedor",         "type": "varchar(20)"},
            {"name": "id_contenedor_destino", "type": "varchar(20)"},
            {"name": "id_ubicacion_origen",   "type": "int"},
            {"name": "id_ubicacion_destino",  "type": "int",          "not_null": True},
            {"name": "id_recepcion",          "type": "int"},
            {"name": "id_pedido",             "type": "int"},
            {"name": "estado",                "type": "enum('Pendiente','Confirmada','Anulada')",
                                              "not_null": True, "default": "'Pendiente'"},
            {"name": "observaciones",         "type": "text"},
            {"name": "fecha_creacion",        "type": "datetime",     "not_null": True, "default": "CURRENT_TIMESTAMP"},
            {"name": "fecha_confirmacion",    "type": "datetime"},
            {"name": "fecha_anulacion",       "type": "datetime"},
            {"name": "usuario_creacion",      "type": "varchar(100)", "not_null": True},
            {"name": "usuario_confirmacion",  "type": "varchar(100)"},
            {"name": "usuario_anulacion",     "type": "varchar(100)"},
            {"name": "tenant_id",             "type": "int"},
            {"name": "created_at",            "type": "datetime",     "not_null": True, "default": "CURRENT_TIMESTAMP"},
            {"name": "updated_at",            "type": "datetime",     "not_null": True, "default": "CURRENT_TIMESTAMP_ON_UPDATE"},
        ],
        "indexes": [
            {"columns": ["numero"],               "name": "uq_omc_numero", "unique": True},
            {"columns": ["id_contenedor"],        "name": "idx_omc_contenedor"},
            {"columns": ["id_ubicacion_origen"],  "name": "idx_omc_origen"},
            {"columns": ["id_ubicacion_destino"], "name": "idx_omc_destino"},
            {"columns": ["estado"],               "name": "idx_omc_estado"},
            {"columns": ["id_recepcion"],         "name": "idx_omc_recepcion"},
            {"columns": ["id_pedido"],            "name": "idx_omc_pedido"},
            {"columns": ["tenant_id"],            "name": "idx_omc_tenant"},
        ],
        "foreign_keys": [
            {"columns": ["id_ubicacion_origen"],  "ref_table": "ubicaciones",            "ref_columns": ["id"],
             "on_delete": "RESTRICT", "on_update": "CASCADE"},
            {"columns": ["id_ubicacion_destino"], "ref_table": "ubicaciones",            "ref_columns": ["id"],
             "on_delete": "RESTRICT", "on_update": "CASCADE"},
            {"columns": ["id_recepcion"],         "ref_table": "recepciones_cabecera",   "ref_columns": ["id_recepcion"],
             "on_delete": "SET NULL", "on_update": "CASCADE"},
            {"columns": ["id_pedido"],            "ref_table": "pedidos_cabecera",       "ref_columns": ["id_pedido"],
             "on_delete": "SET NULL", "on_update": "CASCADE"},
        ],
    },
    {
        "name": "omc_contenedores",
        "columns": [
            {"name": "id",                    "type": "int",          "pk": True, "autoincrement": True},
            {"name": "id_omc",                "type": "int",          "not_null": True},
            {"name": "id_contenedor",         "type": "varchar(20)",  "not_null": True},
            {"name": "id_contenedor_destino", "type": "varchar(20)"},
            {"name": "id_ubicacion_origen",   "type": "int",          "not_null": True},
            {"name": "tenant_id",             "type": "int"},
        ],
        "indexes": [
            {"columns": ["tenant_id"], "name": "idx_omc_cont_tenant"},
        ],
        "foreign_keys": [
            {"columns": ["id_omc"],              "ref_table": "omc",         "ref_columns": ["id_omc"],
             "on_delete": "CASCADE", "on_update": "CASCADE"},
            {"columns": ["id_ubicacion_origen"], "ref_table": "ubicaciones", "ref_columns": ["id"],
             "on_delete": "RESTRICT", "on_update": "CASCADE"},
        ],
    },
    {
        "name": "inventarios_cabecera",
        "columns": [
            {"name": "id",               "type": "int",          "pk": True, "autoincrement": True},
            {"name": "numero",           "type": "varchar(20)",  "not_null": True, "unique": True},
            {"name": "descripcion",      "type": "varchar(200)"},
            {"name": "estado",           "type": "enum('Abierto','Cerrado','Anulado')", "default": "'Abierto'"},
            {"name": "fecha_creacion",   "type": "datetime",     "default": "CURRENT_TIMESTAMP"},
            {"name": "usuario_creacion", "type": "varchar(100)"},
            {"name": "fecha_cierre",     "type": "datetime"},
            {"name": "usuario_cierre",   "type": "varchar(100)"},
            {"name": "fecha_anulacion",  "type": "datetime"},
            {"name": "usuario_anulacion","type": "varchar(100)"},
            {"name": "tenant_id",        "type": "int"},
        ],
        "indexes": [
            {"columns": ["tenant_id"], "name": "idx_inventarios_cab_tenant"},
        ],
    },
    {
        "name": "inventarios_detalle",
        "columns": [
            {"name": "id",             "type": "int",          "pk": True, "autoincrement": True},
            {"name": "id_inventario",  "type": "int",          "not_null": True},
            {"name": "id_ubicacion",   "type": "int",          "not_null": True},
            {"name": "id_material",    "type": "int",          "not_null": True},
            {"name": "id_contenedor",  "type": "varchar(20)",  "default": "''"},
            {"name": "lote",           "type": "varchar(100)", "default": "'UNICO'"},
            {"name": "tipo_stock",     "type": "varchar(50)",  "default": "'Libre Venta'"},
            {"name": "stock_sistema",  "type": "decimal(15,3)","default": 0},
            {"name": "stock_contado",  "type": "decimal(15,3)"},
            {"name": "fecha_conteo",   "type": "datetime"},
            {"name": "usuario_conteo", "type": "varchar(100)"},
            {"name": "tenant_id",      "type": "int"},
        ],
        "indexes": [
            {"columns": ["tenant_id"], "name": "idx_inventarios_det_tenant"},
        ],
        "foreign_keys": [
            {"columns": ["id_inventario"], "ref_table": "inventarios_cabecera", "ref_columns": ["id"],
             "on_delete": "CASCADE"},
        ],
    },
]


# ============================================================================
# SEED DATA
# ============================================================================

ADMIN_SEEDS = [
    {
        "table": "tenants",
        "rows": [
            {"id": 1, "codigo": "DEFAULT", "nombre": "Empresa Principal",
             "razon_social": "Empresa Principal S.A.", "activo": True,
             "nombredelalmacen": "Almacen Principal", "metodosdepicking": '"fifo"',
             "bajostock": 0, "dias_filtro_fechas": 30},
        ],
    },
    {
        "table": "admin_usuarios",
        "comment": "SuperAdmin password: Admin@2024!",
        "rows": [
            {"username": "admin", "password_hash": "scrypt:32768:8:1$WQ6PhKOf81VV3FcH$ed1ca47fd1fd381583f0289acf9e839521b5e74a07adfc034382ea5342d608e393b7143fec95b3aef262f1946f95696e3e8acbfc867c91769d63142d4e4a5db2",
             "nombre": "Administrador", "email": "admin@taurus.local", "rol": "SUPERADMIN"},
        ],
    },
    {
        "table": "usuarios",
        "comment": "Operador password: Admin@2024!",
        "rows": [
            {"username": "operador", "password_hash": "scrypt:32768:8:1$WQ6PhKOf81VV3FcH$ed1ca47fd1fd381583f0289acf9e839521b5e74a07adfc034382ea5342d608e393b7143fec95b3aef262f1946f95696e3e8acbfc867c91769d63142d4e4a5db2",
             "nombre": "Operador General", "email": "operador@taurus.local",
             "rol": "OPERADOR", "tenant_id": 1, "activo": True},
        ],
    },
    {
        "table": "configuracion",
        "rows": [
            {"clave": "app_version",  "valor": "1.0.0",      "descripcion": "Version actual de la aplicacion"},
            {"clave": "app_name",     "valor": "Taurus WMS", "descripcion": "Nombre de la aplicacion"},
            {"clave": "mantenimiento","valor": "false",       "descripcion": "Modo mantenimiento (true/false)"},
            {"clave": "DB_HOST",      "valor": "localhost",   "descripcion": "Host del servidor de base de datos"},
            {"clave": "DB_PORT",      "valor": "3306",        "descripcion": "Puerto del servidor MySQL"},
            {"clave": "DB_NAME",      "valor": "taurus_wms",  "descripcion": "Nombre de la base de datos principal"},
            {"clave": "DB_USER",      "valor": "taurus",      "descripcion": "Usuario de la base de datos"},
            {"clave": "DB_PASSWORD",  "valor": "Taurus_2001", "descripcion": "Contrasena de la base de datos"},
            {"clave": "DB_CHAR_SET",  "valor": "utf8mb4",     "descripcion": "Charset de la base de datos"},
            {"clave": "DB_ENGINE",    "valor": "mysql",       "descripcion": "Motor de BD: mysql, postgresql, sqlite"},
        ],
    },
    {
        "table": "roles_rutas",
        "comment": "Permisos de rutas por rol",
        "rows": [
            # ADMIN: acceso total
            {"rol": "ADMIN", "ruta": "*"},
            # OPERADOR: rutas operativas
            *[{  "rol": "OPERADOR", "ruta": r} for r in [
                "/materiales", "/materiales/guardar", "/materiales/eliminar",
                "/materiales/importar", "/materiales/exportar", "/materiales/plantilla",
                "/ubicaciones", "/ubicaciones/guardar", "/ubicaciones/importar",
                "/ubicaciones/exportar", "/ubicaciones/plantilla",
                "/tipoubicacion", "/tipoubicacion/guardar", "/tipoubicacion/eliminar",
                "/tipoubicacion/importar", "/tipoubicacion/exportar", "/tipoubicacion/plantilla",
                "/proveedores", "/proveedores/guardar", "/proveedores/eliminar",
                "/proveedores/importar", "/proveedores/exportar", "/proveedores/plantilla",
                "/clientes", "/clientes/guardar", "/clientes/importar",
                "/clientes/exportar", "/clientes/plantilla",
                "/categorias", "/categorias/guardar", "/categorias/eliminar",
                "/unidades", "/unidades/guardar", "/unidades/eliminar",
                "/unidades/importar", "/unidades/exportar", "/unidades/plantilla",
                "/transportes", "/transportes/guardar",
                "/transportes/importar", "/transportes/exportar", "/transportes/plantilla",
                "/rutas", "/rutas/guardar", "/rutas/eliminar",
                "/rutas/importar", "/rutas/exportar", "/rutas/plantilla",
                "/pedidos", "/pedidos/nuevo", "/pedidos/editar", "/pedidos/guardar",
                "/pedidos/eliminar", "/pedidos/importar", "/pedidos/plantilla",
                "/pedidos/picking_json",
                "/recepciones", "/recepciones/nueva", "/recepciones/guardar",
                "/recepciones/ver", "/recepciones/cerrar", "/recepciones/eliminar",
                "/recepciones/importar", "/recepciones/plantilla",
                "/recepciones/guardar_item", "/recepciones/eliminar_item",
                "/recepciones/confirmar_stock", "/recepciones/anular",
                "/omc", "/omc/nueva", "/omc/guardar", "/omc/ver",
                "/despacho", "/despacho/despachar", "/despacho/despachar_masivo",
                "/stockcontable", "/stockcontable/editar",
                "/stockcontable/importar", "/stockcontable/exportar", "/stockcontable/plantilla",
                "/inventario", "/inventario/crear", "/inventario/*",
                "/parametros", "/actualizar_parametros",
            ]],
            # CONSULTA: solo lectura
            *[{  "rol": "CONSULTA", "ruta": r} for r in [
                "/materiales", "/ubicaciones", "/tipoubicacion", "/proveedores",
                "/clientes", "/categorias", "/unidades", "/transportes", "/rutas",
                "/pedidos", "/recepciones", "/omc", "/despacho",
                "/stockcontable", "/inventario", "/parametros",
            ]],
        ],
    },
]

WMS_SEEDS = [
    {
        "table": "clases_pedido",
        "rows": [
            {"nombre": "Venta",      "activo": True},
            {"nombre": "Reposicion", "activo": True},
            {"nombre": "Muestra",    "activo": True},
            {"nombre": "Devolucion", "activo": True},
        ],
    },
]


# ============================================================================
# GENERADOR DE DDL
# ============================================================================

class DDLEngine:
    """Base class for DDL generation."""

    def __init__(self):
        self.statements = []

    def reset(self):
        self.statements = []

    def add(self, sql):
        self.statements.append(sql.rstrip(";") + ";")

    def add_comment(self, text):
        self.add(f"-- {text}")

    def add_blank(self):
        self.statements.append("")

    def header(self, db_name):
        pass

    def footer(self):
        pass

    def create_database(self, db_name):
        pass

    def drop_database(self, db_name):
        pass

    def use_database(self, db_name):
        pass

    def translate_type(self, col_type):
        return col_type

    def column_def(self, col):
        parts = [self.quote_identifier(col["name"])]
        parts.append(self.translate_type(col["type"]))
        if col.get("pk") and col.get("autoincrement"):
            parts.append(self.autoincrement_clause())
        elif col.get("pk"):
            parts.append("PRIMARY KEY")
        if col.get("not_null") and not (col.get("pk") and col.get("autoincrement")):
            parts.append("NOT NULL")
        if "default" in col:
            parts.append(self.default_clause(col["default"]))
        return " ".join(parts)

    def autoincrement_clause(self):
        return "AUTO_INCREMENT"

    def default_clause(self, default):
        if default is True:
            return "DEFAULT TRUE"
        if default is False:
            return "DEFAULT FALSE"
        if default == "CURRENT_TIMESTAMP":
            return "DEFAULT CURRENT_TIMESTAMP"
        if default == "CURRENT_TIMESTAMP_ON_UPDATE":
            return "DEFAULT CURRENT_TIMESTAMP"
        return f"DEFAULT {default}"

    def quote_identifier(self, name):
        return f"`{name}`"

    def create_table(self, table_def):
        cols = []
        for col in table_def["columns"]:
            cols.append("    " + self.column_def(col))

        if "primary_key" in table_def:
            pk_cols = ", ".join(self.quote_identifier(c) for c in table_def["primary_key"])
            cols.append(f"    PRIMARY KEY ({pk_cols})")

        for idx in table_def.get("indexes", []):
            if idx.get("unique"):
                uq_cols = ", ".join(self.quote_identifier(c) for c in idx["columns"])
                cols.append(f"    UNIQUE KEY {self.quote_identifier(idx['name'])} ({uq_cols})")

        for fk in table_def.get("foreign_keys", []):
            fk_cols = ", ".join(self.quote_identifier(c) for c in fk["columns"])
            ref_cols = ", ".join(self.quote_identifier(c) for c in fk["ref_columns"])
            fk_name = fk.get("name")
            if not fk_name:
                fk_name = "fk_{}_{}".format(table_def["name"], fk["columns"][0])
            fk_def = f"    CONSTRAINT {self.quote_identifier(fk_name)} "
            fk_def += f"FOREIGN KEY ({fk_cols}) REFERENCES {self.quote_identifier(fk['ref_table'])} ({ref_cols})"
            if "on_delete" in fk:
                fk_def += f" ON DELETE {fk['on_delete']}"
            if "on_update" in fk:
                fk_def += f" ON UPDATE {fk['on_update']}"
            cols.append(fk_def)

        body = ",\n".join(cols)
        self.add(f"CREATE TABLE {self.quote_identifier(table_def['name'])} (\n{body}\n){self.table_options()}")

    def table_options(self):
        return ""

    def create_indexes(self, table_def):
        for idx in table_def.get("indexes", []):
            if idx.get("unique"):
                continue  # already handled in CREATE TABLE
            idx_cols = ", ".join(self.quote_identifier(c) for c in idx["columns"])
            self.add(
                f"CREATE UNIQUE INDEX {self.quote_identifier(idx['name'])} "
                f"ON {self.quote_identifier(table_def['name'])} ({idx_cols})"
            )

    def insert_seed(self, table_name, rows, on_conflict="ignore"):
        if not rows:
            return
        cols = list(rows[0].keys())
        col_list = ", ".join(self.quote_identifier(c) for c in cols)
        for row in rows:
            values = []
            for c in cols:
                v = row.get(c)
                if v is None:
                    values.append("NULL")
                elif isinstance(v, bool):
                    values.append("TRUE" if v else "FALSE")
                elif isinstance(v, (int, float)):
                    values.append(str(v))
                else:
                    values.append(self.quote_string(str(v)))
            val_str = ", ".join(values)
            conflict = ""
            if on_conflict == "ignore":
                conflict = self.on_conflict_ignore()
            self.add(f"INSERT{conflict} INTO {self.quote_identifier(table_name)} ({col_list}) VALUES ({val_str})")

    def quote_string(self, s):
        escaped = s.replace("'", "''")
        return f"'{escaped}'"

    def on_conflict_ignore(self):
        return " IGNORE"

    def on_conflict_do_nothing(self, cols=None):
        return ""

    def comment_sql(self, text):
        self.add(f"-- {text}")

    def table_separator(self, table_name):
        self.add_blank()
        self.comment_sql(f"--- {table_name} ---")

    def index_statements(self, table_def):
        """Post CreateTable hook for engines that use separate CREATE INDEX."""
        pass


class MySQLEngine(DDLEngine):
    def __init__(self):
        super().__init__()

    def header(self, db_name):
        self.add("SET NAMES utf8mb4;")
        self.add_blank()

    def create_database(self, db_name):
        self.add(f"CREATE DATABASE IF NOT EXISTS {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")

    def drop_database(self, db_name):
        self.add(f"DROP DATABASE IF EXISTS {db_name}")

    def use_database(self, db_name):
        self.add(f"USE {db_name}")

    def autoincrement_clause(self):
        return "AUTO_INCREMENT"

    def default_clause(self, default):
        if default is True:
            return "DEFAULT TRUE"
        if default is False:
            return "DEFAULT FALSE"
        if default == "CURRENT_TIMESTAMP":
            return "DEFAULT CURRENT_TIMESTAMP"
        if default == "CURRENT_TIMESTAMP_ON_UPDATE":
            return "DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
        return f"DEFAULT {default}"

    def table_options(self):
        return " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"

    def translate_type(self, t):
        if t == "boolean":
            return "TINYINT(1)"
        if t.startswith("enum("):
            return t.upper().replace("enum(", "ENUM(")
        return t

    def on_conflict_ignore(self):
        return " IGNORE"

    def drop_table(self, table_name):
        self.add(f"DROP TABLE IF EXISTS {table_name}")

    def drop_database_sql(self, db_name):
        self.add(f"DROP DATABASE IF EXISTS {db_name}")


class PostgreSQLEngine(DDLEngine):
    def __init__(self):
        super().__init__()

    def header(self, db_name):
        self.add(f"-- PostgreSQL schema for {db_name}")
        self.add_blank()

    def drop_database_sql(self, db_name):
        self.add(f"DROP DATABASE IF EXISTS {db_name}")

    def create_database(self, db_name):
        self.add(f"CREATE DATABASE {db_name}")

    def use_database(self, db_name):
        self.add(f"\\connect {db_name}")

    def quote_identifier(self, name):
        return f'"{name}"'

    def autoincrement_clause(self):
        return "SERIAL"

    def translate_type(self, t):
        if t == "boolean":
            return "BOOLEAN"
        if t == "int":
            return "INTEGER"
        if t == "bigint":
            return "BIGSERIAL"
        if t.startswith("enum("):
            return "VARCHAR(50)"
        if t.startswith("varchar("):
            return t.replace("varchar", "VARCHAR")
        return t

    def default_clause(self, default):
        if default is True:
            return "DEFAULT TRUE"
        if default is False:
            return "DEFAULT FALSE"
        if default == "CURRENT_TIMESTAMP":
            return "DEFAULT CURRENT_TIMESTAMP"
        if default == "CURRENT_TIMESTAMP_ON_UPDATE":
            return "DEFAULT CURRENT_TIMESTAMP"
        if isinstance(default, str) and default.startswith("'"):
            return f"DEFAULT {default}"
        return f"DEFAULT {default}"

    def table_options(self):
        return ""

    def column_def(self, col):
        parts = [self.quote_identifier(col["name"])]
        parts.append(self.translate_type(col["type"]))

        is_serial = col.get("pk") and col.get("autoincrement") and col["type"] in ("int", "bigint")
        if is_serial:
            pass  # SERIAL already implies PK + autoincrement
        elif col.get("pk") and col.get("autoincrement"):
            parts.append(self.autoincrement_clause())
        elif col.get("pk"):
            parts.append("PRIMARY KEY")

        if col.get("not_null") and not is_serial:
            parts.append("NOT NULL")
        if "default" in col:
            parts.append(self.default_clause(col["default"]))

        # Handle enums as CHECK constraints
        if col["type"].startswith("enum("):
            enum_vals = col["type"][5:-1]  # extract values from enum('a','b','c')
            parts.append(f"CHECK ({self.quote_identifier(col['name'])} IN ({enum_vals}))")

        return " ".join(parts)

    def create_table(self, table_def):
        cols = []
        for col in table_def["columns"]:
            cols.append("    " + self.column_def(col))

        if "primary_key" in table_def:
            pk_cols = ", ".join(self.quote_identifier(c) for c in table_def["primary_key"])
            cols.append(f"    PRIMARY KEY ({pk_cols})")

        for fk in table_def.get("foreign_keys", []):
            fk_cols = ", ".join(self.quote_identifier(c) for c in fk["columns"])
            ref_cols = ", ".join(self.quote_identifier(c) for c in fk["ref_columns"])
            fk_name = fk.get("name")
            if not fk_name:
                fk_name = "fk_{}_{}".format(table_def["name"], fk["columns"][0])
            fk_def = f"    CONSTRAINT {self.quote_identifier(fk_name)} "
            fk_def += f"FOREIGN KEY ({fk_cols}) REFERENCES {self.quote_identifier(fk['ref_table'])} ({ref_cols})"
            if "on_delete" in fk:
                fk_def += f" ON DELETE {fk['on_delete']}"
            if "on_update" in fk:
                fk_def += f" ON UPDATE {fk['on_update']}"
            cols.append(fk_def)

        body = ",\n".join(cols)
        self.add(f"CREATE TABLE {self.quote_identifier(table_def['name'])} (\n{body}\n)")

    def create_indexes(self, table_def):
        for idx in table_def.get("indexes", []):
            unique = "UNIQUE " if idx.get("unique") else ""
            idx_cols = ", ".join(self.quote_identifier(c) for c in idx["columns"])
            self.add(
                f"CREATE {unique}INDEX {self.quote_identifier(idx['name'])} "
                f"ON {self.quote_identifier(table_def['name'])} ({idx_cols})"
            )

    def on_conflict_ignore(self):
        return ""

    def insert_seed(self, table_name, rows, on_conflict="ignore"):
        if not rows:
            return
        cols = list(rows[0].keys())
        col_list = ", ".join(self.quote_identifier(c) for c in cols)
        for row in rows:
            values = []
            for c in cols:
                v = row.get(c)
                if v is None:
                    values.append("NULL")
                elif isinstance(v, bool):
                    values.append("TRUE" if v else "FALSE")
                elif isinstance(v, (int, float)):
                    values.append(str(v))
                else:
                    values.append(self.quote_string(str(v)))
            val_str = ", ".join(values)
            self.add(
                f"INSERT INTO {self.quote_identifier(table_name)} ({col_list}) VALUES ({val_str}) "
                f"ON CONFLICT DO NOTHING"
            )


class SQLiteEngine(DDLEngine):
    def __init__(self):
        super().__init__()

    def header(self, db_name):
        self.add(f"-- SQLite schema for {db_name}")
        self.add("PRAGMA foreign_keys = ON;")
        self.add_blank()

    def quote_identifier(self, name):
        return f'"{name}"'

    def autoincrement_clause(self):
        return "AUTOINCREMENT"

    def translate_type(self, t):
        if t == "boolean":
            return "INTEGER"
        if t == "int":
            return "INTEGER"
        if t == "bigint":
            return "INTEGER"
        if t.startswith("enum("):
            return "TEXT"
        if t.startswith("varchar("):
            return "TEXT"
        if t.startswith("decimal("):
            return "REAL"
        if t == "datetime":
            return "TEXT"
        if t == "date":
            return "TEXT"
        return t

    def default_clause(self, default):
        if default is True:
            return "DEFAULT 1"
        if default is False:
            return "DEFAULT 0"
        if default == "CURRENT_TIMESTAMP":
            return "DEFAULT (datetime('now'))"
        if default == "CURRENT_TIMESTAMP_ON_UPDATE":
            return "DEFAULT (datetime('now'))"
        if isinstance(default, str) and default.startswith("'"):
            return f"DEFAULT {default}"
        return f"DEFAULT {default}"

    def table_options(self):
        return ""

    def column_def(self, col):
        parts = [self.quote_identifier(col["name"])]
        parts.append(self.translate_type(col["type"]))

        if col.get("pk") and col.get("autoincrement"):
            parts.append("PRIMARY KEY AUTOINCREMENT")
        elif col.get("pk"):
            parts.append("PRIMARY KEY")

        if col.get("not_null") and not (col.get("pk") and col.get("autoincrement")):
            parts.append("NOT NULL")
        if "default" in col:
            parts.append(self.default_clause(col["default"]))

        return " ".join(parts)

    def create_table(self, table_def):
        cols = []
        for col in table_def["columns"]:
            cols.append("    " + self.column_def(col))

        if "primary_key" in table_def:
            pk_cols = ", ".join(self.quote_identifier(c) for c in table_def["primary_key"])
            cols.append(f"    PRIMARY KEY ({pk_cols})")

        # SQLite supports inline UNIQUE
        for idx in table_def.get("indexes", []):
            if idx.get("unique"):
                uq_cols = ", ".join(self.quote_identifier(c) for c in idx["columns"])
                cols.append(f"    UNIQUE ({uq_cols})")

        for fk in table_def.get("foreign_keys", []):
            fk_cols = ", ".join(self.quote_identifier(c) for c in fk["columns"])
            ref_cols = ", ".join(self.quote_identifier(c) for c in fk["ref_columns"])
            fk_def = f"    FOREIGN KEY ({fk_cols}) REFERENCES {self.quote_identifier(fk['ref_table'])} ({ref_cols})"
            if "on_delete" in fk:
                fk_def += f" ON DELETE {fk['on_delete']}"
            if "on_update" in fk:
                fk_def += f" ON UPDATE {fk['on_update']}"
            cols.append(fk_def)

        body = ",\n".join(cols)
        self.add(f"CREATE TABLE IF NOT EXISTS {self.quote_identifier(table_def['name'])} (\n{body}\n)")

    def create_indexes(self, table_def):
        for idx in table_def.get("indexes", []):
            if idx.get("unique"):
                continue  # handled inline
            unique = "UNIQUE " if idx.get("unique") else ""
            idx_cols = ", ".join(self.quote_identifier(c) for c in idx["columns"])
            self.add(
                f"CREATE {unique}INDEX IF NOT EXISTS {self.quote_identifier(idx['name'])} "
                f"ON {self.quote_identifier(table_def['name'])} ({idx_cols})"
            )

    def on_conflict_ignore(self):
        return ""

    def insert_seed(self, table_name, rows, on_conflict="ignore"):
        if not rows:
            return
        cols = list(rows[0].keys())
        col_list = ", ".join(self.quote_identifier(c) for c in cols)
        for row in rows:
            values = []
            for c in cols:
                v = row.get(c)
                if v is None:
                    values.append("NULL")
                elif isinstance(v, bool):
                    values.append("1" if v else "0")
                elif isinstance(v, (int, float)):
                    values.append(str(v))
                else:
                    values.append(self.quote_string(str(v)))
            val_str = ", ".join(values)
            self.add(
                f"INSERT OR IGNORE INTO {self.quote_identifier(table_name)} ({col_list}) VALUES ({val_str})"
            )

    def drop_table(self, table_name):
        self.add(f"DROP TABLE IF EXISTS {table_name}")

    def drop_database_sql(self, db_name):
        self.add(f"-- SQLite: database is a file, drop by deleting the file: {db_name}.db")


class SQLServerEngine(DDLEngine):
    def __init__(self):
        super().__init__()

    def header(self, db_name):
        self.add(f"-- SQL Server schema for {db_name}")
        self.add_blank()

    def create_database(self, db_name):
        self.add(f"IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = '{db_name}')")
        self.add(f"CREATE DATABASE [{db_name}]")

    def drop_database(self, db_name):
        self.add(f"IF EXISTS (SELECT name FROM sys.databases WHERE name = '{db_name}')")
        self.add(f"DROP DATABASE [{db_name}]")

    def drop_database_sql(self, db_name):
        self.add(f"IF EXISTS (SELECT name FROM sys.databases WHERE name = '{db_name}')")
        self.add(f"DROP DATABASE [{db_name}]")

    def use_database(self, db_name):
        self.add(f"USE [{db_name}]")

    def quote_identifier(self, name):
        return f"[{name}]"

    def autoincrement_clause(self):
        return "IDENTITY(1,1)"

    def translate_type(self, t):
        if t == "boolean":
            return "BIT"
        if t == "int":
            return "INT"
        if t == "bigint":
            return "BIGINT"
        if t.startswith("enum("):
            return "NVARCHAR(50)"
        if t.startswith("varchar("):
            return t.replace("varchar", "NVARCHAR")
        if t == "text":
            return "NVARCHAR(MAX)"
        if t == "datetime":
            return "DATETIME2"
        if t == "date":
            return "DATE"
        return t

    def default_clause(self, default):
        if default is True:
            return "DEFAULT 1"
        if default is False:
            return "DEFAULT 0"
        if default == "CURRENT_TIMESTAMP":
            return "DEFAULT GETDATE()"
        if default == "CURRENT_TIMESTAMP_ON_UPDATE":
            return "DEFAULT GETDATE()"
        if isinstance(default, str) and default.startswith("'"):
            return f"DEFAULT {default}"
        return f"DEFAULT {default}"

    def table_options(self):
        return ""

    def column_def(self, col):
        parts = [self.quote_identifier(col["name"])]
        parts.append(self.translate_type(col["type"]))

        if col.get("pk") and col.get("autoincrement"):
            parts.append(self.autoincrement_clause())
            parts.append("PRIMARY KEY")
        elif col.get("pk"):
            parts.append("PRIMARY KEY")

        if col.get("not_null") and not (col.get("pk") and col.get("autoincrement")):
            parts.append("NOT NULL")
        if "default" in col:
            parts.append(self.default_clause(col["default"]))

        return " ".join(parts)

    def create_table(self, table_def):
        cols = []
        for col in table_def["columns"]:
            cols.append("    " + self.column_def(col))

        if "primary_key" in table_def:
            pk_cols = ", ".join(self.quote_identifier(c) for c in table_def["primary_key"])
            cols.append(f"    PRIMARY KEY ({pk_cols})")

        for fk in table_def.get("foreign_keys", []):
            fk_cols = ", ".join(self.quote_identifier(c) for c in fk["columns"])
            ref_cols = ", ".join(self.quote_identifier(c) for c in fk["ref_columns"])
            fk_name = fk.get("name")
            if not fk_name:
                fk_name = "fk_{}_{}".format(table_def["name"], fk["columns"][0])
            fk_def = f"    CONSTRAINT [{fk_name}] "
            fk_def += f"FOREIGN KEY ({fk_cols}) REFERENCES {self.quote_identifier(fk['ref_table'])} ({ref_cols})"
            if "on_delete" in fk:
                fk_def += f" ON DELETE {fk['on_delete']}"
            if "on_update" in fk:
                fk_def += f" ON UPDATE {fk['on_update']}"
            cols.append(fk_def)

        body = ",\n".join(cols)
        self.add(f"CREATE TABLE {self.quote_identifier(table_def['name'])} (\n{body}\n)")

    def create_indexes(self, table_def):
        for idx in table_def.get("indexes", []):
            unique = "UNIQUE " if idx.get("unique") else ""
            idx_cols = ", ".join(self.quote_identifier(c) for c in idx["columns"])
            idx_name = idx["name"]
            table_name = table_def["name"]
            self.add(
                f"CREATE {unique}INDEX {self.quote_identifier(idx_name)} "
                f"ON {self.quote_identifier(table_name)} ({idx_cols})"
            )

    def on_conflict_ignore(self):
        return ""

    def insert_seed(self, table_name, rows, on_conflict="ignore"):
        if not rows:
            return
        cols = list(rows[0].keys())
        col_list = ", ".join(self.quote_identifier(c) for c in cols)
        for row in rows:
            values = []
            for c in cols:
                v = row.get(c)
                if v is None:
                    values.append("NULL")
                elif isinstance(v, bool):
                    values.append("1" if v else "0")
                elif isinstance(v, (int, float)):
                    values.append(str(v))
                else:
                    values.append(self.quote_string(str(v)))
            val_str = ", ".join(values)
            conflict_col = cols[0]
            self.add(
                f"IF NOT EXISTS (SELECT 1 FROM {self.quote_identifier(table_name)} "
                f"WHERE {self.quote_identifier(conflict_col)} = {values[0]}) "
                f"INSERT INTO {self.quote_identifier(table_name)} ({col_list}) VALUES ({val_str})"
            )

    def drop_table(self, table_name):
        self.add(f"IF OBJECT_ID('{table_name}', 'U') IS NOT NULL DROP TABLE {self.quote_identifier(table_name)}")


# ============================================================================
# GENERADOR PRINCIPAL
# ============================================================================

ENGINE_MAP = {
    "mysql": MySQLEngine,
    "postgresql": PostgreSQLEngine,
    "sqlite": SQLiteEngine,
    "sqlserver": SQLServerEngine,
}


def generate_schema(engine_name, output_file=None):
    """Generate DDL for the specified engine. Returns the SQL as a string."""
    if engine_name not in ENGINE_MAP:
        raise ValueError(f"Unknown engine: {engine_name}. Supported: {', '.join(ENGINE_MAP.keys())}")

    engine = ENGINE_MAP[engine_name]()

    # --- ADMIN DATABASE ---
    engine.header("taurus_admin")
    engine.comment_sql("TAURUS WMS - Schema para taurus_admin")
    engine.comment_sql(f"Engine: {engine_name}")
    engine.comment_sql("Generado por modules/schema_generator.py")
    engine.add_blank()

    engine.drop_database_sql("taurus_admin")
    engine.create_database("taurus_admin")
    engine.use_database("taurus_admin")
    engine.add_blank()

    for table_def in ADMIN_TABLES:
        engine.table_separator(table_def["name"])
        engine.create_table(table_def)
        engine.create_indexes(table_def)

    engine.add_blank()
    engine.comment_sql("--- Datos iniciales ---")
    for seed in ADMIN_SEEDS:
        engine.add_blank()
        if "comment" in seed:
            engine.comment_sql(seed["comment"])
        engine.insert_seed(seed["table"], seed["rows"])

    # --- WMS DATABASE ---
    engine.add_blank()
    engine.add_blank()
    engine.header("taurus_wms")
    engine.comment_sql("TAURUS WMS - Schema para taurus_wms (datos operativos)")
    engine.comment_sql(f"Engine: {engine_name}")
    engine.comment_sql("Generado por modules/schema_generator.py")
    engine.add_blank()

    engine.drop_database_sql("taurus_wms")
    engine.create_database("taurus_wms")
    engine.use_database("taurus_wms")
    engine.add_blank()

    for table_def in WMS_TABLES:
        engine.table_separator(table_def["name"])
        engine.create_table(table_def)
        engine.create_indexes(table_def)

    engine.add_blank()
    engine.comment_sql("--- Datos iniciales ---")
    for seed in WMS_SEEDS:
        engine.add_blank()
        if "comment" in seed:
            engine.comment_sql(seed["comment"])
        engine.insert_seed(seed["table"], seed["rows"])

    # --- FOOTER ---
    engine.add_blank()
    engine.add_blank()
    engine.comment_sql("=== FIN DEL SCRIPT ===")
    engine.comment_sql(f"Schema generado para engine: {engine_name}")
    engine.comment_sql("Usuarios por defecto:")
    engine.comment_sql("  SuperAdmin: admin / Admin@2024!")
    engine.comment_sql("  Operador:   operador / Admin@2024!")

    sql = "\n".join(engine.statements) + "\n"

    if output_file:
        os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(sql)

    return sql


def main():
    parser = argparse.ArgumentParser(description="Generador de schema multi-engine para Taurus WMS")
    parser.add_argument("--engine", choices=["mysql", "postgresql", "sqlite", "sqlserver"],
                        help="Motor de BD target")
    parser.add_argument("--all", action="store_true",
                        help="Genera los 4 archivos de schema (mysql, postgresql, sqlite, sqlserver)")
    parser.add_argument("--output", "-o", type=str,
                        help="Archivo de salida (default: stdout)")
    parser.add_argument("--output-dir", type=str, default=".",
                        help="Directorio de salida para --all (default: .)")
    args = parser.parse_args()

    if args.all:
        for eng in ["mysql", "postgresql", "sqlite", "sqlserver"]:
            out_path = os.path.join(args.output_dir, f"schema_{eng}.sql")
            print(f"Generando {out_path} ...")
            generate_schema(eng, out_path)
        print("Listo.")
    elif args.engine:
        if args.output:
            generate_schema(args.engine, args.output)
            print(f"Generado: {args.output}")
        else:
            print(generate_schema(args.engine))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
