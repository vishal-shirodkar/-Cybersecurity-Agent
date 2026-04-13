from __future__ import annotations

from dataclasses import dataclass

from security_agent.catalog.ranking import score_skill
from security_agent.models.skill import SkillMetadata


@dataclass(frozen=True)
class SearchHit:
    skill: SkillMetadata
    score: int
    reasons: tuple[str, ...]


def search_skills(skills: list[SkillMetadata], query: str, limit: int = 5) -> list[SearchHit]:
    ranked: list[SearchHit] = []
    for skill in skills:
        score = score_skill(skill, query)
        if score.score <= 0:
            continue
        ranked.append(SearchHit(skill=skill, score=score.score, reasons=score.reasons))
    ranked.sort(key=lambda item: (-item.score, item.skill.name))
    return ranked[:limit]
