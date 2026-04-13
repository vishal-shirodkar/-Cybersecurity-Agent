from __future__ import annotations


def classify_risk(text: str) -> str:
    lowered = text.lower()
    high_risk_terms = ("exploit", "ransomware", "payload", "credential dump", "destructive")
    if any(term in lowered for term in high_risk_terms):
        return "high"
    medium_risk_terms = ("scan", "enumerate", "dump", "pentest")
    if any(term in lowered for term in medium_risk_terms):
        return "medium"
    return "low"
