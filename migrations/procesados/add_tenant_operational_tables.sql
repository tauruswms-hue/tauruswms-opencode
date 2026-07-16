-- Agregar tenant_id a tablas operativas
-- Ejecutar: mysql -u root -p taurus_admin < add_tenant_operational_tables.sql

USE taurus_admin;

-- 1. clientes
ALTER TABLE clientes ADD COLUMN tenant_id INT NULL COMMENT 'Empresa propietaria';
ALTER TABLE clientes ADD INDEX idx_clientes_tenant (tenant_id);
ALTER TABLE clientes ADD CONSTRAINT fk_clientes_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT;

-- 2. rutas
ALTER TABLE rutas ADD COLUMN tenant_id INT NULL COMMENT 'Empresa propietaria';
ALTER TABLE rutas ADD INDEX idx_rutas_tenant (tenant_id);
ALTER TABLE rutas ADD CONSTRAINT fk_rutas_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT;

-- 3. clases_pedido
ALTER TABLE clases_pedido ADD COLUMN tenant_id INT NULL COMMENT 'Empresa propietaria';
ALTER TABLE clases_pedido ADD INDEX idx_clases_pedido_tenant (tenant_id);
ALTER TABLE clases_pedido ADD CONSTRAINT fk_clases_pedido_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT;

-- 4. transportes
ALTER TABLE transportes ADD COLUMN tenant_id INT NULL COMMENT 'Empresa propietaria';
ALTER TABLE transportes ADD INDEX idx_transportes_tenant (tenant_id);
ALTER TABLE transportes ADD CONSTRAINT fk_transportes_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT;

-- 5. recepciones_cabecera y recepciones_detalle
ALTER TABLE recepciones_cabecera ADD COLUMN tenant_id INT NULL COMMENT 'Empresa propietaria';
ALTER TABLE recepciones_cabecera ADD INDEX idx_recepciones_cab_tenant (tenant_id);
ALTER TABLE recepciones_cabecera ADD CONSTRAINT fk_recepciones_cab_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT;

ALTER TABLE recepciones_detalle ADD COLUMN tenant_id INT NULL COMMENT 'Empresa propietaria';
ALTER TABLE recepciones_detalle ADD INDEX idx_recepciones_det_tenant (tenant_id);
ALTER TABLE recepciones_detalle ADD CONSTRAINT fk_recepciones_det_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT;

-- 6. pedidos_cabecera y pedidos_detalle
ALTER TABLE pedidos_cabecera ADD COLUMN tenant_id INT NULL COMMENT 'Empresa propietaria';
ALTER TABLE pedidos_cabecera ADD INDEX idx_pedidos_cab_tenant (tenant_id);
ALTER TABLE pedidos_cabecera ADD CONSTRAINT fk_pedidos_cab_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT;

ALTER TABLE pedidos_detalle ADD COLUMN tenant_id INT NULL COMMENT 'Empresa propietaria';
ALTER TABLE pedidos_detalle ADD INDEX idx_pedidos_det_tenant (tenant_id);
ALTER TABLE pedidos_detalle ADD CONSTRAINT fk_pedidos_det_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT;

-- 7. inventarios_cabecera e inventarios_detalle
ALTER TABLE inventarios_cabecera ADD COLUMN tenant_id INT NULL COMMENT 'Empresa propietaria';
ALTER TABLE inventarios_cabecera ADD INDEX idx_inventarios_cab_tenant (tenant_id);
ALTER TABLE inventarios_cabecera ADD CONSTRAINT fk_inventarios_cab_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT;

ALTER TABLE inventarios_detalle ADD COLUMN tenant_id INT NULL COMMENT 'Empresa propietaria';
ALTER TABLE inventarios_detalle ADD INDEX idx_inventarios_det_tenant (tenant_id);
ALTER TABLE inventarios_detalle ADD CONSTRAINT fk_inventarios_det_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT;

-- 8. stockcontable
ALTER TABLE stockcontable ADD COLUMN tenant_id INT NULL COMMENT 'Empresa propietaria';
ALTER TABLE stockcontable ADD INDEX idx_stockcontable_tenant (tenant_id);

-- 9. movimientos (si existe)
-- ALTER TABLE movimientos ADD COLUMN tenant_id INT NULL COMMENT 'Empresa propietaria';
-- ALTER TABLE movimientos ADD INDEX idx_movimientos_tenant (tenant_id);

-- 10. zonas
ALTER TABLE zonas ADD COLUMN tenant_id INT NULL COMMENT 'Empresa propietaria';
ALTER TABLE zonas ADD INDEX idx_zonas_tenant (tenant_id);
ALTER TABLE zonas ADD CONSTRAINT fk_zonas_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT;

-- 11. tipoubicacion
ALTER TABLE tipoubicacion ADD COLUMN tenant_id INT NULL COMMENT 'Empresa propietaria';
ALTER TABLE tipoubicacion ADD INDEX idx_tipoubicacion_tenant (tenant_id);
ALTER TABLE tipoubicacion ADD CONSTRAINT fk_tipoubicacion_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT;

-- Asignar tenant_id=1 a todos los registros existentes (ajustar según necesidad)
SET @tenant_default = (SELECT id FROM tenants LIMIT 1);

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

SELECT 'Migración completada: tenant_id agregado a tablas operativas' AS resultado;