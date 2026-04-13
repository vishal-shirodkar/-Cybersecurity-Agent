import sys
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from security_agent.catalog.repository import CatalogRepository
from security_agent.models.skill import SkillMetadata


class RepositoryTests(unittest.TestCase):
    def test_repository_can_store_and_search_skills(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "catalog.db"
            repository = CatalogRepository(db_path)
            repository.initialize()
            repository.upsert_skill(
                SkillMetadata(
                    name="memory-forensics",
                    description="Analyze volatile memory for suspicious processes",
                    domain="cybersecurity",
                    subdomain="digital-forensics",
                    tags=("memory", "forensics"),
                    relative_path="skills/memory-forensics",
                )
            )
            results = repository.search("memory", limit=5)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].name, "memory-forensics")


if __name__ == "__main__":
    unittest.main()
