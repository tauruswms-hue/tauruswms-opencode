-- db: wms
-- Los códigos alternativo y del proveedor de un material valen, por defecto, lo
-- mismo que su código. El código ya lo aplica al guardar; esta migración completa
-- los materiales que existían antes. Idempotente: solo toca los que están vacíos.
-- SQL estándar, válido en los 4 engines.

UPDATE materiales SET codigo_alternativo = codigo
WHERE codigo_alternativo IS NULL OR codigo_alternativo = '';

UPDATE materiales SET codigo_proveedor = codigo
WHERE codigo_proveedor IS NULL OR codigo_proveedor = '';
