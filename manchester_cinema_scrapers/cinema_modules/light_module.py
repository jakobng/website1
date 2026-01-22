#!/usr/bin/env python3
# light_module.py
# Scraper for The Light cinema (Stockport, 12 screens)
# https://stockport.thelight.co.uk/cinema
#
# Structure: Commercial chain cinema with standard website format

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://stockport.thelight.co.uk"
CINEMA_URL = f"{BASE_URL}/cinema"
NOW_SHOWING_URL = f"{BASE_URL}/cinema/nowshowing"
CINEMA_NAME = "The Light"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}
TIMEOUT = 30

TODAY = dt.date.today()
WINDOW_DAYS = 14  # Look ahead 2 weeks


def _clean(text: str) -> str:
    """Clean whitespace and normalize text."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip())


def _parse_uk_date(date_str: str) -> Optional[dt.date]:
    """
    Parse UK date formats from The Light listings.
    Returns date object or None if parsing fails.
    """
    date_str = date_str.strip()

    # Handle formats like "Friday 22nd November", "Saturday 23rd November"
    # Remove ordinal suffixes
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
        "%d %B",       # 22 November
        "%d %b",       # 22 Nov
    ]

    for fmt in formats:
        try:
            parsed = dt.datetime.strptime(date_str.strip(), fmt)
            parsed = parsed.replace(year=current_year)
            # If date is in the past, assume next year
            if parsed.date() < TODAY - dt.timedelta(days=30):
                parsed = parsed.replace(year=current_year + 1)
            return parsed.date()
        except ValueError:
            continue

    return None


def _parse_time_12h(time_str: str) -> Optional[str]:
    """
    Parse time format from The Light listings.
    Handles both 12-hour (with AM/PM) and 24-hour formats.
    Returns 24-hour format string "HH:MM" or None.
    """
    time_str = time_str.strip().lower()

    # First try 12-hour format with AM/PM
    match_12h = re.match(r"(\d{1,2}):(\d{2})\s*(am|pm)", time_str)
    if match_12h:
        hour = int(match_12h.group(1))
        minute = int(match_12h.group(2))
        period = match_12h.group(3)

        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0

        return f"{hour:02d}:{minute:02d}"

    # Then try 24-hour format like "20:30", "11:00"
    match_24h = re.match(r"(\d{1,2}):(\d{2})", time_str)
    if match_24h:
        hour = int(match_24h.group(1))
        minute = int(match_24h.group(2))

        # Validate hour (0-23) and minute (0-59)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"

    return None


def _extract_film_info(film_element) -> Optional[Dict]:
    """
    Extract film information from a The Light film listing element.
    Returns dict with title, synopsis, etc.
    """
    try:
        # Find film title
        title_elem = film_element.find(['h2', 'h3', 'h4', 'a'], class_=re.compile(r'title|film-title|movie-title'))
        if not title_elem:
            # Try any heading
            title_elem = film_element.find(['h1', 'h2', 'h3', 'h4', 'h5'])

        if not title_elem:
            return None

        title = _clean(title_elem.get_text())

        # Remove age ratings from title
        title = re.sub(r"\s*\(\d{1,2}[A-Z]?\)\s*$", "", title)

        # Find synopsis/description
        synopsis = ""
        desc_elem = film_element.find(['p', 'div'], class_=re.compile(r'description|synopsis|desc|summary|plot'))
        if desc_elem:
            synopsis = _clean(desc_elem.get_text())
        else:
            # Look for paragraphs with substantial content
            paragraphs = film_element.find_all('p')
            for p in paragraphs:
                text = _clean(p.get_text())
                if len(text) > 30:  # Assume longer text is synopsis
                    synopsis = text
                    break

        # Find detail page URL
        detail_url = ""
        title_link = title_elem if title_elem.name == 'a' else title_elem.find_parent('a')
        if title_link and title_link.name == 'a':
            detail_url = urljoin(BASE_URL, title_link.get('href', ''))

        return {
            'title': title,
            'synopsis': synopsis,
            'detail_page_url': detail_url,
        }

    except Exception as e:
        print(f"Error extracting film info: {e}", file=sys.stderr)
        return None


def scrape_light() -> List[Dict]:
    """
    Scrape The Light cinema showtimes from their website.

    Returns a list of showtime records with standard schema:
    - cinema_name: str
    - movie_title: str
    - date_text: str (YYYY-MM-DD)
    - showtime: str (HH:MM)
    - detail_page_url: str
    - director: str (if available)
    - year: str (if available)
    - country: str (if available)
    - runtime_min: str (if available)
    - synopsis: str

    Note: Director, year, runtime etc. are populated by TMDB enrichment in main_scraper.py
    """
    shows = []

    try:
        session = requests.Session()

        # First, get the list of movies from the nowshowing page
        resp = session.get(NOW_SHOWING_URL, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Find all movie links from the nowshowing page
        movie_links = []

        # Try different selectors for movie links
        all_links = soup.find_all('a', href=True)
        movie_candidates = []

        for link in all_links:
            href = link['href']
            if href.startswith('/') and not href.startswith('//') and len(href) > 5:
                # Look for movie-like URLs (not navigation)
                if not any(skip in href for skip in ['/cinema', '/diner', '/activities', '/hire', '/whatson', '/join', '/gifts', '/help', '/account']):
                    title = link.get('title', '')
                    if title or 'class' in link.attrs:
                        movie_candidates.append((href, title, link.get('class', [])))

        # Filter to likely movie links
        for href, title, classes in movie_candidates:
            # Check if it looks like a movie URL (not too generic)
            if ('prog' in classes or 'snap' in classes or
                any(word in href.lower() for word in ['movie', 'film', 'avatar', 'traitor', 'silent'])):
                movie_links.append(urljoin(BASE_URL, href))

        print(f"[{CINEMA_NAME}] Found {len(movie_links)} movie links to check", file=sys.stderr)

        # Visit each movie page to get showtimes
        for movie_url in movie_links[:10]:  # Limit to first 10 for performance
            try:
                movie_resp = session.get(movie_url, headers=HEADERS, timeout=TIMEOUT)
                movie_resp.raise_for_status()
                movie_soup = BeautifulSoup(movie_resp.text, "html.parser")

                # Extract movie title
                title = ""
                title_elem = movie_soup.find(['h1', 'h2'], class_=re.compile(r'title|name|film-title'))
                if title_elem:
                    title = _clean(title_elem.get_text())
                else:
                    # Look for title in the page title or other headings
                    title_elem = movie_soup.find('title')
                    if title_elem:
                        title = _clean(title_elem.get_text())
                        # Remove " | The Light Stockport" suffix
                        title = title.split(' | ')[0]

                if not title:
                    continue

                # Remove age ratings from title
                title = re.sub(r"\s*\((\d{1,2}[A-Z]?|U|PG|12A|15|18)\)\s*$", "", title)

                # Extract synopsis
                synopsis = ""
                desc_elem = movie_soup.find(['p', 'div'], class_=re.compile(r'description|synopsis|plot|summary'))
                if desc_elem:
                    synopsis = _clean(desc_elem.get_text())

                # Look for showtime information in the schedule section
                schedule_div = movie_soup.find('div', class_='schedule')
                if schedule_div:
                    # Find all showtime links
                    showtime_links = schedule_div.find_all('a', class_='showtime')

                    for link in showtime_links:
                        time_span = link.find('span', class_='time')
                        if time_span:
                            time_text = _clean(time_span.get_text())
                            parsed_time = _parse_time_12h(time_text)
                            if parsed_time:
                                # Get the date from the active daystrip link
                                day_link = schedule_div.find('a', class_='active')
                                event_date = TODAY  # Default
                                if day_link:
                                    day_text = _clean(day_link.get_text())
                                    # Parse date like "Fri 23 Jan"
                                    date_match = re.search(r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))', day_text)
                                    if date_match:
                                        try:
                                            parsed_date = _parse_uk_date(date_match.group(1))
                                            if parsed_date:
                                                event_date = parsed_date
                                        except:
                                            pass

                                shows.append({
                                    "cinema_name": CINEMA_NAME,
                                    "movie_title": title,
                                    "movie_title_en": title,
                                    "date_text": event_date.isoformat(),
                                    "showtime": parsed_time,
                                    "detail_page_url": movie_url,
                                    "director": "",
                                    "year": "",
                                    "country": "",
                                    "runtime_min": "",
                                    "synopsis": synopsis,
                                })

                else:
                    # Fallback: Look for any elements containing time patterns (not implemented yet)
                    pass


                # Be polite and don't overwhelm the server
                import time
                time.sleep(0.5)

            except Exception as e:
                print(f"[{CINEMA_NAME}] Error processing {movie_url}: {e}", file=sys.stderr)
                continue

        print(f"[{CINEMA_NAME}] Found {len(shows)} total showings", file=sys.stderr)

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
        key = (s["cinema_name"], s["movie_title"], s["date_text"], s["showtime"])
        if key not in seen:
            seen.add(key)
            unique_shows.append(s)

    return sorted(unique_shows, key=lambda x: (x["date_text"], x["showtime"], x["movie_title"]))


if __name__ == "__main__":
    # Debug mode - save HTML for inspection
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--debug":
        session = requests.Session()
        resp = session.get(NOW_SHOWING_URL, headers=HEADERS, timeout=TIMEOUT)
        with open("light_debug.html", "w", encoding="utf-8") as f:
            f.write(resp.text)
        print("Saved HTML to light_debug.html")
        sys.exit(0)

    data = scrape_light()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"\n[INFO] Total: {len(data)} showings", file=sys.stderr)