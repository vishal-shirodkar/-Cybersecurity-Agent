from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


def _to_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item) for item in value)
    return (str(value),)


@dataclass(frozen=True)
class SkillMetadata:
    name: str
    description: str
    domain: str
    subdomain: str | None = None
    tags: tuple[str, ...] = ()
    version: str | None = None
    author: str | None = None
    license: str | None = None
    relative_path: str | None = None
    source_commit: str | None = None
    references: tuple[str, ...] = ()
    scripts: tuple[str, ...] = ()
    assets: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SkillMetadata":
        return cls(
            name=str(payload.get("name", "")).strip(),
            description=str(payload.get("description", "")).strip(),
            domain=str(payload.get("domain", "")).strip(),
            subdomain=str(payload.get("subdomain")).strip() if payload.get("subdomain") else None,
            tags=_to_tuple(payload.get("tags")),
            version=str(payload.get("version")).strip() if payload.get("version") else None,
            author=str(payload.get("author")).strip() if payload.get("author") else None,
            license=str(payload.get("license")).strip() if payload.get("license") else None,
            relative_path=str(payload.get("relative_path") or payload.get("path")).strip()
            if payload.get("relative_path") or payload.get("path")
            else None,
            source_commit=str(payload.get("source_commit")).strip() if payload.get("source_commit") else None,
            references=_to_tuple(payload.get("references")),
            scripts=_to_tuple(payload.get("scripts")),
            assets=_to_tuple(payload.get("assets")),
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "domain": self.domain,
            "subdomain": self.subdomain,
            "tags": list(self.tags),
            "version": self.version,
            "author": self.author,
            "license": self.license,
            "relative_path": self.relative_path,
            "source_commit": self.source_commit,
            "references": list(self.references),
            "scripts": list(self.scripts),
            "assets": list(self.assets),
        }
