from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class RequestContext:
    query: str
    workspace_root: str
    requested_by: str = "local-operator"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
