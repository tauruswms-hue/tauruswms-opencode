"""
generar_schema.py — Script independiente para generar y/o ejecutar el schema de Taurus WMS.

Uso:
    # Generar archivos SQL (solo genera, no toca la base de datos)
    python generar_schema.py --engine mysql
    python generar_schema.py --engine sqlite
    python generar_schema.py --all                          # genera los 4 archivos

    # Ejecutar contra la base de datos directamente
    python generar_schema.py --engine mysql --execute       # crea admin + wms
    python generar_schema.py --engine sqlite --execute --db-name wms.db

    # Generar + ejecutar
    python generar_schema.py --engine mysql --execute --output schema_mysql.sql

    # Solo la base de datos admin o solo la wms
    python generar_schema.py --engine mysql --execute --admin-only
    python generar_schema.py --engine mysql --execute --wms-only

    # Con semillas de datos
    python generar_schema.py --engine mysql --execute --seed

    # Drop antes de crear
    python generar_schema.py --engine mysql --execute --drop

    # Modo simulacion (muestra el SQL sin ejecutar)
    python generar_schema.py --engine mysql --execute --dry-run

Lectura de configuracion:
    - Lee .env con python-dotenv
    - Para admin: DB_ADMIN_* (host, port, name, user, password, engine)
    - Para wms:   DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, DB_ENGINE
    - Si solo se pasa --engine sin --execute, genera archivos SQL en stdout o --output
"""

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import contextlib

from modules.schema_generator import ENGINE_MAP, generate_schema

# ============================================================================
# CONEXION
# ============================================================================

def _get_env(key, default=''):
    return os.getenv(key, default)


def get_admin_params(engine=None):
    eng = engine or _get_env('DB_ADMIN_ENGINE', 'mysql').strip().lower()
    return {
        'engine': eng,
        'host': _get_env('DB_ADMIN_HOST', 'localhost'),
        'port': int(_get_env('DB_ADMIN_PORT', '3306')),
        'database': _get_env('DB_ADMIN_NAME', 'taurus_admin'),
        'user': _get_env('DB_ADMIN_USER', 'taurus_admin'),
        'password': _get_env('DB_ADMIN_PASSWORD', 'Taurus_2001'),
    }


def get_wms_params(engine=None):
    eng = engine or _get_env('DB_ENGINE', '').strip().lower()
    if not eng:
        try:
            from modules.db_config import get_db_config
            cfg = get_db_config()
            eng = cfg.get('DB_ENGINE', 'mysql').strip().lower()
        except Exception:
            eng = 'mysql'
    return {
        'engine': eng,
        'host': _get_env('DB_HOST', 'localhost'),
        'port': int(_get_env('DB_PORT', '3306')),
        'database': _get_env('DB_NAME', 'taurus_wms'),
        'user': _get_env('DB_USER', 'taurus'),
        'password': _get_env('DB_PASSWORD', 'Taurus_2001'),
    }


def connect_db(params):
    engine = params['engine']
    if engine == 'mysql':
        import pymysql
        return pymysql.connect(
            host=params['host'],
            port=params['port'],
            user=params['user'],
            password=params['password'],
            database=params['database'],
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
        )
    if engine == 'postgresql':
        import psycopg2
        return psycopg2.connect(
            host=params['host'],
            port=params['port'],
            user=params['user'],
            password=params['password'],
            dbname=params['database'],
        )
    if engine == 'sqlite':
        import sqlite3
        conn = sqlite3.connect(params['database'])
        conn.row_factory = sqlite3.Row
        return conn
    if engine == 'sqlserver':
        import pymssql
        return pymssql.connect(
            server=params['host'],
            port=params['port'],
            user=params['user'],
            password=params['password'],
            database=params['database'],
        )
    raise ValueError(f"Engine desconocido: {engine}")


# ============================================================================
# EJECUCION SQL
# ============================================================================

def split_statements(sql_text):
    """Divide el SQL en sentencias individuales, ignorando comentarios y lineas vacias."""
    stmts = []
    current = []
    in_comment = False

    for line in sql_text.split('\n'):
        stripped = line.strip()

        if stripped.startswith('/*'):
            in_comment = True
            continue
        if in_comment:
            if '*/' in stripped:
                in_comment = False
            continue

        if stripped.startswith('--'):
            continue
        if not stripped:
            if current:
                stmts.append('\n'.join(current))
                current = []
            continue

        current.append(stripped)
        if stripped.endswith(';'):
            stmts.append('\n'.join(current))
            current = []

    if current:
        stmts.append('\n'.join(current))

    return stmts


