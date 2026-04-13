from __future__ import annotations

import json
import sys
from pathlib import Path

from security_agent.catalog.repository import CatalogRepository
from security_agent.models.execution_trace import ExecutionTrace
from security_agent.models.request_context import RequestContext
from security_agent.orchestrator.executor import AdvisoryExecutor
from security_agent.orchestrator.intent_classifier import classify_intent
from security_agent.orchestrator.skill_loader import SkillLoader
from security_agent.orchestrator.skill_selector import SkillSelector
from security_agent.policies.approvals import ApprovalPolicy
from security_agent.policies.risk_classifier import classify_risk


class LocalMcpService:
    def __init__(self, repository: CatalogRepository, workspace_root: Path) -> None:
        self.repository = repository
        self.selector = SkillSelector(repository)
        self.executor = AdvisoryExecutor()
        self.approval_policy = ApprovalPolicy()
        self.workspace_root = workspace_root

    def health(self) -> dict[str, object]:
        return {
            "status": "ok",
            "workspace_root": str(self.workspace_root),
            "skill_count": len(self.repository.list_skills()),
        }

    def query(self, query: str, skills_root: Path, limit: int = 3) -> dict[str, object]:
        context = RequestContext(query=query, workspace_root=str(self.workspace_root))
        intent = classify_intent(query)
        hits = self.selector.select(query, limit=limit)
        loader = SkillLoader(skills_root)
        loaded_skills = [loader.load(hit.skill) for hit in hits]
        plan = self.executor.create_plan(context, intent.intent, hits, loaded_skills)
        risk_level = classify_risk(query)
        approval = self.approval_policy.evaluate(risk_level)
        trace = ExecutionTrace(
            user_query=query,
            intent=intent.intent,
            selected_skills=tuple(hit.skill.name for hit in hits),
            citations=tuple(f"skill:{hit.skill.name}" for hit in hits),
            risk_level=risk_level,
            notes=tuple(hit.reasons[0] for hit in hits if hit.reasons),
        )
        return {
            "intent": intent.intent,
            "confidence": intent.confidence,
            "rationale": intent.rationale,
            "approval": {
                "allowed": approval.allowed,
                "requires_confirmation": approval.requires_confirmation,
                "reason": approval.reason,
            },
            "selected_skills": [hit.skill.to_record() for hit in hits],
            "grounded_prompt": plan.prompt,
            "trace": trace.to_dict(),
        }


def run_stdio_loop(service: LocalMcpService, default_skills_root: Path, limit: int = 3) -> int:
    print("Security agent skeleton stdio service started.", file=sys.stderr)
    print("Send one JSON object per line with action=health|query|exit.", file=sys.stderr)
    while True:
        raw_line = sys.stdin.readline()
        if raw_line == "":
            return 0
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            payload = json.loads(raw_line)
            action = payload.get("action")
            if action == "exit":
                print(json.dumps({"status": "bye"}), flush=True)
                return 0
            if action == "health":
                print(json.dumps(service.health()), flush=True)
                continue
            if action == "query":
                query = str(payload.get("query", "")).strip()
                if not query:
                    raise ValueError("'query' is required for action=query")
                skills_root = Path(payload.get("skills_root") or default_skills_root)
                result = service.query(query=query, skills_root=skills_root, limit=int(payload.get("limit", limit)))
                print(json.dumps(result, indent=2), flush=True)
                continue
            raise ValueError(f"Unsupported action: {action}")
        except Exception as exc:  # deliberately surfaced to the caller
            print(json.dumps({"error": str(exc)}), flush=True)
