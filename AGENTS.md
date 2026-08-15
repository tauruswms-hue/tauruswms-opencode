# AGENTS.md — Taurus WMS

## What this is

Flask-based Warehouse Management System. Two Flask apps sharing the same `.env` and `taurus_admin` DB, plus a dev tool:

- **`app.py`** — main WMS app (port 5000)
- **`admin.py`** — admin panel (port 5001, UI at `/admin`); registers the blueprint from `modules/admin.py` and seeds `admin_usuarios` with `admin`/`Admin@2024!` on start (`init_admin_db()`)
- **`schema_app.py`** — schema generator GUI (port 5002), dev-only

One-off/dev scripts (bootstrap, seed, alta de usuarios, fix MySQL) viven en `scripts/` — no forman parte de las apps.

## Run

```bash
python app.py    # main app — http://localhost:5000
python admin.py  # admin panel — http://localhost:5001/admin
```

Or with Docker: `docker compose up --build` (MySQL + wms `:5000` + admin `:5001`).

Seed users (from `ADMIN_SEEDS` in `modules/schema_generator.py`): `admin` and `operador`, both password `Admin@2024!`.

Tests: `pytest` (tests/, sin suite por defecto). Lint: `ruff` (ruff.toml; reglas con ignores para patrones heredados de la app). CI: `.github/workflows/ci.yml` (ruff + pytest con MySQL + build Docker).

## Database

- **Multi-engine, no ORM**: runtime supports `mysql` (default) | `postgresql` | `sqlite` | `sqlserver`, chosen by `DB_ENGINE` (`get_db_engine()`, `modules/db_config.py`). Postgres needs `psycopg2-binary`, SQL Server needs `pymssql` — both **in `requirements.txt`** (Flask, DBUtils, PyMySQL, openpyxl, python-dotenv, Werkzeug, Flask-WTF, Flask-Limiter, psycopg2-binary, pymssql, pytest).
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

- Pending DDL lives in `migrations/*.sql` (not in `procesados/`). Applied with the **migration runner `migrate.py`** (reads `migrations/*.sql` except `create_*` in alphabetical order, tracks applied ones in `schema_migrations`; `--db wms|admin|intercambio`, `--engine`, `--dry-run`, `--verbose`; a file can restrict to one engine with a leading `-- engine: <name>` comment line and/or to one target DB with `-- db: wms|admin|intercambio`). Check pending migrations before writing new schema SQL.
- Table/seed definitions live in `modules/schema_generator.py` (`ADMIN_TABLES`, `WMS_TABLES`, `INTERCAMBIO_TABLES`, `ADMIN_SEEDS`, `ROUTE_CATALOG`). **Any schema change must update these and regenerate:**
  ```bash
  python modules/schema_generator.py --all   # root schema_{engine}.sql + migrations/create_{admin,wms,intercambio}_{engine}.sql (4 engines)
  ```
- `generar_schema.py` — CLI to generate **and execute** schema against live DBs (`--execute`, `--drop`, `--seed`, `--dry-run`, `--admin-only`/`--wms-only`). Reads `.env` (`DB_ADMIN_*`/`DB_*`).
- `schema_app.py` — GUI wrapper (port 5002) writing `schemas/schema_{engine}_admin_wms.sql` (the combined admin+wms+intercambio DDL).

## Roles y permisos

- Catálogo de roles: `roles` (taurus_admin); permisos por rol: `roles_rutas` (rol, ruta). Rutas asignables = `ROUTE_CATALOG` en `modules/schema_generator.py` — al agregar módulos/rutas, actualizarlo (soporta wildcards `/*` y `*`). Matcheo por path en `verificar_permiso_ruta` / `_match_permiso` (`app.py`).
- La asignación rol→ruta aplica a **todos los tenants** (sin scoping). El middleware `verificar_autenticacion_y_permisos` (`app.py`) recalcula `session['rutas_permitidas']` en cada request (los cambios del panel admin aplican sin re-login) y bloquea cualquier ruta catalogada no habilitada para el rol. La consulta a `taurus_admin` está cacheada por rol en `modules/permisos_cache.py` (`obtener_rutas_cached`, TTL `PERMISOS_CACHE_TTL` default 30s; `invalidar_permisos_cache()` llamada desde `modules/admin.py` al tocar roles/rutas).
- Rutas **no** catalogadas quedan auth-only (solo exigen login): `/`, `/login`, `/logout`, `/estado`, `/api/xlsx_sheetnames` (`/login` además es pública). `/omc/tipos_ubicacion` **sí** está en el catálogo (grupo "OMC").
- `SUPERADMIN` y el acceso `*` (switch "Acceso total") bypassan la verificación. Helper `tiene_permiso_ruta` expuesto a Jinja (`app.py:253`) para condicionar la UI.

