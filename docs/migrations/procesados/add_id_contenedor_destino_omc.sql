-- Agrega columna para contenedor destino en OMC (movimiento contenedor a contenedor)
ALTER TABLE omc
    ADD COLUMN id_contenedor_destino VARCHAR(20) NULL DEFAULT NULL
    AFTER id_contenedor;
