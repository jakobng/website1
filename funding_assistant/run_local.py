from __future__ import annotations

import argparse

from src.config import AppConfig
from src.pipeline import run_discovery
from src.service import build_digest_from_db
from src.storage import init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run discovery and print/save a local report (no email)."
    )
    parser.add_argument("--project-id", help="Limit to a single project")
    parser.add_argument("--output", help="Write report to a file path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print("=" * 60, flush=True)
    print("FUNDING ASSISTANT - Starting discovery...", flush=True)
    print("=" * 60, flush=True)
    config = AppConfig()
    print(f"Search provider: {config.search_provider}", flush=True)
    print(f"Model: {config.gemini_model}", flush=True)
    print(f"Max queries per project: {config.max_queries_per_project}", flush=True)
    print("-" * 60, flush=True)
    init_db(config.db_path)
    run_discovery(config, project_id=args.project_id)
    digest = build_digest_from_db(config, project_id=args.project_id)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(digest)
        print(f"Report written to {args.output}")
    else:
        print(digest)


if __name__ == "__main__":
    main()
