-- Migración: muelle de salida por transporte + link pedido en OMC
-- Fecha: 2026-03-09

-- 1. Agregar muelle de salida a transportes
ALTER TABLE transportes
    ADD COLUMN id_muelle_salida INT NULL COMMENT 'Ubicación muelle de despacho asignado',
    ADD CONSTRAINT fk_transporte_muelle FOREIGN KEY (id_muelle_salida) REFERENCES ubicaciones(id);

-- 2. Agregar id_pedido a omc para OMCs generadas desde pedidos
ALTER TABLE omc
    ADD COLUMN id_pedido INT NULL AFTER id_recepcion,
    ADD CONSTRAINT fk_omc_pedido FOREIGN KEY (id_pedido) REFERENCES pedidos_cabecera(id_pedido);
