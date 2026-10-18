"""DataMind: Dataset configuration loader using PyYAML and Pydantic."""

from typing import Dict, List
import yaml
from pydantic import BaseModel, Field


class TableCfg(BaseModel):
    description: str = ""
    columns: Dict[str, str] = Field(default_factory=dict)


class DatasetCfg(BaseModel):
    database: str
    schema_: str
    max_rows: int = 500
    tables: Dict[str, TableCfg] = Field(default_factory=dict)
    joins: List[str] = Field(default_factory=list)
    glossary: Dict[str, str] = Field(default_factory=dict)

    @property
    def schema_name(self) -> str:
        """Alias for schema_ for convenience."""
        return self.schema_


def load_config(path: str) -> DatasetCfg:
    """Load and validate dataset configuration from a YAML file."""
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid YAML config at {path}: expected a dictionary mapping.")
    if "schema" in raw:
        raw["schema_"] = raw.pop("schema")
    return DatasetCfg(**raw)
