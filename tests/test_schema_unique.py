"""Unicidad en la DDL generada y seed idempotente de admin.py (sin BD).

Regresión: schema_generator ignoraba el flag "unique" de columna, las tablas se
creaban sin UNIQUE y init_admin_db() duplicaba el usuario 'admin' en cada arranque.
"""

import re

import pytest

import admin as admin_app_module
from modules.schema_generator import ADMIN_TABLES, ENGINE_MAP, WMS_TABLES, generate_database

COLUMNAS_UNICAS = [
    (t['name'], c['name'])
    for t in ADMIN_TABLES + WMS_TABLES
    for c in t['columns']
    if c.get('unique') and not c.get('pk')
]


def _create_table(sql, tabla):
    """Devuelve el bloque CREATE TABLE de `tabla` (cualquier estilo de quoting)."""
    m = re.search(rf'CREATE TABLE\s+(?:IF NOT EXISTS\s+)?[`"\[]?{tabla}[`"\]]?\s*\((.*?)\n\)', sql, re.S)
    assert m, f"no se encontró CREATE TABLE {tabla}"
    return m.group(1)


def test_hay_columnas_unicas_declaradas():
    assert ('admin_usuarios', 'username') in COLUMNAS_UNICAS
    assert ('usuarios', 'username') in COLUMNAS_UNICAS


@pytest.mark.parametrize('engine', list(ENGINE_MAP))
def test_columnas_unique_generan_constraint(engine):
    sql = generate_database(engine, 'x', ADMIN_TABLES + WMS_TABLES, [], 'test')
    for tabla, columna in COLUMNAS_UNICAS:
        cuerpo = _create_table(sql, tabla)
        linea = next(
            (ln for ln in cuerpo.splitlines() if re.match(rf'\s*[`"\[]?{columna}[`"\]]?\s', ln)),
            None,
        )
        assert linea is not None, f"{engine}: falta la columna {tabla}.{columna}"
        assert 'UNIQUE' in linea.upper(), f"{engine}: {tabla}.{columna} sin UNIQUE: {linea.strip()}"


@pytest.mark.parametrize('engine', list(ENGINE_MAP))
def test_inventarios_numero_unico_por_tenant(engine):
    """numero es correlativo por tenant: UNIQUE compuesto, no global."""
    sql = generate_database(engine, 'x', WMS_TABLES, [], 'test')
    # Inline (UNIQUE KEY ... / UNIQUE (...)) o CREATE UNIQUE INDEX ... ON inventarios_cabecera (...)
    q = r'[`"\[]?'
    qc = r'[`"\]]?'
    assert re.search(
        rf'UNIQUE[^;]*?\(\s*{q}numero{qc}\s*,\s*{q}tenant_id{qc}\s*\)', sql
    ), f"{engine}: falta UNIQUE (numero, tenant_id)"
    linea_numero = next(
        ln for ln in _create_table(sql, 'inventarios_cabecera').splitlines()
        if re.match(r'\s*[`"\[]?numero[`"\]]?\s', ln)
    )
    assert 'UNIQUE' not in linea_numero.upper()


# --------------------------------------------------------------------------
# init_admin_db(): solo siembra con la tabla vacía y fuera de production
# --------------------------------------------------------------------------
class _FakeCursor:
    def __init__(self, total):
        self.total = total
        self.inserts = 0

    def execute(self, sql, params=None):
        if sql.lstrip().upper().startswith('INSERT'):
            self.inserts += 1
            self.total += 1

    def fetchone(self):
        return {'total': self.total}

    def close(self):
        pass


class _FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def commit(self):
        pass

    def close(self):
        pass


@pytest.fixture
def fake_admin_db(monkeypatch):
    def _instalar(total, app_env='development'):
        cursor = _FakeCursor(total)
        monkeypatch.setattr(admin_app_module, '_get_admin_connection', lambda: _FakeConn(cursor))
        monkeypatch.setattr(admin_app_module, 'APP_ENV', app_env)
        return cursor
    return _instalar


def test_init_admin_db_siembra_una_sola_vez(fake_admin_db):
    cursor = fake_admin_db(total=0)
    assert admin_app_module.init_admin_db()
    assert admin_app_module.init_admin_db()
    assert cursor.inserts == 1


def test_init_admin_db_no_toca_tabla_con_usuarios(fake_admin_db):
    cursor = fake_admin_db(total=3)
    admin_app_module.init_admin_db()
    assert cursor.inserts == 0


def test_init_admin_db_no_siembra_en_production(fake_admin_db):
    cursor = fake_admin_db(total=0, app_env='production')
    admin_app_module.init_admin_db()
    assert cursor.inserts == 0
