from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from security_agent.ingestion.parser import parse_skill_file
from security_agent.models.skill import SkillMetadata


@dataclass(frozen=True)
class LoadedSkill:
    metadata: SkillMetadata
    body: str
    references: tuple[str, ...]
    scripts: tuple[str, ...]
    assets: tuple[str, ...]


class SkillLoader:
    def __init__(self, skills_root: Path) -> None:
        self.skills_root = skills_root

    def load(self, skill: SkillMetadata) -> LoadedSkill:
        relative_path = skill.relative_path or f"skills/{skill.name}"
        skill_dir = self.skills_root / relative_path
        skill_file = skill_dir / "SKILL.md"
        body = "Skill body not available yet. Run sync before invoking the loader."
        if skill_file.exists():
            parsed = parse_skill_file(skill_file)
            body = parsed.body
        references = self._list_relative_files(skill_dir / "references")
        scripts = self._list_relative_files(skill_dir / "scripts")
        assets = self._list_relative_files(skill_dir / "assets")
        return LoadedSkill(metadata=skill, body=body, references=references, scripts=scripts, assets=assets)

    def _list_relative_files(self, directory: Path) -> tuple[str, ...]:
        if not directory.exists():
            return ()
        return tuple(str(path.relative_to(self.skills_root)) for path in sorted(directory.glob("**/*")) if path.is_file())
