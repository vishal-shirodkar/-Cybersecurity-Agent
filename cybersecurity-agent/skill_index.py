"""
skill_index.py
--------------
Builds and queries a ChromaDB vector index over all cybersecurity skills
from the Anthropic-Cybersecurity-Skills repository.

Each skill is embedded as a single document combining its name, description,
tags, subdomain, and truncated workflow.  The index is persisted to disk so
it only needs to be built once; subsequent runs load it instantly.

Usage
-----
    # Build the index (first run ~1-3 minutes for 754 skills)
    index = SkillIndex("./Anthropic-Cybersecurity-Skills")
    index.build(force_rebuild=False)

    # Query at any time
    results = index.query_skills("analyze suspicious memory dump", top_k=3)
    for hit in results:
        print(hit.skill_name, hit.score)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

from skill_loader import SkillLoader, Skill


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Directory where ChromaDB will persist its SQLite + vector files
DEFAULT_PERSIST_DIR = "./chroma_db"

# ChromaDB collection name
COLLECTION_NAME = "cybersecurity_skills"

# Maximum characters to include from the workflow body in the embedded document
# (keeps token cost low while preserving the most relevant content)
WORKFLOW_SNIPPET_LEN = 600

# ChromaDB uses sentence-transformers by default when no API key is provided.
# This model runs locally on CPU and produces good results for technical text.
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class SkillMatch:
    """A single result returned by query_skills()."""
    skill_name: str          # kebab-case skill name
    description: str         # short description from frontmatter
    domain: str              # e.g. 'cybersecurity'
    subdomain: str | None    # e.g. 'digital-forensics'
    tags: list[str]          # skill tags
    score: float             # cosine distance — lower is more similar (0.0 = identical)
    document: str            # the embedded text snippet


# ---------------------------------------------------------------------------
# Index class
# ---------------------------------------------------------------------------

class SkillIndex:
    """
    Manages a ChromaDB-backed semantic index over all skills.

    Parameters
    ----------
    repo_root : str | Path
        Path to the local clone of Anthropic-Cybersecurity-Skills.
    persist_dir : str | Path
        Where ChromaDB should store its data files between runs.
    embedding_model : str
        Name of the sentence-transformers model used for local embeddings.
        The model is downloaded automatically on first use.
    """

    def __init__(
        self,
        repo_root: str | Path = "./Anthropic-Cybersecurity-Skills",
        persist_dir: str | Path = DEFAULT_PERSIST_DIR,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    ) -> None:
        self.repo_root    = Path(repo_root).resolve()
        self.persist_dir  = Path(persist_dir).resolve()
        self.loader       = SkillLoader(repo_root)

        # Use the local sentence-transformers embedding function (no API key needed)
        self._embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )

        # Create (or reopen) the persistent ChromaDB client
        self._client = chromadb.PersistentClient(path=str(self.persist_dir))

        # Lazily opened — set after build() or _open_collection()
        self._collection: chromadb.Collection | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(self, force_rebuild: bool = False, verbose: bool = True) -> None:
        """
        Build the ChromaDB index from all skills in the repository.

        Parameters
        ----------
        force_rebuild : bool
            If True, delete the existing collection and rebuild from scratch.
            If False (default), skip building if the collection already exists
            and contains documents.
        verbose : bool
            Print progress messages to stdout.
        """
        # Check whether an up-to-date index already exists
        existing_names = [c.name for c in self._client.list_collections()]

        if COLLECTION_NAME in existing_names and not force_rebuild:
            collection = self._client.get_collection(
                name=COLLECTION_NAME,
                embedding_function=self._embed_fn,
            )
            count = collection.count()
            if count > 0:
                if verbose:
                    print(
                        f"[skill_index] Index already exists with {count} skills. "
                        "Pass force_rebuild=True to rebuild."
                    )
                self._collection = collection
                return

        # Delete stale collection if rebuilding
        if COLLECTION_NAME in existing_names:
            if verbose:
                print("[skill_index] Deleting existing collection for rebuild…")
            self._client.delete_collection(COLLECTION_NAME)

        # Create fresh collection
        collection = self._client.create_collection(
            name=COLLECTION_NAME,
            embedding_function=self._embed_fn,
            metadata={"hnsw:space": "cosine"},  # cosine distance for semantic search
        )
        self._collection = collection

        # Load all skills
        if verbose:
            print(f"[skill_index] Loading skills from: {self.repo_root}")

        skills = self.loader.load_all(verbose=False)

        if not skills:
            raise RuntimeError(
                "No skills loaded — check that the repository is cloned correctly."
            )

        if verbose:
            print(f"[skill_index] Loaded {len(skills)} skills. Embedding now…")
            print("[skill_index] (First run downloads the embedding model — may take a minute)")

        # Embed in batches of 100 to avoid memory spikes
        batch_size = 100
        total      = len(skills)
        start_time = time.time()

        for batch_start in range(0, total, batch_size):
            batch  = skills[batch_start : batch_start + batch_size]
            ids, docs, metas = _batch_to_chroma(batch)

            collection.add(
                ids       = ids,
                documents = docs,
                metadatas = metas,
            )

            if verbose:
                end = min(batch_start + batch_size, total)
                elapsed = time.time() - start_time
                print(
                    f"  [{end:>4}/{total}] embedded  "
                    f"({elapsed:.1f}s elapsed)",
                    flush=True,
                )

        elapsed_total = time.time() - start_time
        if verbose:
            print(
                f"[skill_index] ✓ Index built: {total} skills in "
                f"{elapsed_total:.1f}s → {self.persist_dir}"
            )

    def query_skills(
        self,
        user_input: str,
        top_k: int = 3,
    ) -> list[SkillMatch]:
        """
        Semantic search over the skill index.

        Parameters
        ----------
        user_input : str
            Free-text user query, e.g. 'investigate credential theft in memory'.
        top_k : int
            Number of best-matching skills to return (default 3).

        Returns
        -------
        list[SkillMatch]
            Ranked by cosine similarity (closest first).
        """
        collection = self._require_collection()

        results = collection.query(
            query_texts = [user_input],
            n_results   = top_k,
            include     = ["documents", "metadatas", "distances"],
        )

        matches: list[SkillMatch] = []

        # ChromaDB wraps results in an extra list (one per query_text)
        ids       = results["ids"][0]
        distances = results["distances"][0]
        metadatas = results["metadatas"][0]
        documents = results["documents"][0]

        for skill_id, distance, meta, doc in zip(ids, distances, metadatas, documents):
            matches.append(
                SkillMatch(
                    skill_name  = skill_id,
                    description = meta.get("description", ""),
                    domain      = meta.get("domain", ""),
                    subdomain   = meta.get("subdomain") or None,
                    tags        = json.loads(meta.get("tags_json", "[]")),
                    score       = round(float(distance), 4),
                    document    = doc,
                )
            )

        return matches

    def count(self) -> int:
        """Return the number of skills currently indexed."""
        return self._require_collection().count()

    def is_built(self) -> bool:
        """Return True if the index exists and contains at least one skill."""
        existing_names = [c.name for c in self._client.list_collections()]
        if COLLECTION_NAME not in existing_names:
            return False
        col = self._client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=self._embed_fn,
        )
        return col.count() > 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_collection(self) -> chromadb.Collection:
        """Return the open collection, auto-opening if needed."""
        if self._collection is not None:
            return self._collection

        existing_names = [c.name for c in self._client.list_collections()]
        if COLLECTION_NAME not in existing_names:
            raise RuntimeError(
                "Index has not been built yet. Call index.build() first."
            )

        self._collection = self._client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=self._embed_fn,
        )
        return self._collection


# ---------------------------------------------------------------------------
# Helpers for converting skills to ChromaDB add() inputs
# ---------------------------------------------------------------------------

def _skill_to_document(skill: Skill) -> str:
    """
    Build the text that will be embedded for this skill.

    We combine the most information-dense fields:
      1. name + description (always present, keyword-rich)
      2. subdomain + tags (domain signal)
      3. workflow snippet (procedural context)
      4. when_to_use (trigger conditions)

    Keeping this under ~1 KB per skill ensures fast embedding and
    avoids diluting the semantic signal with boilerplate text.
    """
    parts: list[str] = []

    parts.append(f"Skill: {skill.name}")
    parts.append(f"Description: {skill.description}")

    if skill.subdomain:
        parts.append(f"Subdomain: {skill.subdomain}")

    if skill.tags:
        parts.append(f"Tags: {', '.join(skill.tags)}")

    if skill.when_to_use:
        # First 200 chars of when_to_use gives good trigger-condition signal
        parts.append(f"When to use: {skill.when_to_use[:200]}")

    if skill.workflow_body:
        parts.append(f"Workflow: {skill.workflow_body[:WORKFLOW_SNIPPET_LEN]}")

    return "\n".join(parts)


def _skill_to_metadata(skill: Skill) -> dict[str, str]:
    """
    Build the ChromaDB metadata dict for a skill.

    ChromaDB metadata values must be str, int, float, or bool.
    Lists are serialised as JSON strings.
    """
    return {
        "description":  skill.description[:500],   # guard against very long descriptions
        "domain":       skill.domain,
        "subdomain":    skill.subdomain or "",
        "tags_json":    json.dumps(skill.tags),
        "version":      skill.version or "",
        "author":       skill.author or "",
        "nist_csf":     json.dumps(skill.nist_csf),
        "atlas":        json.dumps(skill.atlas_techniques),
        "d3fend":       json.dumps(skill.d3fend_techniques),
    }


def _batch_to_chroma(
    skills: list[Skill],
) -> tuple[list[str], list[str], list[dict[str, str]]]:
    """Convert a list of Skills to the three parallel lists ChromaDB expects."""
    ids   = [s.name for s in skills]
    docs  = [_skill_to_document(s) for s in skills]
    metas = [_skill_to_metadata(s) for s in skills]
    return ids, docs, metas


# ---------------------------------------------------------------------------
# Quick smoke-test (run directly: python skill_index.py [repo_path])
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    repo_path    = sys.argv[1] if len(sys.argv) > 1 else "./Anthropic-Cybersecurity-Skills"
    persist_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PERSIST_DIR

    print(f"Repo   : {repo_path}")
    print(f"Index  : {persist_path}")
    print()

    idx = SkillIndex(repo_root=repo_path, persist_dir=persist_path)
    idx.build(force_rebuild=False, verbose=True)

    print(f"\nIndex contains {idx.count()} skills.")
    print("\n--- Sample query: 'investigate suspicious memory dump' ---")

    hits = idx.query_skills("investigate suspicious memory dump", top_k=3)
    for i, hit in enumerate(hits, 1):
        print(f"\n#{i}  {hit.skill_name}  (score={hit.score})")
        print(f"    {hit.description[:100]}…")
        print(f"    subdomain: {hit.subdomain}  tags: {hit.tags[:4]}")
