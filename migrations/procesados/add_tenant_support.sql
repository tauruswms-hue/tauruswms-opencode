-- ============================================================================
-- MULTI-TENANT: Estrategia de base de datos compartida
-- Agrega tenant_id a tablas maestras para aislar datos por empresa
-- ============================================================================

-- 1. Crear tabla de tenants (empresas)
CREATE TABLE IF NOT EXISTS tenants (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(20) NOT NULL UNIQUE COMMENT 'Código de empresa (ej: EMP001)',
    nombre VARCHAR(100) NOT NULL COMMENT 'Nombre de la empresa',
    razon_social VARCHAR(200) NULL COMMENT 'Razón social',
    nit VARCHAR(50) NULL COMMENT 'NIT/CI/RUC',
    direccion VARCHAR(255) NULL COMMENT 'Dirección',
    telefono VARCHAR(50) NULL,
    email VARCHAR(100) NULL,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_codigo (codigo),
    INDEX idx_activo (activo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Crear tenant por defecto primero
INSERT INTO tenants (codigo, nombre, razon_social, activo) 
VALUES ('DEFAULT', 'Empresa Principal', 'Empresa Principal S.A.', TRUE);

SET @tenant_default = LAST_INSERT_ID();

-- 2. Agregar tenant_id a tabla usuarios (sin FK primero para no bloquear)
ALTER TABLE usuarios
    ADD COLUMN tenant_id INT NULL COMMENT 'Empresa a la que pertenece el usuario',
    ADD INDEX idx_usuarios_tenant (tenant_id);
ALTER TABLE usuarios
    ADD CONSTRAINT fk_usuarios_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT;

-- 3. Agregar tenant_id a tablas maestras
ALTER TABLE materiales
    ADD COLUMN tenant_id INT NULL COMMENT 'Empresa propietaria',
    ADD INDEX idx_materiales_tenant (tenant_id);
ALTER TABLE materiales
    ADD CONSTRAINT fk_materiales_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT;

ALTER TABLE proveedores
    ADD COLUMN tenant_id INT NULL COMMENT 'Empresa propietaria',
    ADD INDEX idx_proveedores_tenant (tenant_id);
ALTER TABLE proveedores
    ADD CONSTRAINT fk_proveedores_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT;

ALTER TABLE categorias
    ADD COLUMN tenant_id INT NULL COMMENT 'Empresa propietaria',
    ADD INDEX idx_categorias_tenant (tenant_id);
ALTER TABLE categorias
    ADD CONSTRAINT fk_categorias_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT;

ALTER TABLE ubicaciones
    ADD COLUMN tenant_id INT NULL COMMENT 'Empresa propietaria',
    ADD INDEX idx_ubicaciones_tenant (tenant_id);
ALTER TABLE ubicaciones
    ADD CONSTRAINT fk_ubicaciones_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT;

ALTER TABLE unidades_medida
    ADD COLUMN tenant_id INT NULL COMMENT 'Empresa propietaria',
    ADD INDEX idx_unidades_tenant (tenant_id);
ALTER TABLE unidades_medida
    ADD CONSTRAINT fk_unidades_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT;

-- 4. Tablas relación proveedores-materiales y presentaciones
ALTER TABLE material_proveedor
    ADD COLUMN tenant_id INT NULL COMMENT 'Empresa propietaria',
    ADD INDEX idx_matprov_tenant (tenant_id);
ALTER TABLE material_proveedor
    ADD CONSTRAINT fk_matprov_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT;

ALTER TABLE material_presentaciones
    ADD COLUMN tenant_id INT NULL COMMENT 'Empresa propietaria',
    ADD INDEX idx_matpres_tenant (tenant_id);
ALTER TABLE material_presentaciones
    ADD CONSTRAINT fk_matpres_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT;

-- ============================================================================
-- ASIGNAR TENANT POR DEFECTO A DATOS EXISTENTES
-- ============================================================================

UPDATE usuarios SET tenant_id = @tenant_default WHERE tenant_id IS NULL;
UPDATE materiales SET tenant_id = @tenant_default WHERE tenant_id IS NULL;
UPDATE proveedores SET tenant_id = @tenant_default WHERE tenant_id IS NULL;
UPDATE categorias SET tenant_id = @tenant_default WHERE tenant_id IS NULL;
UPDATE ubicaciones SET tenant_id = @tenant_default WHERE tenant_id IS NULL;
UPDATE unidades_medida SET tenant_id = @tenant_default WHERE tenant_id IS NULL;
UPDATE material_proveedor mp 
INNER JOIN materiales m ON mp.id_material = m.id 
SET mp.tenant_id = m.tenant_id 
WHERE mp.tenant_id IS NULL;
UPDATE material_presentaciones mp 
INNER JOIN materiales m ON mp.id_material = m.id 
SET mp.tenant_id = m.tenant_id 
WHERE mp.tenant_id IS NULL;
