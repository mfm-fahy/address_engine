from dataclasses import dataclass, field
from typing import Optional


@dataclass
class IngestionResult:
    source: str = ""
    total_fetched: int = 0
    valid_count: int = 0
    inserted_count: int = 0
    duplicate_count: int = 0
    updated_count: int = 0
    validation_errors: list[str] = field(default_factory=list)
    error: Optional[str] = None
    duration_seconds: float = 0.0
