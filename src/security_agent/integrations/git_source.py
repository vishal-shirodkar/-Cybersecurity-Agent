from __future__ import annotations

from pathlib import Path
import subprocess

from security_agent.ingestion.sync import UpstreamSyncPlan


class GitSkillSource:
    def sync(self, plan: UpstreamSyncPlan) -> int:
        plan.target_dir.parent.mkdir(parents=True, exist_ok=True)
        if plan.target_dir.exists():
            command = plan.update_command()
        else:
            command = plan.clone_command()
        completed = subprocess.run(command, check=False, capture_output=True, text=True, shell=True)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "Git sync failed")
        return completed.returncode
