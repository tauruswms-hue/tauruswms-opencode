-- Tabla de contenedores por OMC (soporta múltiples contenedores por movimiento)
CREATE TABLE omc_contenedores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_omc INT NOT NULL,
    id_contenedor VARCHAR(20) NOT NULL,
    id_contenedor_destino VARCHAR(20) NULL,
    id_ubicacion_origen INT NOT NULL,
    FOREIGN KEY (id_omc) REFERENCES omc(id_omc)
);

C