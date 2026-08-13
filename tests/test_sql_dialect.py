# -*- coding: utf-8 -*-
"""Tests unitarios de modules/sql_dialect.py en los 4 engines."""

import pytest

from modules import sql_dialect as sd


@pytest.fixture(autouse=True)
def _restore_engine():
    """Guarda/restaura el engine global entre tests."""
    engine_prev = sd.get_engine()
    yield
    sd.set_engine(engine_prev)


ENGINES = ['mysql', 'postgresql', 'sqlite', 'sqlserver']


# --------------------------------------------------------------------------
# quote
# --------------------------------------------------------------------------
@pytest.mark.parametrize('engine,open_c,close_c', [
    ('mysql', '`', '`'),
    ('postgresql', '"', '"'),
    ('sqlite', '"', '"'),
    ('sqlserver', '[', ']'),
])
def test_quote_por_engine(engine, open_c, close_c):
    sd.set_engine(engine)
    assert sd.quote('codigo') == f'{open_c}codigo{close_c}'


# --------------------------------------------------------------------------
# year / date
# --------------------------------------------------------------------------
@pytest.mark.parametrize('engine,esperado', [
    ('mysql', 'YEAR(fecha)'),
    ('postgresql', 'EXTRACT(YEAR FROM fecha)::INTEGER'),
    ('sqlite', "strftime('%Y', fecha)"),
    ('sqlserver', 'DATEPART(YEAR, fecha)'),
])
def test_year_por_engine(engine, esperado):
    sd.set_engine(engine)
    assert sd.year('fecha') == esperado


@pytest.mark.parametrize('engine,esperado', [
    ('mysql', 'DATE(fecha)'),
    ('postgresql', '(fecha)::date'),
    ('sqlite', 'DATE(fecha)'),
    ('sqlserver', 'CAST(fecha AS DATE)'),
])
def test_date_por_engine(engine, esperado):
    sd.set_engine(engine)
    assert sd.date('fecha') == esperado


# --------------------------------------------------------------------------
# cast_as_int / cast_as_char
# --------------------------------------------------------------------------
def test_cast_as_int_mysql():
    sd.set_engine('mysql')
    assert sd.cast_as_int('cantidad') == 'CAST(cantidad AS UNSIGNED)'


def test_cast_as_int_otros():
    sd.set_engine('postgresql')
    assert sd.cast_as_int('cantidad') == 'CAST(cantidad AS INTEGER)'


def test_cast_as_char_sqlserver():
    sd.set_engine('sqlserver')
    assert sd.cast_as_char('x') == 'CAST(x AS NVARCHAR(MAX))'


def test_cast_as_char_mysql():
    sd.set_engine('mysql')
    assert sd.cast_as_char('x') == 'CAST(x AS CHAR)'


# --------------------------------------------------------------------------
# substring_index
# --------------------------------------------------------------------------
def test_substring_index_mysql():
    sd.set_engine('mysql')
    assert sd.substring_index('codigo', '-', 1) == "SUBSTRING_INDEX(codigo, '-', 1)"


def test_substring_index_postgres_abs():
    sd.set_engine('postgresql')
    assert sd.substring_index('codigo', '-', -1) == "split_part(codigo, '-', 1)"


def test_substring_index_sqlite_positivo():
    sd.set_engine('sqlite')
    sql = sd.substring_index('codigo', '-', 2)
    assert sql.startswith('(')
    assert 'WITH RECURSIVE' in sql


# --------------------------------------------------------------------------
# concat / group_concat
# --------------------------------------------------------------------------
def test_concat_mysql():
    sd.set_engine('mysql')
    assert sd.concat('a', 'b') == 'CONCAT(a, b)'


def test_concat_postgres():
    sd.set_engine('postgresql')
    assert sd.concat('a', 'b') == 'a || b'


def test_group_concat_mysql_con_orden():
    sd.set_engine('mysql')
    assert sd.group_concat('m.nombre', order_by='m.nombre') == (
        "GROUP_CONCAT(m.nombre ORDER BY m.nombre SEPARATOR ', ')"
    )


def test_group_concat_postgres():
    sd.set_engine('postgresql')
    assert sd.group_concat('m.nombre', order_by='m.nombre') == (
        "STRING_AGG(m.nombre ORDER BY m.nombre, ', ')"
    )


# --------------------------------------------------------------------------
# limit_sql
# --------------------------------------------------------------------------
@pytest.mark.parametrize('engine,esperado', [
    ('mysql', 'LIMIT 10'),
    ('postgresql', 'LIMIT 10'),
    ('sqlite', 'LIMIT 10'),
    ('sqlserver', 'OFFSET 0 ROWS FETCH NEXT 10 ROWS ONLY'),
])
def test_limit_sql(engine, esperado):
    sd.set_engine(engine)
    assert sd.limit_sql(10) == esperado


def test_limit_sql_offset():
    sd.set_engine('mysql')
    assert sd.limit_sql(10, 20) == 'LIMIT 10 OFFSET 20'


# --------------------------------------------------------------------------
# in_clause_sql
# --------------------------------------------------------------------------
def test_in_clause_sql_genera_placeholders():
    assert sd.in_clause_sql([1, 2, 3]) == '%s,%s,%s'


def test_in_clause_sql_lista_vacia():
    with pytest.raises(ValueError):
        sd.in_clause_sql([])


