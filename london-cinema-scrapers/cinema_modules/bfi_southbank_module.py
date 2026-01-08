#!/usr/bin/env python3
# bfi_southbank_module.py
# Scraper for BFI Southbank cinema
# https://whatson.bfi.org.uk/

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# BFI uses whatson.bfi.org.uk for their schedule
BASE_URL = "https://whatson.bfi.org.uk"
SCHEDULE_URL = f"{BASE_URL}/Online/default.asp"
CINEMA_NAME = "BFI Southbank"

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


def _parse_date(date_str: str) -> Optional[dt.date]:
    """Parse various UK date formats."""
    # Try different date formats
    formats = [
        "%d %B %Y",      # 15 January 2025
        "%d %b %Y",      # 15 Jan 2025
        "%Y-%m-%d",      # 2025-01-15
        "%d/%m/%Y",      # 15/01/2025
    ]

    for fmt in formats:
        try:
            return dt.datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue

    return None


def _parse_time(time_str: str) -> Optional[str]:
    """Parse time and return in HH:MM format."""
    time_str = time_str.strip().upper()

    # Handle 12-hour format with AM/PM
    match = re.match(r"(\d{1,2})[:\.]?(\d{2})?\s*(AM|PM)?", time_str)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        period = match.group(3)

        if period == "PM" and hour != 12:
            hour += 12
        elif period == "AM" and hour == 12:
            hour = 0

        return f"{hour:02d}:{minute:02d}"

    return None


def scrape_bfi_southbank() -> List[Dict]:
    """
    Scrape BFI Southbank showtimes.

    Returns a list of showtime records with standard schema:
    - cinema_name: str
    - movie_title: str
    - date_text: str (YYYY-MM-DD)
    - showtime: str (HH:MM)
    - detail_page_url: str
    - director: str (optional)
    - year: str (optional)
    - country: str (optional)
    - runtime_min: str (optional)
    - synopsis: str (optional)
    - movie_title_en: str (optional, same as movie_title for UK)
    """
    shows = []

    try:
        # BFI's schedule page may require session handling or specific parameters
        session = requests.Session()

        # First, try to get the main schedule page
        resp = session.get(SCHEDULE_URL, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # TODO: The BFI website structure needs to be analyzed.
        # They use a proprietary ASP.NET-based system.
        # Common patterns to look for:
        # - Calendar/date navigation
        # - Film listing cards or table rows
        # - Links to individual film pages

        # Look for film listings - these selectors need to be updated
        # based on actual page structure

        # Example structure parsing (placeholder):
        listings = soup.select(".film-listing, .event-item, .showing")

        for listing in listings:
            # Extract title
            title_elem = listing.select_one(".title, h3, h4, .film-title")
            if not title_elem:
                continue

            title = _clean(title_elem.get_text())

            # Extract date
            date_elem = listing.select_one(".date, .showing-date, time")
            date_str = date_elem.get_text() if date_elem else ""
            show_date = _parse_date(date_str)

            if not show_date:
                continue

            # Only include dates within our window
            if not (TODAY <= show_date < TODAY + dt.timedelta(days=WINDOW_DAYS)):
                continue

            # Extract time
            time_elem = listing.select_one(".time, .showing-time")
            time_str = time_elem.get_text() if time_elem else ""
            show_time = _parse_time(time_str)

            if not show_time:
                continue

            # Extract link to detail page
            link_elem = listing.select_one("a[href]")
            detail_url = ""
            if link_elem and link_elem.get("href"):
                detail_url = urljoin(BASE_URL, link_elem["href"])

            shows.append({
                "cinema_name": CINEMA_NAME,
                "movie_title": title,
                "movie_title_en": title,  # Same for UK cinema
                "date_text": show_date.isoformat(),
                "showtime": show_time,
                "detail_page_url": detail_url,
                "director": "",
                "year": "",
                "country": "",
                "runtime_min": "",
                "synopsis": "",
            })

        # If no shows found with default selectors, the page structure
        # likely differs - this is expected for first run
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
    data = scrape_bfi_southbank()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"\nTotal: {len(data)} showings")
