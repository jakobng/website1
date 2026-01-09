#!/usr/bin/env python3
# ica_module.py
# Scraper for ICA (Institute of Contemporary Arts) Cinema
# https://www.ica.art/films
#
# Structure: Film listings on /films, detail pages contain individual showtimes
# Showtimes displayed as plain text: "01:45 pm" | "Fri, 09 Jan 2026" | "Cinema 2"

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.ica.art"
FILMS_URL = f"{BASE_URL}/films"
CINEMA_NAME = "ICA Cinema"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}
TIMEOUT = 30

TODAY = dt.date.today()
WINDOW_DAYS = 14


def _clean(text: str) -> str:
    """Clean whitespace and normalize text."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip())


def _parse_uk_date(date_str: str) -> Optional[dt.date]:
    """
    Parse UK date formats like "Fri, 09 Jan 2026", "9 January 2026", "09 Jan".
    Returns date object or None if parsing fails.
    """
    date_str = date_str.strip()

    # Remove day name prefix if present (e.g., "Fri, ")
    date_str = re.sub(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s*", "", date_str, flags=re.IGNORECASE)

    # Remove ordinal suffixes (1st, 2nd, 3rd, 4th, etc.)
    date_str = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", date_str)

    current_year = dt.date.today().year

    # Try various formats
    formats = [
        "%d %B %Y",      # 9 January 2026
        "%d %b %Y",      # 09 Jan 2026
        "%d %B",         # 9 January (assume current/next year)
        "%d %b",         # 09 Jan
        "%Y-%m-%d",      # 2026-01-09
    ]

    for fmt in formats:
        try:
            parsed = dt.datetime.strptime(date_str.strip(), fmt)
            # If no year in format, determine year
            if "%Y" not in fmt:
                parsed = parsed.replace(year=current_year)
                if parsed.date() < TODAY - dt.timedelta(days=30):
                    parsed = parsed.replace(year=current_year + 1)
            return parsed.date()
        except ValueError:
            continue

    return None


def _parse_time_12h(time_str: str) -> Optional[str]:
    """
    Parse 12-hour time format like "1:45 pm", "6.20pm", "6:20 pm".
    Returns 24-hour format string "HH:MM" or None.
    """
    time_str = time_str.strip().lower()

    # Handle both : and . as separators
    # Match patterns like "1:45 pm", "6.20pm", "12:00 am"
    match = re.match(r"(\d{1,2})[:\.](\d{2})\s*(am|pm)", time_str)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        period = match.group(3)

        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0

        return f"{hour:02d}:{minute:02d}"

    # Also try without minutes (e.g., "2pm")
    match = re.match(r"(\d{1,2})\s*(am|pm)", time_str)
    if match:
        hour = int(match.group(1))
        period = match.group(2)

        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0

        return f"{hour:02d}:00"

    return None


def _extract_screenings_from_detail_page(soup: BeautifulSoup, film_title: str, detail_url: str) -> List[Dict]:
    """
    Extract individual screenings from a film detail page.
    Screenings are typically shown as: time | date | venue
    """
    shows = []

    # Get the full page text for pattern matching
    page_text = soup.get_text()

    # Look for screening patterns in the text
    # Pattern: time (1:45 pm) followed by date (Fri, 09 Jan 2026) and optionally venue (Cinema 2)
    # Multiple screenings may be listed

    # Try to find screening blocks - they often appear in a structured section
    # Look for common patterns

    # Pattern 1: Look for links with "Book tickets" near time/date info
    book_links = soup.find_all("a", string=re.compile(r"book\s*tickets?", re.I))

    # Pattern 2: Look for time patterns in the page
    time_pattern = re.compile(r"(\d{1,2}[:\.]?\d{2}\s*(?:am|pm))", re.I)
    date_pattern = re.compile(r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s*\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*\d{4}", re.I)

    # Find all time matches and nearby dates
    times_found = time_pattern.findall(page_text)
    dates_found = date_pattern.findall(page_text)

    # Try to pair times with dates
    # Look for screening info blocks
    screening_blocks = []

    # Method 1: Look for structured screening elements
    # ICA may use various selectors for screenings
    for selector in [".screening", ".showtime", ".performance", ".event-time",
                     "[class*='screening']", "[class*='showtime']", "li", "p"]:
        elements = soup.select(selector)
        for elem in elements:
            text = elem.get_text()
            time_match = time_pattern.search(text)
            date_match = date_pattern.search(text)

            if time_match and date_match:
                screening_blocks.append({
                    "time_str": time_match.group(1),
                    "date_str": date_match.group(0),
                    "venue": "",
                    "text": text
                })

    # Method 2: Parse adjacent text patterns
    # Look for lines containing both time and date
    lines = page_text.split("\n")
    for line in lines:
        line = line.strip()
        time_match = time_pattern.search(line)
        date_match = date_pattern.search(line)

        if time_match and date_match:
            # Check if we already have this
            existing = any(
                b["time_str"] == time_match.group(1) and b["date_str"] == date_match.group(0)
                for b in screening_blocks
            )
            if not existing:
                # Try to extract venue (Cinema 1, Cinema 2, etc.)
                venue_match = re.search(r"(Cinema\s*\d+|Theatre)", line, re.I)
                screening_blocks.append({
                    "time_str": time_match.group(1),
                    "date_str": date_match.group(0),
                    "venue": venue_match.group(1) if venue_match else "",
                    "text": line
                })

    # If no structured screenings found, try a broader search
    if not screening_blocks:
        # Look for any pairing of time and date in proximity
        # This is a fallback for less structured pages
        for i, time_str in enumerate(times_found):
            if i < len(dates_found):
                screening_blocks.append({
                    "time_str": time_str,
                    "date_str": dates_found[i],
                    "venue": "",
                    "text": ""
                })

    # Convert screening blocks to show records
    for block in screening_blocks:
        parsed_time = _parse_time_12h(block["time_str"])
        parsed_date = _parse_uk_date(block["date_str"])

        if not parsed_time or not parsed_date:
            continue

        # Check if within date window
        if not (TODAY <= parsed_date < TODAY + dt.timedelta(days=WINDOW_DAYS)):
            continue

        shows.append({
            "cinema_name": CINEMA_NAME,
            "movie_title": film_title,
            "movie_title_en": film_title,
            "date_text": parsed_date.isoformat(),
            "showtime": parsed_time,
            "detail_page_url": detail_url,
            "booking_url": "",
            "venue": block.get("venue", ""),
            "director": "",
            "year": "",
            "country": "",
            "runtime_min": "",
            "synopsis": "",
        })

    return shows


def _get_film_listings(session: requests.Session) -> List[dict]:
    """
    Fetch the main films page and extract film listings.
    Returns list of dicts with title, url, date_range.
    """
    films = []

    resp = session.get(FILMS_URL, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Look for film items
    # ICA uses .item elements with links to film pages
    items = soup.select(".item a[href*='/films/']")

    seen_urls = set()
    for item in items:
        href = item.get("href", "")
        if not href or href in seen_urls:
            continue

        # Skip non-film links (like /films itself)
        if href == "/films" or href == "/films/":
            continue

        seen_urls.add(href)
        url = urljoin(BASE_URL, href)

        # Try to get title
        title_elem = item.select_one(".title")
        if title_elem:
            title = _clean(title_elem.get_text())
        else:
            title = _clean(item.get_text())

        # Try to get date range
        date_elem = item.select_one(".date")
        date_range = _clean(date_elem.get_text()) if date_elem else ""

        if title:
            films.append({
                "title": title,
                "url": url,
                "date_range": date_range,
            })

    # Also look for broader item patterns
    if not films:
        for item in soup.select("a[href*='/films/']"):
            href = item.get("href", "")
            if not href or href in seen_urls or href in ["/films", "/films/"]:
                continue

            seen_urls.add(href)
            url = urljoin(BASE_URL, href)
            title = _clean(item.get_text())

            if title and len(title) > 2:
                films.append({
                    "title": title,
                    "url": url,
                    "date_range": "",
                })

    return films


def scrape_ica() -> List[Dict]:
    """
    Scrape ICA Cinema showtimes.

    Process:
    1. Fetch main /films page to get list of current films
    2. For each film, visit detail page to extract individual showtimes

    Returns a list of showtime records with standard schema:
    - cinema_name: str
    - movie_title: str
    - date_text: str (YYYY-MM-DD)
    - showtime: str (HH:MM)
    - detail_page_url: str
    - director, year, country, runtime_min, synopsis: str (optional)
    """
    shows = []

    try:
        session = requests.Session()

        # Get list of films
        film_listings = _get_film_listings(session)
        print(f"[{CINEMA_NAME}] Found {len(film_listings)} film listings", file=sys.stderr)

        if not film_listings:
            print(f"[{CINEMA_NAME}] Warning: No film listings found on main page", file=sys.stderr)
            return []

        # Visit each film's detail page to get showtimes
        for film in film_listings[:30]:  # Limit to avoid too many requests
            title = film["title"]
            url = film["url"]

            try:
                resp = session.get(url, headers=HEADERS, timeout=TIMEOUT)
                resp.raise_for_status()

                soup = BeautifulSoup(resp.text, "html.parser")
                film_shows = _extract_screenings_from_detail_page(soup, title, url)

                if film_shows:
                    print(f"[{CINEMA_NAME}] Found {len(film_shows)} screenings for '{title}'", file=sys.stderr)
                    shows.extend(film_shows)

            except requests.RequestException as e:
                print(f"[{CINEMA_NAME}] Error fetching {url}: {e}", file=sys.stderr)
                continue
            except Exception as e:
                print(f"[{CINEMA_NAME}] Error processing {title}: {e}", file=sys.stderr)
                continue

        print(f"[{CINEMA_NAME}] Total: {len(shows)} showings found", file=sys.stderr)

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
    data = scrape_ica()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"\n[INFO] Total: {len(data)} showings", file=sys.stderr)
