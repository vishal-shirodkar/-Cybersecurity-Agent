"""
skill_router.py — Routes a user query to the best matching cybersecurity skills.

Uses the ChromaDB RAG index (skill_index.py) to perform semantic search over all
ingested skills. Returns ranked matches with display-friendly metadata so agent.py
can load the full skill context and build a grounded system prompt.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.text import Text

from skill_index import SkillIndex, SkillMatch

console = Console()


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class RouteResult:
    """A single routed skill with display-ready metadata."""

    skill_name: str          # Filesystem-safe name (matches directory name)
    domain: str              # e.g. "malware-analysis"
    description: str         # One-line description from index metadata
    score: float             # Cosine distance: 0.0 = perfect match, 1.0 = unrelated
    relevance_pct: int       # Human-readable relevance: (1 - score) * 100

    def is_strong_match(self) -> bool:
        """Returns True if the match is highly relevant (relevance >= 60%)."""
        return self.relevance_pct >= 60

    def is_weak_match(self) -> bool:
        """Returns True if the match is borderline (relevance < 40%)."""
        return self.relevance_pct < 40


@dataclass
class RouterOutput:
    """Full output from the router for a single user query."""

    query: str                       # Original user query
    top_skills: list[RouteResult]    # Ranked list, best first
    had_strong_match: bool           # True if at least one skill scored >= 60%

    @property
    def best(self) -> Optional[RouteResult]:
        """Returns the top-ranked skill, or None if no skills matched."""
        return self.top_skills[0] if self.top_skills else None


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

class SkillRouter:
    """
    Routes a natural-language user query to the most relevant cybersecurity skills.

    Usage:
        router = SkillRouter(skills_repo_path="./Anthropic-Cybersecurity-Skills")
        output = router.route("How do I investigate a ransomware infection?")
        print(output.best.skill_name)
    """

    def __init__(
        self,
        skills_repo_path: str = "./Anthropic-Cybersecurity-Skills",
        chroma_db_path: str = "./chroma_db",
        top_k: int = 3,
    ) -> None:
        self.skills_repo_path = skills_repo_path
        self.chroma_db_path = chroma_db_path
        self.top_k = top_k
        self._index: Optional[SkillIndex] = None

    # ------------------------------------------------------------------
    # Lazy index initialisation
    # ------------------------------------------------------------------

    def _ensure_index(self) -> SkillIndex:
        """Loads or builds the ChromaDB index on first use."""
        if self._index is not None:
            return self._index

        index = SkillIndex(
            repo_root=self.skills_repo_path,
            persist_dir=self.chroma_db_path,
        )

        if not index.is_built():
            console.print(
                "[yellow]⚙  Index not found — building ChromaDB index "
                f"from [bold]{self.skills_repo_path}[/bold] (one-time setup)…[/yellow]"
            )
            try:
                stats = index.build()
                if isinstance(stats, dict):
                    console.print(
                        f"[green]✓  Index built:[/green] "
                        f"{stats.get('indexed', '?')} skills indexed, "
                        f"{stats.get('failed', 0)} failed, "
                        f"took {stats.get('elapsed_seconds', 0):.1f}s"
                    )
                else:
                    console.print("[green]✓  Index built successfully.[/green]")
            except Exception as exc:
                console.print(f"[red]✗  Failed to build index: {exc}[/red]")
                raise
        else:
            console.print("[dim]✓  Loaded existing ChromaDB index[/dim]")

        self._index = index
        return index

    # ------------------------------------------------------------------
    # Core routing logic
    # ------------------------------------------------------------------

    def route(self, query: str) -> RouterOutput:
        """
        Route a user query to the top-k most relevant skills.

        Args:
            query: Natural-language security question or task description.

        Returns:
            RouterOutput with ranked RouteResult objects.
        """
        if not query or not query.strip():
            return RouterOutput(query=query, top_skills=[], had_strong_match=False)

        index = self._ensure_index()

        try:
            matches: list[SkillMatch] = index.query_skills(
                user_input=query,
                top_k=self.top_k,
            )
        except Exception as exc:
            console.print(f"[red]✗  Skill index query failed: {exc}[/red]")
            raise

        results = [_match_to_route_result(m) for m in matches]
        had_strong = any(r.is_strong_match() for r in results)

        return RouterOutput(query=query, top_skills=results, had_strong_match=had_strong)

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    def display_results(self, output: RouterOutput) -> None:
        """Print a formatted table of routing results to the terminal."""
        if not output.top_skills:
            console.print("[yellow]No skills matched the query.[/yellow]")
            return

        table = Table(
            title=f"🔍 Matched Skills for: [italic]{output.query[:80]}[/italic]",
            show_header=True,
            header_style="bold cyan",
            border_style="dim",
            expand=False,
        )
        table.add_column("#", style="dim", width=3, justify="right")
        table.add_column("Skill", style="bold white", min_width=30)
        table.add_column("Domain", style="cyan", min_width=18)
        table.add_column("Relevance", justify="center", min_width=10)
        table.add_column("Description", style="dim", min_width=40, overflow="fold")

        for rank, result in enumerate(output.top_skills, start=1):
            relevance_text = _relevance_badge(result.relevance_pct)
            table.add_row(
                str(rank),
                result.skill_name,
                result.domain,
                relevance_text,
                result.description[:120] if result.description else "—",
            )

        console.print()
        console.print(table)

        if not output.had_strong_match:
            console.print(
                "[yellow]⚠  No strong match found (relevance < 60%). "
                "Try rephrasing your query or be more specific.[/yellow]"
            )
        console.print()


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _match_to_route_result(match: SkillMatch) -> RouteResult:
    """Convert a raw SkillMatch into a display-ready RouteResult."""
    # Cosine distance: 0 = identical, 2 = opposite. Typical range in practice: 0–1.
    # Clamp to [0, 1] to calculate a sane percentage.
    clamped_score = min(max(match.score, 0.0), 1.0)
    relevance_pct = int((1.0 - clamped_score) * 100)

    return RouteResult(
        skill_name=match.skill_name,
        domain=match.domain,
        description=match.description,
        score=match.score,
        relevance_pct=relevance_pct,
    )


def _relevance_badge(pct: int) -> Text:
    """Return a coloured Rich Text badge for a relevance percentage."""
    bar_filled = pct // 10          # 0–10 blocks
    bar = "█" * bar_filled + "░" * (10 - bar_filled)

    if pct >= 70:
        colour = "green"
    elif pct >= 45:
        colour = "yellow"
    else:
        colour = "red"

    t = Text()
    t.append(f"{pct:3d}% ", style=colour)
    t.append(bar, style=f"dim {colour}")
    return t


# ---------------------------------------------------------------------------
# CLI smoke-test  (python skill_router.py <query>)
# ---------------------------------------------------------------------------

def _cli_demo() -> None:
    """Quick smoke-test: run from the terminal with a query as the argument."""
    if len(sys.argv) < 2:
        console.print(
            "[bold]Usage:[/bold]  python skill_router.py [cyan]<query>[/cyan] "
            "[dim]\\[--repo PATH][/dim]"
        )
        console.print(
            '  e.g.  python skill_router.py "How do I investigate a ransomware infection?"'
        )
        sys.exit(1)

    # Allow optional --repo override for the skills repo path
    repo_path = "./Anthropic-Cybersecurity-Skills"
    args = sys.argv[1:]
    if "--repo" in args:
        idx = args.index("--repo")
        repo_path = args[idx + 1]
        args = args[:idx] + args[idx + 2 :]

    query = " ".join(args)

    console.rule("[bold cyan]Cybersecurity Skill Router[/bold cyan]")
    console.print(f"[bold]Query:[/bold] {query}")
    console.print(f"[dim]Skills repo:[/dim] {repo_path}")
    console.print()

    router = SkillRouter(skills_repo_path=repo_path)

    try:
        output = router.route(query)
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        sys.exit(1)

    router.display_results(output)

    if output.best:
        console.print(
            f"[bold green]→ Best match:[/bold green] [bold]{output.best.skill_name}[/bold] "
            f"({output.best.relevance_pct}% relevant)"
        )


if __name__ == "__main__":
    _cli_demo()
