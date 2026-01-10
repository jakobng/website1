#!/usr/bin/env python3
# riverside_studios_module.py
# Scraper for Riverside Studios cinema (Hammersmith)
# https://riversidestudios.co.uk/whats-on/
#
# Structure:
# - Film listings on /whats-on/ page (may need category filter)
# - Each film detail page contains showtimes
# - TODO: Refine selectors once HTML structure is confirmed

from __future__ import annotations

import datetime as dt
import html
import json
import re
import sys
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://riversidestudios.co.uk"
WHATS_ON_URL = f"{BASE_URL}/whats-on/"
CINEMA_NAME = "Riverside Studios"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}
TIMEOUT = 30

TODAY = dt.date.today()
WINDOW_DAYS = 14


def _clean(text: str) -> str:
    """Clean whitespace, decode HTML entities, and normalize text."""
    if not text:
        return ""
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text.strip())


def _parse_date(date_str: str) -> Optional[dt.date]:
    """
    Parse date string in various formats.
    Returns date object or None.
    """
    if not date_str:
        return None

    date_str = date_str.strip()

    # Handle "Today", "Tomorrow"
    lower = date_str.lower()
    if lower == "today":
        return TODAY
    if lower == "tomorrow":
        return TODAY + dt.timedelta(days=1)

    # Try ISO format first (YYYY-MM-DD)
    iso_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", date_str)
    if iso_match:
        try:
            return dt.date(
                int(iso_match.group(1)),
                int(iso_match.group(2)),
                int(iso_match.group(3))
            )
        except ValueError:
            pass

    # Try "DD MMM YYYY" or "DD MMMM YYYY" format
    # Also handles "Sun 11 Jan" or "11 Jan 2025"
    match = re.search(r"(\d{1,2})\s+(\w+)(?:\s+(\d{4}))?", date_str)
    if match:
        try:
            day = int(match.group(1))
            month_str = match.group(2).lower()[:3]
            year = int(match.group(3)) if match.group(3) else None

            month_map = {
                "jan": 1, "feb": 2, "mar": 3, "apr": 4,
                "may": 5, "jun": 6, "jul": 7, "aug": 8,
                "sep": 9, "oct": 10, "nov": 11, "dec": 12
            }
            month = month_map.get(month_str)
            if not month:
                return None

            if year is None:
                year = TODAY.year
                parsed_date = dt.date(year, month, day)
                # If date is more than 30 days in the past, assume next year
                if parsed_date < TODAY - dt.timedelta(days=30):
                    parsed_date = dt.date(year + 1, month, day)
                return parsed_date
            else:
                return dt.date(year, month, day)
        except ValueError:
            pass

    return None


def _parse_time(time_str: str) -> Optional[str]:
    """
    Parse time string in various formats.
    Returns HH:MM format or None.
    """
    if not time_str:
        return None

    time_str = time_str.strip()

    # Match patterns like "14:30", "2:30pm", "2.30pm", "7pm"
    # 24-hour format
    match_24h = re.match(r"(\d{1,2}):(\d{2})", time_str)
    if match_24h:
        hour = int(match_24h.group(1))
        minute = int(match_24h.group(2))
        if 0 <= hour < 24 and 0 <= minute < 60:
            return f"{hour:02d}:{minute:02d}"

    # 12-hour format with am/pm
    match_12h = re.match(r"(\d{1,2})(?:[:\.](\d{2}))?\s*(am|pm)", time_str, re.I)
    if match_12h:
        try:
            hour = int(match_12h.group(1))
            minute = int(match_12h.group(2)) if match_12h.group(2) else 0
            period = match_12h.group(3).lower()

            if period == "pm" and hour != 12:
                hour += 12
            elif period == "am" and hour == 12:
                hour = 0

            if 0 <= hour < 24 and 0 <= minute < 60:
                return f"{hour:02d}:{minute:02d}"
        except ValueError:
            pass

    return None


def _extract_film_links(soup: BeautifulSoup) -> List[str]:
    """
    Extract film/cinema event links from the what's on page.
    Returns list of absolute URLs.
    """
    links = []

    # TODO: Update selectors based on actual HTML structure
    # Look for links to event/film detail pages
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Match event pages - adjust pattern as needed
        if "/whats-on/" in href and href != WHATS_ON_URL:
            if href.startswith("/"):
                full_url = BASE_URL + href
            elif href.startswith("http"):
                full_url = href
            else:
                continue

            if full_url not in links and full_url != WHATS_ON_URL.rstrip("/"):
                links.append(full_url)

    return links


