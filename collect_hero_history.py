#!/usr/bin/env python3
"""Collect historical hero images from git into a local folder."""

from __future__ import annotations

import argparse
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Target:
    name: str
    path: Path


DEFAULT_TARGETS = [
    Target("london", Path("london-cinema-scrapers/ig_posts/post_image_00.png")),
    Target("london", Path("london-cinema-scrapers/ig_posts/post_v2_image_00.png")),
    Target("tokyo", Path("cinema-scrapers/ig_posts/post_image_00.png")),
    Target("tokyo", Path("cinema-scrapers/ig_posts/post_v2_image_00.png")),
]


def run_git(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def collect_history(target: Target, output_root: Path) -> int:
    if not target.path.exists():
        print(f"Skipping missing path: {target.path}")
        return 0

    rev_list = run_git(["rev-list", "--all", "--", str(target.path)])
    if not rev_list:
        print(f"No history found for: {target.path}")
        return 0

    commits = rev_list.splitlines()
    output_dir = output_root / target.name
    output_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for sha in commits:
        try:
            blob = subprocess.check_output(
                ["git", "show", f"{sha}:{target.path}"],
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            continue

        date = run_git(["show", "-s", "--format=%cd", "--date=format:%Y%m%d", sha])
        filename = f"{target.path.stem}_{date}_{sha[:7]}{target.path.suffix}"
        output_path = output_dir / filename
        if output_path.exists():
            continue
        output_path.write_bytes(blob)
        count += 1

    return count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect historical hero images (post_image_00 / post_v2_image_00) from git."
    )
    parser.add_argument(
        "--output",
        default="collected_hero_history",
        help="Output directory to store extracted images.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_root = Path(args.output)
    output_root.mkdir(parents=True, exist_ok=True)

    total = 0
    for target in DEFAULT_TARGETS:
        total += collect_history(target, output_root)

    print(f"Done. Extracted {total} images into {output_root}/")


if __name__ == "__main__":
    main()
