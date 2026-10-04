# AGENTS.md — Taurus WMS

## What this is

Flask-based Warehouse Management System. Two Flask apps sharing the same `.env`, the connections file (`conexiones.json`) and `taurus_admin` DB, plus a dev tool:

- **`app.py`** — main WMS app (port 5000)
- **`admin.py`** — admin panel (port 5001, UI at `/admin`); registers the blueprint from `modules/admin.py` and seeds `admin`/`Admin@2024!` on start (`init_admin_db()`) **only if `admin_usuarios` is empty and `APP_ENV` is not production** — in production the first SUPERADMIN is created with `superusuario-dist/superusuario.exe`
- **`schema_app.py`** — schema generator GUI (port 5002), dev-only

One-off/dev scripts (bootstrap, seed, alta de usuarios, fix MySQL) viven en `scripts/` — no forman parte de las apps.

## Run

```bash
python app.py    # main app — http://localhost:5000
python admin.py  # admin panel — http://localhost:5001/admin
```

Or with Docker: `docker compose up --build` (MySQL + wms `:5000` + admin `:5001`).

No hay usuarios ni tenants por defecto: `ADMIN_SEEDS` (`modules/schema_generator.py`) solo carga roles, rutas por rol y `configuracion`. El primer SUPERADMIN del panel se crea con `superusuario-dist/superusuario.exe`; tenants y usuarios del WMS, desde el panel admin (en desarrollo, `admin.py` crea `admin`/`Admin@2024!` si `admin_usuarios` está vacía). Los tests de integración no dependen de seeds: un fixture de sesión en `tests/conftest.py` crea un tenant si la BD no tiene ninguno activo, y `tests/conftest.py` expone fixtures `usuario_wms` (en `taurus_admin.usuarios`) y `usuario_panel` (en `taurus_admin.admin_usuarios`) que crean usuarios temporales con password propio y los eliminan al final.

Tests: `pytest` (tests/, sin suite por defecto). Lint: `ruff` (ruff.toml; reglas con ignores para patrones heredados de la app). CI: `.github/workflows/ci.yml` (ruff + pytest con MySQL + build Docker).

## Database

- **Multi-engine, no ORM**: runtime supports `mysql` (default) | `postgresql` | `sqlite` | `sqlserver`, chosen per DB by the `engine` key of its section in `conexiones.json` (`get_db_engine()` returns the WMS one, `modules/db_config.py`). Postgres needs `psycopg2-binary`, SQL Server needs `pymssql` — both **in `requirements.txt`** (Flask, DBUtils, PyMySQL, openpyxl, python-dotenv, Werkzeug, Flask-WTF, Flask-Limiter, psycopg2-binary, pymssql, pytest).
- **Three databases**:
  - `taurus_wms` — operational data (tenants configure connection via admin UI)
  - `taurus_admin` — users, tenants, config
  - `taurus_intercambio` — interfase con sistemas externos (ver "Intercambio" abajo)
- **Connection bootstrap**:
  - Las tres conexiones salen de **`conexiones.json`** (raíz del proyecto, o la ruta de la variable de entorno `TAURUS_CONEXIONES`): secciones `admin`, `wms` e `intercambio` (esta última opcional), cada una con `engine`, `host`, `port`, `user`, `password`, `database` y `charset`. Es la única fuente: ni el `.env` ni la tabla `configuracion` guardan conexiones. El archivo está gitignored (no hay plantilla versionada: el formato está en `docs/inicio/configuracion.html`). `conexiones.docker.json` es el de desarrollo que monta `docker-compose.yml`.
  - `get_conexion(base)` devuelve la conexión normalizada; `_leer_conexiones()` valida el archivo y lanza `ConexionesError` con un mensaje que dice qué corregir. `set_conexion(base, datos)` fija una conexión sin leer el archivo (lo usa `superusuario.exe`, que trae su propio `superusuario.json` solo con `taurus_admin`).
  - El archivo se relee cada `CONFIG_CACHE_TTL` segundos (default 30); si cambió, engine y pools se reinician, así un cambio se aplica sin reiniciar las apps. Si no se puede leer al refrescar, se conservan las conexiones conocidas.
  - Al arrancar, `passwords_bd()` (`modules/bootstrap.py`) pasa las contraseñas del archivo a `check_default_secrets`: en production un archivo faltante/ inválido o una contraseña por defecto (incluido el placeholder `CAMBIAR`) bloquea el arranque; en otros entornos solo se loguea.
  - The admin panel uses its own session cookie (`taurus_admin_session`): WMS and admin share host, and cookies don't distinguish ports. A missing/expired CSRF token returns a 400 with an explanatory message (JSON for AJAX) via `register_error_handlers` in `modules/bootstrap.py`.
- **Multi-engine identifier quoting**: never hardcode backticks in SQL. Quote identifiers through `modules/sql_dialect.py` — `sql_quote()` and `insert_ignore_sql()` (see `app.py:289`). Raw MySQL backticks break postgres/sqlite/sqlserver.
- **App code uses pymysql `%s` placeholders and dict-style rows** (`DictCursor`). The sqlite3 driver does not accept `%s`, so `create_*_sqlite.sql` are reference/DLL only — sqlite is not a functional runtime for the app.

## Multi-tenancy

Every operational query uses `tenant_id` from the Flask session. The filter pattern is always:

