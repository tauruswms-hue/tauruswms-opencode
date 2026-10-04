-- db: admin
-- Las conexiones a taurus_wms y taurus_intercambio dejaron de leerse de la
-- tabla configuracion: ahora viven en conexiones.json (ver modules/db_config.py).
-- Esta migración borra las claves viejas para que las contraseñas no queden
-- guardadas en texto plano en taurus_admin.
-- Aplicarla DESPUÉS de crear conexiones.json en el servidor: una versión
-- anterior de la aplicación deja de conectar al WMS sin estas claves.

DELETE FROM configuracion
WHERE clave IN ('DB_ENGINE', 'DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DB_CHAR_SET',
                'INTERCAMBIO_ENGINE', 'INTERCAMBIO_HOST', 'INTERCAMBIO_PORT', 'INTERCAMBIO_NAME',
                'INTERCAMBIO_USER', 'INTERCAMBIO_PASSWORD', 'INTERCAMBIO_CHAR_SET');
