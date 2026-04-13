"""
skill_loader.py
---------------
Loads a single cybersecurity skill from the Anthropic-Cybersecurity-Skills
repository on disk.

Each skill lives in:
    Anthropic-Cybersecurity-Skills/skills/<skill-name>/
        SKILL.md                  ← required (YAML frontmatter + Markdown body)
        references/standards.md   ← optional framework mappings
        references/workflows.md   ← optional deep procedure reference
        assets/template.md        ← optional report/checklist template

Usage:
    loader = SkillLoader("./Anthropic-Cybersecurity-Skills")
    skill  = loader.load("performing-memory-forensics-with-volatility3")
    print(skill.name, skill.domain, skill.workflow_body)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Skill:
    """Fully hydrated skill loaded from disk."""

    # --- Core identity (from YAML frontmatter) ---
    name: str
    description: str
    domain: str
    subdomain: str | None = None
    tags: list[str] = field(default_factory=list)
    version: str | None = None
    author: str | None = None
    license: str | None = None

    # --- Framework mappings (from frontmatter, present in some skills) ---
    nist_csf: list[str] = field(default_factory=list)
    atlas_techniques: list[str] = field(default_factory=list)
    d3fend_techniques: list[str] = field(default_factory=list)
    nist_ai_rmf: list[str] = field(default_factory=list)

    # --- Structured sections parsed from the SKILL.md Markdown body ---
    when_to_use: str = ""
    prerequisites: str = ""
    workflow_body: str = ""       # full workflow section
    verification: str = ""

    # --- Adjacent reference files loaded when present ---
    standards_md: str = ""        # references/standards.md
    workflows_md: str = ""        # references/workflows.md
    template_md: str = ""         # assets/template.md

    # --- Filesystem metadata ---
    skill_dir: str = ""           # absolute path to the skill directory

    def summary(self) -> str:
        """One-line summary for display in the terminal."""
        tags_str = ", ".join(self.tags[:5]) if self.tags else "—"
        return (
            f"[bold]{self.name}[/bold]\n"
            f"  Domain    : {self.domain} / {self.subdomain or '—'}\n"
            f"  Tags      : {tags_str}\n"
            f"  Author    : {self.author or '—'}\n"
            f"  Version   : {self.version or '—'}"
        )


# ---------------------------------------------------------------------------
# Parser helpers
# ---------------------------------------------------------------------------

def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """
    Split YAML frontmatter from Markdown body.

    Returns (metadata_dict, markdown_body).
    Raises ValueError if the frontmatter fence is missing or malformed.
    """
    if not content.startswith("---"):
        raise ValueError("SKILL.md is missing the opening '---' frontmatter fence")

    # Find the closing '---' (first occurrence after line 0)
    lines = content.splitlines()
    close_index: int | None = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            close_index = i
            break

    if close_index is None:
        raise ValueError("SKILL.md frontmatter is not closed with '---'")

    frontmatter_text = "\n".join(lines[1:close_index])
    body = "\n".join(lines[close_index + 1:]).strip()

    try:
        metadata = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"YAML parse error in frontmatter: {exc}") from exc

    if not isinstance(metadata, dict):
        raise ValueError("Frontmatter did not parse to a key-value mapping")

    return metadata, body


def _extract_section(body: str, heading: str) -> str:
    """
    Extract the content under a Markdown ## heading from the body.

    Grabs everything from '## {heading}' up to the next '## ' heading (or EOF).
    Returns an empty string if the heading is not found.
    """
    # Build a pattern that captures everything under the target heading
    pattern = rf"^##\s+{re.escape(heading)}\s*\n(.*?)(?=^##\s|\Z)"
    match = re.search(pattern, body, re.MULTILINE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def _safe_list(value: Any) -> list[str]:
    """Coerce a frontmatter value to a list of strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _read_optional(path: Path) -> str:
    """Read a file and return its content; return '' if the file does not exist."""
    if path.exists():
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""
    return ""


# ---------------------------------------------------------------------------
# Loader class
# ---------------------------------------------------------------------------