## Intercambio

Interfase con sistemas externos: el sistema de gestión inserta registros en `taurus_intercambio` y el WMS los aplica.

- **Tablas**: por módulo, una tabla `intercambio_<modulo>` en `taurus_intercambio` (un registro = una operación), más `intercambio_log` (historial de ejecuciones). Módulos: `intercambio_materiales` (→ `wms.materiales`, upsert por `codigo`), `intercambio_rutas` (→ `wms.rutas`, upsert por `nombre_ruta`), `intercambio_transportes` (→ `wms.transportes`, upsert por `codigo`), `intercambio_transporte_rutas` (→ `wms.transporte_rutas`, asignación ruta↔transporte resuelta por `transporte_codigo` + `ruta_nombre`), `intercambio_clientes` (→ `wms.clientes`, upsert por `codigo`, referencias `ruta_nombre` y `transporte_codigo`), `intercambio_pedidos` (→ `wms.pedidos_cabecera` + `pedidos_detalle`, upsert por `nro_pedido`, cabecera en columnas y items en `items_json` como lista `{material_codigo, cantidad, tipo_stock}`; referencias `cliente_codigo`, `ruta_nombre`, `transporte_codigo`, `clase_nombre`). Definidas en `INTERCAMBIO_TABLES` (`modules/schema_generator.py`).
- **Flujo**: el sistema externo inserta filas con `estado='pendiente'` y `accion` en `alta|modificacion|baja`. El proceso lee las pendientes y aplica cada una sobre el WMS (baja desactiva; en `rutas` borra, en `transporte_rutas` elimina la asignación y en `pedidos` borra el pedido solo si sigue `Pendiente`). Commit por registro; si una falla queda `estado='error'` con `error_mensaje` (truncado a 2000) y el resto continúa. La columna `id_<entidad>_wms` guarda el id resultante en el WMS.
- **Código**: `modules/intercambio.py` — núcleo genérico `_procesar_tabla_intercambio()` + `MODULOS` (catálogo módulo→tabla/columna id/aplicador), `procesar_intercambio_<modulo>()` por módulo y `procesar_intercambio()` que corre todos en orden de dependencia (rutas → transportes → transporte_rutas → clientes → materiales → pedidos). `reintentar_intercambio()` (acepta `tabla`) y `reintentar_todo()`. Conexiones int/wms/admin inyectables (se abren/cierran solas si no se pasan). Para agregar un módulo: nueva tabla en `INTERCAMBIO_TABLES` + aplicar_func + entrada en `MODULOS`.
- **Disparo**: botones en la UI (WMS `/intercambio`, panel admin `/admin/intercambio`) y script `procesar_intercambio.py` (para cron/Task Scheduler, acepta `--tenant <id>`).
- **Scoping por tenant**: los registros llevan `tenant_codigo`, resuelto contra `taurus_admin.tenants.codigo`. Si se pasa `tenant_id` al proceso, solo procesa los de ese tenant.
- **Permisos**: rutas `/intercambio*` en `ROUTE_CATALOG` (grupo "Intercambio") — asignables por rol. La sección admin es solo SUPERADMIN.

## Architecture

