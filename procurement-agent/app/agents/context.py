from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProcurementContext:
    thread_id: str
    from_email: str = ""
    original_requestor: str | None = None
    budget_ceiling: float = 0.0
    requisition_id: int | None = None
    approved_suppliers: list[dict[str, Any]] = field(default_factory=list)
