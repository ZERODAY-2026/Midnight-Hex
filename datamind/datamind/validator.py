"""DataMind: SQL query validation and guardrails using sqlglot."""

import sqlglot
from sqlglot import exp


class SQLRejected(Exception):
    """Exception raised when a generated SQL query violates security or schema guardrails."""
    pass


def validate(
    sql: str,
    allowed_tables: set[str],
    max_rows: int = 500,
    database: str | None = None,
    schema: str | None = None,
) -> str:
    """
    Validate and enforce guardrails on a SQL query:
    1. Single statement only (prevent semicolon chaining)
    2. Read-only SELECT operations only (strictly no DDL, DML, or admin commands)
    3. Tables must strictly belong to allowed_tables set (or defined CTEs)
    4. Enforce row limit (clamp to max_rows)
    """
    if not sql or not sql.strip():
        raise SQLRejected("SQL query is empty.")

    # 1. Reject multiple statements
    try:
        statements = sqlglot.parse(sql, read="snowflake")
    except Exception as e:
        raise SQLRejected(f"Parse error: {e}")

    # Filter out empty statements (e.g. trailing semicolons)
    non_empty_stmts = [s for s in statements if s is not None]
    if len(non_empty_stmts) > 1:
        raise SQLRejected("Multiple SQL statements are strictly forbidden.")
    if not non_empty_stmts:
        raise SQLRejected("No valid SQL statement found.")

    tree = non_empty_stmts[0]

    # 2. Enforce SELECT / UNION / WITH queries only
    if not isinstance(tree, (exp.Select, exp.Union)) and not tree.find(exp.Select):
        raise SQLRejected("Only SELECT queries are allowed.")

    # Forbidden DML/DDL operations
    forbidden = (
        exp.Insert, exp.Update, exp.Delete, exp.Drop,
        exp.Create, exp.Alter, exp.Command
    )
    for f in forbidden:
        if tree.find(f):
            raise SQLRejected(f"Write, DDL, or administrative operations ({f.__name__}) are strictly forbidden.")

    # 3. Check allowed tables against whitelist and CTE aliases
    ctes = {c.alias.upper() for c in tree.find_all(exp.CTE) if c.alias}
    allowed_upper = {t.upper() for t in allowed_tables}

    for t in tree.find_all(exp.Table):
        t_name = t.name.upper()
        if t_name not in allowed_upper and t_name not in ctes:
            raise SQLRejected(f"Table not allowed: {t_name}. Allowed tables: {sorted(list(allowed_upper))}")

        if t_name in ctes and (t.db or t.catalog):
            raise SQLRejected(f"Qualified CTE references are not allowed: {t.sql(dialect='snowflake')}")
        if t.catalog and database and t.catalog.upper() != database.upper():
            raise SQLRejected(f"Database not allowed: {t.catalog}. Expected database: {database}")
        if t.db and schema and t.db.upper() != schema.upper():
            raise SQLRejected(f"Schema not allowed: {t.db}. Expected schema: {schema}")

    # 4. Limit enforcement
    limit_node = tree.find(exp.Limit)
    if not limit_node:
        tree = tree.limit(max_rows)
    else:
        # If user/LLM supplied a LIMIT, clamp it so it cannot exceed max_rows
        try:
            val = int(limit_node.expression.this)
            if val > max_rows:
                limit_node.set("expression", exp.Literal.number(max_rows))
        except Exception:
            # If dynamic or non-integer, replace with max_rows
            limit_node.set("expression", exp.Literal.number(max_rows))

    return tree.sql(dialect="snowflake")
