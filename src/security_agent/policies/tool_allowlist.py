from __future__ import annotations


class ToolAllowlist:
    def __init__(self, approved_tools: tuple[str, ...]) -> None:
        self.approved_tools = approved_tools

    def is_allowed(self, tool_name: str) -> bool:
        return tool_name in self.approved_tools
