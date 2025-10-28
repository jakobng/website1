"""Scraper orchestration utilities."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable, List, Sequence

from .base import ScraperProtocol


def _run_single(scraper: ScraperProtocol) -> Sequence[dict]:
    print(f"\nScraping {scraper.metadata.cinema_name} …")
    results = scraper.scrape()
    print(f"→ {len(results)} showings from {scraper.metadata.cinema_name}.")
    return results


def run_scrapers(
    scrapers: Iterable[ScraperProtocol],
    *,
    parallel: bool = False,
    max_workers: int | None = None,
) -> List[dict]:
    """Execute scrapers sequentially or in a thread pool."""

    collected: List[dict] = []
    scraper_list = list(scrapers)

    if not parallel or len(scraper_list) <= 1:
        for scraper in scraper_list:
            try:
                collected.extend(_run_single(scraper))
            except Exception as exc:  # noqa: BLE001 - we need to log and continue
                print(f"⚠️ Error in {scraper.metadata.cinema_name}: {exc}")
        return collected

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(_run_single, scraper): scraper for scraper in scraper_list}
        for future in as_completed(future_map):
            scraper = future_map[future]
            try:
                collected.extend(future.result())
            except Exception as exc:  # noqa: BLE001 - we need to log and continue
                print(f"⚠️ Error in {scraper.metadata.cinema_name}: {exc}")
    return collected
