"""
schema_app.py — GUI para generar y ejecutar schemas de Taurus WMS.

Ejecutar:
    python schema_app.py

Abre http://localhost:5002 en el navegador.
"""

import os
import sys
import traceback

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import contextlib

from modules.schema_generator import ENGINE_MAP, generate_schema

app = Flask(__name__)
app.secret_key = os.getenv('ADMIN_SECRET_KEY', 'dev-fallback')

SCHEMAS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schemas')


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/')
def index():
    env_config = {
        'engine': os.getenv('DB_ENGINE', 'mysql'),
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '3306'),
        'database': os.getenv('DB_NAME', 'taurus_wms'),
        'user': os.getenv('DB_USER', 'taurus'),
        'admin_engine': os.getenv('DB_ADMIN_ENGINE', 'mysql'),
        'admin_host': os.getenv('DB_ADMIN_HOST', 'localhost'),
        'admin_port': os.getenv('DB_ADMIN_PORT', '3306'),
        'admin_database': os.getenv('DB_ADMIN_NAME', 'taurus_admin'),
        'admin_user': os.getenv('DB_ADMIN_USER', 'taurus_admin'),
    }
    return render_template('schema.html', config=env_config)


@app.route('/api/generate', methods=['POST'])
def api_generate():
    try:
        data = request.json
        engine = data.get('engine', 'mysql')
        if engine not in ENGINE_MAP:
            return jsonify({'ok': False, 'error': f'Engine desconocido: {engine}'})

        sql = generate_schema(engine)
        return jsonify({'ok': True, 'sql': sql, 'lines': len(sql.split('\n')), 'size': len(sql)})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e), 'trace': traceback.format_exc()})


@app.route('/api/download', methods=['GET', 'POST'])
def api_download():
    if request.method == 'POST':
        try:
            data = request.json
            engine = data.get('engine', 'mysql')
            if engine not in ENGINE_MAP:
                return jsonify({'ok': False, 'error': f'Engine desconocido: {engine}'})

            os.makedirs(SCHEMAS_DIR, exist_ok=True)
            fname = f'schema_{engine}_admin_wms.sql'
            fpath = os.path.join(SCHEMAS_DIR, fname)
            generate_schema(engine, fpath)
            return jsonify({'ok': True, 'file': fpath, 'filename': fname})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e), 'trace': traceback.format_exc()})

    # GET: serve file
    filename = request.args.get('file', '')
    if not filename or '..' in filename or '/' in filename or '\\' in filename:
        return jsonify({'ok': False, 'error': 'Invalid filename'}), 400
    fpath = os.path.join(SCHEMAS_DIR, filename)
    if not os.path.exists(fpath):
        return jsonify({'ok': False, 'error': 'File not found'}), 404
    return send_file(fpath, as_attachment=True)


@app.route('/api/download_all', methods=['POST'])
def api_download_all():
    try:
        os.makedirs(SCHEMAS_DIR, exist_ok=True)
        generated = []
        for eng in ENGINE_MAP:
            fname = f'schema_{eng}_admin_wms.sql'
            fpath = os.path.join(SCHEMAS_DIR, fname)
            generate_schema(eng, fpath)
            generated.append({'engine': eng, 'filename': fname, 'size': os.path.getsize(fpath)})
        return jsonify({'ok': True, 'files': generated})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/execute', methods=['POST'])
def api_execute():
    try:
        data = request.json
        engine = data.get('engine', 'mysql')
        data.get('target', 'admin')
        host = data.get('host', 'localhost')
        port = int(data.get('port') or 3306)
        database = data.get('database', '')
        user = data.get('user', '')
        password = data.get('password', '')
        data.get('drop', False)

        if engine not in ENGINE_MAP:
            return jsonify({'ok': False, 'error': f'Engine desconocido: {engine}'})

        conn = _connect(engine, host, port, database, user, password)

        sql = generate_schema(engine)
        stmts = _split_statements(sql)

        cursor = conn.cursor()
        executed = 0
        errors = []

        for stmt in stmts:
            if not stmt.strip():
                continue
            try:
                cursor.execute(stmt)
                executed += 1
            except Exception as e:
                err = str(e)
                if 'already exists' in err.lower() or 'Duplicate' in err or 'duplicate key' in err.lower():
                    continue
                errors.append({'sql': stmt[:150], 'error': err[:200]})

        with contextlib.suppress(Exception):
            conn.commit()

        with contextlib.suppress(Exception):
            conn.close()

        return jsonify({
            'ok': len(errors) == 0,
            'executed': executed,
            'errors': errors,
            'total_statements': len(stmts),
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e), 'trace': traceback.format_exc()})


@app.route('/api/test_connection', methods=['POST'])
def api_test_connection():
    try:
        data = request.json
        engine = data.get('engine', 'mysql')
        host = data.get('host', 'localhost')
        port = int(data.get('port', 3306))
        database = data.get('database', '')
        user = data.get('user', '')
        password = data.get('password', '')

        conn = _connect(engine, host, port, database, user, password)
        cursor = conn.cursor()

        if engine == 'mysql':
            cursor.execute("SELECT VERSION() AS ver")
        elif engine == 'postgresql':
            cursor.execute("SELECT version() AS ver")
        elif engine == 'sqlite':
            cursor.execute("SELECT sqlite_version() AS ver")
        elif engine == 'sqlserver':
            cursor.execute("SELECT @@VERSION AS ver")

        row = cursor.fetchone()
        if isinstance(row, dict):
            version_str = str(row.get('ver', row.get(next(iter(row.keys())), '')))
        elif isinstance(row, (tuple, list)):
            version_str = str(row[0])
        else:
            version_str = str(row)

        if engine == 'mysql':
            cursor.execute("SHOW TABLES")
        elif engine == 'postgresql':
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        elif engine == 'sqlite':
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        elif engine == 'sqlserver':
            cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'")

        raw = cursor.fetchall()
        tables = []
        for row in raw:
            if isinstance(row, dict):
                tables.append(next(iter(row.values())))
            else:
                tables.append(row[0])

        conn.close()

        return jsonify({
            'ok': True,
            'version': version_str,
            'tables': tables,
            'table_count': len(tables),
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e), 'trace': traceback.format_exc()})


# ============================================================================
# HELPERS
# ============================================================================

def _connect(engine, host, port, database, user, password):
    if engine == 'mysql':
        import pymysql
        return pymysql.connect(
            host=host, port=port, user=user, password=password,
            database=database, charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
        )
    if engine == 'postgresql':
        import psycopg2
        return psycopg2.connect(
            host=host, port=port, user=user, password=password,
            dbname=database,
        )
    if engine == 'sqlite':
        import sqlite3
        conn = sqlite3.connect(database)
        conn.row_factory = sqlite3.Row
        return conn
    if engine == 'sqlserver':
        import pymssql
        return pymssql.connect(
            server=host, port=port, user=user,
            password=password, database=database,
        )
    raise ValueError(f'Engine desconocido: {engine}')


def _split_statements(sql_text):
    stmts = []
    current = []
    for line in sql_text.split('\n'):
        stripped = line.strip()
        if stripped.startswith('--'):
            continue
        if stripped.startswith('/*'):
            continue
        if stripped == '*/':
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


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    os.makedirs(SCHEMAS_DIR, exist_ok=True)
    print('=' * 50)
    print('  TAURUS WMS - Schema Generator GUI')
    print('=' * 50)
    print('  http://localhost:5002')
    print('=' * 50)
    app.run(host='0.0.0.0', port=5002, debug=True)
