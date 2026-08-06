# AGENTS.md — Taurus WMS

## What this is

Flask-based Warehouse Management System. Two Flask apps sharing the same `.env` and `taurus_admin` DB, plus a dev tool:

- **`app.py`** — main WMS app (port 5000)
- **`admin.py`** — admin panel (port 5001, UI at `/admin`); registers the blueprint from `modules/admin.py` and seeds `admin_usuarios` with `admin`/`Admin@2024!` on start (`init_admin_db()`)
- **`schema_app.py`** — schema generator GUI (port 5002), dev-only

## Run

```bash
python app.py    # main app — http://localhost:5000
python admin.py  # admin panel — http://localhost:5001/admin
```

Seed users (from `ADMIN_SEEDS` in `modules/schema_generator.py`): `admin` and `operador`, both password `Admin@2024!`.

No test suite, no linter, no formatter configured.

## Database

- **Multi-engine, no ORM**: runtime supports `mysql` (default) | `postgresql` | `sqlite` | `sqlserver`, chosen by `DB_ENGINE` (`get_db_engine()`, `modules/db_config.py`). Postgres needs `psycopg2`, SQL Server needs `pymssql` — **neither is in `requirements.txt`** (which lists Flask, PyMySQL, openpyxl, python-dotenv, Werkzeug, Flask-WTF).
- **Three databases**:
  - `taurus_wms` — operational data (tenants configure connection via admin UI)
  - `taurus_admin` — users, tenants, config
  - `taurus_intercambio` — interfase con sistemas externos (ver "Intercambio" abajo)
- **Connection bootstrap**:
  - Admin DB: env vars `DB_ADMIN_*` (`_get_admin_connection()`).
  - WMS DB: `configuracion` table inside `taurus_admin` (`get_db_config()`); env `DB_*` are only fallback.
  - Intercambio DB: `INTERCAMBIO_*` keys in `configuracion`, env `DB_INTERCAMBIO_*` fallback (`get_intercambio_config()`).
  - Caches in `db_config.py`; changes from the UI need `clear_config_cache()` (or app restart).
- **Multi-engine identifier quoting**: never hardcode backticks in SQL. Quote identifiers through `modules/sql_dialect.py` — `sql_quote()` and `insert_ignore_sql()` (see `app.py:289`). Raw MySQL backticks break postgres/sqlite/sqlserver.
- **App code uses pymysql `%s` placeholders and dict-style rows** (`DictCursor`). The sqlite3 driver does not accept `%s`, so `create_*_sqlite.sql` are reference/DLL only — sqlite is not a functional runtime for the app.

## Multi-tenancy

Every operational query uses `tenant_id` from the Flask session. The filter pattern is always:

```sql
WHERE (%s IS NULL OR tenant_id = %s)
```

When `tenant_id` is NULL (superadmin), all rows are returned. This pattern appears in every module — do not omit it.

## Schema changes / migrations

- Pending DDL lives in `migrations/*.sql` (not in `procesados/`); applied manually against the DB — no migration runner. Check pending migrations before writing new schema SQL.
- Table/seed definitions live in `modules/schema_generator.py` (`ADMIN_TABLES`, `WMS_TABLES`, `INTERCAMBIO_TABLES`, `ADMIN_SEEDS`, `ROUTE_CATALOG`). **Any schema change must update these and regenerate:**
  ```bash
  python modules/schema_generator.py --all   # root schema_{engine}.sql + migrations/create_{admin,wms,intercambio}_{engine}.sql (4 engines)
  ```
- `generar_schema.py` — CLI to generate **and execute** schema against live DBs (`--execute`, `--drop`, `--seed`, `--dry-run`, `--admin-only`/`--wms-only`). Reads `.env` (`DB_ADMIN_*`/`DB_*`).
- `schema_app.py` — GUI wrapper (port 5002) writing `schemas/schema_{engine}_admin_wms.sql` (the combined admin+wms+intercambio DDL).

## Roles y permisos

- Catálogo de roles: `roles` (taurus_admin); permisos por rol: `roles_rutas` (rol, ruta). Rutas asignables = `ROUTE_CATALOG` en `modules/schema_generator.py` — al agregar módulos/rutas, actualizarlo (soporta wildcards `/*` y `*`). Matcheo por path en `verificar_permiso_ruta` / `_match_permiso` (`app.py`).
- La asignación rol→ruta aplica a **todos los tenants** (sin scoping). El middleware `verificar_autenticacion_y_permisos` (`app.py`) recalcula `session['rutas_permitidas']` en cada request (los cambios del panel admin aplican sin re-login) y bloquea cualquier ruta catalogada no habilitada para el rol.
- Rutas **no** catalogadas quedan auth-only (solo exigen login): `/`, `/login`, `/logout`, `/acerca`, `/estado`, `/api/xlsx_sheetnames` (`/login` y `/acerca` además son públicas). `/rentradas`, `/rsalidas` y `/omc/tipos_ubicacion` **sí** están en el catálogo (grupos "Sistema"/"OMC").
- `SUPERADMIN` y el acceso `*` (switch "Acceso total") bypassan la verificación. Helper `tiene_permiso_ruta` expuesto a Jinja (`app.py:218`) para condicionar la UI.

## Intercambio

Interfase con sistemas externos: el sistema de gestión inserta registros en `taurus_intercambio` y el WMS los aplica.

