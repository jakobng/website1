from __future__ import annotations

import argparse
import time

from src.config import AppConfig
from src.emailer import build_digest, send_email
from src.pipeline import run_discovery
from src.scheduler import start_scheduler
from src.service import build_digest_from_db, process_replies, run_discovery_and_email
from src.storage import init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Film funding discovery assistant")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Initialize the SQLite database")

    discover_parser = subparsers.add_parser("discover", help="Run discovery for projects")
    discover_parser.add_argument("--project-id", help="Limit to a single project")
    discover_parser.add_argument("--depth", type=int, help="Follow-up depth")
    discover_parser.add_argument(
        "--send-email", action="store_true", help="Send digest after discovery"
    )

    digest_parser = subparsers.add_parser("send-digest", help="Send digest from DB")
    digest_parser.add_argument("--project-id", help="Limit digest to a project")

    report_parser = subparsers.add_parser(
        "report", help="Print or save a report from the database"
    )
    report_parser.add_argument("--project-id", help="Limit report to a project")
    report_parser.add_argument("--limit", type=int, default=20, help="Max results")
    report_parser.add_argument("--output", help="Write report to a file path")

    subparsers.add_parser("process-replies", help="Process unread email replies")
    subparsers.add_parser("run-all", help="Run discovery and then process replies")
    subparsers.add_parser("schedule", help="Start scheduled discovery + reply checks")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = AppConfig()

    if args.command == "init-db":
        init_db(config.db_path)
        print(f"Database initialized at {config.db_path}")
        return

    if args.command == "discover":
        reports = run_discovery(
            config,
            project_id=args.project_id,
            depth=args.depth,
        )
        if args.send_email:
            results = []
            pivots = []
            for report in reports:
                results.extend(report.stored_results)
                pivots.extend(report.pivot_suggestions)
            digest = build_digest(results, pivots)
            send_email(config, "Film Funding Digest", digest)
        return

    if args.command == "send-digest":
        digest = build_digest_from_db(config, project_id=args.project_id)
        send_email(config, "Film Funding Digest", digest)
        return

    if args.command == "report":
        digest = build_digest_from_db(
            config, project_id=args.project_id, limit=args.limit
        )
        if args.output:
            output_path = args.output
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(digest)
            print(f"Report written to {output_path}")
        else:
            print(digest)
        return

    if args.command == "process-replies":
        process_replies(config)
        return

    if args.command == "run-all":
        run_discovery_and_email(config)
        process_replies(config)
        return

    if args.command == "schedule":
        scheduler = start_scheduler(config)
        print("Scheduler running. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(60)
        finally:
            scheduler.shutdown()


if __name__ == "__main__":
    main()
