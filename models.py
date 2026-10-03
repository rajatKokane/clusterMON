from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Metric:
    node_id: str
    timestamp: datetime
    category: str
    member_id: str
    name: str
    value: Optional[float] = None
    text_value: Optional[str] = None
    unit: Optional[str] = None
    health: Optional[str] = None
    state: Optional[str] = None


@dataclass(frozen=True)
class CollectionResult:
    node_id: str
    timestamp: datetime
    metrics: list
    status: str
    error: Optional[str] = None