```sql
WHERE (%s IS NULL OR tenant_id = %s)
```

When `tenant_id` is NULL (superadmin), all rows are returned. This pattern appears in every module — do not omit it.

## Schema changes / migrations

- Pending DDL lives in `docs/migrations/*.sql` (not in `procesados/`). Applied with the **migration runner `migrate.py`** (reads `docs/migrations/*.sql` except `create_*` in alphabetical order, tracks applied ones in `schema_migrations`; `--db wms|admin|intercambio`, `--engine`, `--dry-run`, `--verbose`, `--baseline` (registra las pendientes sin ejecutarlas: usar tras crear una BD nueva desde `create_*.sql`); a file can restrict to one engine with a leading `-- engine: <name>` comment line and/or to one target DB with `-- db: wms|admin|intercambio`). Check pending migrations before writing new schema SQL.
- Table/seed definitions live in `modules/schema_generator.py` (`ADMIN_TABLES`, `WMS_TABLES`, `INTERCAMBIO_TABLES`, `ADMIN_SEEDS`, `ROUTE_CATALOG`). **Any schema change must update these and regenerate:**
  ```bash
  python modules/schema_generator.py --all   # root schema_{engine}.sql + docs/migrations/create_{admin,wms,intercambio}_{engine}.sql (4 engines)
  ```
- `generar_schema.py` — CLI to generate **and execute** schema against live DBs (`--execute`, `--drop`, `--seed`, `--dry-run`, `--admin-only`/`--wms-only`). Reads the `admin` and `wms` sections of `conexiones.json`.
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
- **`modules/db_config.py`** — central connection helper: `get_db_connection()` (wms), `_get_admin_connection()` (admin), `get_intercambio_connection()` (intercambio). All three use a **DBUtils `PooledDB` pool** (one per engine+config, max 20 connections, `ping=1`, rollback on return) — `conn.close()` returns the connection to the pool, it never really closes; pools are torn down by `clear_config_cache()`. SQLite bypasses the pool (reference/runtime only). DBUtils 3.x imports from `dbutils.pooled_db` (fallback `DBUtils.PooledDB`). `get_db_engine()` devuelve el engine de la BD WMS y `get_conexion(base)` los datos de conexión de cualquiera de las tres (leídos de `conexiones.json`); `get_wms_runtime_config()` devuelve la config plana del WMS (host/user/password/database/charset/port) para formularios; `probar_conexion()` prueba una conexión con kwargs por engine sin tocar el pool.
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
- `crear_tablas.py` is a one-time bootstrap script with hardcoded credentials — do not run in production. Other one-off/interactive scripts in `scripts/` (not part of the apps): `crear_datos_ejemplo.py`, `alta_usuario.py` (GUI, usuarios WMS en `taurus_admin.usuarios`), `admin_superusuario.py` (consola, usuarios del panel en `admin_usuarios`), `_fix_mysql_user.py` (más docs y datos de ejemplo en `scripts/sample_data/`). `migrate.py` (migration runner), `procesar_intercambio.py` (cron) and `admin_superusuario.py` ARE production tools — keep them working.
- **`superusuario-dist/`** — ejecutable portable (`superusuario.exe`, PyInstaller) de `scripts/admin_superusuario.py`; lee credenciales de `superusuario.json` junto al .exe o `--config <ruta>` (`superusuario.json` está versionado con valores de plantilla y `password: CAMBIAR` — no commitear credenciales reales). Tras cambiar el script o sus dependencias (`modules/db_config.py`, `sql_dialect.py`, `passwords.py`) regenerarlo con `python scripts/build_superusuario.py` (`requirements-build.txt`).
- **`docs/`** — documentación de la aplicación en HTML estático (se abre desde disco, sin build): `index.html` + una carpeta por sección (`inicio/`, `arquitectura/`, `administracion/`, `modulos/`, `integraciones/`, `operacion/`, `desarrollo/`). El menú, el mapa de la portada y anterior/siguiente salen de `NAV` en `docs/assets/docs.js`: una página nueva se crea copiando `docs/_plantilla.html` y registrándola ahí con su estado (`completa` | `borrador` | `pendiente`). Las páginas pueden anidarse con `hijos`. Al cambiar algo documentado, actualizar su página. Las páginas `docs/inicio/base-de-datos/taurus-{admin,wms,intercambio}.html` embeben los `create_*_mysql.sql` y son **generadas**: tras `schema_generator.py --all` correr `python docs/generar_scripts_bd.py` (no editarlas a mano).
- Política de contraseñas única en `modules/passwords.py` (`validar_password`, mínimo 8): la usan el panel admin y los scripts de usuarios.
- `schema_generator.py`: el flag `unique` de columna genera `UNIQUE` en los 4 engines; claves únicas por tenant van como índice compuesto (`uk_<tabla>_<col>_tenant`). CI falla si los `schema_*.sql` / `create_*.sql` commiteados no coinciden con `--all`.
- Root `.gitignore` covers `.env`, `conexiones.json`, `__pycache__/`, `.venv/`, `.idea/`, `picking_docs/`, `*.db` — `.env` won't show in `git status`
- Template files in `templates/partials/` are Jinja2 includes (modals, sidebar), not standalone pages
- `picking_docs/` contains generated PDF pick tickets — not source code
