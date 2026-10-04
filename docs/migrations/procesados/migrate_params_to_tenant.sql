-- Migración: Mover parámetros de taurus_wms.parametros a taurus_admin.tenants
-- Ejecutar en MySQL

-- 1. Agregar columnas a la tabla tenants en taurus_admin
ALTER TABLE taurus_admin.tenants
ADD COLUMN nombredelalmacen VARCHAR(255) DEFAULT '' AFTER telefono,
ADD COLUMN metodosdepicking LONGTEXT AFTER nombredelalmacen,
ADD COLUMN bajostock INT DEFAULT 0 AFTER metodosdepicking,
ADD COLUMN dias_filtro_fechas INT DEFAULT 30 AFTER bajostock;

-- 2. Migrar datos de taurus_wms.parametros a taurus_admin.tenants
UPDATE taurus_admin.tenants t
INNER JOIN taurus_wms.parametros p ON t.id = p.tenant_id
SET 
    t.nombredelalmacen = COALESCE(p.nombredelalmacen, ''),
    t.metodosdepicking = p.metodosdepicking,
    t.bajostock = COALESCE(p.bajostock, 0),
    t.dias_filtro_fechas = COALESCE(p.dias_filtro_fechas, 30);

-- 3. Eliminar tabla parametros (después de verificar la migración)
DROP TABLE taurus_wms.parametros;
