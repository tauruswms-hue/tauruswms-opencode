-- Crear tabla de clases de pedido
CREATE TABLE clases_pedido (
    id_clase INT AUTO_INCREMENT PRIMARY KEY,
    nombre   VARCHAR(100) NOT NULL,
    activo   TINYINT(1) NOT NULL DEFAULT 1
);

-- Datos iniciales
INSERT INTO clases_pedido (nombre) VALUES
    ('Venta'),
    ('Reposición'),
    ('Muestra'),
    ('Devolución');

-- Agregar columna FK en pedidos_cabecera
ALTER TABLE pedidos_cabecera
    ADD COLUMN id_clase INT NULL AFTER id_cliente,
    ADD CONSTRAINT fk_pedido_clase FOREIGN KEY (id_clase) REFERENCES clases_pedido (id_clase);
