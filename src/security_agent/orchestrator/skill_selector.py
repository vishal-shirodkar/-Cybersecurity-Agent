from __future__ import annotations

from security_agent.catalog.repository import CatalogRepository
from security_agent.catalog.search import SearchHit, search_skills


class SkillSelector:
    def __init__(self, repository: CatalogRepository) -> None:
        self.repository = repository

    def select(self, query: str, limit: int = 3) -> list[SearchHit]:
        skills = self.repository.list_skills()
        return search_skills(skills, query, limit)
