from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class UpstreamSyncPlan:
    repository_url: str
    target_dir: Path
    branch: str = "main"

    def clone_command(self) -> str:
        return f"git clone --branch {self.branch} {self.repository_url} {self.target_dir}"

    def update_command(self) -> str:
        return f"git -C {self.target_dir} pull --ff-only origin {self.branch}"


def build_default_sync_plan(base_dir: Path) -> UpstreamSyncPlan:
    return UpstreamSyncPlan(
        repository_url="https://github.com/mukul975/Anthropic-Cybersecurity-Skills.git",
        target_dir=base_dir / "Anthropic-Cybersecurity-Skills",
    )
