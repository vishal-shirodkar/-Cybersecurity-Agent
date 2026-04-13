"""
agent.py — Main CLI entry point for the Cybersecurity AI Agent.

Workflow per query:
  1. Load ANTHROPIC_API_KEY from .env
  2. Accept user query via Click CLI (or interactive REPL mode)
  3. Route to best matching skill via SkillRouter (ChromaDB RAG)
  4. Load full skill context from disk via SkillLoader
  5. Build a grounded system prompt from skill data
  6. Stream Claude's response back using the Anthropic SDK
  7. Optionally save a markdown report via ReportGenerator

Usage:
    python agent.py ask "How do I investigate a ransomware infection?"
    python agent.py ask "detect lateral movement" --top-k 5 --no-report
    python agent.py chat                         # interactive REPL mode
    python agent.py list-skills                  # list all indexed skills
    python agent.py build-index                  # force-rebuild ChromaDB index
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.text import Text

# Load .env before importing local modules that may use env vars
load_dotenv()

from skill_loader import SkillLoader, Skill
from skill_router import SkillRouter, RouterOutput, RouteResult

console = Console()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_REPO_PATH = "./Anthropic-Cybersecurity-Skills"
DEFAULT_CHROMA_PATH = "./chroma_db"
DEFAULT_TOP_K = 3
MAX_WORKFLOW_CHARS = 4000    # truncate very long workflow sections in the prompt
MAX_STANDARDS_CHARS = 2000   # truncate standards reference in the prompt


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------

def _build_system_prompt(skill: Skill) -> str:
    """
    Construct a grounded system prompt that injects the full skill context
    so Claude acts as a specialist for that specific security domain.
    """

    # Build the framework references block (only include non-empty lists)
    framework_lines = []
    if skill.nist_csf:
        framework_lines.append(f"- NIST CSF: {', '.join(skill.nist_csf)}")
    if skill.atlas_techniques:
        framework_lines.append(f"- MITRE ATT&CK/ATLAS: {', '.join(skill.atlas_techniques)}")
    if skill.d3fend_techniques:
        framework_lines.append(f"- MITRE D3FEND: {', '.join(skill.d3fend_techniques)}")
    if skill.nist_ai_rmf:
        framework_lines.append(f"- NIST AI RMF: {', '.join(skill.nist_ai_rmf)}")
    frameworks_block = "\n".join(framework_lines) if framework_lines else "Not specified"

    # Truncate very long sections so we don't burn the full context window
    workflow_snippet = (
        skill.workflow_body[:MAX_WORKFLOW_CHARS] + "\n…[truncated]"
        if len(skill.workflow_body) > MAX_WORKFLOW_CHARS
        else skill.workflow_body
    )
    standards_snippet = (
        skill.standards_md[:MAX_STANDARDS_CHARS] + "\n…[truncated]"
        if len(skill.standards_md) > MAX_STANDARDS_CHARS
        else skill.standards_md
    )

    return f"""You are a senior cybersecurity specialist with deep expertise in {skill.domain}.
You are answering a question grounded in the following security skill.

## Active Skill: {skill.name}
**Domain:** {skill.domain}  
**Subdomain:** {skill.subdomain or "—"}  
**Tags:** {", ".join(skill.tags) if skill.tags else "—"}  
**Version:** {skill.version or "—"}

## Description
{skill.description}

## When to Use
{skill.when_to_use or "Not specified"}

## Prerequisites
{skill.prerequisites or "Not specified"}

## Workflow
{workflow_snippet or "Not specified"}

## Verification Steps
{skill.verification or "Not specified"}

## Framework References
{frameworks_block}

{f"## Standards Reference{chr(10)}{standards_snippet}" if standards_snippet else ""}

---

