import re


_engine = 'mysql'


def set_engine(engine):
    global _engine
    _engine = engine


def get_engine():
    return _engine


def quote(col):
    if _engine == 'mysql':
        return f'`{col}`'
    if _engine == 'sqlserver':
        return f'[{col}]'
    return f'"{col}"'


def year(col):
    if _engine == 'mysql':
        return f'YEAR({col})'
    if _engine == 'postgresql':
        return f'EXTRACT(YEAR FROM {col})::INTEGER'
    if _engine == 'sqlserver':
        return f'DATEPART(YEAR, {col})'
    return f"strftime('%Y', {col})"


def date(col):
    if _engine == 'mysql':
        return f'DATE({col})'
    if _engine == 'postgresql':
        return f'({col})::date'
    if _engine == 'sqlserver':
        return f'CAST({col} AS DATE)'
    return f'DATE({col})'


def cast_as_int(expr):
    if _engine == 'mysql':
        return f'CAST({expr} AS UNSIGNED)'
    return f'CAST({expr} AS INTEGER)'


def cast_as_char(expr):
    if _engine == 'mysql':
        return f'CAST({expr} AS CHAR)'
    if _engine == 'sqlserver':
        return f'CAST({expr} AS NVARCHAR(MAX))'
    return f'CAST({expr} AS TEXT)'


def substring_index(expr, delim, n):
    if _engine == 'mysql':
        return f"SUBSTRING_INDEX({expr}, '{delim}', {n})"
    if _engine == 'postgresql':
        return f"split_part({expr}, '{delim}', {abs(n)})"
    if _engine == 'sqlserver':
        if n > 0:
            return (
                f"LEFT({expr}, CHARINDEX('{delim}', {expr}) - 1)"
            )
        return (
            f"RIGHT({expr}, LEN({expr}) - CHARINDEX('{delim}', "
            f"REVERSE({expr})))"
        )
    # SQLite — recursive CTE to split and pick parts
    d = len(delim)
    cte = (
        f"WITH RECURSIVE s(id, val, rest) AS ("
        f"SELECT 1, "
        f"CASE WHEN instr({expr},'{delim}')>0 "
        f"THEN substr({expr},1,instr({expr},'{delim}')-1) ELSE {expr} END, "
        f"CASE WHEN instr({expr},'{delim}')>0 "
        f"THEN substr({expr},instr({expr},'{delim}')+{d}) ELSE '' END "
        f"UNION ALL "
        f"SELECT id+1, "
        f"CASE WHEN instr(rest,'{delim}')>0 "
        f"THEN substr(rest,1,instr(rest,'{delim}')-1) ELSE rest END, "
        f"CASE WHEN instr(rest,'{delim}')>0 "
        f"THEN substr(rest,instr(rest,'{delim}')+{d}) ELSE '' END "
        f"FROM s WHERE rest<>''"
        f")"
    )
    if n > 0:
        return f"({cte} SELECT group_concat(val,'{delim}') FROM s WHERE id<={n})"
    return f"({cte} SELECT group_concat(val,'{delim}') FROM s WHERE id>(SELECT max(id)-{abs(n)} FROM s))"


def concat(*parts):
    if _engine == 'mysql':
        return f"CONCAT({', '.join(parts)})"
    return ' || '.join(parts)


def group_concat(expr, order_by=None, separator=', '):
    if _engine == 'mysql':
        parts = [expr]
        if order_by:
            parts.append(f'ORDER BY {order_by}')
        parts.append(f"SEPARATOR '{separator}'")
        return f"GROUP_CONCAT({' '.join(parts)})"
    if _engine == 'postgresql':
        inner = expr
        if order_by:
            inner = f'{expr} ORDER BY {order_by}'
        return f"STRING_AGG({inner}, '{separator}')"
    if _engine == 'sqlserver':
        inner = expr
        if order_by:
            inner = f'{expr} ORDER BY {order_by}'
        return f"STRING_AGG({inner}, '{separator}')"
    return f"GROUP_CONCAT({expr})"


def limit_sql(n, offset=0):
    if _engine == 'sqlserver':
        return f'OFFSET {offset} ROWS FETCH NEXT {n} ROWS ONLY'
    if offset:
        return f'LIMIT {n} OFFSET {offset}'
    return f'LIMIT {n}'


