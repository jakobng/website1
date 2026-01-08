#!/usr/bin/env python3
# bfi_southbank_module.py
# Scraper for BFI Southbank cinema
# https://whatson.bfi.org.uk/
#
# Structure: BFI embeds showtime data as a JavaScript array in the page.
# We extract this array and parse it to get film listings.

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from typing import Dict, List, Optional
from urllib.parse import urljoin

try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False
    import requests

from bs4 import BeautifulSoup

BASE_URL = "https://whatson.bfi.org.uk"
SCHEDULE_URL = f"{BASE_URL}/Online/default.asp"
CINEMA_NAME = "BFI Southbank"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-GB,en;q=0.9,en-US;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
    "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}
TIMEOUT = 30

TODAY = dt.date.today()
WINDOW_DAYS = 14


def _clean(text: str) -> str:
    """Clean whitespace and normalize text."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip())


def _parse_bfi_date(date_str: str) -> Optional[dt.date]:
    """
    Parse BFI date format like "Friday 09 January 2026 18:10".
    Returns date object or None.
    """
    if not date_str:
        return None

    # Remove day name and time
    # Pattern: "DayName DD Month YYYY HH:MM"
    match = re.match(
        r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+(\d{1,2})\s+(\w+)\s+(\d{4})",
        date_str,
        re.I
    )

    if match:
        day = int(match.group(1))
        month_name = match.group(2)
        year = int(match.group(3))

        months = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12
        }

        month = months.get(month_name.lower())
        if month:
            try:
                return dt.date(year, month, day)
            except ValueError:
                pass

    return None


def _extract_js_array(html: str) -> List[List]:
    """
    Extract the JavaScript array containing showtime data from the page.
    The data is embedded as a large JS array in the page source.
    """
    # Look for the array pattern - it starts with [ and contains event entries
    # Each entry is an array starting with a GUID
    pattern = r'\[\s*\[\s*"[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}"'

    # Find where the array starts
    match = re.search(pattern, html, re.I)
    if not match:
        return []

    start_pos = match.start()

    # Now we need to find where the array ends - count brackets
    depth = 0
    end_pos = start_pos

    for i, char in enumerate(html[start_pos:], start_pos):
        if char == '[':
            depth += 1
        elif char == ']':
            depth -= 1
            if depth == 0:
                end_pos = i + 1
                break

    if end_pos <= start_pos:
        return []

    array_str = html[start_pos:end_pos]

    try:
        return json.loads(array_str)
    except json.JSONDecodeError:
        # Try to fix common issues
        # Replace single quotes with double quotes
        array_str = array_str.replace("'", '"')
        try:
            return json.loads(array_str)
        except json.JSONDecodeError:
            return []


def _is_film_screening(entry: List) -> bool:
    """
    Check if an entry is a film screening (not education, library, etc.)
    """
    if len(entry) < 5:
        return False

    # Check the programme type (index 3)
    programme = str(entry[3]).lower() if len(entry) > 3 else ""

    # Skip non-film events
    skip_programmes = ['education', 'library']
    for skip in skip_programmes:
        if skip in programme:
            return False

    # Check if title contains non-film keywords
    title = str(entry[5]).lower() if len(entry) > 5 else ""
    skip_titles = ['filmmakers club', 'library research', 'workshop', 'course']
    for skip in skip_titles:
        if skip in title:
            return False

    return True


def scrape_bfi_southbank() -> List[Dict]:
    """
    Scrape BFI Southbank showtimes.

    The BFI website embeds showtime data as a JavaScript array.
    Array structure (key indices):
    - [2]: Venue name (BFI Southbank)
    - [5]: Full title (with event info)
    - [6]: Short title
    - [7]: Full date string "Friday 09 January 2026 18:10"
    - [8]: Time "18:10"
    - [11]: Year
    - [17]: Tags (comma-separated: "70mm,Digital,David Lynch")
    - [18]: Detail page URL (relative)
    - [46]: Country (when present)
    """
    shows = []

    try:
        # Try curl first (most reliable for bypassing bot detection)
        import subprocess
        html_text = None

        try:
            result = subprocess.run(
                [
                    'curl', '-sL',
                    '-A', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    '-H', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    '-H', 'Accept-Language: en-GB,en;q=0.9',
                    '--compressed',
                    SCHEDULE_URL
                ],
                capture_output=True,
                text=True,
                timeout=TIMEOUT
            )
            if result.returncode == 0 and len(result.stdout) > 1000:
                html_text = result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Fallback to cloudscraper or requests
        if not html_text:
            if HAS_CLOUDSCRAPER:
                scraper = cloudscraper.create_scraper(
                    browser={
                        'browser': 'chrome',
                        'platform': 'windows',
                        'desktop': True
                    }
                )
                resp = scraper.get(SCHEDULE_URL, timeout=TIMEOUT)
            else:
                import requests
                session = requests.Session()
                resp = session.get(SCHEDULE_URL, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            html_text = resp.text

        # Extract the JavaScript array from the page
        entries = _extract_js_array(html_text)
        print(f"[{CINEMA_NAME}] Found {len(entries)} total entries", file=sys.stderr)

        for entry in entries:
            if not isinstance(entry, list) or len(entry) < 20:
                continue

            # Skip non-film events
            if not _is_film_screening(entry):
                continue

            # Check venue is BFI Southbank
            venue = str(entry[2]) if len(entry) > 2 else ""
            if "BFI Southbank" not in venue and "Southbank" not in venue:
                continue

            # Extract title - prefer short title [6], fallback to full title [5]
            short_title = _clean(str(entry[6])) if len(entry) > 6 else ""
            full_title = _clean(str(entry[5])) if len(entry) > 5 else ""
            title = short_title or full_title

            if not title:
                continue

            # Extract date
            date_str = str(entry[7]) if len(entry) > 7 else ""
            show_date = _parse_bfi_date(date_str)

            if not show_date:
                continue

            # Check if within our window
            if not (TODAY <= show_date < TODAY + dt.timedelta(days=WINDOW_DAYS)):
                continue

            # Extract time
            show_time = str(entry[8]) if len(entry) > 8 else ""
            if not re.match(r"\d{1,2}:\d{2}", show_time):
                continue

            # Normalize time to HH:MM
            time_parts = show_time.split(':')
            if len(time_parts) == 2:
                show_time = f"{int(time_parts[0]):02d}:{time_parts[1]}"

            # Extract tags (format info like 70mm, Digital, etc.)
            tags_str = str(entry[17]) if len(entry) > 17 else ""
            format_tags = [t.strip() for t in tags_str.split(',') if t.strip()]

            # Filter to relevant format tags
            format_keywords = ['70mm', '35mm', '4k', 'imax', 'digital', 'dolby', '3d']
            format_tags = [t for t in format_tags if any(kw in t.lower() for kw in format_keywords)]

            # Extract detail page URL
            detail_path = str(entry[18]) if len(entry) > 18 else ""
            detail_url = urljoin(BASE_URL + "/Online/", detail_path) if detail_path else ""

            # Extract country (around index 46)
            country = ""
            if len(entry) > 46 and entry[46]:
                country = _clean(str(entry[46]))

            shows.append({
                "cinema_name": CINEMA_NAME,
                "movie_title": title,
                "movie_title_en": title,
                "date_text": show_date.isoformat(),
                "showtime": show_time,
                "detail_page_url": detail_url,
                "booking_url": detail_url,
                "director": "",
                "year": "",
                "country": country,
                "runtime_min": "",
                "synopsis": "",
                "format_tags": format_tags,
            })

        print(f"[{CINEMA_NAME}] Found {len(shows)} film showings", file=sys.stderr)

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
    print(f"\n[INFO] Total: {len(data)} showings", file=sys.stderr)
