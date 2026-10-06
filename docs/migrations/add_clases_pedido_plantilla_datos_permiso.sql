-- db: admin
-- La descarga de clases sugeridas (/clases-pedido/plantilla-datos/*) pasa a estar
-- en el catálogo de rutas. Se la otorga a los roles que ya podían importar clases
-- de pedido, que es desde donde se usa. Idempotente. SQL estándar, válido en los
-- 4 engines.
INSERT INTO roles_rutas (rol, ruta)
SELECT rol, '/clases-pedido/plantilla-datos/*'
FROM roles_rutas
WHERE ruta = '/clases-pedido/importar'
  AND NOT EXISTS (
      SELECT 1 FROM roles_rutas rr2
      WHERE rr2.rol = roles_rutas.rol AND rr2.ruta = '/clases-pedido/plantilla-datos/*'
  );
