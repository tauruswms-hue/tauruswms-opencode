# AGENTS.md — Taurus WMS

## What this is

Flask-based Warehouse Management System. Two separate Flask apps:

- **`app.py`** — main WMS app (port 5000)
- **`admin.py`** — admin panel for tenant/user management (port 5001)

Both share the same `.env` and `taurus_admin` database for admin config.

## Run

```bash
python app.py    # main app — http://localhost:5000
python admin.py  # admin panel — http://localhost:5001
```

No test suite, no linter, no formatter configured. `requirements.txt` lists 3 packages but the codebase also requires `pymysql`, `openpyxl`, and `werkzeug` (used directly, not via requirements).

## Database

- **Engine**: MySQL via `pymysql` (no ORM)
- **Three databases**:
  - `taurus_wms` — operational data (tenants configure this via admin UI)
  - `taurus_admin` — users, tenants, config (connection from `.env`)
  - `taurus_intercambio` — interfase con sistemas externos: tablas `intercambio_*` donde el sistema de gestión inserta registros para que el WMS los aplique (ver "Intercambio" abajo)
- **Config bootstrap**: DB connection params for `taurus_wms` are stored in the `configuracion` table inside `taurus_admin` (`modules/db_config.py:26`). `.env` provides only the admin DB credentials and fallback values.
- **Schema changes**: SQL migration scripts in `migrations/`. Processed migrations go in `migrations/procesados/`. Run manually against MySQL — no migration runner. Check `migrations/*.sql` (not in `procesados/`) for pending migrations before making schema changes.
- **Multi-engine DDL scripts**: `migrations/create_admin_{engine}.sql`, `migrations/create_wms_{engine}.sql` y `migrations/create_intercambio_{engine}.sql` para cada motor (mysql, postgresql, sqlite, sqlserver). Se regeneran desde `modules/schema_generator.py` con `python modules/schema_generator.py --all` (también genera `schema_{engine}.sql` combinados en la raíz). **Todo cambio de esquema debe actualizar las definiciones en `schema_generator.py` y regenerar estos scripts.**
- **Roles y permisos**: la tabla `roles` (catálogo de roles, en `taurus_admin`) y `roles_rutas` (permisos por rol, en `taurus_admin`). El catálogo de rutas asignables es `ROUTE_CATALOG` en `modules/schema_generator.py` — al agregar módulos/rutas, actualizarlo (soporta wildcards `/*` y `*`). El matcheo por path con wildcard está en `verificar_permiso_ruta` (`app.py`).
- **Enforcement global de permisos**: la asignación rol→ruta aplica a **todos los tenants** (no hay scoping por tenant). El middleware `verificar_autenticacion_y_permisos` (`app.py`) recalcula `session['rutas_permitidas']` en cada request (los cambios del panel admin aplican sin re-login) y bloquea cualquier ruta catalogada no habilitada para el rol. Rutas **no** incluidas en `ROUTE_CATALOG` quedan auth-only (solo exigen login): `/`, `/login`, `/logout`, `/acerca`, `/estado`, `/rentradas`, `/rsalidas`, `/omc/tipos_ubicacion` (estas últimas se agregan al catálogo al incorporarles gestión). `SUPERADMIN` y acceso `*` (switch "Acceso total" en `admin/roles/rutas`) bypassan la verificación.

## Multi-tenancy

Every operational query uses `tenant_id` from the Flask session. The filter pattern is always:

```sql
WHERE (%s IS NULL OR tenant_id = %s)
```

When `tenant_id` is NULL (superadmin), all rows are returned. This pattern appears in every module — do not omit it.

## Intercambio

Interfase con sistemas externos: el sistema de gestión inserta registros en `taurus_intercambio` y el WMS los aplica.

