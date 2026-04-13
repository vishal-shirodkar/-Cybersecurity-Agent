from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from security_agent.catalog.manifest_loader import load_manifest
from security_agent.catalog.repository import CatalogRepository
from security_agent.config import AppConfig
from security_agent.integrations.mcp_server import LocalMcpService, run_stdio_loop
from security_agent.logging_config import configure_logging


def _resolve_skills_root(args: argparse.Namespace, config: AppConfig) -> Path:
    if getattr(args, "skills_root", None):
        return Path(args.skills_root)
    return config.upstream_dir / "Anthropic-Cybersecurity-Skills"


def _resolve_index_file(args: argparse.Namespace, config: AppConfig) -> Path | None:
    if getattr(args, "index_file", None):
        return Path(args.index_file)
    default_index = _resolve_skills_root(args, config) / "index.json"
    return default_index if default_index.exists() else None


def _build_repository(config: AppConfig, index_file: Path | None = None) -> CatalogRepository:
    repository = CatalogRepository(config.catalog_db)
    repository.initialize()
    if index_file and index_file.exists():
        repository.upsert_many(load_manifest(index_file))
    return repository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Security agent skeleton CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor", help="Show project and data directory health")
    subparsers.add_parser("init-db", help="Create the local SQLite catalog")

    sync_manifest = subparsers.add_parser("sync-manifest", help="Seed the catalog from index.json")
    sync_manifest.add_argument("--index-file", required=True, help="Path to the upstream index.json")

    query = subparsers.add_parser("query", help="Select skills and build a grounded prompt")
    query.add_argument("--query", required=True, help="User request to classify and ground")
    query.add_argument("--skills-root", help="Path to the synced skills repository root")
    query.add_argument("--index-file", help="Path to the upstream index.json")
    query.add_argument("--limit", type=int, default=3, help="Maximum skills to select")

    serve = subparsers.add_parser("serve-mcp", help="Start the local stdio development transport")
    serve.add_argument("--skills-root", help="Path to the synced skills repository root")
    serve.add_argument("--index-file", help="Path to the upstream index.json")
    serve.add_argument("--limit", type=int, default=3, help="Maximum skills to select")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    config = AppConfig.from_env().ensure_directories()
    configure_logging(config.log_level)

    if args.command == "doctor":
        doctor_payload = {
            "workspace_root": str(config.workspace_root),
            "data_dir": str(config.data_dir),
            "upstream_dir": str(config.upstream_dir),
            "cache_dir": str(config.cache_dir),
            "catalog_db": str(config.catalog_db),
            "approved_tools": list(config.approved_tools),
                    "suggested_commands": [
                        "python main.py init-db",
                        "powershell -File scripts\\sync_skills.ps1",
                        "python main.py query --query \"Investigate suspicious PowerShell behavior\"",
                        "python main.py serve-mcp",
                    ],
                }
        print(json.dumps(doctor_payload, indent=2))
        return 0

    if args.command == "init-db":
        repository = _build_repository(config)
        print(json.dumps({"status": "initialized", "catalog_db": str(repository.db_path)}, indent=2))
        return 0

    if args.command == "sync-manifest":
        index_file = Path(args.index_file)
        repository = _build_repository(config, index_file=index_file)
        print(json.dumps({"status": "seeded", "catalog_db": str(repository.db_path), "index_file": str(index_file)}, indent=2))
        return 0

    index_file = _resolve_index_file(args, config)
    repository = _build_repository(config, index_file=index_file)
    service = LocalMcpService(repository, config.workspace_root)
    skills_root = _resolve_skills_root(args, config)

    if args.command == "query":
        result = service.query(query=args.query, skills_root=skills_root, limit=args.limit)
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "serve-mcp":
        return run_stdio_loop(service, skills_root, args.limit)

    parser.error(f"Unsupported command: {args.command}")
    return 2
