from __future__ import annotations

from pathlib import Path

from security_agent.catalog.repository import CatalogRepository
from security_agent.integrations.mcp_server import LocalMcpService


class ApiServer:
    def __init__(self, repository: CatalogRepository, workspace_root: Path) -> None:
        self.service = LocalMcpService(repository, workspace_root)

    def health(self) -> dict[str, object]:
        return self.service.health()
