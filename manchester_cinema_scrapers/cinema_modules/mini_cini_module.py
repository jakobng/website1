#!/usr/bin/env python3
# mini_cini_module.py
# Scraper for Mini Cini (36-seat venue at Ducie Street Warehouse)
# https://duciestreetwarehouse.com/cinema/
#
# Structure: Boutique cinema with curated film selections

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://duciestreetwarehouse.com"
CINEMA_URL = f"{BASE_URL}/cinema/"
CINEMA_NAME = "Mini Cini"

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
    Parse UK date formats from Mini Cini listings.
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
    Parse 12-hour time format from Mini Cini listings.
    Returns 24-hour format string "HH:MM" or None.
    """
    time_str = time_str.strip().lower()

    # Match patterns like "7:30pm", "8:00 pm", "12:15am"
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


def _extract_film_info(film_element) -> Optional[Dict]:
    """
    Extract film information from a film listing element.
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
        desc_elem = film_element.find(['p', 'div'], class_=re.compile(r'description|synopsis|desc|summary'))
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


def scrape_mini_cini() -> List[Dict]:
    """
    Scrape Mini Cini showtimes from their website.

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
        resp = session.get(CINEMA_URL, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Find film listings - look for containers with film information
        film_containers = soup.find_all(['div', 'article', 'section'], class_=re.compile(r'film|movie|showing|event|screening'))

        # If no specific classes found, try broader search
        if not film_containers:
            # Look for any divs containing time information
            all_divs = soup.find_all('div')
            film_containers = []
            for div in all_divs:
                text = _clean(div.get_text())
                if re.search(r'\d{1,2}:\d{2}\s*(?:am|pm)', text, re.IGNORECASE) and len(text) > 50:
                    film_containers.append(div)

        print(f"[{CINEMA_NAME}] Found {len(film_containers)} potential film containers", file=sys.stderr)

        for container in film_containers:
            # Extract film info
            film_info = _extract_film_info(container)
            if not film_info:
                continue

            # Look for showtimes within this container
            container_text = _clean(container.get_text())

            # Find all showtimes in the container
            time_matches = re.findall(r'(\d{1,2}:\d{2}\s*(?:am|pm))', container_text, re.IGNORECASE)

            # Look for date information
            event_date = None
            date_patterns = [
                r'(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December))',
                r'((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))'
            ]

            for pattern in date_patterns:
                date_match = re.search(pattern, container_text, re.IGNORECASE)
                if date_match:
                    event_date = _parse_uk_date(date_match.group(1))
                    if event_date:
                        break

            # If no specific date found, assume today or look for date headers
            if not event_date:
                date_headers = soup.find_all(['h2', 'h3', 'h4'], string=re.compile(r'\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'))
                for header in date_headers:
                    header_date = _parse_uk_date(_clean(header.get_text()))
                    if header_date:
                        event_date = header_date
                        break

            # If still no date, check if this is for today
            if not event_date:
                # Look for "Today", "Now Playing" indicators
                if re.search(r'\b(today|now playing|this week)\b', container_text, re.IGNORECASE):
                    event_date = TODAY

            # Process each showtime
            for time_match in time_matches:
                parsed_time = _parse_time_12h(time_match)
                if parsed_time and event_date:
                    # Check if within our date window
                    if TODAY <= event_date < TODAY + dt.timedelta(days=WINDOW_DAYS):
                        shows.append({
                            "cinema_name": CINEMA_NAME,
                            "movie_title": film_info['title'],
                            "movie_title_en": film_info['title'],  # Will be populated by TMDB
                            "date_text": event_date.isoformat(),
                            "showtime": parsed_time,
                            "detail_page_url": film_info['detail_page_url'],
                            "director": "",  # Will be populated by TMDB
                            "year": "",      # Will be populated by TMDB
                            "country": "",   # Will be populated by TMDB
                            "runtime_min": "",  # Will be populated by TMDB
                            "synopsis": film_info['synopsis'],
                        })

        # If we didn't find structured listings, try a different approach
        if not shows:
            # Look for time listings in a more general way across the page
            page_text = _clean(soup.get_text())
            all_times = re.findall(r'(\d{1,2}:\d{2}\s*(?:am|pm))', page_text, re.IGNORECASE)

            # This is a fallback - we'd need more context to properly associate times with films
            print(f"[{CINEMA_NAME}] Fallback: found {len(all_times)} times but need better parsing", file=sys.stderr)

        print(f"[{CINEMA_NAME}] Found {len(shows)} showings", file=sys.stderr)

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
    data = scrape_mini_cini()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"\n[INFO] Total: {len(data)} showings", file=sys.stderr)