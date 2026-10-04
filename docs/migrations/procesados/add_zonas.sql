-- ============================================================
-- Crear tabla zonas y migrar campo zona de ubicaciones
-- ============================================================

-- 1. Tabla zonas
CREATE TABLE IF NOT EXISTS zonas (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    codigo      VARCHAR(20)  NOT NULL COMMENT 'Código único de la zona',
    nombre      VARCHAR(100) NOT NULL COMMENT 'Nombre descriptivo',
    descripcion TEXT         NULL,
    activo      TINYINT(1)   NOT NULL DEFAULT 1,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE INDEX uk_zona_codigo (codigo),
    INDEX        idx_zona_activo (activo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Migrar valores de texto existentes en ubicaciones.zona → zonas
INSERT IGNORE INTO zonas (codigo, nombre)
SELECT DISTINCT zona, zona
FROM ubicaciones
WHERE zona IS NOT NULL AND zona <> '';

-- 3. Agregar columna id_zona (FK) en ubicaciones
ALTER TABLE ubicaciones
    ADD COLUMN IF NOT EXISTS id_zona INT NULL
        COMMENT 'Referencia a zonas.id' AFTER zona;

-- 4. Poblar id_zona a partir de la columna texto zona
UPDATE ubicaciones u
JOIN   zonas z ON z.codigo = u.zona
SET    u.id_zona = z.id
WHERE  u.zona IS NOT NULL AND u.zona <> '';

-- 5. Agregar orden_picking
ALTER TABLE ubicaciones
    ADD COLUMN IF NOT EXISTS orden_picking INT NOT NULL DEFAULT 0
        COMMENT 'Orden de picking dentro de la zona' AFTER id_zona;

-- 6. FK constraint
ALTER TABLE ubicaciones
    ADD CONSTRAINT IF NOT EXISTS fk_ubicaciones_zona
        FOREIGN KEY (id_zona) REFERENCES zonas(id)
        ON UPDATE CASCADE ON DELETE SET NULL;

-- 7. La columna zona (texto) queda en desuso; eliminar luego de validar:
-- ALTER TABLE ubicaciones DROP COLUMN zona;