def _extract_metadata(soup: BeautifulSoup) -> Dict:
    """
    Extract film metadata from a detail page.
    """
    metadata = {
        "director": "",
        "runtime_min": "",
        "synopsis": "",
        "year": "",
        "country": "",
    }

    # Try meta description for synopsis
    meta_desc = soup.find("meta", {"name": "description"})
    if meta_desc and meta_desc.get("content"):
        metadata["synopsis"] = _clean(meta_desc["content"])[:500]

    if not metadata["synopsis"]:
        og_desc = soup.find("meta", {"property": "og:description"})
        if og_desc and og_desc.get("content"):
            metadata["synopsis"] = _clean(og_desc["content"])[:500]

    # Look for runtime in page text
    page_text = soup.get_text(" ", strip=True)
    runtime_match = re.search(r"(\d+)\s*(?:min(?:ute)?s?|mins)", page_text, re.I)
    if runtime_match:
        metadata["runtime_min"] = runtime_match.group(1)

    # Look for director
    director_match = re.search(
        r"Director[:\s]+([A-Za-z\s\-\.]+?)(?:\s*[|\•\n]|$)",
        page_text
    )
    if director_match:
        metadata["director"] = _clean(director_match.group(1))

    return metadata


def _extract_showtimes_from_detail(soup: BeautifulSoup, film_url: str) -> List[Dict]:
    """
    Extract showtimes from a film detail page.
    """
    shows = []

    # Get film title
    title = ""
    title_elem = soup.find("h1")
    if title_elem:
        title = _clean(title_elem.get_text())

    if not title:
        og_title = soup.find("meta", {"property": "og:title"})
        if og_title and og_title.get("content"):
            title = _clean(og_title["content"])
            # Remove site name suffix if present
            title = re.sub(r"\s*[-–|]\s*Riverside Studios.*$", "", title, flags=re.I)

    if not title:
        return []

    metadata = _extract_metadata(soup)

    # TODO: Update these selectors based on actual HTML structure
    # Look for date/time elements - common patterns:

    # Pattern 1: Look for time elements with datetime attribute
    for time_elem in soup.find_all("time", {"datetime": True}):
        try:
            datetime_str = time_elem.get("datetime", "")
            parsed_dt = dt.datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
            show_date = parsed_dt.date()
            show_time = parsed_dt.strftime("%H:%M")

            if TODAY <= show_date < TODAY + dt.timedelta(days=WINDOW_DAYS):
                shows.append({
                    "cinema_name": CINEMA_NAME,
                    "movie_title": title,
                    "movie_title_en": title,
                    "date_text": show_date.isoformat(),
                    "showtime": show_time,
                    "detail_page_url": film_url,
                    "booking_url": "",
                    "director": metadata["director"],
                    "year": metadata["year"],
                    "country": metadata["country"],
                    "runtime_min": metadata["runtime_min"],
                    "synopsis": metadata["synopsis"],
                })
        except (ValueError, AttributeError):
            continue

    # Pattern 2: Look for date headers with time slots
    # This will need to be customized based on actual HTML

    return shows


def scrape_riverside_studios() -> List[Dict]:
    """
    Scrape Riverside Studios cinema showtimes.

    Fetches the what's on page to get film links, then scrapes each
    film's detail page for showtimes.

    Returns a list of showtime records with standard schema.
    """
    shows = []

    try:
        session = requests.Session()

        # Fetch the what's on page
        print(f"[{CINEMA_NAME}] Fetching listings from {WHATS_ON_URL}", file=sys.stderr)
        resp = session.get(WHATS_ON_URL, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        film_links = _extract_film_links(soup)

        print(f"[{CINEMA_NAME}] Found {len(film_links)} event pages", file=sys.stderr)

        # Fetch each film detail page
        for film_url in film_links:
            try:
                print(f"[{CINEMA_NAME}] Fetching {film_url}", file=sys.stderr)
                resp = session.get(film_url, headers=HEADERS, timeout=TIMEOUT)
                resp.raise_for_status()

                film_soup = BeautifulSoup(resp.text, "html.parser")
                film_shows = _extract_showtimes_from_detail(film_soup, film_url)
                shows.extend(film_shows)

            except requests.RequestException as e:
                print(f"[{CINEMA_NAME}] Error fetching {film_url}: {e}", file=sys.stderr)
                continue

        print(f"[{CINEMA_NAME}] Found {len(shows)} total showings", file=sys.stderr)

        if not shows:
            print(f"[{CINEMA_NAME}] Note: No shows found. Page structure may need analysis.", file=sys.stderr)

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
    data = scrape_riverside_studios()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"\n[INFO] Total: {len(data)} showings", file=sys.stderr)
