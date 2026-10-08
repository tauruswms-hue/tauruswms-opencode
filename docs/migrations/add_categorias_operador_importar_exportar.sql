-- db: admin
-- El rol OPERADOR podía guardar e inactivar categorías pero no importarlas,
-- exportarlas ni bajar la plantilla, cosa que sí puede en los demás maestros.
-- Se otorgan esas tres rutas a los roles que ya tienen /categorias/guardar.
-- Idempotente. SQL estándar, válido en los 4 engines.
INSERT INTO roles_rutas (rol, ruta)
SELECT rol, '/categorias/importar'
FROM roles_rutas
WHERE ruta = '/categorias/guardar'
  AND NOT EXISTS (
      SELECT 1 FROM roles_rutas rr2
      WHERE rr2.rol = roles_rutas.rol AND rr2.ruta = '/categorias/importar'
  );

INSERT INTO roles_rutas (rol, ruta)
SELECT rol, '/categorias/exportar/*'
FROM roles_rutas
WHERE ruta = '/categorias/guardar'
  AND NOT EXISTS (
      SELECT 1 FROM roles_rutas rr2
      WHERE rr2.rol = roles_rutas.rol AND rr2.ruta = '/categorias/exportar/*'
  );

INSERT INTO roles_rutas (rol, ruta)
SELECT rol, '/categorias/plantilla/*'
FROM roles_rutas
WHERE ruta = '/categorias/guardar'
  AND NOT EXISTS (
      SELECT 1 FROM roles_rutas rr2
      WHERE rr2.rol = roles_rutas.rol AND rr2.ruta = '/categorias/plantilla/*'
  );
