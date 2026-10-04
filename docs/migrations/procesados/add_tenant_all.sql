-- ============================================================================
-- MULTI-TENANT: Agregar tenant_id a TODAS las tablas de taurus_wms
-- La tabla tenants está en taurus_admin (base de datos administrativa)
-- ============================================================================
-- Ejecutar: mysql -u root -p taurus_wms < add_tenant_all_tables.sql
-- ============================================================================

USE taurus_wms;

SET @tenant_default = 1;

-- ============================================================================
-- TABLAS MAESTRAS (si no tienen tenant_id)
-- ============================================================================

-- 1. usuarios
-- ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS tenant_id INT(11) NULL;
-- ALTER TABLE usuarios ADD INDEX idx_usuarios_tenant (tenant_id);

-- 2. materiales
-- ALTER TABLE materiales ADD COLUMN IF NOT EXISTS tenant_id INT(11) NULL;
-- ALTER TABLE materiales ADD INDEX idx_materiales_tenant (tenant_id);

-- 3. proveedores
-- ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS tenant_id INT(11) NULL;
-- ALTER TABLE proveedores ADD INDEX idx_proveedores_tenant (tenant_id);

-- 4. categorias
-- ALTER TABLE categorias ADD COLUMN IF NOT EXISTS tenant_id INT(11) NULL;
-- ALTER TABLE categorias ADD INDEX idx_categorias_tenant (tenant_id);

-- 5. ubicaciones
-- ALTER TABLE ubicaciones ADD COLUMN IF NOT EXISTS tenant_id INT(11) NULL;
-- ALTER TABLE ubicaciones ADD INDEX idx_ubicaciones_tenant (tenant_id);

-- 6. unidades_medida
-- ALTER TABLE unidades_medida ADD COLUMN IF NOT EXISTS tenant_id INT(11) NULL;
-- ALTER TABLE unidades_medida ADD INDEX idx_unidades_tenant (tenant_id);

-- 7. material_proveedor
-- ALTER TABLE material_proveedor ADD COLUMN IF NOT EXISTS tenant_id INT(11) NULL;
-- ALTER TABLE material_proveedor ADD INDEX idx_matprov_tenant (tenant_id);

-- 8. material_presentaciones
-- ALTER TABLE material_presentaciones ADD COLUMN IF NOT EXISTS tenant_id INT(11) NULL;
-- ALTER TABLE material_presentaciones ADD INDEX idx_matpres_tenant (tenant_id);

-- ============================================================================
-- TABLAS OPERATIVAS (si no tienen tenant_id)
-- ============================================================================

-- 9. clientes
-- ALTER TABLE clientes ADD COLUMN IF NOT EXISTS tenant_id INT(11) NULL;
-- ALTER TABLE clientes ADD INDEX idx_clientes_tenant (tenant_id);

-- 10. rutas
-- ALTER TABLE rutas ADD COLUMN IF NOT EXISTS tenant_id INT(11) NULL;
-- ALTER TABLE rutas ADD INDEX idx_rutas_tenant (tenant_id);

-- 11. clases_pedido
-- ALTER TABLE clases_pedido ADD COLUMN IF NOT EXISTS tenant_id INT(11) NULL;
-- ALTER TABLE clases_pedido ADD INDEX idx_clases_pedido_tenant (tenant_id);

-- 12. transportes
-- ALTER TABLE transportes ADD COLUMN IF NOT EXISTS tenant_id INT(11) NULL;
-- ALTER TABLE transportes ADD INDEX idx_transportes_tenant (tenant_id);

-- 13. recepciones_cabecera
-- ALTER TABLE recepciones_cabecera ADD COLUMN IF NOT EXISTS tenant_id INT(11) NULL;
-- ALTER TABLE recepciones_cabecera ADD INDEX idx_recepciones_cab_tenant (tenant_id);

-- 14. recepciones_detalle
-- ALTER TABLE recepciones_detalle ADD COLUMN IF NOT EXISTS tenant_id INT(11) NULL;
-- ALTER TABLE recepciones_detalle ADD INDEX idx_recepciones_det_tenant (tenant_id);

-- 15. pedidos_cabecera
-- ALTER TABLE pedidos_cabecera ADD COLUMN IF NOT EXISTS tenant_id INT(11) NULL;
-- ALTER TABLE pedidos_cabecera ADD INDEX idx_pedidos_cab_tenant (tenant_id);

-- 16. pedidos_detalle
-- ALTER TABLE pedidos_detalle ADD COLUMN IF NOT EXISTS tenant_id INT(11) NULL;
-- ALTER TABLE pedidos_detalle ADD INDEX idx_pedidos_det_tenant (tenant_id);

-- 17. inventarios_cabecera
-- ALTER TABLE inventarios_cabecera ADD COLUMN IF NOT EXISTS tenant_id INT(11) NULL;
-- ALTER TABLE inventarios_cabecera ADD INDEX idx_inventarios_cab_tenant (tenant_id);

-- 18. inventarios_detalle
-- ALTER TABLE inventarios_detalle ADD COLUMN IF NOT EXISTS tenant_id INT(11) NULL;
-- ALTER TABLE inventarios_detalle ADD INDEX idx_inventarios_det_tenant (tenant_id);