def execute_schema(conn, sql_text, dry_run=False, verbose=False):
    """Ejecuta todas las sentencias SQL contra la conexion dada."""
    stmts = split_statements(sql_text)
    executed = 0
    errors = 0

    cursor = conn.cursor()
    for stmt in stmts:
        if not stmt.strip():
            continue
        if dry_run:
            print(f"  [DRY-RUN] {stmt[:120]}...")
            executed += 1
            continue
        try:
            if verbose:
                print(f"  > {stmt[:120]}...")
            cursor.execute(stmt)
            executed += 1
        except Exception as e:
            err_msg = str(e)
            if 'already exists' in err_msg.lower() or 'Duplicate' in err_msg:
                if verbose:
                    print(f"  [SKIP] {err_msg[:80]}")
            else:
                print(f"  [ERROR] {err_msg[:120]}")
                print(f"  [SQL]   {stmt[:120]}...")
                errors += 1

    if not dry_run:
        with contextlib.suppress(Exception):
            conn.commit()

    return executed, errors


# ============================================================================
# LOGICA PRINCIPAL
# ============================================================================

def run_generate(engine, output_dir=None, admin_only=False, wms_only=False):
    """Genera archivos SQL para el engine dado."""
    results = {}

    if not wms_only:
        sql = generate_schema(engine)
        if output_dir:
            fname = os.path.join(output_dir, f"schema_{engine}_admin_wms.sql")
            os.makedirs(output_dir, exist_ok=True)
            with open(fname, "w", encoding="utf-8") as f:
                f.write(sql)
            print(f"[OK] Generado: {fname}")
            results['file'] = fname
        else:
            print(sql)
            results['stdout'] = True

    return results


def run_execute(engine, drop=False, seed=False, dry_run=False, verbose=False,
                admin_only=False, wms_only=False, admin_db=None, wms_db=None):
    """Ejecuta el schema contra la base de datos directamente."""
    admin_params = get_admin_params(engine)
    wms_params = get_wms_params(engine)

    if admin_db:
        admin_params['database'] = admin_db
    if wms_db:
        wms_params['database'] = wms_db

    total_executed = 0
    total_errors = 0

    # --- ADMIN DATABASE ---
    if not wms_only:
        print(f"\n{'='*60}")
        print(f"BASE DE DATOS ADMIN: {admin_params['database']} ({engine})")
        print(f"{'='*60}")

        sql = generate_schema(engine)

        if drop and not dry_run:
            print(f"[DROP] Eliminando base de datos admin '{admin_params['database']}'...")
            try:
                _drop_database(admin_params)
            except Exception as e:
                print(f"  [WARN] {e}")

        if admin_params['engine'] == 'sqlite':
            print(f"[CONNECT] SQLite: {admin_params['database']}")
        else:
            print(f"[CONNECT] {admin_params['host']}:{admin_params['port']}/{admin_params['database']}")

        try:
            conn = connect_db(admin_params)
            executed, errors = execute_schema(conn, sql, dry_run=dry_run, verbose=verbose)
            total_executed += executed
            total_errors += errors
            if not dry_run:
                conn.close()
            print(f"[OK] Admin: {executed} sentencias, {errors} errores")
        except Exception as e:
            print(f"[ERROR] No se pudo conectar a la BD admin: {e}")
            total_errors += 1

    # --- WMS DATABASE ---
    if not admin_only:
        print(f"\n{'='*60}")
        print(f"BASE DE DATOS WMS: {wms_params['database']} ({engine})")
        print(f"{'='*60}")

        sql = generate_schema(engine)

        if drop and not dry_run:
            print(f"[DROP] Eliminando base de datos wms '{wms_params['database']}'...")
            try:
                _drop_database(wms_params)
            except Exception as e:
                print(f"  [WARN] {e}")

        if wms_params['engine'] == 'sqlite':
            print(f"[CONNECT] SQLite: {wms_params['database']}")
        else:
            print(f"[CONNECT] {wms_params['host']}:{wms_params['port']}/{wms_params['database']}")

        try:
            conn = connect_db(wms_params)
            executed, errors = execute_schema(conn, sql, dry_run=dry_run, verbose=verbose)
            total_executed += executed
            total_errors += errors
            if not dry_run:
                conn.close()
            print(f"[OK] WMS: {executed} sentencias, {errors} errores")
        except Exception as e:
            print(f"[ERROR] No se pudo conectar a la BD wms: {e}")
            total_errors += 1

    return total_executed, total_errors


