from __future__ import annotations

from pathlib import Path

from security_agent.integrations.mcp_server import LocalMcpService


class CopilotWrapper:
    def __init__(self, service: LocalMcpService) -> None:
        self.service = service

    def invoke(self, query: str, skills_root: Path, limit: int = 3) -> dict[str, object]:
        return self.service.query(query=query, skills_root=skills_root, limit=limit)
