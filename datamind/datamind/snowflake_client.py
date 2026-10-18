"""DataMind: Snowflake client with query execution and query ID tracking."""

import os
import uuid
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()


class SnowflakeClient:
    """Snowflake connection client handling authentication, queries, and query IDs."""

    def __init__(
        self,
        account: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        role: Optional[str] = None,
        warehouse: Optional[str] = None,
        database: Optional[str] = None,
        schema: Optional[str] = None,
    ):
        self.account = account or os.environ.get("SNOWFLAKE_ACCOUNT")
        self.user = user or os.environ.get("SNOWFLAKE_USER")
        self.password = password or os.environ.get("SNOWFLAKE_PASSWORD")
        self.role = role or os.environ.get("SNOWFLAKE_ROLE", "DATAMIND_READONLY")
        self.warehouse = warehouse or os.environ.get("SNOWFLAKE_WAREHOUSE", "DATAMIND_WH")
        self.database = database
        self.schema = schema
        credentials = (self.account, self.user, self.password)
        self.credentials_missing = any(
            not value or value.strip().lower().startswith(("your_", "<", "replace_me"))
            for value in credentials
        )
        demo_requested = os.environ.get("DATAMIND_DEMO_MODE", "false").lower() in ("true", "1", "yes")
        self.demo_mode = demo_requested or self.credentials_missing
        self.demo_reason = (
            "Demo mode was explicitly enabled"
            if demo_requested
            else "Snowflake credentials are missing"
        )

        self.conn = None
        if not self.demo_mode:
            self._connect()

    def _connect(self):
        """Establish connection with Snowflake."""
        import snowflake.connector

        self.conn = snowflake.connector.connect(
            account=self.account,
            user=self.user,
            password=self.password,
            role=self.role,
            warehouse=self.warehouse,
            database=self.database,
            schema=self.schema,
        )

    def run(self, sql: str) -> Dict[str, Any]:
        """Execute a validated SQL query in Snowflake and return columns, rows, and query ID."""
        if self.demo_mode:
            # Simulation/Demo mode for offline evaluation or initial local test
            return self._mock_run(sql)
        if self.conn is None:
            raise RuntimeError("Snowflake connection is unavailable; refusing to simulate a live query.")

        cur = self.conn.cursor()
        try:
            cur.execute(sql)
            cols = [c[0] for c in cur.description] if cur.description else []
            rows = cur.fetchall()
            # Snowflake query ID (sfqid) uniquely identifies query execution in Snowflake history
            query_id = cur.sfqid or "N/A"
            return {"columns": cols, "rows": rows, "query_id": query_id}
        finally:
            cur.close()

    def columns(self, db: str, schema: str) -> List[List[Any]]:
        """Fetch columns metadata from Snowflake's INFORMATION_SCHEMA."""
        if self.demo_mode:
            return []

        query = (
            f"SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE "
            f"FROM {db}.INFORMATION_SCHEMA.COLUMNS "
            f"WHERE TABLE_SCHEMA = '{schema}' "
            f"ORDER BY TABLE_NAME, ORDINAL_POSITION"
        )
        return self.run(query)["rows"]

    def _mock_run(self, sql: str) -> Dict[str, Any]:
        """Fallback mock executor for offline development or testing without active credentials."""
        return {
            "columns": ["SIMULATION"],
            "rows": [["No live Snowflake query was executed."]],
            "query_id": f"simulation-{uuid.uuid4().hex[:12]}",
        }

    def close(self):
        """Close connection if open."""
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
