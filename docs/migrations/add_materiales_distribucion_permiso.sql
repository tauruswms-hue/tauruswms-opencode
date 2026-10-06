-- db: admin
-- Otorga la ruta /materiales/distribucion/* (ver el stock de un material por
-- posición) a los roles que ya tenían /materiales, para que quede habilitada
-- en instalaciones existentes. Idempotente. SQL estándar, válido en los 4 engines.
INSERT INTO roles_rutas (rol, ruta)
SELECT rol, '/materiales/distribucion/*'
FROM roles_rutas
WHERE ruta = '/materiales'
  AND NOT EXISTS (
      SELECT 1 FROM roles_rutas rr2
      WHERE rr2.rol = roles_rutas.rol AND rr2.ruta = '/materiales/distribucion/*'
  );
