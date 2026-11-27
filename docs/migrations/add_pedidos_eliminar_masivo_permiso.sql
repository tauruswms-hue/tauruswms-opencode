-- db: admin
-- La anulación masiva (/pedidos/eliminar_masivo) pasa a estar en el catálogo de
-- rutas. Se la otorga a los roles que ya podían anular pedidos. Idempotente.
-- SQL estándar, válido en los 4 engines.
INSERT INTO roles_rutas (rol, ruta)
SELECT rol, '/pedidos/eliminar_masivo'
FROM roles_rutas
WHERE ruta = '/pedidos/eliminar/*'
  AND NOT EXISTS (
      SELECT 1 FROM roles_rutas rr2
      WHERE rr2.rol = roles_rutas.rol AND rr2.ruta = '/pedidos/eliminar_masivo'
  );
