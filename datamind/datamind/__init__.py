"""DataMind: Talk to your data.

Conversational SQL Analytics Platform powered by Snowflake & Google Gemma.
"""

from .models import AgentResult
from .config import load_config, DatasetCfg
from .snowflake_client import SnowflakeClient
from .schema import build_schema_text
from .agent import answer
from .validator import validate, SQLRejected
from .explain import numbers_grounded

__all__ = [
    "AgentResult",
    "load_config",
    "DatasetCfg",
    "SnowflakeClient",
    "build_schema_text",
    "answer",
    "validate",
    "SQLRejected",
    "numbers_grounded",
]