-- 19. stockcontable
-- ALTER TABLE stockcontable ADD COLUMN IF NOT EXISTS tenant_id INT(11) NULL;
-- ALTER TABLE stockcontable ADD INDEX idx_stockcontable_tenant (tenant_id);

-- 20. zonas
-- ALTER TABLE zonas ADD COLUMN IF NOT EXISTS tenant_id INT(11) NULL;
-- ALTER TABLE zonas ADD INDEX idx_zonas_tenant (tenant_id);

-- 21. tipoubicacion
-- ALTER TABLE tipoubicacion ADD COLUMN IF NOT EXISTS tenant_id INT(11) NULL;
-- ALTER TABLE tipoubicacion ADD INDEX idx_tipoubicacion_tenant (tenant_id);

-- ============================================================================
-- TABLAS OMC (CRÍTICAS - Faltaban en migraciones anteriores)
-- ============================================================================

-- 22. omc
ALTER TABLE omc ADD COLUMN IF NOT EXISTS tenant_id INT(11) NULL COMMENT 'Empresa propietaria';
ALTER TABLE omc ADD INDEX idx_omc_tenant (tenant_id);

-- 23. omc_contenedores
ALTER TABLE omc_contenedores ADD COLUMN IF NOT EXISTS tenant_id INT(11) NULL COMMENT 'Empresa propietaria';
ALTER TABLE omc_contenedores ADD INDEX idx_omc_cont_tenant (tenant_id);

-- ============================================================================
-- TABLAS DE PARÁMETROS (compartidas pero referenciables)
-- ============================================================================

-- 24. parametros (tabla única del sistema)
-- ALTER TABLE parametros ADD COLUMN IF NOT EXISTS tenant_id INT(11) NULL;
-- ALTER TABLE parametros ADD INDEX idx_parametros_tenant (tenant_id);

-- ============================================================================
-- ACTUALIZAR tenant_id PARA DATOS EXISTENTES
-- ============================================================================

-- Asignar tenant_id a tablas maestras basadas en datos existentes
UPDATE materiales SET tenant_id = @tenant_default WHERE tenant_id IS NULL;
UPDATE proveedores SET tenant_id = @tenant_default WHERE tenant_id IS NULL;
UPDATE categorias SET tenant_id = @tenant_default WHERE tenant_id IS NULL;
UPDATE ubicaciones SET tenant_id = @tenant_default WHERE tenant_id IS NULL;
UPDATE unidades_medida SET tenant_id = @tenant_default WHERE tenant_id IS NULL;

-- Asignar tenant_id a tablas operativas
UPDATE clientes SET tenant_id = @tenant_default WHERE tenant_id IS NULL;
UPDATE rutas SET tenant_id = @tenant_default WHERE tenant_id IS NULL;
UPDATE clases_pedido SET tenant_id = @tenant_default WHERE tenant_id IS NULL;
UPDATE transportes SET tenant_id = @tenant_default WHERE tenant_id IS NULL;
UPDATE recepciones_cabecera SET tenant_id = @tenant_default WHERE tenant_id IS NULL;
UPDATE recepciones_detalle SET tenant_id = @tenant_default WHERE tenant_id IS NULL;
UPDATE pedidos_cabecera SET tenant_id = @tenant_default WHERE tenant_id IS NULL;
UPDATE pedidos_detalle SET tenant_id = @tenant_default WHERE tenant_id IS NULL;
UPDATE inventarios_cabecera SET tenant_id = @tenant_default WHERE tenant_id IS NULL;
UPDATE inventarios_detalle SET tenant_id = @tenant_default WHERE tenant_id IS NULL;
UPDATE stockcontable SET tenant_id = @tenant_default WHERE tenant_id IS NULL;
UPDATE zonas SET tenant_id = @tenant_default WHERE tenant_id IS NULL;
UPDATE tipoubicacion SET tenant_id = @tenant_default WHERE tenant_id IS NULL;

-- OMC y omc_contenedores
UPDATE omc SET tenant_id = @tenant_default WHERE tenant_id IS NULL;
UPDATE omc_contenedores SET tenant_id = @tenant_default WHERE tenant_id IS NULL;

-- Material_proveedor y material_presentaciones (heredar de materiales)
UPDATE material_proveedor mp 
INNER JOIN materiales m ON mp.id_material = m.id 
SET mp.tenant_id = m.tenant_id 
WHERE mp.tenant_id IS NULL;

UPDATE material_presentaciones mp 
INNER JOIN materiales m ON mp.id_material = m.id 
SET mp.tenant_id = m.tenant_id 
WHERE mp.tenant_id IS NULL;

-- ============================================================================
-- VERIFICACIÓN
-- ============================================================================
SELECT 'Migración completada: tenant_id agregado a todas las tablas' AS resultado;

-- Listar tablas con tenant_id
SELECT TABLE_NAME 
FROM information_schema.COLUMNS 
WHERE TABLE_SCHEMA = 'taurus_wms' 
AND COLUMN_NAME = 'tenant_id'
GROUP BY TABLE_NAME;
