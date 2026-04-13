import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from security_agent.ingestion.parser import parse_skill_file


class ParserTests(unittest.TestCase):
    def test_parse_skill_file_reads_frontmatter_and_body(self) -> None:
        skill_file = ROOT / "tests" / "fixtures" / "sample_skills" / "memory-forensics" / "SKILL.md"
        parsed = parse_skill_file(skill_file)
        self.assertEqual(parsed.metadata.name, "memory-forensics")
        self.assertEqual(parsed.metadata.subdomain, "digital-forensics")
        self.assertIn("Analyze volatile memory", parsed.metadata.description)
        self.assertIn("Run volatility plugins", parsed.body)


if __name__ == "__main__":
    unittest.main()
