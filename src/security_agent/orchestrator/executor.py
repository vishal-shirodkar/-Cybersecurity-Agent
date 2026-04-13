from __future__ import annotations

from dataclasses import dataclass

from security_agent.catalog.search import SearchHit
from security_agent.models.request_context import RequestContext
from security_agent.orchestrator.prompt_builder import PromptBuilder
from security_agent.orchestrator.skill_loader import LoadedSkill


@dataclass(frozen=True)
class ExecutionPlan:
    prompt: str
    selected_skills: tuple[str, ...]


class AdvisoryExecutor:
    def __init__(self) -> None:
        self.prompt_builder = PromptBuilder()

    def create_plan(
        self,
        context: RequestContext,
        intent: str,
        hits: list[SearchHit],
        loaded_skills: list[LoadedSkill],
    ) -> ExecutionPlan:
        prompt = self.prompt_builder.build(context, intent, hits, loaded_skills)
        return ExecutionPlan(
            prompt=prompt,
            selected_skills=tuple(hit.skill.name for hit in hits),
        )
