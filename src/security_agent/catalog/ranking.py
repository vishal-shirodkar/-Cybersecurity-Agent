from __future__ import annotations

from dataclasses import dataclass
import re

from security_agent.models.skill import SkillMetadata

TOKEN_RE = re.compile(r"[a-zA-Z0-9_+-]+")


@dataclass(frozen=True)
class SearchScore:
    score: int
    reasons: tuple[str, ...]


def tokenize(text: str) -> tuple[str, ...]:
    return tuple(token.lower() for token in TOKEN_RE.findall(text))


def score_skill(skill: SkillMetadata, query: str) -> SearchScore:
    query_tokens = tokenize(query)
    haystack = set(tokenize(" ".join([skill.name, skill.description, skill.subdomain or "", " ".join(skill.tags)])))
    score = 0
    reasons: list[str] = []
    for token in query_tokens:
        if token in skill.name.lower():
            score += 5
            reasons.append(f"name matched '{token}'")
        elif token in skill.tags:
            score += 4
            reasons.append(f"tag matched '{token}'")
        elif token in haystack:
            score += 2
            reasons.append(f"content matched '{token}'")
    if skill.subdomain and skill.subdomain.replace("-", " ") in query.lower():
        score += 3
        reasons.append(f"subdomain matched '{skill.subdomain}'")
    return SearchScore(score=score, reasons=tuple(dict.fromkeys(reasons)))
