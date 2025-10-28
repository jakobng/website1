"""Base objects and lightweight helpers shared by all scrapers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Protocol, Sequence

__all__ = [
    "ShowTime",
    "ScraperMetadata",
    "ScraperProtocol",
    "ScraperAdapter",
]


@dataclass(slots=True)
class ShowTime:
    """Container for a single showtime entry returned by a venue scraper."""

    cinema_name: str
    movie_title: str
    showtime: str
    date_text: str = ""
    detail_page_url: str = ""
    director: str = ""
    year: str = ""
    country: str = ""
    runtime_min: str = ""
    synopsis: str = ""
    movie_title_en: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        data = {
            "cinema_name": self.cinema_name,
            "movie_title": self.movie_title,
            "showtime": self.showtime,
            "date_text": self.date_text,
            "detail_page_url": self.detail_page_url,
            "director": self.director,
            "year": self.year,
            "country": self.country,
            "runtime_min": self.runtime_min,
            "synopsis": self.synopsis,
            "movie_title_en": self.movie_title_en,
        }
        data.update(self.extra)
        return {key: value for key, value in data.items() if value is not None}


@dataclass(slots=True)
class ScraperMetadata:
    """Metadata about a scraper used by the orchestrator."""

    slug: str
    cinema_name: str
    module: str
    description: str = ""


class ScraperProtocol(Protocol):
    """Simple protocol shared by scraper adapters."""

    metadata: ScraperMetadata

    def scrape(self) -> Sequence[Dict[str, Any]]:
        ...


Normalizer = Callable[[Sequence[Dict[str, Any]]], Sequence[Dict[str, Any]]]


class ScraperAdapter:
    """Wraps a callable that yields raw showtime dictionaries."""

    def __init__(
        self,
        metadata: ScraperMetadata,
        runner: Callable[[], Sequence[Dict[str, Any]]],
        normalizer: Optional[Normalizer] = None,
    ) -> None:
        self.metadata = metadata
        self._runner = runner
        self._normalizer = normalizer

    def scrape(self) -> Sequence[Dict[str, Any]]:
        raw_items = list(self._runner() or [])
        if self._normalizer is not None:
            raw_items = list(self._normalizer(raw_items))
        return [dict(item) for item in raw_items]
