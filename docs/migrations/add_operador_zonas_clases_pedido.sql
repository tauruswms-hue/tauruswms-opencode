-- db: admin
-- El rol OPERADOR administra todos los maestros menos dos: no tenía ninguna ruta de Zonas
-- (aunque sí todas las de Ubicaciones y Tipos de Ubicación, que dependen de ellas) ni de
-- Clases de Pedido. Se otorgan:
--   * las rutas de Zonas a los roles que ya pueden guardar ubicaciones;
--   * las rutas de Clases de Pedido a los roles que ya pueden guardar rutas de entrega.
-- Idempotente. SQL estándar, válido en los 4 engines.
INSERT INTO roles_rutas (rol, ruta)
SELECT DISTINCT b.rol, n.ruta
FROM roles_rutas b
JOIN (
    SELECT '/zonas' AS ruta UNION ALL
    SELECT '/zonas/guardar' UNION ALL
    SELECT '/zonas/eliminar/*' UNION ALL
    SELECT '/zonas/importar' UNION ALL
    SELECT '/zonas/exportar/*' UNION ALL
    SELECT '/zonas/plantilla/*'
) n ON 1 = 1
WHERE b.ruta = '/ubicaciones/guardar'
  AND NOT EXISTS (SELECT 1 FROM roles_rutas rr WHERE rr.rol = b.rol AND rr.ruta = n.ruta);

INSERT INTO roles_rutas (rol, ruta)
SELECT DISTINCT b.rol, n.ruta
FROM roles_rutas b
JOIN (
    SELECT '/clases-pedido' AS ruta UNION ALL
    SELECT '/clases-pedido/guardar' UNION ALL
    SELECT '/clases-pedido/eliminar/*' UNION ALL
    SELECT '/clases-pedido/importar' UNION ALL
    SELECT '/clases-pedido/exportar/*' UNION ALL
    SELECT '/clases-pedido/plantilla/*' UNION ALL
    SELECT '/clases-pedido/plantilla-datos/*'
) n ON 1 = 1
WHERE b.ruta = '/rutas/guardar'
  AND NOT EXISTS (SELECT 1 FROM roles_rutas rr WHERE rr.rol = b.rol AND rr.ruta = n.ruta);
