#!/usr/bin/env python3
# prince_charles_module.py
# Scraper for Prince Charles Cinema, Leicester Square
# https://princecharlescinema.com/

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://princecharlescinema.com"
SCHEDULE_URL = f"{BASE_URL}/next-7-days/"
CINEMA_NAME = "Prince Charles Cinema"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}
TIMEOUT = 30

TODAY = dt.date.today()
WINDOW_DAYS = 7


def _clean(text: str) -> str:
    """Clean whitespace and normalize text."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip())


def _parse_uk_date(date_str: str) -> Optional[dt.date]:
    """
    Parse UK date formats commonly used on cinema websites.
    Examples: "Wednesday 15 January", "15 Jan 2025", "15/01/2025"
    """
    date_str = date_str.strip()

    # Remove day name if present
    date_str = re.sub(r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s*", "", date_str, flags=re.IGNORECASE)

    # Try different formats
    formats = [
        "%d %B %Y",      # 15 January 2025
        "%d %B",         # 15 January (assume current year)
        "%d %b %Y",      # 15 Jan 2025
        "%d %b",         # 15 Jan (assume current year)
        "%Y-%m-%d",      # 2025-01-15
        "%d/%m/%Y",      # 15/01/2025
        "%d/%m",         # 15/01 (assume current year)
    ]

    current_year = dt.date.today().year

    for fmt in formats:
        try:
            parsed = dt.datetime.strptime(date_str.strip(), fmt)
            # If year not in format, use current year
            if "%Y" not in fmt:
                parsed = parsed.replace(year=current_year)
            return parsed.date()
        except ValueError:
            continue

    return None


def _parse_time(time_str: str) -> Optional[str]:
    """Parse time and return in HH:MM format."""
    time_str = time_str.strip().upper()

    # Handle 24-hour format (18:30)
    match_24 = re.match(r"(\d{1,2}):(\d{2})", time_str)
    if match_24:
        hour = int(match_24.group(1))
        minute = int(match_24.group(2))
        return f"{hour:02d}:{minute:02d}"

    # Handle 12-hour format with AM/PM (6:30pm, 6.30 PM)
    match_12 = re.match(r"(\d{1,2})[:\.](\d{2})\s*(AM|PM)", time_str)
    if match_12:
        hour = int(match_12.group(1))
        minute = int(match_12.group(2))
        period = match_12.group(3)

        if period == "PM" and hour != 12:
            hour += 12
        elif period == "AM" and hour == 12:
            hour = 0

        return f"{hour:02d}:{minute:02d}"

    return None


def _extract_film_metadata(detail_url: str) -> Dict:
    """
    Fetch film detail page and extract metadata.
    Returns dict with director, year, runtime_min, synopsis.
    """
    defaults = {
        "director": "",
        "year": "",
        "runtime_min": "",
        "synopsis": "",
    }

    if not detail_url:
        return defaults

    try:
        resp = requests.get(detail_url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Look for common metadata patterns
        # Director
        director_match = soup.find(string=re.compile(r"Director", re.I))
        if director_match:
            parent = director_match.find_parent()
            if parent:
                text = parent.get_text()
                match = re.search(r"Director[:\s]+([^,\n]+)", text, re.I)
                if match:
                    defaults["director"] = _clean(match.group(1))

        # Year - look for 4-digit year in parens or metadata
        year_match = re.search(r"\b(19\d{2}|20\d{2})\b", soup.get_text())
        if year_match:
            defaults["year"] = year_match.group(1)

        # Runtime - look for "X mins" or "X minutes"
        runtime_match = re.search(r"(\d+)\s*(?:mins?|minutes?)", soup.get_text(), re.I)
        if runtime_match:
            defaults["runtime_min"] = runtime_match.group(1)

        # Synopsis - look for description/synopsis section
        synopsis_elem = soup.select_one(".synopsis, .description, .film-description, [class*='synopsis']")
        if synopsis_elem:
            defaults["synopsis"] = _clean(synopsis_elem.get_text())[:500]

    except Exception as e:
        print(f"[{CINEMA_NAME}] Error fetching detail page {detail_url}: {e}", file=sys.stderr)

    return defaults


def scrape_prince_charles() -> List[Dict]:
    """
    Scrape Prince Charles Cinema showtimes.

    Returns a list of showtime records with standard schema.
    """
    shows = []
    meta_cache = {}

    try:
        session = requests.Session()
        resp = session.get(SCHEDULE_URL, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Prince Charles Cinema "Next 7 Days" page structure
        # Look for film/event listings grouped by date

        # Try common listing patterns
        # Pattern 1: Date headers with film listings underneath
        date_sections = soup.select(".date-section, .day-listings, [class*='schedule']")

        if date_sections:
            for section in date_sections:
                # Find date header
                date_elem = section.select_one(".date, h2, h3, .day-header")
                if not date_elem:
                    continue

                section_date = _parse_uk_date(date_elem.get_text())
                if not section_date:
                    continue

                if not (TODAY <= section_date < TODAY + dt.timedelta(days=WINDOW_DAYS)):
                    continue

                # Find film listings in this section
                films = section.select(".film, .event, .showing, li")
                for film in films:
                    title_elem = film.select_one(".title, .film-title, h4, a")
                    if not title_elem:
                        continue

                    title = _clean(title_elem.get_text())
                    if not title or len(title) < 2:
                        continue

                    # Get link
                    link = film.select_one("a[href]")
                    detail_url = ""
                    if link and link.get("href"):
                        detail_url = urljoin(BASE_URL, link["href"])

                    # Get showtimes
                    time_elems = film.select(".time, .showtime, time")
                    times = []
                    for te in time_elems:
                        parsed_time = _parse_time(te.get_text())
                        if parsed_time:
                            times.append(parsed_time)

                    # If no specific time elements, look for time patterns in text
                    if not times:
                        text = film.get_text()
                        time_matches = re.findall(r"\b(\d{1,2}[:\.]?\d{2}\s*(?:AM|PM)?)\b", text, re.I)
                        for tm in time_matches:
                            parsed = _parse_time(tm)
                            if parsed:
                                times.append(parsed)

                    # Get metadata (cached by detail URL)
                    if detail_url and detail_url not in meta_cache:
                        meta_cache[detail_url] = _extract_film_metadata(detail_url)

                    metadata = meta_cache.get(detail_url, {})

                    # Create a showing entry for each time
                    for show_time in times:
                        shows.append({
                            "cinema_name": CINEMA_NAME,
                            "movie_title": title,
                            "movie_title_en": title,
                            "date_text": section_date.isoformat(),
                            "showtime": show_time,
                            "detail_page_url": detail_url,
                            "director": metadata.get("director", ""),
                            "year": metadata.get("year", ""),
                            "country": "",
                            "runtime_min": metadata.get("runtime_min", ""),
                            "synopsis": metadata.get("synopsis", ""),
                        })

        # Pattern 2: Flat list of showings with embedded date/time
        if not shows:
            listings = soup.select(".film-listing, .screening, .event-item, article")

            for listing in listings:
                title_elem = listing.select_one(".title, h3, h4, .film-title, a")
                if not title_elem:
                    continue

                title = _clean(title_elem.get_text())
                if not title or len(title) < 2:
                    continue

                # Look for date and time in listing
                text = listing.get_text()

                # Extract date
                date_match = re.search(
                    r"(\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*(?:\s+\d{4})?)",
                    text, re.I
                )
                show_date = None
                if date_match:
                    show_date = _parse_uk_date(date_match.group(1))

                if not show_date:
                    continue

                if not (TODAY <= show_date < TODAY + dt.timedelta(days=WINDOW_DAYS)):
                    continue

                # Extract times
                time_matches = re.findall(r"\b(\d{1,2}[:\.]?\d{2}\s*(?:AM|PM)?)\b", text, re.I)
                times = [_parse_time(tm) for tm in time_matches]
                times = [t for t in times if t]

                if not times:
                    continue

                # Get link
                link = listing.select_one("a[href]")
                detail_url = ""
                if link and link.get("href"):
                    detail_url = urljoin(BASE_URL, link["href"])

                for show_time in times:
                    shows.append({
                        "cinema_name": CINEMA_NAME,
                        "movie_title": title,
                        "movie_title_en": title,
                        "date_text": show_date.isoformat(),
                        "showtime": show_time,
                        "detail_page_url": detail_url,
                        "director": "",
                        "year": "",
                        "country": "",
                        "runtime_min": "",
                        "synopsis": "",
                    })

        if not shows:
            print(f"[{CINEMA_NAME}] Note: No shows found. Page structure may need analysis.", file=sys.stderr)
            print(f"[{CINEMA_NAME}] URL: {SCHEDULE_URL}", file=sys.stderr)

    except requests.RequestException as e:
        print(f"[{CINEMA_NAME}] HTTP Error: {e}", file=sys.stderr)
        raise
    except Exception as e:
        print(f"[{CINEMA_NAME}] Error: {e}", file=sys.stderr)
        raise

    # Deduplicate
    seen = set()
    unique_shows = []
    for s in shows:
        key = (s["movie_title"], s["date_text"], s["showtime"])
        if key not in seen:
            seen.add(key)
            unique_shows.append(s)

    return sorted(unique_shows, key=lambda x: (x["date_text"], x["showtime"], x["movie_title"]))


if __name__ == "__main__":
    data = scrape_prince_charles()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"\nTotal: {len(data)} showings")
