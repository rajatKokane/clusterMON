from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Union


@dataclass(frozen=True)
class Metric:
    node_id: str
    timestamp: datetime
    category: str
    member_id: str
    name: str
    value: Union[float, str, None]
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