def upsert_sql(table, columns, conflict_col, update_cols):
    placeholders = ', '.join(['%s'] * len(columns))
    cols = ', '.join(columns)

    if _engine == 'mysql':
        updates = ', '.join([f'{c} = VALUES({c})' for c in update_cols])
        return (
            f'INSERT INTO {table} ({cols}) VALUES ({placeholders}) '
            f'ON DUPLICATE KEY UPDATE {updates}'
        )

    if _engine == 'postgresql':
        updates = ', '.join([f'{c} = EXCLUDED.{c}' for c in update_cols])
        return (
            f'INSERT INTO {table} ({cols}) VALUES ({placeholders}) '
            f'ON CONFLICT ({conflict_col}) DO UPDATE SET {updates}'
        )

    if _engine == 'sqlserver':
        source_cols = ', '.join([f's.{c}' for c in update_cols])
        target_updates = ', '.join([f'target.{c} = source.{c}' for c in update_cols])
        src_values = ', '.join([f'@p{i}' for i in range(len(columns))])
        src_alias = ', '.join(columns)
        return (
            f'MERGE INTO {table} AS target '
            f'USING (VALUES ({src_values})) AS source ({src_alias}) '
            f'ON target.{conflict_col} = source.{conflict_col} '
            f'WHEN MATCHED THEN UPDATE SET {target_updates} '
            f'WHEN NOT MATCHED THEN INSERT ({cols}) VALUES ({", ".join([f"source.{c}" for c in columns])});'
        )

    updates = ', '.join([f'{c} = excluded.{c}' for c in update_cols])
    return (
        f'INSERT INTO {table} ({cols}) VALUES ({placeholders}) '
        f'ON CONFLICT ({conflict_col}) DO UPDATE SET {updates}'
    )


def upsert_incremental_sql(table, columns, conflict_col, increment_cols, passthrough_cols=None):
    placeholders = ', '.join(['%s'] * len(columns))
    cols = ', '.join(columns)

    if _engine == 'mysql':
        updates = []
        for c in increment_cols:
            updates.append(f'{c} = {c} + VALUES({c})')
        if passthrough_cols:
            for c in passthrough_cols:
                updates.append(f'{c} = VALUES({c})')
        return (
            f'INSERT INTO {table} ({cols}) VALUES ({placeholders}) '
            f'ON DUPLICATE KEY UPDATE {", ".join(updates)}'
        )

    if _engine == 'postgresql':
        updates = []
        for c in increment_cols:
            updates.append(f'{c} = {table}.{c} + EXCLUDED.{c}')
        if passthrough_cols:
            for c in passthrough_cols:
                updates.append(f'{c} = EXCLUDED.{c}')
        return (
            f'INSERT INTO {table} ({cols}) VALUES ({placeholders}) '
            f'ON CONFLICT ({conflict_col}) DO UPDATE SET {", ".join(updates)}'
        )

    if _engine == 'sqlserver':
        updates = []
        for c in increment_cols:
            updates.append(f'target.{c} = target.{c} + source.{c}')
        if passthrough_cols:
            for c in passthrough_cols:
                updates.append(f'target.{c} = source.{c}')
        src_values = ', '.join([f'@p{i}' for i in range(len(columns))])
        src_alias = ', '.join(columns)
        return (
            f'MERGE INTO {table} AS target '
            f'USING (VALUES ({src_values})) AS source ({src_alias}) '
            f'ON target.{conflict_col} = source.{conflict_col} '
            f'WHEN MATCHED THEN UPDATE SET {", ".join(updates)} '
            f'WHEN NOT MATCHED THEN INSERT ({cols}) VALUES ({", ".join([f"source.{c}" for c in columns])});'
        )

    updates = []
    for c in increment_cols:
        updates.append(f'{c} = {c} + excluded.{c}')
    if passthrough_cols:
        for c in passthrough_cols:
            updates.append(f'{c} = excluded.{c}')
    return (
        f'INSERT INTO {table} ({cols}) VALUES ({placeholders}) '
        f'ON CONFLICT ({conflict_col}) DO UPDATE SET {", ".join(updates)}'
    )


