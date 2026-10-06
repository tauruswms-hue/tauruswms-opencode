-- engine: mysql
-- db: wms
-- proveedores.direccion pasa de 255 a 500 caracteres (el formulario y la
-- importación admiten hasta 500: DIRECCION_MAX en modules/proveedores.py).
-- Solo amplía la columna; se puede correr más de una vez.
ALTER TABLE proveedores MODIFY direccion varchar(500) NULL;
