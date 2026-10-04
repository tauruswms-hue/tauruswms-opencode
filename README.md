# Taurus WMS

Sistema de gestión de almacenes (Warehouse Management System) en Flask.
Dos apps Flask que comparten la base administrativa `taurus_admin`:

- **`app.py`** — app principal del WMS (puerto 5000)
- **`admin.py`** — panel de administración (puerto 5001, UI en `/admin`)
- **`schema_app.py`** — generador de schema por GUI (puerto 5002, solo desarrollo)

## Requisitos

- Python 3.10+ (probado con 3.12)
- MySQL 8 (recomendado) | PostgreSQL | SQLite | SQL Server
- Los drivers opcionales ya están en `requirements.txt` (`psycopg2-binary`, `pymssql`)

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt

copy .env.example .env          # Windows  (Linux/Mac: cp .env.example .env)
```

Editar `.env` y **cambiar los secretos** (`SECRET_KEY`, `ADMIN_SECRET_KEY`,
`SECRET_SALT`), y completar en `conexiones.json` las credenciales de las tres
bases (secciones `admin`, `wms` e `intercambio`). En `APP_ENV=production`
la app se niega a arrancar si detecta valores por defecto.

## Crear la base de datos

```bash
# Generar y ejecutar el schema completo (admin + wms + intercambio) con datos iniciales
python generar_schema.py --engine mysql --execute --seed

# Solo generar los archivos SQL (sin tocar la BD)
python modules/schema_generator.py --all
```

Migraciones incrementales (una vez que el schema base existe):

```bash
python migrate.py                # aplica docs/migrations/*.sql pendientes al WMS
python migrate.py --db admin     # contra taurus_admin
python migrate.py --dry-run      # muestra qué se aplicaría sin ejecutar
```

Las migraciones ya aplicadas se registran en la tabla `schema_migrations` y se
mueven a `docs/migrations/procesados/`.

## Ejecutar

```bash
python app.py     # WMS  — http://localhost:5000
python admin.py   # Admin — http://localhost:5001/admin
```

No hay usuarios ni tenants por defecto. El primer usuario del panel admin se crea
con `superusuario-dist/superusuario.exe`; los tenants y usuarios del WMS, desde el
panel. En desarrollo, `admin.py` crea `admin` / `Admin@2024!` si la tabla de
usuarios del panel está vacía.

## Docker

```bash
docker compose up --build
```

Levanta MySQL + las dos apps (WMS en `:5000`, admin en `:5001`). El schema se
crea la primera vez con `python modules/schema_generator.py` + `migrate.py`
dentro del contenedor, o localmente contra el MySQL del compose.

## Tests

```bash
pytest -q
```

Los tests de integración requieren MySQL (con `conexiones.json` configurado) y se omiten
automáticamente si no hay conexión. El CI (GitHub Actions) corre lint
(`ruff`), pytest con MySQL en un contenedor y el build de la imagen Docker.

## API REST (`/api/v1`)

API JSON para integraciones con sistemas externos. Todos los endpoints están
acotados al tenant del token.

### Autenticación

Cada tenant tiene un token de API. Se genera desde el panel admin
(`/admin/parametros/<tenant>/api-token`, solo SUPERADMIN) y se guarda como
hash SHA-256 en `tenants.api_token` — el token plano **solo se muestra una
vez**. Se envía en cada request:

```
Authorization: Bearer <token>
```

Respuestas de error siempre con `{ "ok": false, "error": "mensaje" }`:

| Código | Motivo |
|--------|--------|
| 400 | Parámetros inválidos o faltantes |
| 401 | Falta o es incorrecto el header `Authorization: Bearer <token>` (token inválido) |
| 403 | El tenant está desactivado |
| 404 | Recurso no encontrado |
| 409 | Conflicto de estado (p. ej. cerrar una recepción no Abierta) |
| 500 | Error interno |

Limitado a **60 requests/minuto** por dirección IP (Flask-Limiter).

### Catálogos (GET)

| Endpoint | Descripción | Params |
|----------|-------------|--------|
| `GET /api/v1/materiales` | Lista de materiales | `q`, `activo` (bool), `limite` |
| `GET /api/v1/materiales/<codigo>` | Material por `codigo` o `codigo_barras` | — |
| `GET /api/v1/ubicaciones` | Catálogo de ubicaciones | `q`, `tipo`, `limite` |
| `GET /api/v1/stock` | Stock por posición | `ubicacion`, `material`, `lote`, `tipo_stock`, `todos`, `limite` |
| `GET /api/v1/recepciones` | Recepciones (cabecera + totales) | `estado`, `proveedor`, `limite` |
| `GET /api/v1/recepciones/<numero>` | Recepción con sus items | — |
| `GET /api/v1/pedidos` | Pedidos | `estado`, `limite` |
| `GET /api/v1/omcs` | Órdenes de movimiento | `estado`, `limite` |

- `limite`: default 100, rango 1–500.
- `stock` con `todos=true` (default) devuelve solo filas con saldo distinto de
  cero; `todos=false` trae todas.
- En `/stock`, `material` acepta `codigo` o `codigo_barras`.

### Escritura (POST)

| Endpoint | Descripción |
|----------|-------------|
| `POST /api/v1/recepciones` | Alta de recepción con sus items |
| `POST /api/v1/recepciones/<numero>/agregar-item` | Agrega/actualiza un item en recepción Abierta |
| `POST /api/v1/recepciones/<numero>/cerrar` | Cierra la recepción: mueve stock y genera una OMC Pendiente |
| `POST /api/v1/omcs/<numero>/confirmar` | Confirma una OMC de recepción (StockEntrando → Disponible) |

**Alta de recepción** (`POST /api/v1/recepciones`):

```json
{
  "proveedor_codigo": "PROV001",
  "ubicacion_recep_codigo": "R-01",
  "ubicacion_destino_codigo": "A-01-01",
  "observaciones": "Compra 12345",
  "items": [
    {
      "material_codigo": "MAT001",
      "cantidad": 100,
      "lote": "L2024-01",
      "fecha_vencimiento": "2026-12-31",
      "tipo_stock": "Libre Venta"
    }
  ]
}
```

Genera el número `REC-AAAA-NNNNN` y un contenedor. Si algún item es inválido
(material inexistente/inactivo, cantidad ≤ 0) se reporta en `errores` y el
resto se inserta; si **ninguno** es válido se revierte todo con 400.

**`POST /api/v1/recepciones/<numero>/cerrar`**: mueve el stock (Saliendo desde
la ubicación de recepción, Entrando hacia la de destino), marca la recepción
`Cerrada` y genera una OMC `Pendiente` (devolverá `numero_omc`).

**`POST /api/v1/omcs/<numero>/confirmar`**: solo aplica a OMCs de recepción
(no a las de pedido); pasa el stock de `StockEntrando` a Disponible y marca la
OMC y la recepción `Confirmadas`.

### Ejemplo (curl)

```bash
TOKEN="<token-del-tenant>"
curl -s http://localhost:5000/api/v1/materiales -H "Authorization: Bearer $TOKEN"
curl -s -X POST http://localhost:5000/api/v1/recepciones \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"proveedor_codigo":"PROV001","ubicacion_recep_codigo":"R-01",
       "items":[{"material_codigo":"MAT001","cantidad":10}]}'
