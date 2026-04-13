from __future__ import annotations

from urllib.request import urlopen


def fetch_text(url: str, timeout: int = 30) -> str:
    with urlopen(url, timeout=timeout) as response:  # nosec B310 - caller chooses trusted URLs
        return response.read().decode("utf-8")
