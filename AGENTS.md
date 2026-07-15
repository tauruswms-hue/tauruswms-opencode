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
- **Two databases**:
  - `taurus_wms` — operational data (tenants configure this via admin UI)
  - `taurus_admin` — users, tenants, config (connection from `.env`)
- **Config bootstrap**: DB connection params for `taurus_wms` are stored in the `configuracion` table inside `taurus_admin` (`modules/db_config.py:26`). `.env` provides only the admin DB credentials and fallback values.
- **Schema changes**: SQL migration scripts in `migrations/`. Processed migrations go in `migrations/procesados/`. Run manually against MySQL — no migration runner. Check `migrations/*.sql` (not in `procesados/`) for pending migrations before making schema changes.

## Multi-tenancy

Every operational query uses `tenant_id` from the Flask session. The filter pattern is always:

```sql
WHERE (%s IS NULL OR tenant_id = %s)
```

When `tenant_id` is NULL (superadmin), all rows are returned. This pattern appears in every module — do not omit it.

## Architecture

- **Blueprints** in `modules/` — one per domain (materiales, pedidos, recepciones, despacho, etc.)
- **`modules/db_config.py`** — central DB connection helper. Use `get_db_connection()` for operational queries, `_get_admin_connection()` for admin DB.
- **`modules/batch_utils.py`** — shared CSV/JSON/XLSX import/export helpers used by materiales, pedidos, recepciones, etc.
- **No REST API** — all routes return rendered Jinja2 templates. JSON endpoints exist only for inline AJAX actions (save, delete, test connection).
- **Auth**: Session-based. Login reads from `taurus_admin.usuarios`. Role-based route permissions via `roles_rutas` table. `@verificar_permiso_decorator` in `app.py`.
- **Session expiry**: 8 hours (`app.py:616`). Login redirect at 5 min idle (`app.py:273`).

## Key conventions

- UI language is **Spanish** (variable names, route names, flash messages, DB column names)
- Column `descipción` in `tipoubicacion` table has an accent — match it exactly in SQL
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
