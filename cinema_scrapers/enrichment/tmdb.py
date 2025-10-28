"""TMDB and Letterboxd enrichment helpers."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, MutableMapping, Optional, Sequence, Tuple

import requests
from bs4 import BeautifulSoup

from ..config import ScraperSettings
from ..utils import clean_title

TMDB_API_BASE_URL = "https://api.themoviedb.org/3"
LETTERBOXD_TMDB_BASE_URL = "https://letterboxd.com/tmdb/"


def python_is_predominantly_latin(text: str) -> bool:
    if not text:
        return False
    if not re.search(r"[a-zA-Z]", text):
        return False
    japanese_chars = re.findall(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]", text)
    latin_chars = re.findall(r"[a-zA-Z]", text)
    if not japanese_chars:
        return True
    if latin_chars:
        if len(latin_chars) > len(japanese_chars) * 2:
            return True
        if len(japanese_chars) <= 2 and len(latin_chars) > len(japanese_chars):
            return True
        return False
    return False


@dataclass
class GeminiClient:
    """Optional thin wrapper around the Google Generative AI client."""

    api_key: str
    model_name: str = "gemini-2.5-flash"
    _model: Optional[object] = field(init=False, default=None, repr=False)

    def _load_model(self) -> Optional[object]:
        if not self.api_key or "YOUR_GEMINI_API_KEY" in self.api_key:
            return None
        if self._model is not None:
            return self._model
        try:
            import google.generativeai as genai  # type: ignore[import-not-found]
        except Exception:  # noqa: BLE001 - the dependency is optional
            return None
        try:
            genai.configure(api_key=self.api_key)
            self._model = genai.GenerativeModel(self.model_name)
        except Exception:
            self._model = None
        return self._model

    def suggest_title(
        self,
        cleaned_title: str,
        context_title: str,
        *,
        year: Optional[str] = None,
        director: Optional[str] = None,
        country: Optional[str] = None,
    ) -> Optional[str]:
        model = self._load_model()
        if model is None:
            return None
        title_to_use = context_title or cleaned_title
        if not title_to_use:
            return None
        context_parts = []
        if year:
            context_parts.append(f"released in or around {year}")
        if director:
            context_parts.append(f"directed by {director}")
        if country:
            context_parts.append(f"from {country}")
        context_str = f" ({', '.join(context_parts)})" if context_parts else ""
        prompt = (
            "What is the official English title OR the original language title "
            f"for the film '{title_to_use}'{context_str}?\n"
            "If it's an English-language film, return its original English title.\n"
            "Respond with ONLY the single most common title. "
            "If you cannot determine a title, return the exact phrase 'NO_TITLE_FOUND'."
        )
        try:
            response = model.generate_content(prompt)
        except Exception:  # noqa: BLE001 - Gemini is best-effort
            return None
        if not getattr(response, "text", None):
            return None
        alt_title = response.text.strip().replace('"', "")
        if not alt_title or "NO_TITLE_FOUND" in alt_title.upper():
            return None
        return alt_title


@dataclass
class TMDBEnricher:
    settings: ScraperSettings
    session: requests.Session = field(default_factory=requests.Session)
    gemini: Optional[GeminiClient] = None
    cache: MutableMapping[str, Dict[str, object]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.cache:
            self.cache.update(self.settings.load_tmdb_cache())

    @property
    def enabled(self) -> bool:
        return bool(self.settings.tmdb_api_key and "YOUR_TMDB_API_KEY" not in self.settings.tmdb_api_key)

    def _tmdb_get(self, url: str, *, params: Optional[Dict[str, str]] = None) -> Optional[Dict[str, object]]:
        if not self.enabled:
            return None
        try:
            response = self.session.get(url, params=params, headers=self.settings.request_headers, timeout=10)
            response.raise_for_status()
            time.sleep(self.settings.tmdb_details_delay)
            return response.json()
        except Exception:  # noqa: BLE001 - API hiccups should not crash scraping
            return None

    def search_tmdb(
        self,
        title: str,
        *,
        year: Optional[str] = None,
        language_code: Optional[str] = None,
    ) -> Dict[str, object]:
        if not title or not self.enabled:
            return {"id": None, "tmdb_title": None, "tmdb_original_title": None}
        params = {
            "api_key": self.settings.tmdb_api_key,
            "query": title,
            "include_adult": "false",
        }
        if year:
            params["primary_release_year"] = year
        if language_code:
            params["language"] = language_code
        try:
            response = self.session.get(
                f"{TMDB_API_BASE_URL}/search/movie",
                params=params,
                headers=self.settings.request_headers,
                timeout=10,
            )
            response.raise_for_status()
            time.sleep(self.settings.tmdb_search_delay)
            payload = response.json()
        except Exception:  # noqa: BLE001 - best effort search
            return {"id": None, "tmdb_title": None, "tmdb_original_title": None}
        results = payload.get("results") if isinstance(payload, dict) else None
        if not results:
            return {"id": None, "tmdb_title": None, "tmdb_original_title": None}
        best_match = None
        highest_score = -1.0
        title_lower = title.lower()
        for result in results[:10]:
            res_title = (result.get("title") or "").lower()
            res_original = (result.get("original_title") or "").lower()
            score = 0.0
            if title_lower == res_title or title_lower == res_original:
                score += 100
            elif title_lower in res_title or title_lower in res_original:
                score += 50
            release_date = result.get("release_date", "")
            if year and release_date:
                try:
                    release_year = release_date.split("-")[0]
                    if release_year == year:
                        score += 200
                    else:
                        score = -999
                except Exception:  # noqa: BLE001
                    pass
            if score < 0:
                continue
            score += float(result.get("popularity", 0)) / 100
            if score > highest_score:
                highest_score = score
                best_match = result
        if not best_match or highest_score < 50:
            return {"id": None, "tmdb_title": None, "tmdb_original_title": None}
        tmdb_id = best_match.get("id")
        chosen_display_title = best_match.get("title")
        original_title = best_match.get("original_title")
        details = self._tmdb_get(
            f"{TMDB_API_BASE_URL}/movie/{tmdb_id}",
            params={"api_key": self.settings.tmdb_api_key, "language": "en-US"},
        ) or {}
        chosen_display_title = details.get("title") or chosen_display_title
        original_title = details.get("original_title") or original_title
        if chosen_display_title and not python_is_predominantly_latin(chosen_display_title):
            if original_title and python_is_predominantly_latin(original_title):
                chosen_display_title = original_title
            else:
                alt_titles = self._tmdb_get(
                    f"{TMDB_API_BASE_URL}/movie/{tmdb_id}/alternative_titles",
                    params={"api_key": self.settings.tmdb_api_key},
                ) or {}
                for alt in alt_titles.get("titles", []):
                    if alt.get("iso_3166_1") in {"US", "GB"} and python_is_predominantly_latin(alt.get("title")):
                        chosen_display_title = alt.get("title")
                        break
        return {
            "id": tmdb_id,
            "tmdb_title": chosen_display_title,
            "tmdb_original_title": original_title,
        }

    def _letterboxd_title(self, tmdb_id: int) -> Optional[str]:
        url = f"{LETTERBOXD_TMDB_BASE_URL}{tmdb_id}"
        try:
            response = self.session.get(url, headers=self.settings.request_headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
        except Exception:  # noqa: BLE001 - optional feature
            return None
        tag = soup.find("meta", property="og:title")
        if not tag or not tag.get("content"):
            return None
        title = tag["content"].strip()
        title = re.sub(r"\s+–\s+Letterboxd$", "", title, flags=re.IGNORECASE).strip()
        title = re.sub(r"\s+\([^)]*directed by[^)]*\)$", "", title, flags=re.IGNORECASE).strip()
        return title

    def enrich(self, listings: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
        if not listings:
            return []
        unique_films: Dict[Tuple[str, str], Dict[str, object]] = {}
        for listing in listings:
            original_title = (listing.get("movie_title") or listing.get("title") or "").strip()
            if not original_title:
                continue
            cleaned_title = clean_title(original_title)
            if not cleaned_title:
                continue
            year_from_listing = str(listing.get("year", "")).strip()
            year = (re.search(r"\b(19[7-9]\d|20[0-2]\d|203\d)\b", year_from_listing or "") or ["N/A"])[0]
            film_key = (cleaned_title, year)
            if film_key not in unique_films:
                unique_films[film_key] = {
                    "original_title": original_title,
                    "english_title": listing.get("movie_title_en"),
                    "director": listing.get("director"),
                    "country": listing.get("country"),
                }
        enrichment_map: Dict[Tuple[str, str], Dict[str, object]] = {}
        for (cleaned_title, year), film_info in unique_films.items():
            cache_key = f"{cleaned_title}|{'' if year == 'N/A' else year}|{film_info.get('director') or ''}"
            if cache_key in self.cache:
                enrichment_map[(cleaned_title, year)] = self.cache[cache_key]
                continue
            tmdb_result: Dict[str, object] = {}
            search_year = year if year != "N/A" else None
            english_title = film_info.get("english_title")
            if english_title:
                tmdb_result = self.search_tmdb(english_title, year=search_year)
            if not tmdb_result.get("id"):
                tmdb_result = self.search_tmdb(cleaned_title, year=search_year, language_code="ja-JP")
            if not tmdb_result.get("id") and self.gemini:
                alt_title = self.gemini.suggest_title(
                    cleaned_title,
                    film_info.get("original_title", ""),
                    year=search_year,
                    director=film_info.get("director"),
                    country=film_info.get("country"),
                )
                if alt_title:
                    time.sleep(self.settings.gemini_delay)
                    tmdb_result = self.search_tmdb(alt_title, year=search_year)
            if search_year and tmdb_result.get("id"):
                details = self._tmdb_get(
                    f"{TMDB_API_BASE_URL}/movie/{tmdb_result['id']}",
                    params={"api_key": self.settings.tmdb_api_key},
                )
                release_year = (details or {}).get("release_date", "").split("-")[0]
                if release_year and release_year != search_year:
                    tmdb_result = {}
            enrichment_map[(cleaned_title, year)] = tmdb_result
            self.cache[cache_key] = tmdb_result
        enriched_listings: List[Dict[str, object]] = []
        for listing in listings:
            listing_dict = dict(listing)
            original_title = (listing_dict.get("movie_title") or listing_dict.get("title") or "").strip()
            cleaned_title = clean_title(original_title)
            year_from_listing = str(listing_dict.get("year", "")).strip()
            year = (re.search(r"\b(19[7-9]\d|20[0-2]\d|203\d)\b", year_from_listing or "") or ["N/A"])[0]
            film_key = (cleaned_title, year)
            enriched = enrichment_map.get(film_key, {})
            if enriched.get("id"):
                listing_dict["letterboxd_link"] = f"{LETTERBOXD_TMDB_BASE_URL}{enriched['id']}"
                listing_dict["tmdb_display_title"] = enriched.get("tmdb_title")
                listing_dict["tmdb_original_title"] = enriched.get("tmdb_original_title")
                letterboxd_title = enriched.get("letterboxd_english_title")
                if not letterboxd_title:
                    letterboxd_title = self._letterboxd_title(int(enriched["id"]))
                    if letterboxd_title:
                        enriched["letterboxd_english_title"] = letterboxd_title
                        time.sleep(self.settings.letterboxd_delay)
                if letterboxd_title:
                    listing_dict["letterboxd_english_title"] = letterboxd_title
            enriched_listings.append(listing_dict)
        self.settings.save_tmdb_cache(dict(self.cache))
        return enriched_listings
