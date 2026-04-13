from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class AppConfig:
    workspace_root: Path
    data_dir: Path
    upstream_dir: Path
    cache_dir: Path
    catalog_db: Path
    log_level: str
    approved_tools: tuple[str, ...]

    @classmethod
    def from_env(cls) -> "AppConfig":
        workspace_root = Path(os.environ.get("SECURITY_AGENT_WORKSPACE", Path(__file__).resolve().parents[2]))
        data_dir = workspace_root / "data"
        upstream_dir = data_dir / "upstream"
        cache_dir = data_dir / "cache"
        catalog_db = Path(os.environ.get("SECURITY_AGENT_CATALOG_DB", data_dir / "catalog.db"))
        log_level = os.environ.get("SECURITY_AGENT_LOG_LEVEL", "INFO")
        approved_tools = tuple(
            tool.strip()
            for tool in os.environ.get("SECURITY_AGENT_APPROVED_TOOLS", "python,powershell,web_fetch").split(",")
            if tool.strip()
        )
        return cls(
            workspace_root=workspace_root,
            data_dir=data_dir,
            upstream_dir=upstream_dir,
            cache_dir=cache_dir,
            catalog_db=catalog_db,
            log_level=log_level,
            approved_tools=approved_tools,
        )

    def ensure_directories(self) -> "AppConfig":
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.upstream_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return self