def _drop_database(params):
    engine = params['engine']
    if engine == 'mysql':
        import pymysql
        conn = pymysql.connect(
            host=params['host'],
            port=params['port'],
            user=params['user'],
            password=params['password'],
            charset='utf8mb4',
        )
        cursor = conn.cursor()
        db = params['database']
        cursor.execute(f"DROP DATABASE IF EXISTS `{db}`")
        conn.commit()
        cursor.close()
        conn.close()
    elif engine == 'postgresql':
        import psycopg2
        conn = psycopg2.connect(
            host=params['host'],
            port=params['port'],
            user=params['user'],
            password=params['password'],
            dbname='postgres',
        )
        conn.autocommit = True
        cursor = conn.cursor()
        db = params['database']
        cursor.execute(f"DROP DATABASE IF EXISTS \"{db}\"")
        cursor.close()
        conn.close()
    elif engine == 'sqlite':
        db_path = params['database']
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"  [DROP] Archivo eliminado: {db_path}")
    elif engine == 'sqlserver':
        import pymssql
        conn = pymssql.connect(
            server=params['host'],
            port=params['port'],
            user=params['user'],
            password=params['password'],
            database='master',
        )
        cursor = conn.cursor()
        db = params['database']
        cursor.execute(f"IF EXISTS (SELECT name FROM sys.databases WHERE name = '{db}') DROP DATABASE [{db}]")
        conn.commit()
        cursor.close()
        conn.close()


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generador y ejecutor de schema multi-engine para Taurus WMS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python generar_schema.py --engine mysql                     # genera schema_mysql_admin_wms.sql
  python generar_schema.py --engine sqlite --all              # genera los 4 archivos
  python genera_schema.py --engine mysql --execute            # ejecuta contra la BD
  python generar_schema.py --engine mysql --execute --drop    # drop + recreate
  python generar_schema.py --engine mysql --execute --dry-run # muestra sin ejecutar
  python generar_schema.py --engine sqlite --execute --db-name wms.sqlite
        """,
    )
    parser.add_argument(
        "--engine", choices=["mysql", "postgresql", "sqlite", "sqlserver"],
        help="Motor de BD target (default: lee de .env)",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Genera archivos para los 4 engines",
    )
    parser.add_argument(
        "--execute", action="store_true",
        help="Ejecuta el schema contra la base de datos",
    )
    parser.add_argument(
        "--output", "-o", type=str,
        help="Archivo de salida para --engine (default: stdout si no hay --execute)",
    )
    parser.add_argument(
        "--output-dir", type=str, default=".",
        help="Directorio de salida para --all (default: .)",
    )
    parser.add_argument(
        "--drop", action="store_true",
        help="Elimina la base de datos antes de crear el schema",
    )
    parser.add_argument(
        "--seed", action="store_true",
        help="Incluye datos iniciales (usuarios, tenants, roles, etc.)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Muestra las sentencias SQL sin ejecutarlas",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Muestra cada sentencia SQL mientras se ejecuta",
    )
    parser.add_argument(
        "--admin-only", action="store_true",
        help="Solo genera/ejecuta la base de datos admin",
    )
    parser.add_argument(
        "--wms-only", action="store_true",
        help="Solo genera/ejecuta la base de datos wms",
    )
    parser.add_argument(
        "--admin-db", type=str,
        help="Nombre de la BD admin (override de .env)",
    )
    parser.add_argument(
        "--wms-db", type=str,
        help="Nombre de la BD wms (override de .env)",
    )
    parser.add_argument(
        "--db-name", type=str,
        help="Nombre de la BD (override para ambos admin y wms si se usa solo un engine)",
    )

    args = parser.parse_args()

    # --- Validar ---
    if not args.engine and not args.all:
        # Intentar leer de .env
        env_engine = _get_env('DB_ENGINE', '').strip().lower()
        if env_engine in ENGINE_MAP:
            args.engine = env_engine
            print(f"[INFO] Usando engine de .env: {env_engine}")
        else:
            parser.print_help()
            sys.exit(1)

    # --- Generar ---
    if args.all:
        output_dir = args.output_dir
        for eng in ENGINE_MAP:
            fname = os.path.join(output_dir, f"schema_{eng}_admin_wms.sql")
            print(f"[GEN] {fname}")
            generate_schema(eng, fname)
        print("[OK] Archivos generados.")
        if not args.execute:
            return

    if args.engine:
        # Apply --db-name overrides
        if args.db_name:
            if not args.admin_db:
                args.admin_db = args.db_name
            if not args.wms_db:
                args.wms_db = args.db_name

        # --- Generar archivo ---
        if args.output and not args.execute:
            generate_schema(args.engine, args.output)
            print(f"[OK] Generado: {args.output}")
            return

        # --- Ejecutar ---
        if args.execute:
            print(f"\n[Taurus WMS] Schema Generator — engine: {args.engine}")
            print(f"  Admin DB: {args.admin_db or _get_env('DB_ADMIN_NAME', 'taurus_admin')}")
            print(f"  WMS DB:   {args.wms_db or _get_env('DB_NAME', 'taurus_wms')}")
            print(f"  Drop:     {args.drop}")
            print(f"  Dry-run:  {args.dry_run}")
            print(f"  Seed:     {args.seed}")

            executed, errors = run_execute(
                engine=args.engine,
                drop=args.drop,
                seed=args.seed,
                dry_run=args.dry_run,
                verbose=args.verbose,
                admin_only=args.admin_only,
                wms_only=args.wms_only,
                admin_db=args.admin_db,
                wms_db=args.wms_db,
            )

            print(f"\n{'='*60}")
            print(f"RESUMEN: {executed} sentencias ejecutadas, {errors} errores")
            if args.dry_run:
                print("(dry-run: no se ejecuto nada)")
            print(f"{'='*60}")

            # Generar archivo tambien si se pidio --output
            if args.output:
                generate_schema(args.engine, args.output)
                print(f"[OK] Archivo generado: {args.output}")

            if errors > 0:
                sys.exit(1)
            return

        # --- Solo generar a stdout ---
        print(generate_schema(args.engine))


if __name__ == "__main__":
    main()