- **Tablas**: por módulo, una tabla `intercambio_<modulo>` en `taurus_intercambio` (un registro = una operación), más `intercambio_log` (historial de ejecuciones). Módulos: `intercambio_materiales` (→ `wms.materiales`, upsert por `codigo`), `intercambio_rutas` (→ `wms.rutas`, upsert por `nombre_ruta`), `intercambio_transportes` (→ `wms.transportes`, upsert por `codigo`), `intercambio_transporte_rutas` (→ `wms.transporte_rutas`, asignación ruta↔transporte resuelta por `transporte_codigo` + `ruta_nombre`), `intercambio_clientes` (→ `wms.clientes`, upsert por `codigo`, referencias `ruta_nombre` y `transporte_codigo`), `intercambio_pedidos` (→ `wms.pedidos_cabecera` + `pedidos_detalle`, upsert por `nro_pedido`, cabecera en columnas y items en `items_json` como lista `{material_codigo, cantidad, tipo_stock}`; referencias `cliente_codigo`, `ruta_nombre`, `transporte_codigo`, `clase_nombre`). Definidas en `INTERCAMBIO_TABLES` (`modules/schema_generator.py`).
- **Flujo**: el sistema externo inserta filas con `estado='pendiente'` y `accion` en `alta|modificacion|baja`. El proceso lee las pendientes y aplica cada una sobre el WMS (baja desactiva; en `rutas` borra, en `transporte_rutas` elimina la asignación y en `pedidos` borra el pedido solo si sigue `Pendiente`). Commit por registro; si una falla queda `estado='error'` con `error_mensaje` (truncado a 2000) y el resto continúa. La columna `id_<entidad>_wms` guarda el id resultante en el WMS.
- **Código**: `modules/intercambio.py` — núcleo genérico `_procesar_tabla_intercambio()` + `MODULOS` (catálogo módulo→tabla/columna id/aplicador), `procesar_intercambio_<modulo>()` por módulo y `procesar_intercambio()` que corre todos en orden de dependencia (rutas → transportes → transporte_rutas → clientes → materiales → pedidos). `reintentar_intercambio()` (acepta `tabla`) y `reintentar_todo()`. Conexiones int/wms/admin inyectables (se abren/cierran solas si no se pasan). Para agregar un módulo: nueva tabla en `INTERCAMBIO_TABLES` + aplicar_func + entrada en `MODULOS`.
- **Disparo**: botones en la UI (WMS `/intercambio`, panel admin `/admin/intercambio`) y script `procesar_intercambio.py` (para cron/Task Scheduler, acepta `--tenant <id>`).
- **Config de conexión a `taurus_intercambio`**: claves `INTERCAMBIO_*` en la tabla `configuracion` de `taurus_admin` (editables desde el panel admin), con fallback a variables de entorno `DB_INTERCAMBIO_*`. Leído por `get_intercambio_config()` / `get_intercambio_connection()` (`modules/db_config.py`). Ojo: la cache se invalida con `clear_config_cache()` — si se cambian los valores desde la UI en la misma sesión, reiniciar o limpiar cache.
- **Scoping por tenant**: los registros llevan `tenant_codigo`, que se resuelve contra `taurus_admin.tenants.codigo`. Si se pasa `tenant_id` al proceso, solo procesa los de ese tenant.
- **Permisos**: rutas `/intercambio*` en `ROUTE_CATALOG` (grupo "Intercambio") — asignables por rol desde el panel admin. La sección admin es solo SUPERADMIN.
- **Nota**: los `%s` placeholders (pymysql) no funcionan con sqlite3 en runtime; los scripts `create_*_sqlite.sql` solo sirven como referencia/DLL, no para ejecutar el WMS.

## Architecture

- **Blueprints** in `modules/` — one per domain (materiales, pedidos, recepciones, despacho, etc.)
- **`modules/db_config.py`** — central DB connection helper. Use `get_db_connection()` for operational queries, `_get_admin_connection()` for admin DB.
- **`modules/batch_utils.py`** — shared CSV/JSON/XLSX import/export helpers used by materiales, pedidos, recepciones, etc.
- **No REST API** — all routes return rendered Jinja2 templates. JSON endpoints exist only for inline AJAX actions (save, delete, test connection).
- **Auth**: Session-based. Login reads from `taurus_admin.usuarios`. Role-based route permissions via `roles_rutas` table. `@verificar_permiso_decorator` in `app.py`.
- **Session expiry**: 8 hours (`app.py:616`). Login redirect at 5 min idle (`app.py:273`).

## Key conventions

- UI language is **Spanish** (variable names, route names, flash messages, DB column names)
- Column `descripcion` in `tipoubicacion` table — no accent, match it exactly in SQL
- ID columns are inconsistent: some tables use `id`, others `id_pedido`, `id_cliente`, `id_transporte`, etc. Check the actual table before writing queries.
- Tenant IDs in admin URLs are base64-encoded (`encode_id`/`decode_id` in `modules/admin.py`) — do not pass raw integers in admin routes
- `openpyxl` is used for XLSX export; `werkzeug.security` for password hashing (`scrypt`)

## Gotchas

- `ADMIN_DB_CONFIG` in `app.py` and `modules/db_config.py` both have hardcoded default password (`Taurus_2001`) — this is intentional for dev, not a secret leak
- Both `app.py` and `admin.py` have hardcoded `secret_key` values — same pattern, dev-only
- `requirements.txt` lists only 3 packages; install `pymysql`, `openpyxl` manually or via `pip install` as needed
- No `.gitignore` at project root (only in `.venv/` and `.idea/`) — watch for committing `.env` or `__pycache__`
- `crear_tablas.py` is a one-time bootstrap script with hardcoded credentials — do not run in production
- Template files in `templates/partials/` are Jinja2 includes (modals, sidebar), not standalone pages
- `picking_docs/` contains generated PDF pick tickets — not source code
