from __future__ import annotations

import subprocess

from security_agent.policies.tool_allowlist import ToolAllowlist


class LocalShell:
    def __init__(self, allowlist: ToolAllowlist) -> None:
        self.allowlist = allowlist

    def run(self, command: str, tool_name: str = "powershell", dry_run: bool = True) -> dict[str, object]:
        if not self.allowlist.is_allowed(tool_name):
            raise PermissionError(f"Tool '{tool_name}' is not approved")
        if dry_run:
            return {"command": command, "status": "dry-run"}
        completed = subprocess.run(command, check=False, capture_output=True, text=True, shell=True)
        return {
            "command": command,
            "status": "completed" if completed.returncode == 0 else "failed",
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "returncode": completed.returncode,
        }
