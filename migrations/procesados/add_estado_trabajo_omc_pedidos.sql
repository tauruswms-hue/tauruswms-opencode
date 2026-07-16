-- Migración: agregar estado 'Trabajo OMC' y 'Terminado' a pedidos_cabecera
-- Fecha: 2026-03-09
-- Ejecutar solo si el campo estado es ENUM. Si es VARCHAR, no es necesario.

-- Verificar tipo actual:
-- SELECT COLUMN_TYPE FROM information_schema.COLUMNS
-- WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'pedidos_cabecera' AND COLUMN_NAME = 'estado';

-- Si el resultado es ENUM(...), ejecutar el ALTER siguiente agregando los valores faltantes.
-- Ajustar los valores existentes según lo que devuelva la consulta anterior.


