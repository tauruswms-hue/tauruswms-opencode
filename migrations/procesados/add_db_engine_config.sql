-- Migración: Agregar registro DB_ENGINE en tabla configuracion
-- Permite configurar el motor de base de datos (mysql, postgresql, sqlite)

INSERT INTO configuracion (clave, valor, descripcion)
VALUES ('DB_ENGINE', 'mysql', 'Motor de base de datos: mysql, postgresql, sqlite')
ON DUPLICATE KEY UPDATE valor = VALUES(valor);
