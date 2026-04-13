from __future__ import annotations

import re

SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)([^\s]+)"),
    re.compile(r"(?i)(token\s*[=:]\s*)([^\s]+)"),
)


def redact_sensitive_content(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(r"\1[REDACTED]", redacted)
    return redacted