- **Tablas**: por módulo, una tabla `intercambio_<modulo>` en `taurus_intercambio` (un registro = una operación), más `intercambio_log` (historial de ejecuciones). Módulos: `intercambio_materiales` (→ `wms.materiales`, upsert por `codigo`), `intercambio_rutas` (→ `wms.rutas`, upsert por `nombre_ruta`), `intercambio_transportes` (→ `wms.transportes`, upsert por `codigo`), `intercambio_transporte_rutas` (→ `wms.transporte_rutas`, asignación ruta↔transporte resuelta por `transporte_codigo` + `ruta_nombre`), `intercambio_clientes` (→ `wms.clientes`, upsert por `codigo`, referencias `ruta_nombre` y `transporte_codigo`), `intercambio_pedidos` (→ `wms.pedidos_cabecera` + `pedidos_detalle`, upsert por `nro_pedido`, cabecera en columnas y items en `items_json` como lista `{material_codigo, cantidad, tipo_stock}`; referencias `cliente_codigo`, `ruta_nombre`, `transporte_codigo`, `clase_nombre`). Definidas en `INTERCAMBIO_TABLES` (`modules/schema_generator.py`).
- **Flujo**: el sistema externo inserta filas con `estado='pendiente'` y `accion` en `alta|modificacion|baja`. El proceso lee las pendientes y aplica cada una sobre el WMS (baja desactiva; en `rutas` borra, en `transporte_rutas` elimina la asignación y en `pedidos` borra el pedido solo si sigue `Pendiente`). Commit por registro; si una falla queda `estado='error'` con `error_mensaje` (truncado a 2000) y el resto continúa. La columna `id_<entidad>_wms` guarda el id resultante en el WMS.
- **Código**: `modules/intercambio.py` — núcleo genérico `_procesar_tabla_intercambio()` + `MODULOS` (catálogo módulo→tabla/columna id/aplicador), `procesar_intercambio_<modulo>()` por módulo y `procesar_intercambio()` que corre todos en orden de dependencia (rutas → transportes → transporte_rutas → clientes → materiales → pedidos). `reintentar_intercambio()` (acepta `tabla`) y `reintentar_todo()`. Conexiones int/wms/admin inyectables (se abren/cierran solas si no se pasan). Para agregar un módulo: nueva tabla en `INTERCAMBIO_TABLES` + aplicar_func + entrada en `MODULOS`.
- **Disparo**: botones en la UI (WMS `/intercambio`, panel admin `/admin/intercambio`) y script `procesar_intercambio.py` (para cron/Task Scheduler, acepta `--tenant <id>`).
- **Scoping por tenant**: los registros llevan `tenant_codigo`, resuelto contra `taurus_admin.tenants.codigo`. Si se pasa `tenant_id` al proceso, solo procesa los de ese tenant.
- **Permisos**: rutas `/intercambio*` en `ROUTE_CATALOG` (grupo "Intercambio") — asignables por rol. La sección admin es solo SUPERADMIN.

## Architecture

- **Blueprints** in `modules/` — one per domain (materiales, pedidos, recepciones, despacho, etc.); each exposes a `<name>_bp` registered in `app.py`.
- **`modules/db_config.py`** — central connection helper: `get_db_connection()` (wms), `_get_admin_connection()` (admin), `get_intercambio_connection()` (intercambio).
- **`modules/batch_utils.py`** — shared CSV/JSON/XLSX import/export helpers used by materiales, pedidos, recepciones, etc.
- **No REST API** — all routes return rendered Jinja2 templates. JSON endpoints exist only for inline AJAX actions (save, delete, test connection, xlsx sheetnames).
- **Auth**: Session-based. Login reads from `taurus_admin.usuarios` (joined with `tenants`). `@verificar_permiso_decorator` in `app.py`.
- **Session expiry**: 8 hours, enforced in `verificar_autenticacion_y_permisos` (`app.py:713`). Login page also clears sessions idle >5 min (`app.py:343`).

## Key conventions

- UI language is **Spanish** (variable names, route names, flash messages, DB column names)
- Column `descripcion` in `tipoubicacion` table — no accent, match it exactly in SQL
- ID columns are inconsistent: some tables use `id`, others `id_pedido`, `id_cliente`, `id_transporte`, etc. Check `modules/schema_generator.py` for the real table before writing queries
- Tenant IDs in admin URLs are base64-encoded (`encode_id`/`decode_id` in `modules/admin.py`) — do not pass raw integers in admin routes
- `openpyxl` is used for XLSX export; `werkzeug.security` for password hashing (`scrypt`)

## Gotchas

- `ADMIN_DB_CONFIG` / default passwords (`Taurus_2001`), `Admin@2024!` seeds, and `'dev-fallback'` secret keys are hardcoded — intentional for dev, not secret leaks
- `crear_tablas.py` is a one-time bootstrap script with hardcoded credentials — do not run in production. Other one-off/interactive root scripts (not part of the apps): `crear_datos_ejemplo.py`, `alta_usuario.py`, `admin_superusuario.py`, `_fix_mysql_user.py`
- Root `.gitignore` covers `.env`, `__pycache__/`, `.venv/`, `.idea/`, `picking_docs/`, `*.db` — `.env` won't show in `git status`
- Template files in `templates/partials/` are Jinja2 includes (modals, sidebar), not standalone pages
- `picking_docs/` contains generated PDF pick tickets — not source code
