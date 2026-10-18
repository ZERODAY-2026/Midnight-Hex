"""DataMind: Schema introspection and YAML metadata merger."""

from typing import Dict, List, Any
from .config import DatasetCfg
from .snowflake_client import SnowflakeClient


def build_schema_text(cfg: DatasetCfg, sf: SnowflakeClient) -> str:
    """
    Introspect Snowflake INFORMATION_SCHEMA.COLUMNS and merge with YAML descriptions.
    Falls back gracefully to YAML table and column definitions if Snowflake columns cannot be introspected.
    """
    sf_columns_by_table: Dict[str, List[Dict[str, str]]] = {}

    try:
        raw_cols = sf.columns(cfg.database, cfg.schema_)
        for row in raw_cols:
            if len(row) >= 3:
                t_name, c_name, d_type = str(row[0]).upper(), str(row[1]).upper(), str(row[2])
                if t_name not in sf_columns_by_table:
                    sf_columns_by_table[t_name] = []
                sf_columns_by_table[t_name].append({"column": c_name, "type": d_type})
    except Exception:
        sf_columns_by_table = {}

    schema_lines: List[str] = [
        f"Database: {cfg.database}",
        f"Schema: {cfg.schema_}",
        ""
    ]

    for table_name, table_cfg in cfg.tables.items():
        t_upper = table_name.upper()
        schema_lines.append(f"Table: {t_upper}")
        if table_cfg.description:
            schema_lines.append(f"  Description: {table_cfg.description}")
        schema_lines.append("  Columns:")

        # Merge live columns with YAML descriptions
        if t_upper in sf_columns_by_table:
            for col_info in sf_columns_by_table[t_upper]:
                c_name = col_info["column"]
                c_type = col_info["type"]
                desc = table_cfg.columns.get(c_name, "")
                desc_str = f" - {desc}" if desc else ""
                schema_lines.append(f"    - {c_name} ({c_type}){desc_str}")
        else:
            # Fallback to YAML columns if Snowflake columns not found
            for c_name, desc in table_cfg.columns.items():
                schema_lines.append(f"    - {c_name.upper()}: {desc}")

        schema_lines.append("")

    return "\n".join(schema_lines)