# --------------------------------------------------------------------------
# upsert_sql
# --------------------------------------------------------------------------
@pytest.mark.parametrize('engine,clave', [
    ('mysql', 'ON DUPLICATE KEY UPDATE'),
    ('postgresql', 'ON CONFLICT'),
    ('sqlite', 'ON CONFLICT'),
    ('sqlserver', 'MERGE INTO'),
])
def test_upsert_sql_clave(engine, clave):
    sd.set_engine(engine)
    sql = sd.upsert_sql('materiales', ['codigo', 'descripcion'], 'codigo', ['descripcion'])
    assert clave in sql


def test_upsert_sql_mysql_no_actualiza_conflict():
    sd.set_engine('mysql')
    sql = sd.upsert_sql('materiales', ['codigo', 'descripcion'], 'codigo', ['descripcion'])
    assert 'codigo = VALUES(codigo)' not in sql
    assert 'descripcion = VALUES(descripcion)' in sql


def test_upsert_sql_postgres_excluded():
    sd.set_engine('postgresql')
    sql = sd.upsert_sql('materiales', ['codigo', 'descripcion'], 'codigo', ['descripcion'])
    assert 'EXCLUDED.descripcion' in sql


def test_upsert_sql_sqlserver_merge():
    sd.set_engine('sqlserver')
    sql = sd.upsert_sql('materiales', ['codigo', 'descripcion'], 'codigo', ['descripcion'])
    assert 'target.codigo = source.codigo' in sql


# --------------------------------------------------------------------------
# upsert_incremental_sql
# --------------------------------------------------------------------------
def test_upsert_incremental_mysql_suma():
    sd.set_engine('mysql')
    sql = sd.upsert_incremental_sql(
        'stockcontable', ['Ubicacion', 'Material', 'StockDisponible'],
        'Ubicacion', ['StockDisponible'])
    assert 'StockDisponible = StockDisponible + VALUES(StockDisponible)' in sql


def test_upsert_incremental_postgres_suma():
    sd.set_engine('postgresql')
    sql = sd.upsert_incremental_sql(
        'stockcontable', ['Ubicacion', 'Material', 'StockDisponible'],
        'Ubicacion', ['StockDisponible'])
    assert 'StockDisponible = stockcontable.StockDisponible + EXCLUDED.StockDisponible' in sql


def test_upsert_incremental_sqlserver_suma():
    sd.set_engine('sqlserver')
    sql = sd.upsert_incremental_sql(
        'stockcontable', ['Ubicacion', 'Material', 'StockDisponible'],
        'Ubicacion', ['StockDisponible'])
    assert 'target.StockDisponible = target.StockDisponible + source.StockDisponible' in sql


# --------------------------------------------------------------------------
# upsert_coalesce_sql
# --------------------------------------------------------------------------
def test_upsert_coalesce_mysql():
    sd.set_engine('mysql')
    sql = sd.upsert_coalesce_sql(
        'tabla', ['a', 'b'], 'a', ['b'], ['b'])
    assert 'COALESCE(VALUES(b), b)' in sql


def test_upsert_coalesce_postgres():
    sd.set_engine('postgresql')
    sql = sd.upsert_coalesce_sql(
        'tabla', ['a', 'b'], 'a', ['b'], ['b'])
    assert 'COALESCE(EXCLUDED.b, tabla.b)' in sql


# --------------------------------------------------------------------------
# insert_ignore_sql
# --------------------------------------------------------------------------
@pytest.mark.parametrize('engine,clave', [
    ('mysql', 'INSERT IGNORE INTO'),
    ('postgresql', 'ON CONFLICT (codigo) DO NOTHING'),
    ('sqlite', 'INSERT OR IGNORE INTO'),
])
def test_insert_ignore_sql(engine, clave):
    sd.set_engine(engine)
    assert clave in sd.insert_ignore_sql('materiales', ['codigo', 'descripcion'])


def test_insert_ignore_sql_sqlserver():
    sd.set_engine('sqlserver')
    sql = sd.insert_ignore_sql('materiales', ['codigo', 'descripcion'])
    assert 'IF NOT EXISTS (SELECT 1 FROM materiales WHERE codigo = @p0)' in sql


# --------------------------------------------------------------------------
# get_lastrowid / execute_insert / is_duplicate_key_error
# --------------------------------------------------------------------------
class _CursorFake:
    lastrowid = 42

    def execute(self, sql, params=None):
        self.executed = sql

    def fetchone(self):
        return (99,)


def test_get_lastrowid_por_defecto():
    sd.set_engine('mysql')
    assert sd.get_lastrowid(_CursorFake()) == 42


def test_execute_insert_mysql_usa_lastrowid():
    sd.set_engine('mysql')
    cur = _CursorFake()
    assert sd.execute_insert(cur, 'INSERT ...') == 42


def test_execute_insert_postgres_returning():
    sd.set_engine('postgresql')
    cur = _CursorFake()
    assert sd.execute_insert(cur, 'INSERT ...') == 99
    assert 'RETURNING id' in cur.executed


def test_is_duplicate_key_error_mysql():
    sd.set_engine('mysql')
    assert sd.is_duplicate_key_error(type('E', (), {'args': (1062,)})())
    assert not sd.is_duplicate_key_error(type('E', (), {'args': (1451,)})())


def test_is_duplicate_key_error_postgres():
    sd.set_engine('postgresql')
    exc = type('E', (), {'orig': type('O', (), {'pgcode': '23505'})()})()
    assert sd.is_duplicate_key_error(exc)
