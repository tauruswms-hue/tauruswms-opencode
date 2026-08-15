-- Fase 4.2: elimina asignaciones de roles a rutas que ya no existen.
-- /movimientos, /dashboard, /rentradas y /rsalidas fueron removidos de app.py.
-- Aplicar sobre la BD admin: python migrate.py --db admin
DELETE FROM roles_rutas WHERE ruta IN ('/movimientos', '/dashboard', '/rentradas', '/rsalidas');
