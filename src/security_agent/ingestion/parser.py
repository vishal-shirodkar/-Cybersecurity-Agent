from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from security_agent.models.skill import SkillMetadata


@dataclass(frozen=True)
class ParsedSkill:
    metadata: SkillMetadata
    body: str


def split_frontmatter(content: str) -> tuple[str, str]:
    if not content.startswith("---"):
        raise ValueError("Skill file is missing YAML frontmatter")

    lines = content.splitlines()
    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break

    if end_index is None:
        raise ValueError("Skill file frontmatter is not terminated")

    metadata_text = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :]).strip()
    return metadata_text, body


def _parse_scalar(value: str) -> Any:
    cleaned = value.strip()
    if cleaned == "":
        return ""

    if cleaned.startswith("[") and cleaned.endswith("]"):
        inner = cleaned[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("\"'") for item in inner.split(",") if item.strip()]

    if cleaned.startswith(("'", '"')) and cleaned.endswith(("'", '"')) and len(cleaned) >= 2:
        return cleaned[1:-1]

    lowered = cleaned.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return cleaned


def _parse_minimal_yaml(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    lines = text.splitlines()
    index = 0

    while index < len(lines):
        raw_line = lines[index]
        if not raw_line.strip():
            index += 1
            continue

        if raw_line.startswith("- "):
            raise ValueError("Unexpected list item without a key")
        if ":" not in raw_line:
            raise ValueError(f"Invalid frontmatter line: {raw_line}")

        key, raw_value = raw_line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()

        if value in {"", "|", "|-", ">", ">-"}:
            block_lines: list[str] = []
            list_items: list[Any] = []
            block_mode = value if value else None
            index += 1

            while index < len(lines):
                candidate = lines[index]
                if candidate.startswith("- "):
                    list_items.append(_parse_scalar(candidate[2:]))
                    index += 1
                    continue
                if candidate.startswith("  ") or candidate.startswith("\t"):
                    block_lines.append(candidate.lstrip())
                    index += 1
                    continue
                if not candidate.strip():
                    if block_lines:
                        block_lines.append("")
                    index += 1
                    continue
                break

            if list_items:
                result[key] = list_items
            else:
                if block_mode in {">", ">-"}:
                    result[key] = " ".join(line.strip() for line in block_lines if line.strip())
                else:
                    result[key] = "\n".join(block_lines).strip()
            continue

        result[key] = _parse_scalar(value)
        index += 1

    return result


def parse_frontmatter(text: str) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError:
        yaml = None

    if yaml is not None:
        loaded = yaml.safe_load(text) or {}
        if not isinstance(loaded, dict):
            raise ValueError("Frontmatter must deserialize to a mapping")
        return loaded

    return _parse_minimal_yaml(text)


def parse_skill_file(path: Path) -> ParsedSkill:
    content = path.read_text(encoding="utf-8")
    metadata_text, body = split_frontmatter(content)
    metadata = parse_frontmatter(metadata_text)
    skill = SkillMetadata.from_dict(metadata)
    return ParsedSkill(metadata=skill, body=body)
