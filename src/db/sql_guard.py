from __future__ import annotations
import re


_DDL_DML_PATTERN = re.compile(r"\b(insert|update|delete|merge|alter|drop|truncate|create|grant|revoke|call|copy)\b", re.IGNORECASE)
_MULTI_STMT_PATTERN = re.compile(r";\s*\S")


def _wrap_table_with_filter(table_name: str, client_column: str) -> str:
    return (
        f"(SELECT * FROM public.{table_name} "
        f"WHERE {client_column} NOT IN (SELECT client_code FROM public.clients WHERE marker = 'Бонус'))"
    )


def _replace_from_join(query: str, table_name: str, client_column: str) -> str:
    """
    Replace FROM/JOIN occurrences of a table with a filtered subquery enforcing the bonus-client filter.
    Handles optional schema qualification and optional alias, e.g.:
      FROM profit p  -> FROM (SELECT * FROM public.profit WHERE ...) p
      JOIN public.orders AS o -> JOIN (SELECT * FROM public.orders WHERE ...) o
      FROM debt -> FROM (SELECT * FROM public.debt WHERE ...) debt
    Also handles CTE queries (WITH statements).
    """
    # FROM <schema?>table [AS] <alias> | FROM <schema?>table
    from_pattern = re.compile(
        rf"\bFROM\s+(?:public\.)?{table_name}\b(\s+(?:AS\s+)?(?P<alias>[a-zA-Z_][a-zA-Z0-9_]*))?",
        re.IGNORECASE,
    )
    join_pattern = re.compile(
        rf"\bJOIN\s+(?:public\.)?{table_name}\b(\s+(?:AS\s+)?(?P<alias>[a-zA-Z_][a-zA-Z0-9_]*))?",
        re.IGNORECASE,
    )

    def _from_repl(m: re.Match) -> str:
        alias = m.group('alias')
        wrapped = _wrap_table_with_filter(table_name, client_column)
        if alias:
            return f"FROM {wrapped} {alias}"
        else:
            # Keep table name as alias for compatibility with column qualifiers
            return f"FROM {wrapped} {table_name}"

    def _join_repl(m: re.Match) -> str:
        alias = m.group('alias')
        wrapped = _wrap_table_with_filter(table_name, client_column)
        if alias:
            return f"JOIN {wrapped} {alias}"
        else:
            return f"JOIN {wrapped} {table_name}"

    query = from_pattern.sub(_from_repl, query)
    query = join_pattern.sub(_join_repl, query)
    return query


def guard_sql(sql: str) -> str:
    """
    Enforce safety and business filters for incoming SQL:
    - Allow only single SELECT statements
    - For tables profit, orders, debt, managers_plan add filter to exclude clients with marker='Бонус'
    """
    if not sql or not sql.strip():
        raise ValueError("Empty SQL query")

    # Trim whitespace and remove trailing semicolon
    query = sql.strip()
    if query.endswith(';'):
        query = query[:-1]

    # Disallow multiple statements
    if _MULTI_STMT_PATTERN.search(query):
        raise ValueError("Multiple SQL statements are not allowed")

    # Allow only SELECT or WITH (CTE)
    if not re.match(r"^\s*(select|with)\b", query, re.IGNORECASE):
        raise ValueError("Only SELECT or WITH (CTE) statements are allowed")

    # Block obvious DDL/DML keywords anywhere
    if _DDL_DML_PATTERN.search(query):
        raise ValueError("DDL/DML statements are not allowed")

    # Inject bonus-client filter via table wrapping
    table_client_map = {
        'profit': 'client_code',
        'orders': 'client_code',
        'debt': 'client_code',
        'managers_plan': 'client_code',
    }

    guarded = query
    for table, client_col in table_client_map.items():
        guarded = _replace_from_join(guarded, table, client_col)

    # Handle stock via products->clients relationship
    # Wrap stock with product filter excluding products whose linked client has marker = 'Бонус'
    def _wrap_stock() -> str:
        return (
            "(SELECT * FROM public.stock WHERE product_code IN ("
            "SELECT pr.product_code FROM public.products pr "
            "LEFT JOIN public.clients c ON pr.client_code = c.client_code "
            "WHERE c.client_code IS NULL OR c.marker <> 'Бонус'" 
            "))"
        )

    def _stock_repl_from(m: re.Match) -> str:
        alias = m.group('alias')
        wrapped = _wrap_stock()
        return f"FROM {wrapped} {alias or 'stock'}"

    def _stock_repl_join(m: re.Match) -> str:
        alias = m.group('alias')
        wrapped = _wrap_stock()
        return f"JOIN {wrapped} {alias or 'stock'}"

    stock_from = re.compile(r"\bFROM\s+(?:public\.)?stock\b(\s+(?:AS\s+)?(?P<alias>[a-zA-Z_][a-zA-Z0-9_]*))?", re.IGNORECASE)
    stock_join = re.compile(r"\bJOIN\s+(?:public\.)?stock\b(\s+(?:AS\s+)?(?P<alias>[a-zA-Z_][a-zA-Z0-9_]*))?", re.IGNORECASE)
    guarded = stock_from.sub(_stock_repl_from, guarded)
    guarded = stock_join.sub(_stock_repl_join, guarded)

    return guarded


