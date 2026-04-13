from __future__ import annotations

from security_agent.catalog.search import SearchHit
from security_agent.models.request_context import RequestContext
from security_agent.orchestrator.skill_loader import LoadedSkill


class PromptBuilder:
    def build(
        self,
        context: RequestContext,
        intent: str,
        hits: list[SearchHit],
        loaded_skills: list[LoadedSkill],
    ) -> str:
        lines = [
            "Security Agent Grounded Prompt",
            f"User request: {context.query}",
            f"Classified intent: {intent}",
            "",
            "Selected skills:",
        ]
        for hit in hits:
            lines.append(f"- {hit.skill.name} (score={hit.score}): {hit.skill.description}")
            for reason in hit.reasons:
                lines.append(f"  - reason: {reason}")

        lines.append("")
        lines.append("Skill guidance:")
        for skill in loaded_skills:
            lines.append(f"[skill:{skill.metadata.name}]")
            lines.append(skill.body[:1200].strip() or "No workflow body loaded.")
            if skill.references:
                lines.append(f"References: {', '.join(skill.references)}")
            if skill.scripts:
                lines.append(f"Scripts: {', '.join(skill.scripts)}")
            if skill.assets:
                lines.append(f"Assets: {', '.join(skill.assets)}")
            lines.append("")

        lines.append("Expected behavior:")
        lines.append("- cite the selected skills in every response")
        lines.append("- surface prerequisites before recommending tool execution")
        lines.append("- request approval before risky or destructive actions")
        return "\n".join(lines).strip()
