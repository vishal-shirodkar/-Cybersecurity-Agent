from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ApprovalDecision:
    allowed: bool
    requires_confirmation: bool
    reason: str


class ApprovalPolicy:
    def evaluate(self, risk_level: str) -> ApprovalDecision:
        if risk_level == "high":
            return ApprovalDecision(False, True, "High-risk tasks require explicit approval")
        if risk_level == "medium":
            return ApprovalDecision(True, True, "Medium-risk tasks should be operator-approved")
        return ApprovalDecision(True, False, "Low-risk tasks can proceed in advisory mode")
