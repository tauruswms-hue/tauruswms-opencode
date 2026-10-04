-- db: admin
-- Fase 5.3: otorga la ruta /reportes/* a los roles que ya tenian /reportes
-- para que el modulo de reportes (pagina y exportaciones) quede habilitado
-- en instalaciones existentes.
INSERT INTO roles_rutas (rol, ruta)
SELECT rol, '/reportes/*'
FROM roles_rutas
WHERE ruta = '/reportes'
  AND NOT EXISTS (
      SELECT 1 FROM roles_rutas rr2
      WHERE rr2.rol = roles_rutas.rol AND rr2.ruta = '/reportes/*'
  );
