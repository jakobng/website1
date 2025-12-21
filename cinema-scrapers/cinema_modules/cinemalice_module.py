#!/usr/bin/env python3
# cinemalice_module.py — Rev-1 (2025-12-21)
#
# Scraper for シネマリス (CineMalice) - https://cinemalice.theater/
# A new mini-theater in Tokyo that opened December 2025.
#
# This cinema displays movie schedule with date ranges (releaseDateFrom/To)
# rather than specific daily showtimes. The scraper extracts movies and
# generates entries for each day within the screening period.
# ---------------------------------------------------------------------

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from html import unescape
from typing import Dict, List, Optional

import requests

CINEMA_NAME = "シネマリス"
BASE_URL = "https://cinemalice.theater"
SCHEDULE_URL = f"{BASE_URL}/schedules"
HEADERS = {"User-Agent": "Mozilla/5.0 (CineMaliceScraper/2025)"}
TIMEOUT = 30

TODAY = dt.date.today()
WINDOW_DAYS = 7

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _fetch_page(url: str) -> Optional[str]:
    """Fetch page HTML content."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        resp.encoding = 'utf-8'
        return resp.text
    except requests.RequestException as e:
        print(f"ERROR: [{CINEMA_NAME}] Could not fetch {url}: {e}", file=sys.stderr)
        return None


def _extract_screenings_data(html: str) -> List[Dict]:
    """
    Extract movie data from the React Server Component payload.
    The data is embedded as escaped JSON in the page.
    """
    # Find cmsScreeningsData array in the RSC payload
    idx = html.find('cmsScreeningsData')
    if idx == -1:
        print(f"ERROR: [{CINEMA_NAME}] Could not find cmsScreeningsData in page", file=sys.stderr)
        return []

    chunk = html[idx:idx+100000]  # Get a large enough chunk

    # The data is escaped with \" sequences - we need to handle both escaped and unescaped forms
    # First, try to extract with escaped quotes pattern
    movies = []

    # Pattern for escaped JSON (\"field\":\"value\")
    escaped_pattern = True
    if '\\"title\\"' in chunk:
        escaped_pattern = True
    elif '"title"' in chunk:
        escaped_pattern = False

    if escaped_pattern:
        # Extract with escaped quote patterns
        title_matches = re.findall(r'\\"title\\":\\"([^\\]+)\\"', chunk)
        director_matches = re.findall(r'\\"director\\":\\"([^\\]*)\\"', chunk)
        runtime_matches = re.findall(r'\\"screeningTimes\\":\\"([^\\]*)\\"', chunk)
        date_from_matches = re.findall(r'\\"releaseDateFrom\\":\\"([^\\]+)\\"', chunk)
        date_to_matches = re.findall(r'\\"releaseDateTo\\":\\"([^\\]+)\\"', chunk)
        cast_matches = re.findall(r'\\"cast\\":\\"([^\\]*)\\"', chunk)
        website_matches = re.findall(r'\\"website\\":\\"([^\\]*)\\"', chunk)
        slug_matches = re.findall(r'\\"slug\\":\\"([^\\]+)\\"', chunk)
    else:
        # Extract with normal quote patterns
        title_matches = re.findall(r'"title":"([^"]+)"', chunk)
        director_matches = re.findall(r'"director":"([^"]*)"', chunk)
        runtime_matches = re.findall(r'"screeningTimes":"([^"]*)"', chunk)
        date_from_matches = re.findall(r'"releaseDateFrom":"([^"]+)"', chunk)
        date_to_matches = re.findall(r'"releaseDateTo":"([^"]+)"', chunk)
        cast_matches = re.findall(r'"cast":"([^"]*)"', chunk)
        website_matches = re.findall(r'"website":"([^"]*)"', chunk)
        slug_matches = re.findall(r'"slug":"([^"]+)"', chunk)

    # Build movie objects by matching indices
    # Note: Some fields appear multiple times in nested objects, so we need to be careful
    # The title field is unique per movie, so we use it as the anchor
    for i, title in enumerate(title_matches):
        movie = {'title': title}

        if i < len(director_matches):
            movie['director'] = director_matches[i]

        if i < len(runtime_matches):
            movie['runtime'] = runtime_matches[i]

        if i < len(date_from_matches):
            movie['date_from'] = date_from_matches[i]

        if i < len(date_to_matches):
            movie['date_to'] = date_to_matches[i]

        if i < len(cast_matches):
            movie['cast'] = cast_matches[i]

        if i < len(website_matches):
            movie['website'] = website_matches[i]

        if i < len(slug_matches):
            movie['slug'] = slug_matches[i]

        # Note: Synopsis is not extracted here as it's in complex HTML format
        # and will be enriched by TMDB later

        movies.append(movie)

    return movies


def _parse_runtime(runtime_str: str) -> Optional[str]:
    """Extract numeric runtime from string like '106分'."""
    if not runtime_str:
        return None
    match = re.search(r'(\d+)', runtime_str)
    return match.group(1) if match else None


def _generate_daily_entries(movie: Dict) -> List[Dict]:
    """
    Generate showtime entries for each day within the movie's screening period.
    Since CineMalice doesn't provide specific showtimes, we create one entry
    per day with showtime marked as 'スケジュール確認' (check schedule).
    """
    entries = []

    if 'date_from' not in movie or 'date_to' not in movie:
        return entries

    try:
        date_from = dt.date.fromisoformat(movie['date_from'])
        date_to = dt.date.fromisoformat(movie['date_to'])
    except ValueError:
        return entries

    # Only include dates within our window (today + WINDOW_DAYS)
    window_end = TODAY + dt.timedelta(days=WINDOW_DAYS)

    current_date = max(date_from, TODAY)
    end_date = min(date_to, window_end)

    while current_date <= end_date:
        entry = {
            "cinema_name": CINEMA_NAME,
            "movie_title": movie.get('title', ''),
            "movie_title_en": "",
            "date_text": current_date.isoformat(),
            "showtime": "スケジュール確認",  # "Check schedule" - cinema doesn't provide specific times
            "director": movie.get('director', ''),
            "year": "",
            "country": "",
            "runtime_min": _parse_runtime(movie.get('runtime', '')),
            "synopsis": "",  # Will be filled by TMDB enrichment
            "detail_page_url": movie.get('website', '') or f"{BASE_URL}/movie/{movie.get('slug', '')}",
        }
        entries.append(entry)
        current_date += dt.timedelta(days=1)

    return entries


# ---------------------------------------------------------------------
# Main scraper
# ---------------------------------------------------------------------

def scrape_cinemalice(max_days: int = 7) -> List[Dict[str, str]]:
    """
    Scrape シネマリス (CineMalice) schedule.

    Returns a list of showtime dictionaries with standard schema.
    """
    global WINDOW_DAYS
    WINDOW_DAYS = max_days

    html = _fetch_page(SCHEDULE_URL)
    if not html:
        return []

    movies = _extract_screenings_data(html)
    if not movies:
        print(f"WARNING: [{CINEMA_NAME}] No movies found in schedule", file=sys.stderr)
        return []

    all_entries = []
    for movie in movies:
        entries = _generate_daily_entries(movie)
        all_entries.extend(entries)

    # Deduplicate (same movie, same date)
    seen = set()
    unique_entries = []
    for entry in all_entries:
        key = (entry["movie_title"], entry["date_text"])
        if key not in seen:
            seen.add(key)
            unique_entries.append(entry)

    # Sort by date, then title
    unique_entries.sort(key=lambda x: (x.get("date_text", ""), x.get("movie_title", "")))

    return unique_entries


# ---------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------

if __name__ == "__main__":
    import json as json_module
    from pathlib import Path

    showings = scrape_cinemalice()
    if showings:
        out_path = Path(__file__).with_name("cinemalice_schedule_TEST.json")
        out_path.write_text(json_module.dumps(showings, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Test run successful. Saved {len(showings)} showtimes → {out_path}")
    else:
        print("No showtimes found.")
