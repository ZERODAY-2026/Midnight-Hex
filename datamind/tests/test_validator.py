"""Unit tests for DataMind SQL guardrails and validator."""

import pytest
from datamind.validator import validate, SQLRejected

ALLOWED_TABLES = {"ORDERS", "CUSTOMER", "NATION", "REGION", "LINEITEM"}


def test_valid_simple_select():
    sql = "SELECT O_ORDERKEY, O_TOTALPRICE FROM ORDERS WHERE O_ORDERSTATUS = 'O'"
    validated = validate(sql, ALLOWED_TABLES, max_rows=100)
    assert "SELECT" in validated
    assert "LIMIT 100" in validated.upper()


def test_valid_join_query():
    sql = """
    SELECT C.C_NAME, N.N_NAME
    FROM CUSTOMER C
    JOIN NATION N ON C.C_NATIONKEY = N.N_NATIONKEY
    LIMIT 25
    """
    validated = validate(sql, ALLOWED_TABLES, max_rows=100)
    assert "JOIN" in validated
    assert "LIMIT 25" in validated.upper()


def test_limit_clamping():
    sql = "SELECT * FROM ORDERS LIMIT 1000"
    validated = validate(sql, ALLOWED_TABLES, max_rows=200)
    # Must clamp to 200
    assert "LIMIT 200" in validated.upper()


def test_cte_support():
    sql = """
    WITH TOP_ORDERS AS (
        SELECT O_CUSTKEY, SUM(O_TOTALPRICE) AS TOTAL
        FROM ORDERS
        GROUP BY O_CUSTKEY
    )
    SELECT C.C_NAME, T.TOTAL
    FROM TOP_ORDERS T
    JOIN CUSTOMER C ON T.O_CUSTKEY = C.C_CUSTKEY
    """
    validated = validate(sql, ALLOWED_TABLES, max_rows=50)
    assert "TOP_ORDERS" in validated
    assert "LIMIT 50" in validated.upper()


@pytest.mark.parametrize("malicious_sql", [
    "DROP TABLE ORDERS",
    "DELETE FROM CUSTOMER WHERE C_CUSTKEY = 1",
    "INSERT INTO ORDERS (O_ORDERKEY) VALUES (999)",
    "UPDATE CUSTOMER SET C_ACCTBAL = 999999",
    "ALTER TABLE ORDERS DROP COLUMN O_COMMENT",
    "TRUNCATE TABLE LINEITEM",
    "GRANT ALL PRIVILEGES ON DATABASE SNOWFLAKE_SAMPLE_DATA TO ROLE PUBLIC",
])
def test_reject_dangerous_operations(malicious_sql):
    with pytest.raises(SQLRejected):
        validate(malicious_sql, ALLOWED_TABLES, max_rows=100)


def test_reject_unauthorized_table():
    sql = "SELECT * FROM INTERNAL_PAYROLL WHERE SALARY > 100000"
    with pytest.raises(SQLRejected, match="Table not allowed"):
        validate(sql, ALLOWED_TABLES, max_rows=100)


def test_dataset_whitelist_rejects_table_from_another_dataset():
    with pytest.raises(SQLRejected, match="Table not allowed: ORDERS"):
        validate(
            "SELECT * FROM ORDERS",
            {"ENERGY_CONSUMPTION"},
            database="DATAMIND_DB",
            schema="OWID",
        )


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM OTHER_DB.OWID.ENERGY_CONSUMPTION",
        "SELECT * FROM DATAMIND_DB.OTHER_SCHEMA.ENERGY_CONSUMPTION",
    ],
)
def test_reject_qualified_table_outside_active_dataset(sql):
    with pytest.raises(SQLRejected, match="(Database|Schema) not allowed"):
        validate(
            sql,
            {"ENERGY_CONSUMPTION"},
            database="DATAMIND_DB",
            schema="OWID",
        )


def test_reject_semicolon_chaining():
    sql = "SELECT * FROM ORDERS; DROP TABLE ORDERS;"
    with pytest.raises(SQLRejected, match="Multiple SQL statements"):
        validate(sql, ALLOWED_TABLES, max_rows=100)


def test_reject_empty_sql():
    with pytest.raises(SQLRejected):
        validate("", ALLOWED_TABLES, max_rows=100)


def test_reject_parse_error():
    with pytest.raises(SQLRejected, match="Parse error"):
        validate("SELECT FROM WHERE ???", ALLOWED_TABLES, max_rows=100)