def upsert_coalesce_sql(table, columns, conflict_col, increment_cols, coalesce_cols):
    placeholders = ', '.join(['%s'] * len(columns))
    cols = ', '.join(columns)

    if _engine == 'mysql':
        updates = []
        for c in increment_cols:
            updates.append(f'{c} = {c} + VALUES({c})')
        for c in coalesce_cols:
            updates.append(f'{c} = COALESCE(VALUES({c}), {c})')
        return (
            f'INSERT INTO {table} ({cols}) VALUES ({placeholders}) '
            f'ON DUPLICATE KEY UPDATE {", ".join(updates)}'
        )

    if _engine == 'postgresql':
        updates = []
        for c in increment_cols:
            updates.append(f'{c} = {table}.{c} + EXCLUDED.{c}')
        for c in coalesce_cols:
            updates.append(f'{c} = COALESCE(EXCLUDED.{c}, {table}.{c})')
        return (
            f'INSERT INTO {table} ({cols}) VALUES ({placeholders}) '
            f'ON CONFLICT ({conflict_col}) DO UPDATE SET {", ".join(updates)}'
        )

    if _engine == 'sqlserver':
        updates = []
        for c in increment_cols:
            updates.append(f'target.{c} = target.{c} + source.{c}')
        for c in coalesce_cols:
            updates.append(f'target.{c} = COALESCE(source.{c}, target.{c})')
        src_values = ', '.join([f'@p{i}' for i in range(len(columns))])
        src_alias = ', '.join(columns)
        return (
            f'MERGE INTO {table} AS target '
            f'USING (VALUES ({src_values})) AS source ({src_alias}) '
            f'ON target.{conflict_col} = source.{conflict_col} '
            f'WHEN MATCHED THEN UPDATE SET {", ".join(updates)} '
            f'WHEN NOT MATCHED THEN INSERT ({cols}) VALUES ({", ".join([f"source.{c}" for c in columns])});'
        )

    updates = []
    for c in increment_cols:
        updates.append(f'{c} = {c} + excluded.{c}')
    for c in coalesce_cols:
        updates.append(f'{c} = COALESCE(excluded.{c}, {c})')
    return (
        f'INSERT INTO {table} ({cols}) VALUES ({placeholders}) '
        f'ON CONFLICT ({conflict_col}) DO UPDATE SET {", ".join(updates)}'
    )


def insert_ignore_sql(table, columns):
    placeholders = ', '.join(['%s'] * len(columns))
    cols = ', '.join(columns)

    if _engine == 'mysql':
        return f'INSERT IGNORE INTO {table} ({cols}) VALUES ({placeholders})'

    if _engine == 'postgresql':
        conflict_col = columns[0]
        return (
            f'INSERT INTO {table} ({cols}) VALUES ({placeholders}) '
            f'ON CONFLICT ({conflict_col}) DO NOTHING'
        )

    if _engine == 'sqlserver':
        conflict_col = columns[0]
        src_values = ', '.join([f'@p{i}' for i in range(len(columns))])
        src_alias = ', '.join(columns)
        return (
            f'IF NOT EXISTS (SELECT 1 FROM {table} WHERE {conflict_col} = @p0) '
            f'INSERT INTO {table} ({cols}) VALUES ({placeholders})'
        )

    return f'INSERT OR IGNORE INTO {table} ({cols}) VALUES ({placeholders})'


def get_lastrowid(cursor, result=None):
    if _engine == 'postgresql' and result is not None:
        if hasattr(result, 'inserted_primary_key') and result.inserted_primary_key:
            return result.inserted_primary_key[0]
    return cursor.lastrowid


def execute_insert(cursor, sql, params=None, id_col='id'):
    if _engine == 'postgresql':
        insert_sql = sql.rstrip().rstrip(';') + f' RETURNING {id_col}'
        cursor.execute(insert_sql, params)
        row = cursor.fetchone()
        return row[0] if row else None
    if _engine == 'sqlserver':
        cursor.execute(sql, params)
        cursor.execute('SELECT SCOPE_IDENTITY()')
        row = cursor.fetchone()
        return row[0] if row else None
    cursor.execute(sql, params)
    return cursor.lastrowid


def is_duplicate_key_error(exc):
    if _engine == 'mysql':
        return hasattr(exc, 'args') and exc.args[0] == 1062
    if _engine == 'postgresql':
        return hasattr(exc, 'orig') and hasattr(exc.orig, 'pgcode') and exc.orig.pgcode == '23505'
    if _engine == 'sqlserver':
        if hasattr(exc, 'args') and len(exc.args) > 0:
            return exc.args[0] in (2627, 2601)
    return False
