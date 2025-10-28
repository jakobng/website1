"""Command line entry point for running the cinema scrapers."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

import requests

from . import ScraperSettings, load_scrapers, run_scrapers
from .enrichment.tmdb import GeminiClient, TMDBEnricher


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the cinema scraper suite")
    parser.add_argument("--parallel", action="store_true", help="Run venue scrapers in parallel")
    parser.add_argument("--max-workers", type=int, default=None, help="Maximum worker threads when using --parallel")
    parser.add_argument("--skip-enrichment", action="store_true", help="Skip TMDB/Letterboxd enrichment")
    parser.add_argument("--output", type=Path, default=None, help="Override the output JSON path")
    parser.add_argument("--tmdb-cache", type=Path, default=None, help="Override the TMDB cache path")
    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    settings = ScraperSettings()
    if args.output:
        settings.output_path = args.output
    if args.tmdb_cache:
        settings.tmdb_cache_path = args.tmdb_cache
    settings.ensure_cache_dirs()

    scrapers = load_scrapers()
    listings = run_scrapers(scrapers, parallel=args.parallel, max_workers=args.max_workers)

    if not args.skip_enrichment:
        gemini_client = None
        if settings.gemini_api_key:
            gemini_client = GeminiClient(api_key=settings.gemini_api_key)
        enricher = TMDBEnricher(settings=settings, session=requests.Session(), gemini=gemini_client)
        listings = enricher.enrich(listings)
        listings = sorted(
            listings,
            key=lambda x: (
                x.get("cinema_name") or x.get("cinema", ""),
                x.get("date_text", ""),
                x.get("showtime", ""),
            ),
        )

    settings.ensure_cache_dirs()
    settings.output_path.write_text(json.dumps(listings, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Saved {len(listings)} showings to {settings.output_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
