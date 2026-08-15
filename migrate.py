"""
migrate.py — Migration runner para Taurus WMS.

Lee migrations/*.sql (excepto create_* que son el bootstrap completo generado
por schema_generator) en orden alfabetico y aplica solo las no registradas en
la tabla de control schema_migrations, que vive en la BD objetivo.

Uso:
    python migrate.py                    # aplica pendientes al WMS (taurus_wms)
    python migrate.py --db admin         # aplica al admin (taurus_admin)
    python migrate.py --db intercambio   # aplica a taurus_intercambio
    python migrate.py --dry-run          # muestra que se aplicaria sin ejecutar
    python migrate.py --engine mysql     # override del engine (lee .env por defecto)

Convencion de archivos:
    - Todo migrations/*.sql se aplica en todos los engines salvo que la primera
      linea sea `-- engine: mysql` (o postgresql/sqlite/sqlserver), en cuyo caso
      se aplica solo en ese engine.
    - Un archivo puede restringirse a una BD objetivo con `-- db: wms|admin|intercambio`
      en las primeras lineas (se aplica solo cuando migrate.py corre con ese --db).
    - Los archivos create_*.sql (bootstrap generado) se ignoran: se aplican con
      `python modules/schema_generator.py --all` o `generar_schema.py --execute`.
    - Las migraciones ya aplicadas se mueven a migrations/procesados/.
"""

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generar_schema import split_statements
from modules.db_config import (
    _get_admin_connection,
    get_db_config,
    get_db_connection,
    get_intercambio_config,
    get_intercambio_connection,
)

MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'migrations')


def _tabla_control_sql(engine):
    if engine == 'sqlserver':
        return (
            "IF OBJECT_ID(N'dbo.schema_migrations', N'U') IS NULL "
            "CREATE TABLE schema_migrations ("
            "  nombre NVARCHAR(255) NOT NULL PRIMARY KEY,"
            "  engine NVARCHAR(32) NOT NULL,"
            "  aplicada_en DATETIME DEFAULT GETDATE()"
            ")"
        )
    return (
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "  nombre VARCHAR(255) NOT NULL PRIMARY KEY,"
        "  engine VARCHAR(32) NOT NULL,"
        "  aplicada_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        ")"
    )


def _engine_marcado(sql_text):
    """Devuelve el engine marcado en las primeras lineas (o None = aplica en todos)."""
    for linea in sql_text.splitlines()[:3]:
        s = linea.strip().lower()
        if s.startswith('-- engine:'):
            eng = s.split(':', 1)[1].strip()
            if eng:
                return eng
    return None


def _db_marcado(sql_text):
    """Devuelve la BD objetivo marcada en las primeras lineas (o None = aplica en todas)."""
    for linea in sql_text.splitlines()[:3]:
        s = linea.strip().lower()
        if s.startswith('-- db:'):
            db = s.split(':', 1)[1].strip()
            if db:
                return db
    return None


def _listar_migraciones():
    archivos = sorted(f for f in os.listdir(MIGRATIONS_DIR) if f.endswith('.sql'))
    return [f for f in archivos if not f.startswith('create_')]


def _aplicadas(conn, engine):
    cursor = conn.cursor()
    cursor.execute("SELECT nombre, engine FROM schema_migrations")
    rows = cursor.fetchall()
    cursor.close()
    return {row['nombre']: row['engine'] for row in rows}


def _conectar(engine, db):
    if db == 'admin':
        return _get_admin_connection()
    if db == 'intercambio':
        return get_intercambio_connection()
    return get_db_connection()


def _engine_objetivo(engine, db):
    if engine:
        return engine.strip().lower()
    if db == 'admin':
        import os as _os
        return _os.getenv('DB_ADMIN_ENGINE', 'mysql').strip().lower()
    if db == 'intercambio':
        return get_intercambio_config().get('INTERCAMBIO_ENGINE', 'mysql').strip().lower()
    return get_db_config().get('DB_ENGINE', 'mysql').strip().lower()


def run(db='wms', engine=None, dry_run=False, verbose=False):
    engine = _engine_objetivo(engine, db)
    print(f"== Migraciones Taurus WMS ==  BD: {db}  engine: {engine}")

    conn = _conectar(engine, db)
    try:
        cursor = conn.cursor()
        cursor.execute(_tabla_control_sql(engine))
        conn.commit()
        cursor.close()

        aplicadas = _aplicadas(conn, engine)
        pendientes = [f for f in _listar_migraciones() if f not in aplicadas]

        if not pendientes:
            print("[OK] No hay migraciones pendientes.")
            return 0, 0

        total = 0
        for nombre in pendientes:
            path = os.path.join(MIGRATIONS_DIR, nombre)
            with open(path, encoding='utf-8') as fh:
                sql_text = fh.read()

            solo_engine = _engine_marcado(sql_text)
            if solo_engine and solo_engine != engine:
                if verbose:
                    print(f"  [SKIP] {nombre} (solo {solo_engine})")
                continue

            solo_db = _db_marcado(sql_text)
            if solo_db and solo_db != db:
                if verbose:
                    print(f"  [SKIP] {nombre} (solo {solo_db})")
                continue

            print(f"  [APLICAR] {nombre}")
            stmts = split_statements(sql_text)
            if dry_run:
                for stmt in stmts:
                    print(f"      [DRY-RUN] {stmt[:120]}")
                continue

            try:
                cur = conn.cursor()
                for stmt in stmts:
                    if not stmt.strip():
                        continue
                    cur.execute(stmt)
                conn.commit()
                cur.execute(
                    "INSERT INTO schema_migrations (nombre, engine) VALUES (%s, %s)",
                    (nombre, engine),
                )
                conn.commit()
                cur.close()
                total += 1
            except Exception as e:
                conn.rollback()
                print(f"  [ERROR] {nombre}: {str(e)[:200]}")
                print("  La migracion fallo. Corregi el archivo o aplicala a mano.")
                return total, 1

        print(f"[OK] {total} migraciones aplicadas.")
        return total, 0
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', choices=['wms', 'admin', 'intercambio'], default='wms',
                        help='BD objetivo (default: wms)')
    parser.add_argument('--engine', choices=['mysql', 'postgresql', 'sqlite', 'sqlserver'],
                        help='Override del engine (default: lee de .env/config)')
    parser.add_argument('--dry-run', action='store_true', help='Muestra sin ejecutar')
    parser.add_argument('--verbose', '-v', action='store_true')
    args = parser.parse_args()

    _, errores = run(db=args.db, engine=args.engine, dry_run=args.dry_run, verbose=args.verbose)
    if errores:
        sys.exit(1)


if __name__ == '__main__':
    main()
