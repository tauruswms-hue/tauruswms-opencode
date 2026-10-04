-- Insertar configuración de base de datos en la tabla configuracion
-- BD: taurus_admin

USE taurus_admin;

INSERT INTO configuracion (clave, valor, descripcion) VALUES 
('DB_HOST', 'localhost', 'Host del servidor de base de datos'),
('DB_PORT', '3306', 'Puerto del servidor MySQL'),
('DB_NAME', 'taurus_wms', 'Nombre de la base de datos principal'),
('DB_USER', 'taurus', 'Usuario de la base de datos'),
('DB_PASSWORD', 'Taurus_2001', 'Contraseña de la base de datos'),
('DB_CHAR_SET', 'utf8mb4', 'Charset de la base de datos')
ON DUPLICATE KEY UPDATE valor = VALUES(valor), descripcion = VALUES(descripcion);
