-- engine: mysql
-- db: wms
-- Contactos de clientes: un cliente puede tener varios, cada uno con nombre,
-- apellido, departamento o sección, rol, teléfono y mail. La DDL multi-engine
-- ya se regeneró; esta migración cubre las instalaciones MySQL existentes.
-- Se puede correr más de una vez: la tabla se crea solo si no existe y el
-- contacto único anterior (clientes.contacto_nombre) se copia solo a los
-- clientes que todavía no tienen ningún contacto.

CREATE TABLE IF NOT EXISTS `cliente_contactos` (
    `id` int AUTO_INCREMENT PRIMARY KEY,
    `id_cliente` int NOT NULL,
    `nombre` varchar(100) NOT NULL,
    `apellido` varchar(100),
    `departamento` varchar(100),
    `rol` varchar(100),
    `telefono` varchar(50),
    `email` varchar(100),
    `tenant_id` int,
    KEY `idx_cliente_contactos_cliente` (`id_cliente`),
    KEY `idx_cliente_contactos_tenant` (`tenant_id`),
    CONSTRAINT `fk_cliente_contactos_id_cliente` FOREIGN KEY (`id_cliente`) REFERENCES `clientes` (`id_cliente`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO cliente_contactos (id_cliente, nombre, tenant_id)
SELECT c.id_cliente, c.contacto_nombre, c.tenant_id
FROM clientes c
WHERE c.contacto_nombre IS NOT NULL AND c.contacto_nombre <> ''
  AND NOT EXISTS (SELECT 1 FROM cliente_contactos cc WHERE cc.id_cliente = c.id_cliente);
