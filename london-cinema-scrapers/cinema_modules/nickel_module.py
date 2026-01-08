#!/usr/bin/env python3
# nickel_module.py
# Scraper for The Nickel, Clerkenwell (grindhouse cinema)
# https://thenickel.co.uk/

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://thenickel.co.uk"
SCHEDULE_URL = BASE_URL  # Main page often has schedule for small venues
CINEMA_NAME = "The Nickel"

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
    """Parse UK date formats."""
    date_str = date_str.strip()
    date_str = re.sub(r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s*", "", date_str, flags=re.IGNORECASE)

    formats = [
        "%d %B %Y", "%d %B", "%d %b %Y", "%d %b",
        "%Y-%m-%d", "%d/%m/%Y", "%d/%m",
    ]

    current_year = dt.date.today().year

    for fmt in formats:
        try:
            parsed = dt.datetime.strptime(date_str.strip(), fmt)
            if "%Y" not in fmt:
                parsed = parsed.replace(year=current_year)
            return parsed.date()
        except ValueError:
            continue
    return None


def _parse_time(time_str: str) -> Optional[str]:
    """Parse time and return in HH:MM format."""
    time_str = time_str.strip().upper()

    match_24 = re.match(r"(\d{1,2}):(\d{2})", time_str)
    if match_24:
        return f"{int(match_24.group(1)):02d}:{match_24.group(2)}"

    match_12 = re.match(r"(\d{1,2})[:\.](\d{2})\s*(AM|PM)", time_str)
    if match_12:
        hour = int(match_12.group(1))
        minute = int(match_12.group(2))
        if match_12.group(3) == "PM" and hour != 12:
            hour += 12
        elif match_12.group(3) == "AM" and hour == 12:
            hour = 0
        return f"{hour:02d}:{minute:02d}"

    return None


def scrape_nickel() -> List[Dict]:
    """
    Scrape The Nickel showtimes.
    """
    shows = []

    try:
        session = requests.Session()
        resp = session.get(SCHEDULE_URL, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # TODO: Analyze actual page structure and update selectors
        # The Nickel likely lists upcoming screenings on their main page

        listings = soup.select(".film, .screening, .event, .showing, article")

        for listing in listings:
            title_elem = listing.select_one(".title, h3, h4, .film-title, a")
            if not title_elem:
                continue

            title = _clean(title_elem.get_text())
            if not title or len(title) < 2:
                continue

            # Extract date and time - update based on actual structure
            # ...

        if not shows:
            print(f"[{CINEMA_NAME}] Note: No shows found. Page structure needs analysis.", file=sys.stderr)

    except requests.RequestException as e:
        print(f"[{CINEMA_NAME}] HTTP Error: {e}", file=sys.stderr)
        raise
    except Exception as e:
        print(f"[{CINEMA_NAME}] Error: {e}", file=sys.stderr)
        raise

    return shows


if __name__ == "__main__":
    data = scrape_nickel()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"\nTotal: {len(data)} showings")
