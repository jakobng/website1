#!/usr/bin/env python3
# prince_charles_module.py
# Scraper for Prince Charles Cinema, Leicester Square
# https://princecharlescinema.com/
#
# Structure: WordPress site with jacro-plugin
# Schedule page uses .jacro-event elements with nested date/time listings

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
SCHEDULE_URL = f"{BASE_URL}/whats-on/"
CINEMA_NAME = "Prince Charles Cinema"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}
TIMEOUT = 30

TODAY = dt.date.today()
WINDOW_DAYS = 14  # PCC shows listings far in advance


def _clean(text: str) -> str:
    """Clean whitespace and normalize text."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip())


def _parse_uk_date(date_str: str) -> Optional[dt.date]:
    """
    Parse UK date formats like "Thursday 8th January", "Friday 9th January".
    Returns date object or None if parsing fails.
    """
    date_str = date_str.strip()

    # Remove ordinal suffixes (1st, 2nd, 3rd, 4th, etc.)
    date_str = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", date_str)

    # Remove day name if present
    date_str = re.sub(
        r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+",
        "",
        date_str,
        flags=re.IGNORECASE
    )

    current_year = dt.date.today().year

    # Try formats
    formats = [
        "%d %B",       # 8 January (assume current/next year)
        "%d %B %Y",    # 8 January 2025
        "%d %b",       # 8 Jan
        "%d %b %Y",    # 8 Jan 2025
    ]

    for fmt in formats:
        try:
            parsed = dt.datetime.strptime(date_str.strip(), fmt)
            # If no year in format, determine year
            if "%Y" not in fmt:
                # Assume current year, but if date is in the past, use next year
                parsed = parsed.replace(year=current_year)
                if parsed.date() < TODAY - dt.timedelta(days=30):
                    parsed = parsed.replace(year=current_year + 1)
            return parsed.date()
        except ValueError:
            continue

    return None


def _parse_time_12h(time_str: str) -> Optional[str]:
    """
    Parse 12-hour time format like "12:00 pm", "8:30 am".
    Returns 24-hour format string "HH:MM" or None.
    """
    time_str = time_str.strip().lower()

    # Match patterns like "12:00 pm", "8:30am", "6:15 pm"
    match = re.match(r"(\d{1,2}):(\d{2})\s*(am|pm)", time_str)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        period = match.group(3)

        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0

        return f"{hour:02d}:{minute:02d}"

    return None


# Note: Metadata extraction from PCC detail pages is unreliable.
# The main_scraper.py handles TMDB enrichment which provides better metadata.
# Keeping this function as a stub for potential future use.


def scrape_prince_charles() -> List[Dict]:
    """
    Scrape Prince Charles Cinema showtimes from their What's On page.

    Returns a list of showtime records with standard schema:
    - cinema_name: str
    - movie_title: str
    - date_text: str (YYYY-MM-DD)
    - showtime: str (HH:MM)
    - detail_page_url: str
    - format_tags: list (optional) - e.g., ["35mm", "4K"]

    Note: Director, year, runtime etc. are populated by TMDB enrichment in main_scraper.py
    """
    shows = []

    try:
        session = requests.Session()
        resp = session.get(SCHEDULE_URL, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Find all film event blocks
        events = soup.select(".jacro-event")
        print(f"[{CINEMA_NAME}] Found {len(events)} film listings", file=sys.stderr)

        for event in events:
            # Extract film title and detail URL
            film_link = None
            film_title = None

            for link in event.find_all("a"):
                href = link.get("href", "")
                text = link.get_text(strip=True)
                if "/film/" in href and text:
                    film_link = href
                    film_title = text
                    break

            if not film_title:
                continue

            # Parse performance list to extract date/time pairs
            perf_list = event.select_one(".performance-list-items")
            if not perf_list:
                continue

            current_date = None

            # Iterate through children to match dates with times
            for child in perf_list.children:
                if not hasattr(child, "name"):
                    continue

                # Date heading
                if child.name == "div" and "heading" in child.get("class", []):
                    date_text = child.get_text(strip=True)
                    parsed_date = _parse_uk_date(date_text)
                    if parsed_date:
                        current_date = parsed_date

                # Showtime entry
                elif child.name == "li" and current_date:
                    # Check if within our date window
                    if not (TODAY <= current_date < TODAY + dt.timedelta(days=WINDOW_DAYS)):
                        continue

                    # Extract time
                    time_elem = child.select_one(".time")
                    if not time_elem:
                        continue

                    time_str = time_elem.get_text(strip=True)
                    parsed_time = _parse_time_12h(time_str)
                    if not parsed_time:
                        continue

                    # Extract format tags (35mm, 4K, 70mm, etc.)
                    format_tags = []
                    tag_elems = child.select(".movietag .tag")
                    for tag in tag_elems:
                        tag_text = tag.get_text(strip=True)
                        if tag_text:
                            format_tags.append(tag_text)

                    # Extract booking URL
                    book_link = child.select_one("a.film_book_button")
                    booking_url = book_link.get("href", "") if book_link else ""

                    # Create showing record
                    shows.append({
                        "cinema_name": CINEMA_NAME,
                        "movie_title": film_title,
                        "movie_title_en": film_title,
                        "date_text": current_date.isoformat(),
                        "showtime": parsed_time,
                        "detail_page_url": film_link or "",
                        "booking_url": booking_url,
                        "director": "",
                        "year": "",
                        "country": "",
                        "runtime_min": "",
                        "synopsis": "",
                        "format_tags": format_tags,
                    })

        print(f"[{CINEMA_NAME}] Found {len(shows)} showings", file=sys.stderr)

    except requests.RequestException as e:
        print(f"[{CINEMA_NAME}] HTTP Error: {e}", file=sys.stderr)
        raise
    except Exception as e:
        print(f"[{CINEMA_NAME}] Error: {e}", file=sys.stderr)
        raise

    # Deduplicate (shouldn't happen but just in case)
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
    print(f"\n[INFO] Total: {len(data)} showings", file=sys.stderr)
