from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntentClassification:
    intent: str
    confidence: float
    rationale: str


def classify_intent(query: str) -> IntentClassification:
    lowered = query.lower()
    if any(term in lowered for term in ("memory", "volatility", "dump", "forensics")):
        return IntentClassification("digital-forensics", 0.9, "Detected memory/forensics terminology")
    if any(term in lowered for term in ("hunt", "ioc", "beacon", "alert")):
        return IntentClassification("threat-hunting", 0.8, "Detected threat hunting terminology")
    if any(term in lowered for term in ("phish", "xss", "sqli", "api")):
        return IntentClassification("application-security", 0.7, "Detected application security terminology")
    return IntentClassification("general-cybersecurity", 0.5, "Fell back to generic cybersecurity intent")
