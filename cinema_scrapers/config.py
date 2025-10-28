"""Configuration helpers for the scraper suite."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    )
}


@dataclass(slots=True)
class ScraperSettings:
    """Central configuration that may be adjusted via environment variables."""

    tmdb_api_key: str = field(default_factory=lambda: os.getenv("TMDB_API_KEY", ""))
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    tmdb_cache_path: Path = field(
        default_factory=lambda: Path(os.getenv("TMDB_CACHE_PATH", "cinema_scrapers/data/tmdb_cache.json"))
    )
    output_path: Path = field(
        default_factory=lambda: Path(os.getenv("SHOWTIMES_OUTPUT_PATH", "cinema_scrapers/data/showtimes.json"))
    )
    request_headers: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_HEADERS))
    tmdb_search_delay: float = float(os.getenv("TMDB_SEARCH_DELAY", "0.3"))
    tmdb_details_delay: float = float(os.getenv("TMDB_DETAILS_DELAY", "0.3"))
    tmdb_alternative_titles_delay: float = float(os.getenv("TMDB_ALT_TITLES_DELAY", "0.3"))
    letterboxd_delay: float = float(os.getenv("LETTERBOXD_DELAY", "0.5"))
    gemini_delay: float = float(os.getenv("GEMINI_DELAY", "1.0"))

    def ensure_cache_dirs(self) -> None:
        self.tmdb_cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def load_tmdb_cache(self) -> Dict[str, dict]:
        if self.tmdb_cache_path.exists():
            try:
                return json.loads(self.tmdb_cache_path.read_text("utf-8"))
            except Exception:
                return {}
        return {}

    def save_tmdb_cache(self, cache: Dict[str, dict]) -> None:
        self.ensure_cache_dirs()
        self.tmdb_cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
