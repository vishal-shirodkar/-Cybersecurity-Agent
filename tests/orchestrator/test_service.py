import sys
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from security_agent.catalog.repository import CatalogRepository
from security_agent.integrations.mcp_server import LocalMcpService
from security_agent.models.skill import SkillMetadata


class ServiceTests(unittest.TestCase):
    def test_service_returns_grounded_prompt(self) -> None:
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
                    relative_path="tests/fixtures/sample_skills/memory-forensics",
                )
            )
            service = LocalMcpService(repository, ROOT)
            result = service.query(
                query="Investigate a suspicious memory dump",
                skills_root=ROOT,
                limit=1,
            )
            self.assertEqual(result["intent"], "digital-forensics")
            self.assertEqual(result["trace"]["selected_skills"], ["memory-forensics"])
            self.assertIn("skill:memory-forensics", result["grounded_prompt"])


if __name__ == "__main__":
    unittest.main()