```

## Configuración multi-engine

El motor de cada BD se indica en la clave `engine` de su sección en
`conexiones.json` (`mysql` | `postgresql` | `sqlite` | `sqlserver`).
Toda la generación de schema es multi-engine (`python modules/schema_generator.py --all`).
SQLite es de referencia/DLL — la app corre funcionalmente sobre MySQL.

## Estructura

```
app.py                  # App WMS (blueprints, auth, permisos, middleware)
admin.py                # Panel admin (puerto 5001)
modules/
  db_config.py          # Conexiones (pool DBUtils) + config de BD multi-engine
  schema_generator.py   # Definición de tablas/roles y generación multi-engine
  sql_dialect.py        # Quoting/helpers SQL por engine (nunca backticks a mano)
  context.py            # get_tenant_filter() + constantes de sesión
  bootstrap.py          # Arranque compartido (secretos, sesión, error handlers)
  api.py                # API REST /api/v1 (Bearer token por tenant)
  intercambio.py        # Interfase con sistemas externos (taurus_intercambio)
  auditoria.py          # Historial de movimientos de stock
  reportes.py           # Reportes por tenant (stock, valorizado, auditoría, ...)
  permisos_cache.py     # Cache de rutas por rol (TTL)
  movil.py              # Módulo móvil (recepción, picking, inventario)
  *.py                  # Un blueprint por dominio (materiales, pedidos, ...)
scripts/                # One-offs y datos de ejemplo (no forman parte de las apps)
docs/migrations/             # DDL incremental + bootstrap generado (create_*.sql)
tests/                  # pytest (unit + integración)
```

## Troubleshooting

- **`Falta SECRET_KEY en .env`** — el `.env` no tiene los secretos; copiar
  `.env.example` y completar.
- **Arranque bloqueado en producción** — hay passwords/secretos por defecto;
  cambiarlos (`Admin@2024!`, `Taurus_2001`, etc.).
- **`No module named 'DBUtils'`** — el venv no tiene `requirements.txt`
  instalado (DBUtils 3.x importa desde `dbutils.pooled_db`).
- **`No se encontró el archivo de conexiones`** — falta `conexiones.json`;
  crearlo en la raíz con las secciones `admin`, `wms` e `intercambio`. Las conexiones a las tres
  bases se leen solo de ese archivo (o de la ruta indicada en la variable
  `TAURUS_CONEXIONES`); los cambios se toman sin reiniciar.