class SkillLoader:
    """
    Loads skills from a local clone of the Anthropic-Cybersecurity-Skills repo.

    Parameters
    ----------
    repo_root : str | Path
        Path to the repository root (the directory that contains 'skills/').
    """

    def __init__(self, repo_root: str | Path = "./Anthropic-Cybersecurity-Skills") -> None:
        self.repo_root = Path(repo_root).resolve()
        self.skills_dir = self.repo_root / "skills"

        if not self.repo_root.exists():
            raise FileNotFoundError(
                f"Skills repo not found at: {self.repo_root}\n"
                "Run: git clone https://github.com/mukul975/Anthropic-Cybersecurity-Skills.git"
            )
        if not self.skills_dir.exists():
            raise FileNotFoundError(
                f"'skills/' directory missing inside: {self.repo_root}"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, skill_name: str) -> Skill:
        """
        Load a fully hydrated Skill by its kebab-case name.

        Parameters
        ----------
        skill_name : str
            e.g. 'performing-memory-forensics-with-volatility3'

        Returns
        -------
        Skill
        """
        skill_dir = self.skills_dir / skill_name
        if not skill_dir.exists():
            raise FileNotFoundError(
                f"Skill directory not found: {skill_dir}\n"
                f"Check available skills with loader.list_skill_names()"
            )

        skill_md_path = skill_dir / "SKILL.md"
        if not skill_md_path.exists():
            raise FileNotFoundError(f"SKILL.md missing in: {skill_dir}")

        # --- Parse SKILL.md ---
        content = skill_md_path.read_text(encoding="utf-8")
        metadata, body = _parse_frontmatter(content)

        # --- Extract structured sections from the Markdown body ---
        when_to_use  = _extract_section(body, "When to Use")
        prerequisites = _extract_section(body, "Prerequisites")
        verification  = _extract_section(body, "Verification")
        # Workflow may be labelled slightly differently across skills
        workflow_body = (
            _extract_section(body, "Workflow")
            or _extract_section(body, "Workflow Steps")
            or _extract_section(body, "Steps")
        )

        # --- Load adjacent reference files (all optional) ---
        standards_md = _read_optional(skill_dir / "references" / "standards.md")
        workflows_md = _read_optional(skill_dir / "references" / "workflows.md")
        template_md  = _read_optional(skill_dir / "assets" / "template.md")

        return Skill(
            # Identity
            name        = str(metadata.get("name", skill_name)).strip(),
            description = str(metadata.get("description", "")).strip(),
            domain      = str(metadata.get("domain", "")).strip(),
            subdomain   = str(metadata["subdomain"]).strip() if metadata.get("subdomain") else None,
            tags        = _safe_list(metadata.get("tags")),
            version     = str(metadata["version"]).strip() if metadata.get("version") else None,
            author      = str(metadata["author"]).strip() if metadata.get("author") else None,
            license     = str(metadata["license"]).strip() if metadata.get("license") else None,

            # Framework mappings
            nist_csf          = _safe_list(metadata.get("nist_csf")),
            atlas_techniques  = _safe_list(metadata.get("atlas_techniques")),
            d3fend_techniques = _safe_list(metadata.get("d3fend_techniques")),
            nist_ai_rmf       = _safe_list(metadata.get("nist_ai_rmf")),

            # Structured body sections
            when_to_use   = when_to_use,
            prerequisites = prerequisites,
            workflow_body = workflow_body,
            verification  = verification,

            # Adjacent files
            standards_md = standards_md,
            workflows_md = workflows_md,
            template_md  = template_md,

            # Filesystem metadata
            skill_dir = str(skill_dir),
        )

    def list_skill_names(self) -> list[str]:
        """Return a sorted list of all available skill directory names."""
        return sorted(
            d.name
            for d in self.skills_dir.iterdir()
            if d.is_dir() and (d / "SKILL.md").exists()
        )

    def load_all(self, verbose: bool = False) -> list[Skill]:
        """
        Load every available skill.  Skips skills that fail to parse and
        prints a warning instead of crashing the whole batch.

        Parameters
        ----------
        verbose : bool
            If True, print a progress dot for each skill loaded.
        """
        skills: list[Skill] = []
        names  = self.list_skill_names()
        failed: list[str]   = []

        for name in names:
            try:
                skills.append(self.load(name))
                if verbose:
                    print(".", end="", flush=True)
            except Exception as exc:  # noqa: BLE001
                failed.append(f"{name}: {exc}")

        if verbose:
            print()  # newline after dots

        if failed:
            print(f"\n[skill_loader] Warning: {len(failed)} skill(s) failed to load:")
            for msg in failed[:10]:
                print(f"  - {msg}")
            if len(failed) > 10:
                print(f"  ... and {len(failed) - 10} more")

        return skills


# ---------------------------------------------------------------------------
# Quick smoke-test (run directly: python skill_loader.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    repo_path = sys.argv[1] if len(sys.argv) > 1 else "./Anthropic-Cybersecurity-Skills"

    print(f"Loading skills from: {repo_path}")
    loader = SkillLoader(repo_path)

    names = loader.list_skill_names()
    print(f"Found {len(names)} skills.")

    if names:
        first = names[0]
        print(f"\nLoading first skill: '{first}' ...")
        skill = loader.load(first)
        print(f"  name        : {skill.name}")
        print(f"  domain      : {skill.domain}")
        print(f"  subdomain   : {skill.subdomain}")
        print(f"  tags        : {skill.tags}")
        print(f"  when_to_use : {skill.when_to_use[:120]}..." if skill.when_to_use else "  when_to_use : (empty)")
        print(f"  workflow    : {skill.workflow_body[:120]}..." if skill.workflow_body else "  workflow    : (empty)")
        print(f"  standards   : {'yes' if skill.standards_md else 'no'}")
        print(f"  workflows   : {'yes' if skill.workflows_md else 'no'}")
        print(f"  template    : {'yes' if skill.template_md else 'no'}")
