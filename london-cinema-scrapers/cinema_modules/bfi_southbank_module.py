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
import os
import re
import sys
from typing import Dict, Iterable, List, Optional
from urllib.parse import urljoin

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
WINDOW_DAYS = 7


def _read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _load_html_override() -> Optional[str]:
    path = os.getenv("BFI_HTML_PATH")
    if path:
        return _read_text_file(path)
    return None


def _load_json_ld_override() -> Optional[List[dict]]:
    path = os.getenv("BFI_JSON_LD_PATH")
    if not path:
        return None
    raw = _read_text_file(path)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return None


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


def _parse_time(time_str: str) -> Optional[str]:
    """Parse time and return in HH:MM format."""
    time_str = time_str.strip().upper()

    # Find where the array starts
    match = re.search(pattern, html, re.I)
    if not match:
        return []

    start_pos = match.start()

    # Now we need to find where the array ends - count brackets
    depth = 0
    end_pos = start_pos

    return None


def _parse_iso_datetime(value: str) -> Optional[dt.datetime]:
    """Parse ISO-ish datetime strings, normalizing Z offsets."""
    if not value:
        return None
    cleaned = value.strip().replace("Z", "+00:00")
    try:
        return dt.datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def _iter_json_nodes(value: object) -> Iterable[dict]:
    """Yield dict nodes from nested JSON structures."""
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _iter_json_nodes(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_json_nodes(item)


def _extract_json_ld(soup: BeautifulSoup) -> List[dict]:
    """Collect JSON-LD blocks from the page."""
    blocks: List[dict] = []
    for script in soup.select("script[type='application/ld+json']"):
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            blocks.append(data)
        elif isinstance(data, list):
            blocks.extend([item for item in data if isinstance(item, dict)])
    return blocks


def _collect_event_nodes(json_ld: List[dict]) -> List[dict]:
    """Return JSON-LD nodes that represent events."""
    events: List[dict] = []
    for block in json_ld:
        for node in _iter_json_nodes(block):
            node_type = node.get("@type")
            if isinstance(node_type, list):
                is_event = any("Event" in t for t in node_type if isinstance(t, str))
            else:
                is_event = isinstance(node_type, str) and "Event" in node_type
            if is_event:
                events.append(node)
    return events


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

    Optional overrides for offline testing:
    - BFI_HTML_PATH: path to a saved HTML file for the schedule page.
    - BFI_JSON_LD_PATH: path to a JSON/JSON-LD blob to parse instead of the page.
    """
    shows = []

    try:
        # BFI's schedule page may require session handling or specific parameters
        html_override = _load_html_override()
        soup = None
        if html_override:
            soup = BeautifulSoup(html_override, "html.parser")
        else:
            session = requests.Session()
            session.trust_env = False

            # First, try to get the main schedule page
            resp = session.get(SCHEDULE_URL, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")

        json_ld_blocks = _load_json_ld_override()
        if json_ld_blocks is None and soup is not None:
            json_ld_blocks = _extract_json_ld(soup)
        if json_ld_blocks is None:
            json_ld_blocks = []
        event_nodes = _collect_event_nodes(json_ld_blocks)

        for event in event_nodes:
            title = _clean(event.get("name", "")) or _clean(event.get("headline", ""))
            if not title:
                continue

            event_url = event.get("url", "")
            detail_url = urljoin(BASE_URL, event_url) if event_url else ""

            sub_events = event.get("subEvent") or event.get("eventSchedule") or []
            if isinstance(sub_events, dict):
                sub_events = [sub_events]
            if not isinstance(sub_events, list):
                sub_events = []

            if sub_events:
                for sub in sub_events:
                    start_value = sub.get("startDate") or sub.get("startTime")
                    parsed_dt = _parse_iso_datetime(start_value)
                    if not parsed_dt:
                        continue
                    show_date = parsed_dt.date()
                    if not (TODAY <= show_date < TODAY + dt.timedelta(days=WINDOW_DAYS)):
                        continue
                    shows.append({
                        "cinema_name": CINEMA_NAME,
                        "movie_title": title,
                        "movie_title_en": title,
                        "date_text": show_date.isoformat(),
                        "showtime": parsed_dt.strftime("%H:%M"),
                        "detail_page_url": detail_url,
                        "director": "",
                        "year": "",
                        "country": "",
                        "runtime_min": "",
                        "synopsis": "",
                    })
            else:
                start_value = event.get("startDate") or event.get("startTime")
                parsed_dt = _parse_iso_datetime(start_value)
                if not parsed_dt:
                    continue
                show_date = parsed_dt.date()
                if not (TODAY <= show_date < TODAY + dt.timedelta(days=WINDOW_DAYS)):
                    continue
                shows.append({
                    "cinema_name": CINEMA_NAME,
                    "movie_title": title,
                    "movie_title_en": title,
                    "date_text": show_date.isoformat(),
                    "showtime": parsed_dt.strftime("%H:%M"),
                    "detail_page_url": detail_url,
                    "director": "",
                    "year": "",
                    "country": "",
                    "runtime_min": "",
                    "synopsis": "",
                })

        if not shows and soup is not None:
            listings = soup.select(".film-listing, .event-item, .showing, article")

            for listing in listings:
                title_elem = listing.select_one(".title, h3, h4, .film-title")
                if not title_elem:
                    continue

                title = _clean(title_elem.get_text())
                if not title:
                    continue

                date_elem = listing.select_one(".date, .showing-date, time")
                date_str = date_elem.get_text() if date_elem else ""
                show_date = _parse_date(date_str)
                if not show_date:
                    continue

                if not (TODAY <= show_date < TODAY + dt.timedelta(days=WINDOW_DAYS)):
                    continue

                time_elem = listing.select_one(".time, .showing-time")
                time_str = time_elem.get_text() if time_elem else ""
                show_time = _parse_time(time_str)
                if not show_time:
                    continue

                link_elem = listing.select_one("a[href]")
                detail_url = ""
                if link_elem and link_elem.get("href"):
                    detail_url = urljoin(BASE_URL, link_elem["href"])

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