- **Blueprints** in `modules/` — one per domain (materiales, pedidos, recepciones, despacho, etc.); each exposes a `<name>_bp` registered in `app.py`. `modules/reportes.py` (`reportes_bp`, rutas `/reportes` y `/reportes/exportar/<tipo>/<formato>`) agrupa reportes por tenant (stock, valorizado, auditoría, recepciones, pedidos) con exportación CSV/XLSX/JSON vía `batch_utils`. `modules/auditoria.py` expone `registrar_movimiento()` que escribe el historial en `stock_movimientos` (best-effort; cantidad con signo: positivo=ingreso, negativo=egreso) desde todos los flujos de stock (recepciones, OMC, pedidos, móvil, API, ajustes/importación de stockcontable).
- **`modules/db_config.py`** — central connection helper: `get_db_connection()` (wms), `_get_admin_connection()` (admin), `get_intercambio_connection()` (intercambio). All three use a **DBUtils `PooledDB` pool** (one per engine+config, max 20 connections, `ping=1`, rollback on return) — `conn.close()` returns the connection to the pool, it never really closes; pools are torn down by `clear_config_cache()`. SQLite bypasses the pool (reference/runtime only). DBUtils 3.x imports from `dbutils.pooled_db` (fallback `DBUtils.PooledDB`). `get_db_engine()` resuelve el engine por DB (wms/admin/intercambio) con `DB_ENGINE`/`DB_<BD>_ENGINE`; `get_wms_runtime_config()` devuelve la config plana del WMS (host/user/password/database/charset/port) para formularios; `test_connection()` prueba una conexión con kwargs por engine sin tocar el pool.
- **`modules/context.py`** — helpers transversales: `get_tenant_filter()` (lee `tenant_id` de la sesión; base del patrón `WHERE (%s IS NULL OR tenant_id = %s)`) y constantes de sesión (`SESSION_MAX_AGE_SECONDS` = 8 h, `LOGIN_IDLE_TIMEOUT_SECONDS` = 5 min).
- **`modules/bootstrap.py`** — arranque compartido entre `app.py` y `admin.py`: `check_default_secrets(APP_ENV, [(nombre, valor)], logger)` (bloquea en production si hay secretos por defecto), `harden_session_config(app, APP_ENV)` (cookie httpOnly/SameSite/Secure, sesión permanente 8 h) y `register_error_handlers(app, logger, template=...)` (handlers 404/403/500 centralizados).
- **`modules/batch_utils.py`** — shared CSV/JSON/XLSX import/export helpers used by materiales, pedidos, recepciones, etc.
- **No REST API** — all routes return rendered Jinja2 templates. JSON endpoints exist only for inline AJAX actions (save, delete, test connection, xlsx sheetnames).
- **Auth**: Session-based. Login reads from `taurus_admin.usuarios` (joined with `tenants`). `@verificar_permiso_decorator` in `app.py`.
- **Session expiry**: 8 hours, enforced in `verificar_autenticacion_y_permisos` (`app.py:643`). Login page also clears sessions idle >5 min (constante `LOGIN_IDLE_TIMEOUT_SECONDS`).

## Key conventions

- UI language is **Spanish** (variable names, route names, flash messages, DB column names)
- Column `descripcion` in `tipoubicacion` table — no accent, match it exactly in SQL
- ID columns are inconsistent: some tables use `id`, others `id_pedido`, `id_cliente`, `id_transporte`, etc. Check `modules/schema_generator.py` for the real table before writing queries
- Tenant IDs in admin URLs are base64-encoded (`encode_id`/`decode_id` in `modules/admin.py`) — do not pass raw integers in admin routes
- `openpyxl` is used for XLSX export; `werkzeug.security` for password hashing (`scrypt`)

## Gotchas

- `ADMIN_DB_CONFIG` / default passwords (`Taurus_2001`), `Admin@2024!` seeds, and `'dev-fallback'` secret keys are hardcoded — intentional for dev, not secret leaks
- `crear_tablas.py` is a one-time bootstrap script with hardcoded credentials — do not run in production. Other one-off/interactive scripts in `scripts/` (not part of the apps): `crear_datos_ejemplo.py`, `alta_usuario.py`, `admin_superusuario.py`, `_fix_mysql_user.py` (más docs y datos de ejemplo en `scripts/sample_data/`). `migrate.py` (migration runner) and `procesar_intercambio.py` (cron) ARE production tools — keep them working.
- Root `.gitignore` covers `.env`, `__pycache__/`, `.venv/`, `.idea/`, `picking_docs/`, `*.db` — `.env` won't show in `git status`
- Template files in `templates/partials/` are Jinja2 includes (modals, sidebar), not standalone pages
- `picking_docs/` contains generated PDF pick tickets — not source code
