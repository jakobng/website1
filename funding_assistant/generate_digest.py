#!/usr/bin/env python3
"""Generate a curated funding digest from discovered results."""

import argparse
from datetime import datetime
from pathlib import Path

import yaml

from src.config import AppConfig
from src.digest import generate_digest


def load_projects(path: Path) -> list[dict]:
    """Load projects from YAML file."""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("projects", [])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a curated funding digest"
    )
    parser.add_argument(
        "--project",
        "-p",
        dest="project_id",
        help="Generate digest for a specific project only",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.5,
        help="Minimum score threshold (default: 0.5)",
    )
    parser.add_argument(
        "--max-grants",
        type=int,
        default=20,
        help="Maximum grants per project (default: 20)",
    )
    parser.add_argument(
        "--max-orgs",
        type=int,
        default=10,
        help="Maximum organizations per project (default: 10)",
    )
    parser.add_argument(
        "--no-mark",
        action="store_true",
        help="Don't mark results as shown (useful for testing)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output file path (default: data/digest_YYYYMMDD.txt)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    
    config = AppConfig()
    
    # Load projects
    projects_path = Path("data/projects.yml")
    if not projects_path.exists():
        print(f"Error: Projects file not found: {projects_path}")
        return
    
    projects = load_projects(projects_path)
    
    # Filter to specific project if requested
    if args.project_id:
        projects = [p for p in projects if p["id"] == args.project_id]
        if not projects:
            print(f"Error: Project not found: {args.project_id}")
            return
    
    print(f"Generating digest for {len(projects)} project(s)...")
    
    # Generate digest
    digest_text = generate_digest(
        config=config,
        projects=projects,
        mark_shown=not args.no_mark,
        min_score=args.min_score,
        max_grants_per_project=args.max_grants,
        max_orgs_per_project=args.max_orgs,
    )
    
    # Determine output path
    if args.output:
        output_path = args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(f"data/digest_{timestamp}.txt")
    
    # Ensure directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write output
    output_path.write_text(digest_text, encoding="utf-8")
    print(f"\nDigest saved to: {output_path.absolute()}")
    
    # Also print to console
    print("\n" + "=" * 60)
    print("DIGEST PREVIEW (first 100 lines):")
    print("=" * 60)
    lines = digest_text.split("\n")
    for line in lines[:100]:
        print(line)
    if len(lines) > 100:
        print(f"\n... ({len(lines) - 100} more lines in file)")


if __name__ == "__main__":
    main()
