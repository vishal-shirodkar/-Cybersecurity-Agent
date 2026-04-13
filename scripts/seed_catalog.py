from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from security_agent.app import main

if __name__ == "__main__":
    index_file = ROOT / "data" / "upstream" / "Anthropic-Cybersecurity-Skills" / "index.json"
    raise SystemExit(main(["sync-manifest", "--index-file", str(index_file)]))
