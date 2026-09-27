-- engine: mysql
-- db: admin
-- Unicidad de claves naturales en taurus_admin.
-- schema_generator ignoraba el flag "unique" a nivel columna, así que
-- admin_usuarios.username, usuarios.username, tenants.codigo y
-- configuracion.clave se crearon sin índice UNIQUE. Con eso, el
-- INSERT IGNORE de init_admin_db() (admin.py) duplicaba el usuario 'admin'
-- en cada arranque. La DDL multi-engine ya se regeneró con el fix; esta
-- migración cubre las instalaciones MySQL existentes.
-- Cada índice se crea solo si la columna no tiene ya uno UNIQUE (idempotente,
-- y seguro en instalaciones nuevas que ya traen el UNIQUE inline).

-- 1) admin_usuarios: conservar el registro más antiguo de cada username
--    (el que usa el login) y reasignarle el historial de auditoría.
UPDATE audit_logs a
JOIN admin_usuarios dup ON dup.id = a.usuario_id
JOIN (SELECT username, MIN(id) AS id FROM admin_usuarios GROUP BY username) keep_u
  ON keep_u.username = dup.username AND keep_u.id <> dup.id
SET a.usuario_id = keep_u.id;

DELETE dup FROM admin_usuarios dup
JOIN (SELECT username, MIN(id) AS id FROM admin_usuarios GROUP BY username) keep_u
  ON keep_u.username = dup.username AND keep_u.id <> dup.id;

SET @sql := IF((SELECT COUNT(*) FROM information_schema.statistics
                WHERE table_schema = DATABASE() AND table_name = 'admin_usuarios'
                  AND column_name = 'username' AND non_unique = 0) = 0,
               'CREATE UNIQUE INDEX uq_admin_usuarios_username ON admin_usuarios (username)',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 2) usuarios.username (login del WMS). Si hay duplicados falla con
--    "Duplicate entry": resolverlos a mano y volver a correr migrate.py.
SET @sql := IF((SELECT COUNT(*) FROM information_schema.statistics
                WHERE table_schema = DATABASE() AND table_name = 'usuarios'
                  AND column_name = 'username' AND non_unique = 0) = 0,
               'CREATE UNIQUE INDEX uq_usuarios_username ON usuarios (username)',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 3) tenants.codigo (lo usa intercambio para resolver tenant_codigo).
SET @sql := IF((SELECT COUNT(*) FROM information_schema.statistics
                WHERE table_schema = DATABASE() AND table_name = 'tenants'
                  AND column_name = 'codigo' AND non_unique = 0) = 0,
               'CREATE UNIQUE INDEX uq_tenants_codigo ON tenants (codigo)',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 4) configuracion.clave.
SET @sql := IF((SELECT COUNT(*) FROM information_schema.statistics
                WHERE table_schema = DATABASE() AND table_name = 'configuracion'
                  AND column_name = 'clave' AND non_unique = 0) = 0,
               'CREATE UNIQUE INDEX uq_configuracion_clave ON configuracion (clave)',
               'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
