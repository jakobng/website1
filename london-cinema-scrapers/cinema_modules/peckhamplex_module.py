#!/usr/bin/env python3
# peckhamplex_module.py
# Scraper for Peckhamplex Cinema, Peckham
# https://www.peckhamplex.london/
#
# Structure: Film listing page + individual film detail pages
# Showtimes are embedded in each film's detail page with Veezi booking links
# Booking URLs: ticketing.eu.veezi.com/purchase/[ID]?siteToken=[TOKEN]

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.peckhamplex.london"
FILMS_URL = f"{BASE_URL}/films/out-now"
CINEMA_NAME = "Peckhamplex"

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


def _parse_date_text(date_str: str) -> Optional[dt.date]:
    """
    Parse date formats like "Friday, January 9, 2026" or "Friday 9th January 2026".
    Returns date object or None if parsing fails.
    """
    date_str = date_str.strip()

    # Remove ordinal suffixes (1st, 2nd, 3rd, 4th, etc.)
    date_str = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", date_str)

    # Remove day name and comma if present
    date_str = re.sub(
        r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)[,\s]+",
        "",
        date_str,
        flags=re.IGNORECASE
    )

    current_year = dt.date.today().year

    # Try various date formats
    formats = [
        "%B %d, %Y",    # January 9, 2026
        "%B %d %Y",     # January 9 2026
        "%d %B %Y",     # 9 January 2026
        "%d %B",        # 9 January (assume current/next year)
        "%B %d",        # January 9 (assume current/next year)
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


def _parse_time(time_str: str) -> Optional[str]:
    """
    Parse time formats like "19:30", "7:30pm", "19.30".
    Returns 24-hour format string "HH:MM" or None.
    """
    time_str = time_str.strip().lower()

    # Match HH:MM or HH.MM format (24-hour)
    match = re.search(r"(\d{1,2})[:.](\d{2})", time_str)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))

        # Check for am/pm suffix
        if "pm" in time_str and hour != 12:
            hour += 12
        elif "am" in time_str and hour == 12:
            hour = 0

        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"

    return None


