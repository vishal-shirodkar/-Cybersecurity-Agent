from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ExecutionTrace:
    user_query: str
    intent: str
    selected_skills: tuple[str, ...]
    citations: tuple[str, ...]
    risk_level: str
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["selected_skills"] = list(self.selected_skills)
        payload["citations"] = list(self.citations)
        payload["notes"] = list(self.notes)
        return payload
