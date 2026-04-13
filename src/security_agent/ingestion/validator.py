from __future__ import annotations

from pathlib import Path

from security_agent.models.skill import SkillMetadata

REQUIRED_FIELDS = ("name", "description", "domain")


def validate_skill(skill: SkillMetadata, skill_dir: Path | None = None) -> list[str]:
    errors: list[str] = []
    for field_name in REQUIRED_FIELDS:
        if not getattr(skill, field_name):
            errors.append(f"Missing required field: {field_name}")
    if skill.domain and skill.domain != "cybersecurity":
        errors.append("Skill domain must be 'cybersecurity'")
    if skill_dir is not None and skill.name and skill_dir.name != skill.name:
        errors.append("Skill directory name does not match skill name")
    return errors


def assert_valid_skill(skill: SkillMetadata, skill_dir: Path | None = None) -> None:
    errors = validate_skill(skill, skill_dir)
    if errors:
        raise ValueError("; ".join(errors))
