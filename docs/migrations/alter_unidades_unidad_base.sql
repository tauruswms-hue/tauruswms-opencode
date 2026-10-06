-- engine: mysql
-- db: wms
-- unidades_medida.unidad_base_referencia pasa a guardar el CÓDIGO de la unidad
-- base (otra unidad de la misma magnitud) en lugar de un símbolo suelto: se
-- amplía al largo de unidades_medida.codigo y deja de tener 'U' por defecto
-- (NULL = la unidad es ella misma una unidad base). Ver modules/unidades.py.
-- Los valores anteriores que no coinciden con el código de ninguna unidad no
-- se tocan: la aplicación los trata como "sin unidad base" y se corrigen al
-- guardar la unidad. Se puede correr más de una vez.
ALTER TABLE unidades_medida MODIFY unidad_base_referencia varchar(50) NULL DEFAULT NULL;
