-- db: wms
-- Recepciones y la app móvil reconocían las ubicaciones de recepción por el nombre de su tipo
-- (descripción con el texto "Recepci"). Ahora usan la operación del tipo ('R'), que se carga
-- desde la pantalla de Tipos de Ubicación. Para que las instalaciones que dependían del nombre
-- sigan recibiendo en las mismas ubicaciones, se marca como de recepción a los tipos con ese
-- texto que todavía no tienen operación.
-- Idempotente. SQL estándar, válido en los 4 engines.
UPDATE tipoubicacion
SET operacion = 'R'
WHERE (operacion IS NULL OR operacion = '')
  AND descripcion LIKE '%Recepci%';