def _get_film_urls(session: requests.Session) -> List[Dict[str, str]]:
    """
    Get list of film URLs and titles from the films listing page.
    Returns list of dicts with 'url' and 'title' keys.
    """
    films = []

    try:
        resp = session.get(FILMS_URL, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Find film links - typically in card/tile elements
        # Look for links to /film/ pages
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if "/film/" in href:
                title_elem = link.find(["h2", "h3", "h4", "span", "p"])
                title = ""
                if title_elem:
                    title = _clean(title_elem.get_text())
                if not title:
                    # Try to get text from the link itself
                    title = _clean(link.get_text())

                if title and href:
                    full_url = urljoin(BASE_URL, href)
                    # Avoid duplicates
                    if not any(f["url"] == full_url for f in films):
                        films.append({"url": full_url, "title": title})

        print(f"[{CINEMA_NAME}] Found {len(films)} films on listing page", file=sys.stderr)

    except requests.RequestException as e:
        print(f"[{CINEMA_NAME}] Error fetching film list: {e}", file=sys.stderr)

    return films


def _scrape_film_detail(session: requests.Session, film_url: str, film_title: str) -> List[Dict]:
    """
    Scrape showtimes from a film detail page.
    """
    shows = []

    try:
        resp = session.get(film_url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Get film title from page - look for h1 with class="page-title"
        # The first h1 just contains "Peckhamplex" (cinema name)
        title_elem = soup.find("h1", class_="page-title")
        if title_elem:
            page_title = _clean(title_elem.get_text())
            if page_title and page_title.lower() != "peckhamplex":
                film_title = page_title

        # Fallback: try the title tag
        if not film_title or film_title.lower() == "peckhamplex":
            title_tag = soup.find("title")
            if title_tag:
                # Extract title before " - Peckhamplex"
                page_title = title_tag.get_text()
                if " - Peckhamplex" in page_title:
                    film_title = page_title.split(" - Peckhamplex")[0].strip()

        # Fallback: extract from URL slug if title still looks wrong
        if not film_title or film_title.lower() == "peckhamplex":
            # Extract from URL like /film/avatar-fire-and-ash-3d
            slug_match = re.search(r"/film/([^/]+)/?$", film_url)
            if slug_match:
                slug = slug_match.group(1)
                # Convert slug to title: avatar-fire-and-ash-3d -> Avatar Fire And Ash 3d
                film_title = " ".join(word.capitalize() for word in slug.replace("-", " ").split())

        # Extract runtime if available (e.g., "3 hours 17 minutes")
        runtime_min = ""
        page_text = soup.get_text()
        runtime_match = re.search(r"(\d+)\s*hours?\s*(\d+)?\s*minutes?", page_text, re.IGNORECASE)
        if runtime_match:
            hours = int(runtime_match.group(1))
            minutes = int(runtime_match.group(2)) if runtime_match.group(2) else 0
            runtime_min = str(hours * 60 + minutes)
        else:
            # Try just minutes format
            runtime_match = re.search(r"(\d+)\s*mins?", page_text, re.IGNORECASE)
            if runtime_match:
                runtime_min = runtime_match.group(1)

        # Extract format tags (3D, 2D, etc.) - only if in title
        format_tags = []
        if "3d" in film_title.lower():
            format_tags.append("3D")

        # Find showtime sections
        # Look for booking links to Veezi
        current_date = None

        # First approach: Look for date headers followed by time links
        for elem in soup.find_all(["h2", "h3", "h4", "p", "div", "span", "a"]):
            text = _clean(elem.get_text())

            # Check if this is a date header
            if any(day in text for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]):
                parsed_date = _parse_date_text(text)
                if parsed_date:
                    current_date = parsed_date

            # Check if this is a booking link with time
            if elem.name == "a" and "veezi" in elem.get("href", "").lower():
                booking_url = elem.get("href", "")
                time_text = _clean(elem.get_text())
                parsed_time = _parse_time(time_text)

                if parsed_time and current_date:
                    # Check if within window
                    if TODAY <= current_date < TODAY + dt.timedelta(days=WINDOW_DAYS):
                        shows.append({
                            "cinema_name": CINEMA_NAME,
                            "movie_title": film_title,
                            "movie_title_en": film_title,
                            "date_text": current_date.isoformat(),
                            "showtime": parsed_time,
                            "detail_page_url": film_url,
                            "booking_url": booking_url,
                            "director": "",
                            "year": "",
                            "country": "",
                            "runtime_min": runtime_min,
                            "synopsis": "",
                            "format_tags": format_tags if format_tags else [],
                        })

        # Second approach: Find all Veezi links and extract date/time from surrounding context
        if not shows:
            veezi_links = soup.find_all("a", href=lambda x: x and "veezi" in x.lower())

            for link in veezi_links:
                booking_url = link.get("href", "")

                # Look for date and time in parent elements
                parent = link.parent
                search_depth = 0
                found_date = None
                found_time = None

                while parent and search_depth < 5:
                    parent_text = _clean(parent.get_text())

                    # Try to find date in parent
                    if not found_date:
                        for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
                            if day in parent_text:
                                # Extract the date portion
                                date_match = re.search(
                                    rf"{day}[,\s]+(\w+\s+\d+[,\s]+\d{{4}}|\d+\s+\w+\s+\d{{4}}|\w+\s+\d+|\d+\s+\w+)",
                                    parent_text,
                                    re.IGNORECASE
                                )
                                if date_match:
                                    found_date = _parse_date_text(f"{day} {date_match.group(1)}")
                                    break

                    parent = parent.parent
                    search_depth += 1

                # Get time from link text
                link_text = _clean(link.get_text())
                found_time = _parse_time(link_text)

                if found_date and found_time:
                    if TODAY <= found_date < TODAY + dt.timedelta(days=WINDOW_DAYS):
                        shows.append({
                            "cinema_name": CINEMA_NAME,
                            "movie_title": film_title,
                            "movie_title_en": film_title,
                            "date_text": found_date.isoformat(),
                            "showtime": found_time,
                            "detail_page_url": film_url,
                            "booking_url": booking_url,
                            "director": "",
                            "year": "",
                            "country": "",
                            "runtime_min": runtime_min,
                            "synopsis": "",
                            "format_tags": format_tags if format_tags else [],
                        })

    except requests.RequestException as e:
        print(f"[{CINEMA_NAME}] Error fetching {film_url}: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[{CINEMA_NAME}] Parse error for {film_url}: {e}", file=sys.stderr)

    return shows


def scrape_peckhamplex() -> List[Dict]:
    """
    Scrape Peckhamplex Cinema showtimes.

    Returns a list of showtime records with standard schema:
    - cinema_name: str
    - movie_title: str
    - date_text: str (YYYY-MM-DD)
    - showtime: str (HH:MM)
    - detail_page_url: str
    - booking_url: str
    - format_tags: list (optional) - e.g., ["3D"]
    """
    shows = []

    try:
        session = requests.Session()

        # Get list of films
        films = _get_film_urls(session)

        # Scrape each film's detail page
        for film in films:
            film_shows = _scrape_film_detail(session, film["url"], film["title"])
            shows.extend(film_shows)

        print(f"[{CINEMA_NAME}] Found {len(shows)} showings from {len(films)} films", file=sys.stderr)

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
    data = scrape_peckhamplex()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"\n[INFO] Total: {len(data)} showings", file=sys.stderr)
