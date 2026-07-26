-- ============================================================================
-- TAURUS WMS - Script Completo de Generacion de Base de Datos
-- Fecha: 2026-07-21
-- Descripcion: Crea desde cero ambas bases de datos (taurus_admin y taurus_wms)
--              con todas las tablas, relaciones, datos iniciales y procedimientos.
--
-- USO:
--   mysql -u root -p < schema_completo.sql
--
-- NOTAS:
--   - Se asume MySQL 8.0+ (XAMPP)
--   - El usuario admin por defecto es: admin / Admin@2024!
--   - La BD taurus_admin almacena configuracion y usuarios del sistema
--   - La BD taurus_wms almacena datos operativos (multi-tenant)
--   - Este script es 100% ASCII-safe (sin acentos en comentarios ni strings)
--   - La columna descipcion de tipoubicacion se renombra con tilde via
--     prepared statement al final del script (requerido por el codigo Python)
-- ============================================================================

SET NAMES utf8mb4;

-- ============================================================================
-- PARTE 1: BASE DE DATOS DE ADMINISTRACION (taurus_admin)
-- ============================================================================

DROP DATABASE IF EXISTS taurus_admin;
CREATE DATABASE taurus_admin CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE taurus_admin;

-- ----------------------------------------------------------------------------
-- 1.1 Tabla de administradores del sistema (SUPERADMIN)
-- ----------------------------------------------------------------------------
CREATE TABLE admin_usuarios (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    username       VARCHAR(50)  NOT NULL UNIQUE,
    password_hash  VARCHAR(255) NOT NULL,
    nombre         VARCHAR(100) NOT NULL,
    email          VARCHAR(100) NULL,
    rol            ENUM('SUPERADMIN','ADMIN') DEFAULT 'ADMIN',
    activo         BOOLEAN DEFAULT TRUE,
    ultimo_acceso  DATETIME NULL,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_rol (rol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 1.2 Tabla de tenants (empresas)
-- ----------------------------------------------------------------------------
CREATE TABLE tenants (
    id                 INT PRIMARY KEY,
    codigo             VARCHAR(20)  NOT NULL UNIQUE COMMENT 'Codigo de empresa encriptado',
    nombre             VARCHAR(100) NOT NULL COMMENT 'Nombre de la empresa',
    razon_social       VARCHAR(200) NULL,
    cuit               VARCHAR(50)  NULL COMMENT 'CUIT/NIT/CI/RUC',
    direccion          VARCHAR(255) NULL,
    telefono           VARCHAR(50)  NULL,
    email              VARCHAR(100) NULL,
    activo             BOOLEAN DEFAULT TRUE,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    nombredelalmacen   VARCHAR(200) NULL COMMENT 'Nombre del almacen para reportes',
    metodosdepicking   TEXT NULL COMMENT 'JSON con metodos de picking (FIFO/LIFO/etc)',
    bajostock          DECIMAL(12,3) DEFAULT 0 COMMENT 'Umbral de bajo stock para alertas',
    dias_filtro_fechas INT DEFAULT 30 COMMENT 'Dias de filtro por defecto en consultas',
    contexto           LONGTEXT NULL COMMENT 'Contexto para prompts de IA',
    prompt             LONGTEXT NULL COMMENT 'Prompt personalizado de IA',
    proveedor_api_ia   LONGTEXT NULL COMMENT 'Proveedor de API de IA (openai, anthropic, etc)',
    modelo_api_ia      LONGTEXT NULL COMMENT 'Modelo de IA a utilizar',
    api_key            LONGTEXT NULL COMMENT 'API key para servicios de IA',
    INDEX idx_codigo (codigo),
    INDEX idx_activo (activo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 1.3 Tabla de usuarios (por tenant)
-- ----------------------------------------------------------------------------
CREATE TABLE usuarios (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    username           VARCHAR(50)  NOT NULL UNIQUE,
    password_hash      VARCHAR(255) NOT NULL,
    nombre             VARCHAR(100) NOT NULL,
    email              VARCHAR(100) NULL,
    rol                ENUM('ADMIN','OPERADOR','CONSULTA') DEFAULT 'OPERADOR',
    tenant_id          INT NOT NULL,
    activo             BOOLEAN DEFAULT TRUE,
    ultimo_acceso      DATETIME NULL,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    sidebar_preferences LONGTEXT NULL COMMENT 'Preferencias de sidebar del usuario',
    INDEX idx_tenant (tenant_id),
    INDEX idx_rol (rol),
    UNIQUE INDEX idx_username_unico (username),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 1.4 Tabla de configuracion general
-- ----------------------------------------------------------------------------
CREATE TABLE configuracion (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    clave       VARCHAR(100) NOT NULL UNIQUE,
    valor       TEXT NULL,
    descripcion VARCHAR(255) NULL,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_clave (clave)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 1.5 Tabla de logs de auditoria
-- ----------------------------------------------------------------------------
CREATE TABLE audit_logs (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    usuario_id      INT NULL,
    usuario_nombre  VARCHAR(100) NULL,
    accion          VARCHAR(50)  NOT NULL COMMENT 'LOGIN, LOGOUT, CREATE, UPDATE, DELETE, ACCESS',
    modulo          VARCHAR(100) NOT NULL COMMENT 'tenants, usuarios, materiales, etc.',
    detalle         TEXT NULL COMMENT 'JSON con detalles de la accion',
    ip_address      VARCHAR(45) NULL,
    user_agent      VARCHAR(255) NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_usuario (usuario_id),
    INDEX idx_accion (accion),
    INDEX idx_modulo (modulo),
    INDEX idx_fecha (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 1.6 Tabla de permisos de rutas por rol
-- ----------------------------------------------------------------------------
CREATE TABLE roles_rutas (
    rol  VARCHAR(50)  NOT NULL COMMENT 'ROL al que aplica el permiso',
    ruta VARCHAR(255) NOT NULL COMMENT 'Ruta protegida o * para acceso total',
    PRIMARY KEY (rol, ruta)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 1.7 Datos iniciales: tenant por defecto
-- ----------------------------------------------------------------------------
INSERT INTO tenants (id, codigo, nombre, razon_social, activo, nombredelalmacen, metodosdepicking, bajostock, dias_filtro_fechas)
VALUES (1, 'DEFAULT', 'Empresa Principal', 'Empresa Principal S.A.', TRUE, 'Almacen Principal', '"fifo"', 0, 30);

-- ----------------------------------------------------------------------------
-- 1.8 Datos iniciales: usuario SUPERADMIN (password: Admin@2024!)
-- ----------------------------------------------------------------------------
INSERT INTO admin_usuarios (username, password_hash, nombre, email, rol)
VALUES ('admin', 'scrypt:32768:8:1$WQ6PhKOf81VV3FcH$ed1ca47fd1fd381583f0289acf9e839521b5e74a07adfc034382ea5342d608e393b7143fec95b3aef262f1946f95696e3e8acbfc867c91769d63142d4e4a5db2', 'Administrador', 'admin@taurus.local', 'SUPERADMIN');

-- ----------------------------------------------------------------------------
-- 1.9 Datos iniciales: usuario de prueba para tenant 1
-- ----------------------------------------------------------------------------
INSERT INTO usuarios (username, password_hash, nombre, email, rol, tenant_id, activo)
VALUES ('operador', 'scrypt:32768:8:1$WQ6PhKOf81VV3FcH$ed1ca47fd1fd381583f0289acf9e839521b5e74a07adfc034382ea5342d608e393b7143fec95b3aef262f1946f95696e3e8acbfc867c91769d63142d4e4a5db2', 'Operador General', 'operador@taurus.local', 'OPERADOR', 1, TRUE);

-- ----------------------------------------------------------------------------
-- 1.10 Datos iniciales: configuracion de la aplicacion
-- ----------------------------------------------------------------------------
INSERT INTO configuracion (clave, valor, descripcion) VALUES
('app_version', '1.0.0', 'Version actual de la aplicacion'),
('app_name', 'Taurus WMS', 'Nombre de la aplicacion'),
('mantenimiento', 'false', 'Modo mantenimiento (true/false)'),
('DB_HOST', 'localhost', 'Host del servidor de base de datos'),
('DB_PORT', '3306', 'Puerto del servidor MySQL'),
('DB_NAME', 'taurus_wms', 'Nombre de la base de datos principal'),
('DB_USER', 'taurus', 'Usuario de la base de datos'),
('DB_PASSWORD', 'Taurus_2001', 'Contrasena de la base de datos'),
('DB_CHAR_SET', 'utf8mb4', 'Charset de la base de datos');

-- ----------------------------------------------------------------------------
-- 1.11 Datos iniciales: permisos de rutas por rol
-- ----------------------------------------------------------------------------
-- ADMIN: acceso total
INSERT INTO roles_rutas (rol, ruta) VALUES
('ADMIN', '*');

-- OPERADOR: acceso a modulos operativos
INSERT INTO roles_rutas (rol, ruta) VALUES
('OPERADOR', '/materiales'),
('OPERADOR', '/materiales/guardar'),
('OPERADOR', '/materiales/eliminar'),
('OPERADOR', '/materiales/importar'),
('OPERADOR', '/materiales/exportar'),
('OPERADOR', '/materiales/plantilla'),
('OPERADOR', '/ubicaciones'),
('OPERADOR', '/ubicaciones/guardar'),
('OPERADOR', '/ubicaciones/importar'),
('OPERADOR', '/ubicaciones/exportar'),
('OPERADOR', '/ubicaciones/plantilla'),
('OPERADOR', '/tipoubicacion'),
('OPERADOR', '/tipoubicacion/guardar'),
('OPERADOR', '/tipoubicacion/eliminar'),
('OPERADOR', '/tipoubicacion/importar'),
('OPERADOR', '/tipoubicacion/exportar'),
('OPERADOR', '/tipoubicacion/plantilla'),
('OPERADOR', '/proveedores'),
('OPERADOR', '/proveedores/guardar'),
('OPERADOR', '/proveedores/eliminar'),
('OPERADOR', '/proveedores/importar'),
('OPERADOR', '/proveedores/exportar'),
('OPERADOR', '/proveedores/plantilla'),
('OPERADOR', '/clientes'),
('OPERADOR', '/clientes/guardar'),
('OPERADOR', '/clientes/importar'),
('OPERADOR', '/clientes/exportar'),
('OPERADOR', '/clientes/plantilla'),
('OPERADOR', '/categorias'),
('OPERADOR', '/categorias/guardar'),
('OPERADOR', '/categorias/eliminar'),
('OPERADOR', '/unidades'),
('OPERADOR', '/unidades/guardar'),
('OPERADOR', '/unidades/eliminar'),
('OPERADOR', '/unidades/importar'),
('OPERADOR', '/unidades/exportar'),
('OPERADOR', '/unidades/plantilla'),
('OPERADOR', '/transportes'),
('OPERADOR', '/transportes/guardar'),
('OPERADOR', '/transportes/importar'),
('OPERADOR', '/transportes/exportar'),
('OPERADOR', '/transportes/plantilla'),
('OPERADOR', '/rutas'),
('OPERADOR', '/rutas/guardar'),
('OPERADOR', '/rutas/eliminar'),
('OPERADOR', '/rutas/importar'),
('OPERADOR', '/rutas/exportar'),
('OPERADOR', '/rutas/plantilla'),
('OPERADOR', '/pedidos'),
('OPERADOR', '/pedidos/nuevo'),
('OPERADOR', '/pedidos/editar'),
('OPERADOR', '/pedidos/guardar'),
('OPERADOR', '/pedidos/eliminar'),
('OPERADOR', '/pedidos/importar'),
('OPERADOR', '/pedidos/plantilla'),
('OPERADOR', '/pedidos/picking_json'),
('OPERADOR', '/recepciones'),
('OPERADOR', '/recepciones/nueva'),
('OPERADOR', '/recepciones/guardar'),
('OPERADOR', '/recepciones/ver'),
('OPERADOR', '/recepciones/cerrar'),
('OPERADOR', '/recepciones/eliminar'),
('OPERADOR', '/recepciones/importar'),
('OPERADOR', '/recepciones/plantilla'),
('OPERADOR', '/recepciones/guardar_item'),
('OPERADOR', '/recepciones/eliminar_item'),
('OPERADOR', '/recepciones/confirmar_stock'),
('OPERADOR', '/recepciones/anular'),
('OPERADOR', '/omc'),
('OPERADOR', '/omc/nueva'),
('OPERADOR', '/omc/guardar'),
('OPERADOR', '/omc/ver'),
('OPERADOR', '/despacho'),
('OPERADOR', '/despacho/despachar'),
('OPERADOR', '/despacho/despachar_masivo'),
('OPERADOR', '/stockcontable'),
('OPERADOR', '/stockcontable/editar'),
('OPERADOR', '/stockcontable/importar'),
('OPERADOR', '/stockcontable/exportar'),
('OPERADOR', '/stockcontable/plantilla'),
('OPERADOR', '/inventario'),
('OPERADOR', '/inventario/crear'),
('OPERADOR', '/inventario/*'),
('OPERADOR', '/parametros'),
('OPERADOR', '/actualizar_parametros');

-- CONSULTA: solo lectura (acceso a listados)
INSERT INTO roles_rutas (rol, ruta) VALUES
('CONSULTA', '/materiales'),
('CONSULTA', '/ubicaciones'),
('CONSULTA', '/tipoubicacion'),
('CONSULTA', '/proveedores'),
('CONSULTA', '/clientes'),
('CONSULTA', '/categorias'),
('CONSULTA', '/unidades'),
('CONSULTA', '/transportes'),
('CONSULTA', '/rutas'),
('CONSULTA', '/pedidos'),
('CONSULTA', '/recepciones'),
('CONSULTA', '/omc'),
('CONSULTA', '/despacho'),
('CONSULTA', '/stockcontable'),
('CONSULTA', '/inventario'),
('CONSULTA', '/parametros');


-- ============================================================================
-- PARTE 2: BASE DE DATOS OPERATIVA (taurus_wms)
-- ============================================================================

DROP DATABASE IF EXISTS taurus_wms;
CREATE DATABASE taurus_wms CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE taurus_wms;

-- ----------------------------------------------------------------------------
-- 2.1 Zonas
-- ----------------------------------------------------------------------------
CREATE TABLE zonas (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    codigo      VARCHAR(20)  NOT NULL COMMENT 'Codigo unico de la zona',
    nombre      VARCHAR(100) NOT NULL COMMENT 'Nombre descriptivo',
    descripcion TEXT         NULL,
    activo      TINYINT(1)   NOT NULL DEFAULT 1,
    tenant_id   INT NULL COMMENT 'Empresa propietaria',
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE INDEX uk_zona_codigo (codigo),
    INDEX idx_zona_activo (activo),
    INDEX idx_zonas_tenant (tenant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 2.2 Tipo de ubicacion
-- ----------------------------------------------------------------------------
-- NOTA: la columna descipcion lleva tilde en la BD original (descipcion con tilde).
-- Se crea aqui sin tilde y se renombra con prepared statement al final del script.
CREATE TABLE tipoubicacion (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    descipcion      VARCHAR(100) NOT NULL,
    operacion       CHAR(1) NULL DEFAULT NULL,
    soporte_picking TINYINT(1) NOT NULL DEFAULT 0,
    tenant_id       INT NULL,
    INDEX idx_tipoubicacion_tenant (tenant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 2.3 Categorias
-- ----------------------------------------------------------------------------
CREATE TABLE categorias (
    id_categoria INT AUTO_INCREMENT PRIMARY KEY,
    codigo       VARCHAR(50)  NULL UNIQUE,
    nombre       VARCHAR(100) NOT NULL,
    descripcion  TEXT         NULL,
    activo       TINYINT(1)   NOT NULL DEFAULT 1,
    tenant_id    INT NULL COMMENT 'Empresa propietaria',
    created_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_categorias_tenant (tenant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 2.4 Proveedores
-- ----------------------------------------------------------------------------
CREATE TABLE proveedores (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    codigo       VARCHAR(50)  NULL UNIQUE,
    razonsocial  VARCHAR(200) NOT NULL,
    cuit         VARCHAR(50)  NULL,
    direccion    VARCHAR(255) NULL,
    telefono     VARCHAR(50)  NULL,
    email        VARCHAR(100) NULL,
    activo       TINYINT(1)   NOT NULL DEFAULT 1,
    tenant_id    INT NULL COMMENT 'Empresa propietaria',
    created_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_proveedores_tenant (tenant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 2.5 Rutas
-- ----------------------------------------------------------------------------
CREATE TABLE rutas (
    id_ruta      INT AUTO_INCREMENT PRIMARY KEY,
    nombre_ruta  VARCHAR(100) NOT NULL,
    descripcion  TEXT         NULL,
    tenant_id    INT NULL COMMENT 'Empresa propietaria',
    INDEX idx_rutas_tenant (tenant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 2.6 Unidades de medida
-- ----------------------------------------------------------------------------
CREATE TABLE unidades_medida (
    id_unidad               INT AUTO_INCREMENT PRIMARY KEY,
    codigo                  VARCHAR(50)   NOT NULL,
    nombre                  VARCHAR(100)  NOT NULL,
    simbolo                 VARCHAR(20)   NULL,
    tipo_magnitud           VARCHAR(50)   DEFAULT 'CANTIDAD',
    conversion_a_base       DECIMAL(12,4) DEFAULT 1.0000,
    unidad_base_referencia  VARCHAR(10)   DEFAULT 'U',
    decimales_permitidos    INT           DEFAULT 0,
    activo                  TINYINT(1)    NOT NULL DEFAULT 1,
    tenant_id               INT NULL COMMENT 'Empresa propietaria',
    INDEX idx_unidades_tenant (tenant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 2.7 Ubicaciones
-- ----------------------------------------------------------------------------
CREATE TABLE ubicaciones (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    codigo             VARCHAR(50)   NOT NULL UNIQUE,
    nombre             VARCHAR(100)  NULL,
    descipcion         VARCHAR(200)  NULL,
    tipoubicacion      INT           NULL COMMENT 'FK -> tipoubicacion.id',
    zona               VARCHAR(50)   NULL COMMENT 'DEPRECATED: usar id_zona',
    id_zona            INT           NULL COMMENT 'FK -> zonas.id',
    pasillo            VARCHAR(20)   NULL,
    estante            VARCHAR(20)   NULL,
    nivel              VARCHAR(20)   NULL,
    posicion           VARCHAR(20)   NULL,
    coordenadaA        VARCHAR(20)   NULL,
    coordenadaB        VARCHAR(20)   NULL,
    coordenadaC        VARCHAR(20)   NULL,
    coordenadaD        VARCHAR(20)   NULL,
    capacidad_maxima   INT           NOT NULL DEFAULT 0,
    ocupado            INT           NOT NULL DEFAULT 0,
    disponible_entrada TINYINT(1)    NOT NULL DEFAULT 1,
    disponible_salida  TINYINT(1)    NOT NULL DEFAULT 1,
    orden_picking      INT           NOT NULL DEFAULT 0 COMMENT 'Orden de picking dentro de la zona',
    activo             TINYINT(1)    NOT NULL DEFAULT 1,
    tenant_id          INT NULL COMMENT 'Empresa propietaria',
    created_at         TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ubicaciones_tenant (tenant_id),
    INDEX idx_ubi_zona (id_zona),
    INDEX idx_ubi_tipo (tipoubicacion),
    CONSTRAINT fk_ubicaciones_zona FOREIGN KEY (id_zona)
        REFERENCES zonas(id) ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 2.8 Transportes
-- ----------------------------------------------------------------------------
CREATE TABLE transportes (
    id_transporte   INT AUTO_INCREMENT PRIMARY KEY,
    codigo          VARCHAR(100) NULL UNIQUE,
    razonsocial     VARCHAR(200) NOT NULL,
    cuit            VARCHAR(50)  NULL,
    telefono        VARCHAR(50)  NULL,
    email           VARCHAR(100) NULL,
    activo          TINYINT(1)   NOT NULL DEFAULT 1,
    id_muelle_salida INT         NULL COMMENT 'FK -> ubicaciones.id (muelle de despacho)',
    tenant_id       INT NULL COMMENT 'Empresa propietaria',
    INDEX idx_transportes_tenant (tenant_id),
    CONSTRAINT fk_transporte_muelle FOREIGN KEY (id_muelle_salida)
        REFERENCES ubicaciones(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 2.9 Transporte - Rutas (relacion N:N)
-- ----------------------------------------------------------------------------
CREATE TABLE transporte_rutas (
    id_transporte  INT NOT NULL COMMENT 'FK -> transportes.id_transporte',
    id_ruta        INT NOT NULL COMMENT 'FK -> rutas.id_ruta',
    observaciones  TEXT NULL,
    PRIMARY KEY (id_transporte, id_ruta),
    CONSTRAINT fk_tr_transporte FOREIGN KEY (id_transporte)
        REFERENCES transportes(id_transporte) ON DELETE CASCADE,
    CONSTRAINT fk_tr_ruta FOREIGN KEY (id_ruta)
        REFERENCES rutas(id_ruta) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 2.10 Clientes
-- ----------------------------------------------------------------------------
CREATE TABLE clientes (
    id_cliente                  INT AUTO_INCREMENT PRIMARY KEY,
    codigo                      VARCHAR(100) NULL UNIQUE,
    razonsocial                 VARCHAR(200) NOT NULL,
    cuit                        VARCHAR(50)  NULL,
    direccion                   VARCHAR(255) NULL,
    localidad                   VARCHAR(100) NULL,
    provincia                   VARCHAR(100) NULL,
    telefono                    VARCHAR(50)  NULL,
    email                       VARCHAR(100) NULL,
    contacto_nombre             VARCHAR(100) NULL,
    id_ruta                     INT NULL COMMENT 'FK -> rutas.id_ruta',
    id_transporte_predeterminado INT NULL COMMENT 'FK -> transportes.id_transporte',
    activo                      TINYINT(1)   NOT NULL DEFAULT 1,
    tenant_id                   INT NULL COMMENT 'Empresa propietaria',
    INDEX idx_clientes_tenant (tenant_id),
    CONSTRAINT fk_cliente_ruta FOREIGN KEY (id_ruta)
        REFERENCES rutas(id_ruta) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_cliente_transporte FOREIGN KEY (id_transporte_predeterminado)
        REFERENCES transportes(id_transporte) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 2.11 Materiales
-- ----------------------------------------------------------------------------
CREATE TABLE materiales (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    codigo           VARCHAR(100)  NOT NULL UNIQUE,
    codigo_barras    VARCHAR(100) NULL DEFAULT NULL COMMENT 'Codigo de barras EAN/UPC (unico)',
    nombre           VARCHAR(255) NOT NULL,
    descripcion      TEXT         NULL,
    categoria_id     INT          NULL COMMENT 'FK -> categorias.id_categoria',
    stock_minimo     DECIMAL(12,3) DEFAULT 0,
    stock_maximo     DECIMAL(12,3) DEFAULT 0,
    unidad_medida_id INT          NULL COMMENT 'FK -> unidades_medida.id_unidad',
    trazabilidad     ENUM('ninguna','lote','serie') NOT NULL DEFAULT 'ninguna',
    peso_bruto       DECIMAL(10,3) NULL COMMENT 'Peso bruto (kg)',
    peso_neto        DECIMAL(10,3) NULL COMMENT 'Peso neto (kg)',
    costo_promedio   DECIMAL(12,4) DEFAULT 0.0000,
    ultimo_costo     DECIMAL(12,4) DEFAULT 0.0000,
    activo           TINYINT(1)    NOT NULL DEFAULT 1,
    tenant_id        INT NULL COMMENT 'Empresa propietaria',
    created_at       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_materiales_tenant (tenant_id),
    INDEX idx_mat_categoria (categoria_id),
    INDEX idx_mat_codigo_barras (codigo_barras),
    CONSTRAINT fk_mat_categoria FOREIGN KEY (categoria_id)
        REFERENCES categorias(id_categoria) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 2.12 Material - Proveedores (relacion N:N)
-- ----------------------------------------------------------------------------
CREATE TABLE material_proveedor (
    id_material          INT NOT NULL COMMENT 'FK -> materiales.id',
    id_proveedor         INT NOT NULL COMMENT 'FK -> proveedores.id',
    codigo_referencia_prov VARCHAR(100) NULL COMMENT 'Codigo del material segun el proveedor',
    es_habitual          TINYINT(1) NOT NULL DEFAULT 0 COMMENT '1 = proveedor habitual',
    tenant_id            INT NULL COMMENT 'Empresa propietaria',
    PRIMARY KEY (id_material, id_proveedor),
    INDEX idx_matprov_tenant (tenant_id),
    CONSTRAINT fk_mp_material FOREIGN KEY (id_material)
        REFERENCES materiales(id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_mp_proveedor FOREIGN KEY (id_proveedor)
        REFERENCES proveedores(id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 2.13 Material - Presentaciones / Embalajes
-- ----------------------------------------------------------------------------
CREATE TABLE material_presentaciones (
    id                INT          NOT NULL AUTO_INCREMENT,
    id_material       INT          NOT NULL COMMENT 'FK -> materiales.id',
    nombre            VARCHAR(100) NOT NULL COMMENT 'ej: Caja x12, Palet x120',
    codigo_barras     VARCHAR(20)  NULL COMMENT 'GTIN-14 u otro; unico globalmente',
    cantidad_unidades DECIMAL(10,3) NOT NULL DEFAULT 1.000 COMMENT 'Unidades base por presentacion',
    peso_bruto        DECIMAL(10,3) NULL COMMENT 'Peso bruto de la presentacion (kg)',
    peso_neto         DECIMAL(10,3) NULL COMMENT 'Peso neto de la presentacion (kg)',
    activo            TINYINT(1)   NOT NULL DEFAULT 1,
    tenant_id         INT NULL COMMENT 'Empresa propietaria',
    PRIMARY KEY (id),
    UNIQUE KEY uq_pres_barcode (codigo_barras),
    INDEX idx_matpres_tenant (tenant_id),
    FOREIGN KEY (id_material) REFERENCES materiales(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 2.14 Stock contable
-- ----------------------------------------------------------------------------
CREATE TABLE stockcontable (
    ID               INT AUTO_INCREMENT PRIMARY KEY,
    Ubicacion        INT NOT NULL COMMENT 'FK -> ubicaciones.id',
    Material         INT NOT NULL COMMENT 'FK -> materiales.id',
    Lote             VARCHAR(100) NOT NULL DEFAULT 'UNICO',
    TipoStock        ENUM('Libre Venta','Calidad','Bloqueado','Mal Estado')
                         NOT NULL DEFAULT 'Libre Venta',
    UltimaEntrada    DATETIME NULL,
    UltimaSalida     DATETIME NULL,
    UltimoMovimiento DATETIME NULL,
    UsuarioUltimoMov VARCHAR(100) NULL COMMENT 'Usuario que realizo el ultimo movimiento',
    FechaVencimiento DATE NULL,
    StockTotal       DECIMAL(15,4) NOT NULL DEFAULT 0,
    StockDisponible  DECIMAL(15,4) NOT NULL DEFAULT 0,
    StockEntrando    DECIMAL(15,4) NOT NULL DEFAULT 0,
    StockSaliendo    DECIMAL(15,4) NOT NULL DEFAULT 0,
    IDContenedor     VARCHAR(10) NOT NULL COMMENT 'Identificador del contenedor',
    tenant_id        INT NULL COMMENT 'Empresa propietaria',
    created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_stock_pos (Ubicacion, Material, IDContenedor),
    INDEX idx_material (Material),
    INDEX idx_ubicacion (Ubicacion),
    INDEX idx_lote (Lote),
    INDEX idx_tipo_stock (TipoStock),
    INDEX idx_contenedor (IDContenedor),
    INDEX idx_stockcontable_tenant (tenant_id),
    CONSTRAINT fk_sc_ubicacion FOREIGN KEY (Ubicacion)
        REFERENCES ubicaciones(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_sc_material FOREIGN KEY (Material)
        REFERENCES materiales(id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 2.15 Clases de pedido
-- ----------------------------------------------------------------------------
CREATE TABLE clases_pedido (
    id_clase  INT AUTO_INCREMENT PRIMARY KEY,
    nombre    VARCHAR(100) NOT NULL,
    activo    TINYINT(1) NOT NULL DEFAULT 1,
    tenant_id INT NULL COMMENT 'Empresa propietaria',
    INDEX idx_clases_pedido_tenant (tenant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Datos iniciales de clases de pedido
INSERT INTO clases_pedido (nombre, activo) VALUES
('Venta', 1),
('Reposicion', 1),
('Muestra', 1),
('Devolucion', 1);

-- ----------------------------------------------------------------------------
-- 2.16 Recepciones de materiales - Cabecera
-- ----------------------------------------------------------------------------
CREATE TABLE recepciones_cabecera (
    id_recepcion         INT AUTO_INCREMENT PRIMARY KEY,
    numero               VARCHAR(20)  NOT NULL COMMENT 'Numero unico: REC-YYYY-NNNNN',
    id_proveedor         INT          NOT NULL COMMENT 'FK -> proveedores.id',
    estado               ENUM('Abierta','Cerrada','Confirmada','Anulada')
                             NOT NULL DEFAULT 'Abierta',
    id_contenedor        VARCHAR(10)  NOT NULL COMMENT 'Contenedor asignado',
    id_ubicacion_recep   INT          NOT NULL COMMENT 'FK -> ubicaciones.id (Recepcion)',
    id_ubicacion_destino INT          NULL     COMMENT 'FK -> ubicaciones.id destino al cerrar',
    observaciones        TEXT         NULL,
    fecha_recepcion      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_cierre         DATETIME     NULL,
    usuario_creacion     VARCHAR(100) NOT NULL,
    usuario_cierre       VARCHAR(100) NULL,
    tenant_id            INT NULL COMMENT 'Empresa propietaria',
    created_at           TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_recepcion_numero (numero),
    INDEX idx_rec_proveedor (id_proveedor),
    INDEX idx_rec_estado (estado),
    INDEX idx_rec_contenedor (id_contenedor),
    INDEX idx_rec_ubicrec (id_ubicacion_recep),
    INDEX idx_rec_ubicdest (id_ubicacion_destino),
    INDEX idx_rec_fecha (fecha_recepcion),
    INDEX idx_recepciones_cab_tenant (tenant_id),
    CONSTRAINT fk_reccab_proveedor FOREIGN KEY (id_proveedor)
        REFERENCES proveedores(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_reccab_ubic_recep FOREIGN KEY (id_ubicacion_recep)
        REFERENCES ubicaciones(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_reccab_ubic_dest FOREIGN KEY (id_ubicacion_destino)
        REFERENCES ubicaciones(id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 2.17 Recepciones de materiales - Detalle
-- ----------------------------------------------------------------------------
CREATE TABLE recepciones_detalle (
    id_detalle        INT AUTO_INCREMENT PRIMARY KEY,
    id_recepcion      INT           NOT NULL COMMENT 'FK -> recepciones_cabecera.id_recepcion',
    id_material       INT           NOT NULL COMMENT 'FK -> materiales.id',
    lote              VARCHAR(100)  NOT NULL DEFAULT 'UNICO',
    fecha_vencimiento DATE          NULL,
    cantidad_esperada DECIMAL(15,4) NOT NULL DEFAULT 0,
    cantidad_recibida DECIMAL(15,4) NOT NULL DEFAULT 0,
    tipo_stock        ENUM('Libre Venta','Calidad','Bloqueado','Mal Estado')
                          NOT NULL DEFAULT 'Libre Venta',
    observaciones     TEXT          NULL,
    tenant_id         INT NULL COMMENT 'Empresa propietaria',
    created_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_det_recep_mat_lote (id_recepcion, id_material, lote, tipo_stock),
    INDEX idx_det_recepcion (id_recepcion),
    INDEX idx_det_material (id_material),
    INDEX idx_det_lote (lote),
    INDEX idx_recepciones_det_tenant (tenant_id),
    CONSTRAINT fk_recdet_cabecera FOREIGN KEY (id_recepcion)
        REFERENCES recepciones_cabecera(id_recepcion) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_recdet_material FOREIGN KEY (id_material)
        REFERENCES materiales(id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 2.18 Pedidos - Cabecera
-- ----------------------------------------------------------------------------
CREATE TABLE pedidos_cabecera (
    id_pedido          INT AUTO_INCREMENT PRIMARY KEY,
    nro_pedido         VARCHAR(20)  NOT NULL COMMENT 'Numero unico: PED-YYYY-NNNNN',
    id_cliente         INT          NOT NULL COMMENT 'FK -> clientes.id_cliente',
    id_clase           INT          NULL     COMMENT 'FK -> clases_pedido.id_clase',
    fecha_pedido       DATE         NOT NULL,
    id_ruta            INT          NULL     COMMENT 'FK -> rutas.id_ruta',
    id_transporte      INT          NULL     COMMENT 'FK -> transportes.id_transporte',
    direccion_entrega  VARCHAR(255) NULL,
    observaciones      TEXT         NULL,
    estado             VARCHAR(50)  NOT NULL DEFAULT 'Pendiente'
                           COMMENT 'Pendiente, Trabajo OMC, Trabajo, Preparado, Despachado, Anulado',
    fecha_despacho     DATETIME     NULL,
    tenant_id          INT NULL COMMENT 'Empresa propietaria',
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_pedido_nro (nro_pedido),
    INDEX idx_pedido_cliente (id_cliente),
    INDEX idx_pedido_estado (estado),
    INDEX idx_pedido_fecha (fecha_pedido),
    INDEX idx_pedidos_cab_tenant (tenant_id),
    CONSTRAINT fk_pedido_cliente FOREIGN KEY (id_cliente)
        REFERENCES clientes(id_cliente) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_pedido_clase FOREIGN KEY (id_clase)
        REFERENCES clases_pedido(id_clase) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_pedido_ruta FOREIGN KEY (id_ruta)
        REFERENCES rutas(id_ruta) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_pedido_transporte FOREIGN KEY (id_transporte)
        REFERENCES transportes(id_transporte) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 2.19 Pedidos - Detalle
-- ----------------------------------------------------------------------------
CREATE TABLE pedidos_detalle (
    id_detalle         INT AUTO_INCREMENT PRIMARY KEY,
    id_pedido          INT           NOT NULL COMMENT 'FK -> pedidos_cabecera.id_pedido',
    id_material        INT           NOT NULL COMMENT 'FK -> materiales.id',
    cantidad           DECIMAL(15,4) NOT NULL DEFAULT 0,
    Cantidad_preparada DECIMAL(10,2) NOT NULL DEFAULT 0 COMMENT 'Unidades realmente preparadas',
    tipo_stock         VARCHAR(20)   NOT NULL DEFAULT 'Libre Venta'
                           COMMENT 'Tipo de stock a consumir: Libre Venta, Calidad, Bloqueado, Mal Estado',
    tenant_id          INT NULL COMMENT 'Empresa propietaria',
    created_at         TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_pd_pedido (id_pedido),
    INDEX idx_pd_material (id_material),
    INDEX idx_pedidos_det_tenant (tenant_id),
    CONSTRAINT fk_pd_pedido FOREIGN KEY (id_pedido)
        REFERENCES pedidos_cabecera(id_pedido) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_pd_material FOREIGN KEY (id_material)
        REFERENCES materiales(id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 2.20 Ordenes de Movimiento de Contenedor (OMC)
-- ----------------------------------------------------------------------------
CREATE TABLE omc (
    id_omc               INT AUTO_INCREMENT PRIMARY KEY,
    numero               VARCHAR(20)  NOT NULL COMMENT 'Numero unico: OMC-YYYY-NNNNN',
    id_contenedor        VARCHAR(20)  NULL COMMENT 'IDContenedor principal (NULL para OMCs multi-contenedor)',
    id_contenedor_destino VARCHAR(20) NULL DEFAULT NULL COMMENT 'Contenedor destino (movimiento a contenedor)',
    id_ubicacion_origen  INT          NULL     COMMENT 'FK -> ubicaciones.id',
    id_ubicacion_destino INT          NOT NULL COMMENT 'FK -> ubicaciones.id destino',
    id_recepcion         INT          NULL     COMMENT 'FK -> recepciones_cabecera (si vino de recepcion)',
    id_pedido            INT          NULL     COMMENT 'FK -> pedidos_cabecera (si vino de pedido)',
    estado               ENUM('Pendiente','Confirmada','Anulada') NOT NULL DEFAULT 'Pendiente',
    observaciones        TEXT         NULL,
    fecha_creacion       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_confirmacion   DATETIME     NULL,
    fecha_anulacion      DATETIME     NULL,
    usuario_creacion     VARCHAR(100) NOT NULL,
    usuario_confirmacion VARCHAR(100) NULL,
    usuario_anulacion    VARCHAR(100) NULL,
    tenant_id            INT NULL COMMENT 'Empresa propietaria',
    created_at           TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_omc_numero (numero),
    INDEX idx_omc_contenedor (id_contenedor),
    INDEX idx_omc_origen (id_ubicacion_origen),
    INDEX idx_omc_destino (id_ubicacion_destino),
    INDEX idx_omc_estado (estado),
    INDEX idx_omc_recepcion (id_recepcion),
    INDEX idx_omc_pedido (id_pedido),
    INDEX idx_omc_tenant (tenant_id),
    CONSTRAINT fk_omc_origen FOREIGN KEY (id_ubicacion_origen)
        REFERENCES ubicaciones(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_omc_destino FOREIGN KEY (id_ubicacion_destino)
        REFERENCES ubicaciones(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_omc_recepcion FOREIGN KEY (id_recepcion)
        REFERENCES recepciones_cabecera(id_recepcion) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_omc_pedido FOREIGN KEY (id_pedido)
        REFERENCES pedidos_cabecera(id_pedido) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 2.21 OMC - Contenedores (multiples contenedores por OMC)
-- ----------------------------------------------------------------------------
CREATE TABLE omc_contenedores (
    id                     INT AUTO_INCREMENT PRIMARY KEY,
    id_omc                 INT          NOT NULL COMMENT 'FK -> omc.id_omc',
    id_contenedor          VARCHAR(20)  NOT NULL COMMENT 'Contenedor origen',
    id_contenedor_destino  VARCHAR(20)  NULL COMMENT 'Contenedor destino (si cambia)',
    id_ubicacion_origen    INT          NOT NULL COMMENT 'FK -> ubicaciones.id',
    tenant_id              INT NULL COMMENT 'Empresa propietaria',
    INDEX idx_omc_cont_tenant (tenant_id),
    CONSTRAINT fk_oc_omc FOREIGN KEY (id_omc)
        REFERENCES omc(id_omc) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_oc_ubicacion_origen FOREIGN KEY (id_ubicacion_origen)
        REFERENCES ubicaciones(id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 2.22 Inventarios - Cabecera
-- ----------------------------------------------------------------------------
CREATE TABLE inventarios_cabecera (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    numero           VARCHAR(20)  NOT NULL UNIQUE,
    descripcion      VARCHAR(200) NULL,
    estado           ENUM('Abierto','Cerrado','Anulado') DEFAULT 'Abierto',
    fecha_creacion   DATETIME     DEFAULT CURRENT_TIMESTAMP,
    usuario_creacion VARCHAR(100) NULL,
    fecha_cierre     DATETIME     NULL,
    usuario_cierre   VARCHAR(100) NULL,
    fecha_anulacion  DATETIME     NULL,
    usuario_anulacion VARCHAR(100) NULL,
    tenant_id        INT NULL COMMENT 'Empresa propietaria',
    INDEX idx_inventarios_cab_tenant (tenant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 2.23 Inventarios - Detalle
-- ----------------------------------------------------------------------------
CREATE TABLE inventarios_detalle (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    id_inventario  INT           NOT NULL,
    id_ubicacion   INT           NOT NULL,
    id_material    INT           NOT NULL,
    id_contenedor  VARCHAR(20)   DEFAULT '',
    lote           VARCHAR(100)  DEFAULT 'UNICO',
    tipo_stock     VARCHAR(50)   DEFAULT 'Libre Venta',
    stock_sistema  DECIMAL(15,3) DEFAULT 0,
    stock_contado  DECIMAL(15,3) NULL,
    fecha_conteo   DATETIME      NULL,
    usuario_conteo VARCHAR(100)  NULL,
    tenant_id      INT NULL COMMENT 'Empresa propietaria',
    INDEX idx_inventarios_det_tenant (tenant_id),
    FOREIGN KEY (id_inventario) REFERENCES inventarios_cabecera(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 2.24 Renombrar columna descipcion -> descipcion con tilde
-- ----------------------------------------------------------------------------
-- La columna se llama descipcion con tilde en la BD original
-- y el Python la referencia con backticks. Usamos UNHEX() para generar la letra con tilde
-- y evitar problemas de encoding del archivo SQL en Windows.
SET @old_col = 'descipcion';
SET @new_col = CONCAT('descipci', UNHEX('C3B3'));
SET @sql = CONCAT(
    'ALTER TABLE tipoubicacion CHANGE COLUMN `', @old_col, '` `', @new_col, '` VARCHAR(100) NOT NULL'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ----------------------------------------------------------------------------
-- 2.25 Procedimiento almacenado: sp_guardar_material
-- ----------------------------------------------------------------------------
DELIMITER //

CREATE PROCEDURE sp_guardar_material(
    IN p_id VARCHAR(255),
    IN p_codigo VARCHAR(100),
    IN p_nombre VARCHAR(255),
    IN p_descripcion TEXT,
    IN p_codigo_barras VARCHAR(100),
    IN p_categoria_id INT,
    IN p_stock_minimo DECIMAL(12,3),
    IN p_stock_maximo DECIMAL(12,3),
    IN p_unidad_medida_id INT,
    IN p_trazabilidad VARCHAR(20),
    IN p_prov_ids TEXT,
    IN p_prov_codigos TEXT,
    IN p_prov_habitual INT,
    IN p_pres_nombres TEXT,
    IN p_pres_barcodes TEXT,
    IN p_pres_cantidades TEXT,
    OUT p_resultado VARCHAR(10),
    OUT p_mensaje VARCHAR(500),
    OUT p_id_material INT
)
BEGIN
    DECLARE v_current_id INT DEFAULT 0;
    DECLARE v_es_update BOOLEAN DEFAULT FALSE;
    DECLARE v_count INT DEFAULT 0;
    DECLARE v_i INT DEFAULT 0;
    DECLARE v_n INT DEFAULT 0;
    DECLARE v_prov_id VARCHAR(255);
    DECLARE v_prov_cod VARCHAR(255);
    DECLARE v_pres_nombre VARCHAR(255);
    DECLARE v_pres_barcode VARCHAR(255);
    DECLARE v_pres_cantidad DECIMAL(12,3);
    DECLARE v_es_habitual INT;
    DECLARE v_barcode VARCHAR(100);
    DECLARE v_digitos VARCHAR(100);
    DECLARE v_suma INT;
    DECLARE v_check_calc INT;
    DECLARE v_indicador INT;
    DECLARE v_gtin_exists INT DEFAULT 0;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_resultado = 'ERROR';
        SET p_mensaje = CONCAT('Error en la transaccion: ', GETSTACKEDDIAGNOSTICS_MESSAGE(1));
        SET p_id_material = 0;
    END;

    SET p_resultado = 'ERROR';
    SET p_mensaje = '';
    SET p_id_material = 0;

    START TRANSACTION;

    IF p_codigo_barras IS NOT NULL AND p_codigo_barras != '' THEN
        SET v_barcode = TRIM(p_codigo_barras);
        IF LENGTH(v_barcode) NOT IN (8, 13) OR v_barcode NOT REGEXP '^[0-9]+$' THEN
            SET p_mensaje = 'El codigo de barras debe tener 8 (EAN-8) o 13 (EAN-13) digitos numericos.';
            ROLLBACK;
        ELSE
            SET v_digitos = v_barcode;
            SET v_suma = 0;
            SET v_i = 1;
            WHILE v_i <= LENGTH(v_digitos) - 1 DO
                IF LENGTH(v_barcode) = 8 THEN
                    SET v_suma = v_suma + (CAST(SUBSTRING(v_digitos, v_i, 1) AS UNSIGNED) * IF(v_i % 2 = 1, 3, 1));
                ELSE
                    SET v_suma = v_suma + (CAST(SUBSTRING(v_digitos, v_i, 1) AS UNSIGNED) * IF(v_i % 2 = 1, 1, 3));
                END IF;
                SET v_i = v_i + 1;
            END WHILE;
            SET v_check_calc = (10 - (v_suma % 10)) % 10;
            IF v_check_calc != CAST(SUBSTRING(v_digitos, LENGTH(v_digitos), 1) AS UNSIGNED) THEN
                SET p_mensaje = 'El codigo de barras tiene un digito verificador invalido.';
                ROLLBACK;
            ELSE
                SELECT COUNT(*) INTO v_count FROM materiales
                WHERE codigo_barras = v_barcode AND (p_id IS NULL OR p_id = '' OR id != CAST(p_id AS UNSIGNED));
                IF v_count > 0 THEN
                    SET p_mensaje = CONCAT('El codigo de barras ', v_barcode, ' ya esta asignado a otro material.');
                    ROLLBACK;
                END IF;
            END IF;
        END IF;
    END IF;

    IF p_mensaje != '' THEN
        SET p_resultado = 'ERROR';
    ELSE
        IF p_id IS NOT NULL AND p_id != '' THEN
            SET v_es_update = TRUE;
            SET v_current_id = CAST(p_id AS UNSIGNED);
            SELECT COUNT(*) INTO v_count FROM materiales WHERE id = v_current_id;
            IF v_count = 0 THEN
                SET p_mensaje = 'El material a actualizar no existe.';
                ROLLBACK;
            ELSE
                UPDATE materiales SET
                    codigo = p_codigo, nombre = p_nombre, descripcion = p_descripcion,
                    codigo_barras = NULLIF(TRIM(p_codigo_barras), ''),
                    categoria_id = p_categoria_id, stock_minimo = p_stock_minimo,
                    stock_maximo = p_stock_maximo, unidad_medida_id = p_unidad_medida_id,
                    trazabilidad = p_trazabilidad
                WHERE id = v_current_id;
            END IF;
        ELSE
            INSERT INTO materiales (codigo, nombre, descripcion, codigo_barras, categoria_id,
                stock_minimo, stock_maximo, unidad_medida_id, trazabilidad)
            VALUES (p_codigo, p_nombre, p_descripcion, NULLIF(TRIM(p_codigo_barras), ''),
                p_categoria_id, p_stock_minimo, p_stock_maximo, p_unidad_medida_id, p_trazabilidad);
            SET v_current_id = LAST_INSERT_ID();
        END IF;

        IF p_mensaje = '' THEN
            DELETE FROM material_proveedor WHERE id_material = v_current_id;
            IF p_prov_ids IS NOT NULL AND p_prov_ids != '' THEN
                SET v_i = 0;
                SET v_n = JSON_LENGTH(p_prov_ids);
                WHILE v_i < v_n DO
                    SET v_prov_id = JSON_UNQUOTE(JSON_EXTRACT(p_prov_ids, CONCAT('$[', v_i, ']')));
                    SET v_prov_cod = JSON_UNQUOTE(JSON_EXTRACT(p_prov_codigos, CONCAT('$[', v_i, ']')));
                    IF v_prov_id IS NOT NULL AND v_prov_id != '' THEN
                        SET v_es_habitual = IF(v_prov_habitual IS NOT NULL AND v_prov_habitual = v_i, 1, 0);
                        INSERT INTO material_proveedor (id_material, id_proveedor, codigo_referencia_prov, es_habitual)
                        VALUES (v_current_id, CAST(v_prov_id AS UNSIGNED), v_prov_cod, v_es_habitual);
                    END IF;
                    SET v_i = v_i + 1;
                END WHILE;
            END IF;

            DELETE FROM material_presentaciones WHERE id_material = v_current_id;
            IF p_pres_nombres IS NOT NULL AND p_pres_nombres != '' THEN
                SET v_i = 0;
                SET v_n = JSON_LENGTH(p_pres_nombres);
                WHILE v_i < v_n DO
                    SET v_pres_nombre = JSON_UNQUOTE(JSON_EXTRACT(p_pres_nombres, CONCAT('$[', v_i, ']')));
                    IF v_pres_nombre IS NOT NULL AND v_pres_nombre != '' THEN
                        SET v_pres_barcode = JSON_UNQUOTE(JSON_EXTRACT(p_pres_barcodes, CONCAT('$[', v_i, ']')));
                        SET v_pres_cantidad = CAST(JSON_UNQUOTE(JSON_EXTRACT(p_pres_cantidades, CONCAT('$[', v_i, ']'))) AS DECIMAL(12,3));
                        IF v_pres_barcode IS NOT NULL AND v_pres_barcode != '' THEN
                            SET v_barcode = TRIM(v_pres_barcode);
                            IF LENGTH(v_barcode) != 14 OR v_barcode NOT REGEXP '^[0-9]+$' THEN
                                SET p_mensaje = CONCAT('Presentacion "', v_pres_nombre, '": el GTIN-14 debe tener exactamente 14 digitos numericos.');
                                SET v_i = v_n;
                            ELSE
                                SET v_suma = 0;
                                SET v_indicador = 1;
                                WHILE v_indicador <= 13 DO
                                    SET v_suma = v_suma + (CAST(SUBSTRING(v_barcode, v_indicador, 1) AS UNSIGNED) * IF((14 - v_indicador) % 2 = 0, 1, 3));
                                    SET v_indicador = v_indicador + 1;
                                END WHILE;
                                SET v_check_calc = (10 - (v_suma % 10)) % 10;
                                IF v_check_calc != CAST(SUBSTRING(v_barcode, 14, 1) AS UNSIGNED) THEN
                                    SET p_mensaje = CONCAT('Presentacion "', v_pres_nombre, '": el GTIN-14 tiene un digito verificador invalido.');
                                    SET v_i = v_n;
                                ELSE
                                    SELECT COUNT(*) INTO v_gtin_exists FROM material_presentaciones WHERE codigo_barras = v_barcode;
                                    IF v_gtin_exists > 0 THEN
                                        SET p_mensaje = CONCAT('El GTIN-14 ', v_barcode, ' ya esta asignado a otra presentacion.');
                                        SET v_i = v_n;
                                    END IF;
                                END IF;
                            END IF;
                        ELSE
                            SET v_barcode = NULL;
                        END IF;
                        IF p_mensaje = '' THEN
                            INSERT INTO material_presentaciones (id_material, nombre, codigo_barras, cantidad_unidades)
                            VALUES (v_current_id, v_pres_nombre, v_barcode, COALESCE(v_pres_cantidad, 1.0));
                        END IF;
                    END IF;
                    SET v_i = v_i + 1;
                END WHILE;
            END IF;

            IF p_mensaje = '' THEN
                COMMIT;
                SET p_resultado = 'OK';
                SET p_mensaje = 'Material guardado correctamente';
                SET p_id_material = v_current_id;
            ELSE
                ROLLBACK;
                SET p_resultado = 'ERROR';
            END IF;
        END IF;
    END IF;
END //

DELIMITER ;


-- ============================================================================
-- FIN DEL SCRIPT
-- ============================================================================

SELECT '========================================' AS '';
SELECT 'Script completado exitosamente' AS resultado;
SELECT '========================================' AS '';
SELECT '' AS '';
SELECT 'BASE DE DATOS CREADAS:' AS '';
SELECT '  - taurus_admin (administracion, usuarios, configuracion)' AS '';
SELECT '  - taurus_wms (datos operativos, multi-tenant)' AS '';
SELECT '' AS '';
SELECT 'USUARIOS CREADOS:' AS '';
SELECT '  - SuperAdmin: admin / Admin@2024!' AS '';
SELECT '  - Operador:   operador / Admin@2024!' AS '';
SELECT '' AS '';
SELECT 'IMPORTANTE: Ejecutar este script con:' AS '';
SELECT '  mysql -u root -p < schema_completo.sql' AS '';
SELECT '' AS '';
SELECT 'NOTA: La columna descipcion de tipoubicacion fue renombrada' AS '';
SELECT '      automaticamente via prepared statement al final del script.' AS '';
