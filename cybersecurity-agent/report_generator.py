"""
report_generator.py — Formats Claude's response into a structured markdown report.

Each report is saved to:
    ./reports/{YYYYMMDD_HHMMSS}_{skill_name}.md

Report structure:
    1. Header  — title, metadata, timestamp, skill identity
    2. Query   — the original user question
    3. Skill Context — key fields from the matched skill (when_to_use, prerequisites, tags)
    4. Analysis — Claude's full streamed response (the main content)
    5. Skill Template — assets/template.md if the skill has one (blank checklist)
    6. Framework References — MITRE / NIST mappings from the skill frontmatter
    7. Footer  — generation metadata

Usage (called automatically by agent.py):
    gen = ReportGenerator(output_dir="./reports")
    path = gen.save(query, response, skill, route_result)
    print(f"Report saved to {path}")

Standalone usage:
    python report_generator.py          # runs a self-contained demo
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console

from skill_loader import Skill
from skill_router import RouteResult

console = Console()

DEFAULT_OUTPUT_DIR = "./reports"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ReportMetadata:
    """Captures everything needed to reproduce or audit a report."""
    query: str
    skill_name: str
    domain: str
    relevance_pct: int
    model: str
    generated_at: str           # ISO-8601 UTC timestamp
    report_path: str            # absolute path where the file was saved


# ---------------------------------------------------------------------------
# ReportGenerator
# ---------------------------------------------------------------------------

class ReportGenerator:
    """
    Formats and persists a markdown analysis report for each agent interaction.

    Args:
        output_dir: Directory where reports are saved. Created if it doesn't exist.
        model: Model name to embed in the report footer (informational only).
    """

    def __init__(
        self,
        output_dir: str = DEFAULT_OUTPUT_DIR,
        model: str = "claude-sonnet-4-20250514",
    ) -> None:
        self.output_dir = Path(output_dir)
        self.model = model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(
        self,
        query: str,
        response: str,
        skill: Skill,
        route_result: RouteResult,
    ) -> str:
        """
        Build and persist a report.

        Args:
            query:        Original user question.
            response:     Full text of Claude's streamed response.
            skill:        Fully loaded Skill object (provides context + template).
            route_result: RouteResult from the router (provides relevance score).

        Returns:
            Absolute path to the saved report file as a string.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc)
        filename = _make_filename(timestamp, skill.name)
        report_path = self.output_dir / filename

        content = self._render(
            query=query,
            response=response,
            skill=skill,
            route_result=route_result,
            timestamp=timestamp,
        )

        report_path.write_text(content, encoding="utf-8")
        return str(report_path.resolve())

    def render_preview(
        self,
        query: str,
        response: str,
        skill: Skill,
        route_result: RouteResult,
    ) -> str:
        """Return the rendered markdown string without saving (useful for testing)."""
        return self._render(
            query=query,
            response=response,
            skill=skill,
            route_result=route_result,
            timestamp=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(
        self,
        query: str,
        response: str,
        skill: Skill,
        route_result: RouteResult,
        timestamp: datetime,
    ) -> str:
        """Assemble all report sections into a single markdown string."""
        sections: list[str] = []

        sections.append(_section_header(query, skill, route_result, timestamp))
        sections.append(_section_query(query))
        sections.append(_section_skill_context(skill))
        sections.append(_section_analysis(response))

        if skill.template_md.strip():
            sections.append(_section_template(skill.template_md))

        if skill.workflows_md.strip():
            sections.append(_section_reference("Detailed Workflow Reference", skill.workflows_md))

        if skill.standards_md.strip():
            sections.append(_section_reference("Framework & Standards Reference", skill.standards_md))

        framework_block = _build_framework_block(skill)
        if framework_block:
            sections.append(_section_frameworks(framework_block))

        sections.append(_section_footer(self.model, timestamp, skill, route_result))

        return "\n\n---\n\n".join(sections) + "\n"

    # ------------------------------------------------------------------
    # Listing helpers
    # ------------------------------------------------------------------

    def list_reports(self) -> list[Path]:
        """Return all report files sorted newest-first."""
        if not self.output_dir.exists():
            return []
        return sorted(
            self.output_dir.glob("*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )


# ---------------------------------------------------------------------------
# Section builders  (each returns a markdown string)
# ---------------------------------------------------------------------------

def _section_header(
    query: str,
    skill: Skill,
    route: RouteResult,
    ts: datetime,
) -> str:
    title = _query_to_title(query)
    relevance_bar = _ascii_bar(route.relevance_pct)
    tags_str = ", ".join(f"`{t}`" for t in skill.tags[:8]) if skill.tags else "—"

    return textwrap.dedent(f"""\
        # {title}

        | Field | Value |
        |---|---|
        | **Skill** | `{skill.name}` |
        | **Domain** | {skill.domain} |
        | **Subdomain** | {skill.subdomain or "—"} |
        | **Relevance** | {route.relevance_pct}% {relevance_bar} |
        | **Generated** | {ts.strftime("%Y-%m-%d %H:%M:%S UTC")} |
        | **Version** | {skill.version or "—"} |
        | **Author** | {skill.author or "—"} |
        | **Tags** | {tags_str} |
    """)


def _section_query(query: str) -> str:
    return textwrap.dedent(f"""\
        ## 🔍 Query

        > {query}
    """)


def _section_skill_context(skill: Skill) -> str:
    parts: list[str] = ["## 📘 Skill Context\n"]

    if skill.description:
        parts.append(f"**Description:** {skill.description}\n")

    if skill.when_to_use.strip():
        parts.append(f"### When to Use\n\n{skill.when_to_use.strip()}")

    if skill.prerequisites.strip():
        parts.append(f"### Prerequisites\n\n{skill.prerequisites.strip()}")

    return "\n\n".join(parts)


def _section_analysis(response: str) -> str:
    return f"## 🤖 AI Analysis\n\n{response.strip()}"


def _section_template(template_md: str) -> str:
    return (
        "## 📋 Skill Template / Checklist\n\n"
        "> *Use this template to document your findings.*\n\n"
        + template_md.strip()
    )


def _section_reference(title: str, content: str) -> str:
    # Truncate very long reference sections to keep report readable
    MAX_CHARS = 3000
    truncated = content.strip()
    if len(truncated) > MAX_CHARS:
        truncated = truncated[:MAX_CHARS] + "\n\n…*(truncated — see full file in skill repo)*"
    return f"## 📚 {title}\n\n{truncated}"


def _section_frameworks(framework_block: str) -> str:
    return f"## 🗂️ Framework Mappings\n\n{framework_block}"


def _section_footer(model: str, ts: datetime, skill: Skill, route: RouteResult) -> str:
    return textwrap.dedent(f"""\
        ## ℹ️ Report Metadata

        | Field | Value |
        |---|---|
        | **Model** | `{model}` |
        | **Skill file** | `{skill.skill_dir}` |
        | **Cosine distance** | {route.score:.4f} |
        | **Relevance** | {route.relevance_pct}% |
        | **Generated** | {ts.isoformat()} |

        *Generated by the Cybersecurity AI Agent — skill sourced from the
        [Anthropic-Cybersecurity-Skills](https://github.com/mukul975/Anthropic-Cybersecurity-Skills)
        repository (Apache-2.0).*
    """)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _make_filename(ts: datetime, skill_name: str) -> str:
    """Generate a sortable, filesystem-safe filename."""
    timestamp_str = ts.strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r"[^\w\-]", "_", skill_name)[:60]
    return f"{timestamp_str}_{safe_name}.md"


def _query_to_title(query: str) -> str:
    """Convert a raw query string to a title-case heading (max 80 chars)."""
    title = query.strip().rstrip("?").strip()
    title = title[:77] + "…" if len(title) > 80 else title
    # Capitalise first letter only (don't title-case — preserves acronyms)
    return title[0].upper() + title[1:] if title else "Security Analysis Report"


def _ascii_bar(pct: int) -> str:
    """Return an ASCII progress bar for relevance percentage."""
    filled = pct // 10
    return "█" * filled + "░" * (10 - filled)


def _build_framework_block(skill: Skill) -> str:
    """Build a markdown list of all non-empty framework mappings."""
    lines: list[str] = []
    if skill.nist_csf:
        lines.append(f"- **NIST CSF:** {', '.join(skill.nist_csf)}")
    if skill.atlas_techniques:
        lines.append(f"- **MITRE ATT&CK / ATLAS:** {', '.join(skill.atlas_techniques)}")
    if skill.d3fend_techniques:
        lines.append(f"- **MITRE D3FEND:** {', '.join(skill.d3fend_techniques)}")
    if skill.nist_ai_rmf:
        lines.append(f"- **NIST AI RMF:** {', '.join(skill.nist_ai_rmf)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Standalone demo  (python report_generator.py)
# ---------------------------------------------------------------------------

def _demo() -> None:
    """Self-contained demo that generates a sample report without calling Claude."""
    from skill_router import RouteResult

    console.print("[bold cyan]ReportGenerator demo[/bold cyan]")

    # Minimal fake skill for demo
    skill = Skill(
        name="demo-ransomware-triage",
        description="Triage and initial response to a ransomware incident.",
        domain="incident-response",
        subdomain="ransomware",
        tags=["ransomware", "triage", "forensics", "windows"],
        version="1.0",
        author="demo",
        when_to_use="Use when a host is suspected of ransomware infection.",
        prerequisites="Admin access to the host; EDR telemetry available.",
        workflow_body=(
            "1. Isolate the host from the network immediately.\n"
            "2. Capture volatile memory with WinPMEM.\n"
            "3. Preserve event logs (Security, System, Application).\n"
            "4. Identify the ransomware family using YARA rules.\n"
            "5. Check for living-off-the-land binaries (LOLBins) in process tree.\n"
            "6. Document encrypted file extensions and ransom note location.\n"
        ),
        verification="Confirm isolation; verify memory image integrity (SHA-256).",
        nist_csf=["RS.RP-1", "RS.AN-1"],
        atlas_techniques=["T1486"],
        template_md=(
            "## Incident Response Checklist\n\n"
            "- [ ] Host isolated\n"
            "- [ ] Memory captured\n"
            "- [ ] Logs preserved\n"
            "- [ ] Ransomware family identified\n"
            "- [ ] Stakeholders notified\n"
        ),
        skill_dir="./demo",
    )

    route = RouteResult(
        skill_name=skill.name,
        domain=skill.domain,
        description=skill.description,
        score=0.18,
        relevance_pct=82,
    )

    fake_response = textwrap.dedent("""\
        ## Ransomware Triage — Initial Response

        Based on the **demo-ransomware-triage** skill, here are the immediate steps:

        1. **Isolate the host** — disconnect from network (pull cable or disable NIC via EDR).
        2. **Capture volatile memory** — use `winpmem_mini_x64.exe` before any reboot.
        3. **Preserve logs** — copy `C:\\Windows\\System32\\winevt\\Logs\\` off-host.
        4. **Identify the strain** — run YARA rules from `https://github.com/Neo23x0/signature-base`.
        5. **Check for LOLBins** — look for `wmic.exe`, `powershell.exe`, `certutil.exe` in parent chain.

        > ⚠️ Do **not** reboot the host before capturing memory — volatile artefacts will be lost.
    """)

    gen = ReportGenerator(output_dir="./reports/demo")
    path = gen.save(
        query="How do I triage a ransomware-infected Windows host?",
        response=fake_response,
        skill=skill,
        route_result=route,
    )

    console.print(f"[green]✓ Report saved →[/green] [bold]{path}[/bold]")

    # Also print a truncated preview
    preview = Path(path).read_text(encoding="utf-8")
    console.print("\n[dim]── Preview (first 60 lines) ──[/dim]")
    for line in preview.splitlines()[:60]:
        console.print(line, markup=False, highlight=False)


if __name__ == "__main__":
    _demo()