**Instructions for your response:**
- Provide actionable, technically precise guidance grounded in the skill above.
- Reference specific steps from the workflow where relevant.
- Use numbered lists for multi-step procedures.
- Call out prerequisites or dependencies the user must satisfy first.
- If a report template is available, structure your answer to match it.
- Be direct and concise. Avoid generic security platitudes.
- If the question is outside this skill's scope, say so and recommend the right domain.
"""


# ---------------------------------------------------------------------------
# Core agent function
# ---------------------------------------------------------------------------

def _run_agent(
    query: str,
    api_key: str,
    router: SkillRouter,
    loader: SkillLoader,
    top_k: int = DEFAULT_TOP_K,
    save_report: bool = True,
    model: str = DEFAULT_MODEL,
) -> str:
    """
    Full agent pipeline: route → load skill → build prompt → stream Claude.

    Returns the complete assistant response as a string.
    """
    import anthropic

    # ── 1. Route the query ──────────────────────────────────────────────────
    console.print(Rule("[bold cyan]Routing Query[/bold cyan]"))
    output: RouterOutput = router.route(query)
    router.display_results(output)

    if not output.top_skills:
        console.print("[red]✗ No skills matched. Try a different query.[/red]")
        return ""

    best: RouteResult = output.best

    # Warn but continue if the match is weak
    if best.is_weak_match():
        console.print(
            f"[yellow]⚠  Weak match ({best.relevance_pct}% relevance). "
            "Proceeding anyway — results may be generic.[/yellow]\n"
        )

    # ── 2. Load the full skill from disk ────────────────────────────────────
    console.print(f"[dim]Loading skill: [bold]{best.skill_name}[/bold]…[/dim]")
    try:
        skill: Skill = loader.load(best.skill_name)
    except FileNotFoundError as exc:
        console.print(f"[red]✗ Could not load skill '{best.skill_name}': {exc}[/red]")
        console.print(
            "[yellow]Hint: Make sure you've cloned the skills repo to "
            f"{loader.repo_root}[/yellow]"
        )
        return ""

    # Show a brief skill summary panel
    console.print(
        Panel(
            Text.from_markup(skill.summary()),
            title="[bold green]✓ Skill Loaded[/bold green]",
            border_style="green",
            expand=False,
        )
    )

    # ── 3. Build the system prompt ──────────────────────────────────────────
    system_prompt = _build_system_prompt(skill)

    # ── 4. Stream Claude's response ─────────────────────────────────────────
    console.print(Rule(f"[bold cyan]Claude ({model})[/bold cyan]"))
    console.print()

    client = anthropic.Anthropic(api_key=api_key)
    full_response_chunks: list[str] = []

    try:
        with client.messages.stream(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": query}],
        ) as stream:
            for text_chunk in stream.text_stream:
                console.print(text_chunk, end="", markup=False, highlight=False)
                full_response_chunks.append(text_chunk)

    except anthropic.AuthenticationError:
        console.print("\n[red]✗ Authentication failed. Check your ANTHROPIC_API_KEY.[/red]")
        return ""
    except anthropic.RateLimitError:
        console.print("\n[red]✗ Rate limit hit. Wait a moment and try again.[/red]")
        return ""
    except anthropic.APIConnectionError as exc:
        console.print(f"\n[red]✗ Connection error: {exc}[/red]")
        return ""

    full_response = "".join(full_response_chunks)
    console.print("\n")   # newline after streamed output

    # ── 5. Optionally save a report ─────────────────────────────────────────
    if save_report and full_response:
        try:
            from report_generator import ReportGenerator
            gen = ReportGenerator()
            report_path = gen.save(
                query=query,
                response=full_response,
                skill=skill,
                route_result=best,
            )
            console.print(
                f"[dim]📄 Report saved → [bold]{report_path}[/bold][/dim]"
            )
        except ImportError:
            pass   # report_generator.py not yet created — silently skip
        except Exception as exc:
            console.print(f"[yellow]⚠  Could not save report: {exc}[/yellow]")

    return full_response


# ---------------------------------------------------------------------------
# Shared Click context helpers
# ---------------------------------------------------------------------------

def _get_api_key(ctx_obj: dict) -> str:
    """Retrieve the API key from context or env, exit with a helpful message if missing."""
    api_key = ctx_obj.get("api_key") or os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        console.print(
            "[red]✗ ANTHROPIC_API_KEY is not set.[/red]\n"
            "  Set it in a [bold].env[/bold] file:\n"
            "    [cyan]ANTHROPIC_API_KEY=sk-ant-…[/cyan]\n"
            "  Or export it in your shell:\n"
            "    [cyan]export ANTHROPIC_API_KEY=sk-ant-…[/cyan]"
        )
        sys.exit(1)
    return api_key


def _make_router_and_loader(ctx_obj: dict) -> tuple[SkillRouter, SkillLoader]:
    repo = ctx_obj.get("repo_path", DEFAULT_REPO_PATH)
    chroma = ctx_obj.get("chroma_path", DEFAULT_CHROMA_PATH)
    router = SkillRouter(
        skills_repo_path=repo,
        chroma_db_path=chroma,
        top_k=ctx_obj.get("top_k", DEFAULT_TOP_K),
    )
    loader = SkillLoader(repo_root=repo)
    return router, loader


# ---------------------------------------------------------------------------
# Click CLI
# ---------------------------------------------------------------------------

@click.group()
@click.option(
    "--repo",
    "repo_path",
    default=DEFAULT_REPO_PATH,
    show_default=True,
    envvar="SKILLS_REPO_PATH",
    help="Path to the cloned Anthropic-Cybersecurity-Skills repository.",
)
@click.option(
    "--chroma-db",
    "chroma_path",
    default=DEFAULT_CHROMA_PATH,
    show_default=True,
    help="Path to the ChromaDB persistence directory.",
)
@click.option(
    "--model",
    default=DEFAULT_MODEL,
    show_default=True,
    help="Anthropic model to use for inference.",
)
@click.option(
    "--top-k",
    default=DEFAULT_TOP_K,
    show_default=True,
    type=int,
    help="Number of candidate skills to retrieve from the index.",
)
@click.pass_context
def cli(ctx: click.Context, repo_path: str, chroma_path: str, model: str, top_k: int) -> None:
    """🔐 Cybersecurity AI Agent — powered by Claude + ChromaDB skill retrieval."""
    ctx.ensure_object(dict)
    ctx.obj["repo_path"] = repo_path
    ctx.obj["chroma_path"] = chroma_path
    ctx.obj["model"] = model
    ctx.obj["top_k"] = top_k
    ctx.obj["api_key"] = os.getenv("ANTHROPIC_API_KEY", "")


# ── ask ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("query", nargs=-1, required=True)
@click.option("--no-report", is_flag=True, default=False, help="Skip saving a markdown report.")
@click.pass_context
def ask(ctx: click.Context, query: tuple[str, ...], no_report: bool) -> None:
    """Ask a single security question.

    Example:\n
        python agent.py ask "How do I investigate a ransomware infection?"\n
        python agent.py ask detect lateral movement --no-report
    """
    api_key = _get_api_key(ctx.obj)
    router, loader = _make_router_and_loader(ctx.obj)
    query_str = " ".join(query)

    console.print(Rule("[bold]Cybersecurity AI Agent[/bold]"))
    console.print(f"[bold]Query:[/bold] {query_str}\n")

    _run_agent(
        query=query_str,
        api_key=api_key,
        router=router,
        loader=loader,
        top_k=ctx.obj["top_k"],
        save_report=not no_report,
        model=ctx.obj["model"],
    )


# ── chat ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--no-report", is_flag=True, default=False, help="Skip saving markdown reports.")
@click.pass_context
def chat(ctx: click.Context, no_report: bool) -> None:
    """Start an interactive REPL session (type 'exit' or Ctrl-C to quit).

    Example:\n
        python agent.py chat
    """
    api_key = _get_api_key(ctx.obj)
    router, loader = _make_router_and_loader(ctx.obj)

    console.print(
        Panel(
            "[bold cyan]Cybersecurity AI Agent[/bold cyan] — Interactive Mode\n"
            "[dim]Type your security question and press Enter.\n"
            "Type [bold]exit[/bold] or press Ctrl-C to quit.[/dim]",
            border_style="cyan",
        )
    )

    # Pre-warm the index so the first query is fast
    try:
        router._ensure_index()
    except Exception as exc:
        console.print(f"[red]✗ Failed to load skill index: {exc}[/red]")
        sys.exit(1)

    while True:
        try:
            query = Prompt.ask("\n[bold cyan]You[/bold cyan]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        if not query:
            continue
        if query.lower() in {"exit", "quit", "q"}:
            console.print("[dim]Goodbye.[/dim]")
            break

        _run_agent(
            query=query,
            api_key=api_key,
            router=router,
            loader=loader,
            top_k=ctx.obj["top_k"],
            save_report=not no_report,
            model=ctx.obj["model"],
        )


# ── build-index ───────────────────────────────────────────────────────────────

@cli.command("build-index")
@click.option("--force", is_flag=True, default=False, help="Rebuild even if index already exists.")
@click.pass_context
def build_index(ctx: click.Context, force: bool) -> None:
    """Build (or rebuild) the ChromaDB skill index.

    Example:\n
        python agent.py build-index\n
        python agent.py build-index --force
    """
    repo_path = ctx.obj["repo_path"]
    chroma_path = ctx.obj["chroma_path"]

    console.print(Rule("[bold cyan]Building Skill Index[/bold cyan]"))
    console.print(f"[dim]Repo   : {repo_path}[/dim]")
    console.print(f"[dim]ChromaDB: {chroma_path}[/dim]\n")

    index = __import__("skill_index").SkillIndex(
        repo_root=repo_path,
        persist_dir=chroma_path,
    )

    if index.is_built() and not force:
        console.print(
            "[yellow]Index already exists. Use --force to rebuild.[/yellow]"
        )
        return

    try:
        stats = index.build(force_rebuild=force)
        if isinstance(stats, dict):
            console.print(
                f"\n[bold green]✓ Index ready:[/bold green] "
                f"{stats.get('indexed', '?')} skills, "
                f"{stats.get('failed', 0)} failed, "
                f"{stats.get('elapsed_seconds', 0):.1f}s"
            )
        else:
            console.print("\n[bold green]✓ Index built successfully.[/bold green]")
    except Exception as exc:
        console.print(f"[red]✗ Build failed: {exc}[/red]")
        sys.exit(1)


# ── list-skills ───────────────────────────────────────────────────────────────

@cli.command("list-skills")
@click.option("--domain", default=None, help="Filter by domain name (partial match).")
@click.pass_context
def list_skills(ctx: click.Context, domain: Optional[str]) -> None:
    """List all available skills in the ChromaDB index.

    Example:\n
        python agent.py list-skills\n
        python agent.py list-skills --domain malware
    """
    from skill_index import SkillIndex
    from rich.table import Table

    index = SkillIndex(
        repo_root=ctx.obj["repo_path"],
        persist_dir=ctx.obj["chroma_path"],
    )

    if not index.is_built():
        console.print(
            "[yellow]Index not built yet. Run:[/yellow] "
            "[bold cyan]python agent.py build-index[/bold cyan]"
        )
        return

    try:
        index._open_collection() if hasattr(index, '_open_collection') else None
        col = index._collection
        if col is None:
            # Force open by doing a dummy query
            col = index._client.get_collection(
                name="cybersecurity_skills",
                embedding_function=index._embed_fn,
            )
        results = col.get(include=["metadatas"])
        metadatas = results.get("metadatas", []) or []
    except Exception as exc:
        console.print(f"[red]✗ Could not read index: {exc}[/red]")
        return

    # Apply optional domain filter
    if domain:
        metadatas = [
            m for m in metadatas
            if domain.lower() in (m.get("domain", "") or "").lower()
        ]

    table = Table(
        title=f"Skills{f' (domain: {domain})' if domain else ''} — {len(metadatas)} total",
        header_style="bold cyan",
        border_style="dim",
        show_lines=False,
    )
    table.add_column("Skill Name", style="bold white", min_width=35)
    table.add_column("Domain", style="cyan", min_width=20)
    table.add_column("Description", style="dim", overflow="fold", min_width=50)

    for meta in sorted(metadatas, key=lambda m: (m.get("domain", ""), m.get("name", ""))):
        table.add_row(
            meta.get("name", "—"),
            meta.get("domain", "—"),
            (meta.get("description", "") or "")[:100],
        )

    console.print(table)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
