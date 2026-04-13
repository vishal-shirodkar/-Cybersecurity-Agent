from __future__ import annotations

import json
from pathlib import Path

from security_agent.models.skill import SkillMetadata


def load_manifest(index_file: Path) -> list[SkillMetadata]:
    payload = json.loads(index_file.read_text(encoding="utf-8"))
    skills = payload.get("skills", [])
    return [SkillMetadata.from_dict(skill) for skill in skills]
