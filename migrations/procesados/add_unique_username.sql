-- Agregar índice único en username para evitar duplicados globalmente

USE taurus_admin;

-- Agregar constraint único en username
ALTER TABLE usuarios ADD UNIQUE INDEX idx_username_unico (username);
