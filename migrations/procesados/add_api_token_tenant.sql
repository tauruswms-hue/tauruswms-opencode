-- Agrega el campo api_token a la tabla tenants (hash sha256 del token Bearer
-- que usan los clientes de la API REST /api/v1). Se genera desde el panel admin.
ALTER TABLE tenants ADD COLUMN api_token VARCHAR(255) NULL AFTER api_key;
