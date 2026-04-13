from __future__ import annotations

from contextlib import closing
import json
import sqlite3
from pathlib import Path

from security_agent.models.skill import SkillMetadata


class CatalogRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def _connect(self):
        return closing(sqlite3.connect(self.db_path))

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS skills (
                    name TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    subdomain TEXT,
                    tags_json TEXT NOT NULL,
                    version TEXT,
                    author TEXT,
                    license TEXT,
                    relative_path TEXT,
                    source_commit TEXT,
                    references_json TEXT NOT NULL,
                    scripts_json TEXT NOT NULL,
                    assets_json TEXT NOT NULL
                );
                """
            )
            connection.commit()

    def upsert_skill(self, skill: SkillMetadata) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO skills (
                    name, description, domain, subdomain, tags_json, version, author,
                    license, relative_path, source_commit, references_json, scripts_json, assets_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    description = excluded.description,
                    domain = excluded.domain,
                    subdomain = excluded.subdomain,
                    tags_json = excluded.tags_json,
                    version = excluded.version,
                    author = excluded.author,
                    license = excluded.license,
                    relative_path = excluded.relative_path,
                    source_commit = excluded.source_commit,
                    references_json = excluded.references_json,
                    scripts_json = excluded.scripts_json,
                    assets_json = excluded.assets_json
                """,
                (
                    skill.name,
                    skill.description,
                    skill.domain,
                    skill.subdomain,
                    json.dumps(skill.tags),
                    skill.version,
                    skill.author,
                    skill.license,
                    skill.relative_path,
                    skill.source_commit,
                    json.dumps(skill.references),
                    json.dumps(skill.scripts),
                    json.dumps(skill.assets),
                ),
            )
            connection.commit()

    def upsert_many(self, skills: list[SkillMetadata]) -> None:
        for skill in skills:
            self.upsert_skill(skill)

    def list_skills(self) -> list[SkillMetadata]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT name, description, domain, subdomain, tags_json, version, author,
                       license, relative_path, source_commit, references_json, scripts_json, assets_json
                FROM skills
                ORDER BY name
                """
            ).fetchall()
        return [self._row_to_skill(row) for row in rows]

    def search(self, query: str, limit: int = 5) -> list[SkillMetadata]:
        like_query = f"%{query.lower()}%"
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT name, description, domain, subdomain, tags_json, version, author,
                       license, relative_path, source_commit, references_json, scripts_json, assets_json
                FROM skills
                WHERE lower(name) LIKE ? OR lower(description) LIKE ? OR lower(tags_json) LIKE ? OR lower(COALESCE(subdomain, '')) LIKE ?
                ORDER BY name
                LIMIT ?
                """,
                (like_query, like_query, like_query, like_query, limit),
            ).fetchall()
        return [self._row_to_skill(row) for row in rows]

    @staticmethod
    def _row_to_skill(row: tuple[object, ...]) -> SkillMetadata:
        return SkillMetadata(
            name=str(row[0]),
            description=str(row[1]),
            domain=str(row[2]),
            subdomain=str(row[3]) if row[3] else None,
            tags=tuple(json.loads(str(row[4]))),
            version=str(row[5]) if row[5] else None,
            author=str(row[6]) if row[6] else None,
            license=str(row[7]) if row[7] else None,
            relative_path=str(row[8]) if row[8] else None,
            source_commit=str(row[9]) if row[9] else None,
            references=tuple(json.loads(str(row[10]))),
            scripts=tuple(json.loads(str(row[11]))),
            assets=tuple(json.loads(str(row[12]))),
        )
