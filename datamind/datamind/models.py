"""DataMind: Data models and result types."""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class AgentResult:
    """Standardized result returned by the DataMind agent."""

    type: str  # "ok" | "clarify" | "unsupported" | "empty" | "error"
    message: Optional[str] = None
    answer: Optional[str] = None
    how: Optional[str] = None
    assumptions: List[str] = field(default_factory=list)
    sql: Optional[str] = None
    query_id: Optional[str] = None
    columns: List[str] = field(default_factory=list)
    rows: List[List[Any]] = field(default_factory=list)
    grounded: bool = True
    simulated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert result object to dictionary."""
        return asdict(self)

    def __getitem__(self, item: str) -> Any:
        """Allow dict-style indexing: res['type'], res['answer'], etc."""
        return getattr(self, item)

    def __setitem__(self, key: str, value: Any) -> None:
        """Allow dict-style assignment."""
        setattr(self, key, value)

    def get(self, item: str, default: Any = None) -> Any:
        """Allow dict-style get: res.get('message')."""
        return getattr(self, item, default)

    def __contains__(self, item: str) -> bool:
        """Allow 'if key in res' checks."""
        return hasattr(self, item)
