#!/usr/bin/env python3
# barbican_module.py
# Scraper for Barbican Cinema
# https://www.barbican.org.uk/whats-on/cinema

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

BASE_URL = "https://www.barbican.org.uk"
SCHEDULE_URL = f"{BASE_URL}/whats-on/cinema"
CINEMA_NAME = "Barbican Cinema"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}
TIMEOUT = 30

TODAY = dt.date.today()
WINDOW_DAYS = 14


def _read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _load_html_override() -> Optional[str]:
    path = os.getenv("BARBICAN_HTML_PATH")
    if path:
        return _read_text_file(path)
    return None


def _load_json_override(env_key: str) -> Optional[List[dict]]:
    path = os.getenv(env_key)
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
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip())


def _parse_iso_datetime(value: str) -> Optional[dt.datetime]:
    if not value:
        return None
    cleaned = value.strip().replace("Z", "+00:00")
    try:
        return dt.datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def _parse_date_text(value: str) -> Optional[dt.date]:
    if not value:
        return None
    cleaned = re.sub(r"\s+", " ", value.strip())
    if not cleaned:
        return None
    iso_match = re.search(r"\d{4}-\d{2}-\d{2}", cleaned)
    if iso_match:
        try:
            return dt.date.fromisoformat(iso_match.group())
        except ValueError:
            return None

    formats_with_year = [
        "%A %d %B %Y",
        "%a %d %B %Y",
        "%d %B %Y",
        "%d %b %Y",
    ]
    for fmt in formats_with_year:
        try:
            return dt.datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue

    formats_without_year = [
        "%A %d %B",
        "%a %d %B",
        "%d %B",
        "%d %b",
    ]
    for fmt in formats_without_year:
        try:
            parsed = dt.datetime.strptime(cleaned, fmt)
            return parsed.replace(year=TODAY.year).date()
        except ValueError:
            continue

    return None


def _parse_time_text(value: str) -> Optional[str]:
    if not value:
        return None
    cleaned = value.strip().upper()
    match = re.search(r"(\d{1,2})[:\.]?(\d{2})?\s*(AM|PM)?", cleaned)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2)) if match.group(2) else 0
    period = match.group(3)

    if period == "PM" and hour != 12:
        hour += 12
    elif period == "AM" and hour == 12:
        hour = 0

    return f"{hour:02d}:{minute:02d}"


def _iter_json_nodes(value: object) -> Iterable[dict]:
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _iter_json_nodes(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_json_nodes(item)


def _extract_json_ld(soup: BeautifulSoup) -> List[dict]:
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


def _extract_next_data(soup: BeautifulSoup) -> Optional[dict]:
    script = soup.select_one("script#__NEXT_DATA__")
    if not script:
        return None
    raw = script.string or script.get_text(strip=True)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data


def _load_next_data_override() -> Optional[dict]:
    path = os.getenv("BARBICAN_NEXT_DATA_PATH")
    if not path:
        return None
    raw = _read_text_file(path)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        return data
    return None


def _collect_event_nodes(json_blocks: List[dict]) -> List[dict]:
    events: List[dict] = []
    for block in json_blocks:
        for node in _iter_json_nodes(block):
            node_type = node.get("@type")
            if isinstance(node_type, list):
                is_event = any("Event" in t for t in node_type if isinstance(t, str))
            else:
                is_event = isinstance(node_type, str) and "Event" in node_type
            if is_event:
                events.append(node)
    return events


def _collect_events_from_next(next_data: dict) -> List[dict]:
    events: List[dict] = []
    for node in _iter_json_nodes(next_data):
        if not isinstance(node, dict):
            continue
        if "startDate" in node and ("title" in node or "name" in node):
            events.append(node)
    return events


def _extract_events_from_html(soup: BeautifulSoup) -> List[dict]:
    events: List[dict] = []
    selectors = [
        "article",
        ".views-row",
        ".event-card",
        ".listing-card",
        ".card",
    ]
    seen_keys = set()

    for item in soup.select(", ".join(selectors)):
        title_elem = item.select_one(
            "h3 a, h2 a, h3, h2, .title, .card-title, .event-title"
        )
        if not title_elem:
            continue
        title = _clean(title_elem.get_text(" ", strip=True))
        if not title:
            continue

        link_elem = item.select_one("a[href]")
        url_value = link_elem.get("href") if link_elem else ""

        time_elem = item.select_one("time[datetime]")
        parsed_dt = None
        if time_elem:
            parsed_dt = _parse_iso_datetime(time_elem.get("datetime", ""))

        show_date = None
        show_time = None
        if parsed_dt:
            show_date = parsed_dt.date()
            show_time = parsed_dt.strftime("%H:%M")
        else:
            date_elem = item.select_one("time, .date, .event-date, .listing-date")
            date_text = date_elem.get_text(" ", strip=True) if date_elem else ""
            time_elem = item.select_one(".time, .event-time, .listing-time")
            time_text = time_elem.get_text(" ", strip=True) if time_elem else ""
            if not time_text and date_text:
                time_text = date_text
            show_date = _parse_date_text(date_text)
            show_time = _parse_time_text(time_text)

        if not show_date or not show_time:
            continue

        key = (title, show_date.isoformat(), show_time)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        events.append({
            "name": title,
            "startDate": f"{show_date.isoformat()}T{show_time}",
            "url": url_value,
        })

    return events


def scrape_barbican() -> List[Dict]:
    """Scrape Barbican Cinema showtimes.

    Optional overrides for offline testing:
    - BARBICAN_HTML_PATH: path to a saved HTML file for the schedule page.
    - BARBICAN_JSON_LD_PATH: path to JSON/JSON-LD blob to parse.
    - BARBICAN_NEXT_DATA_PATH: path to a __NEXT_DATA__ JSON blob.
    """
    shows: List[Dict] = []

    try:
        html_override = _load_html_override()
        soup = None
        if html_override:
            soup = BeautifulSoup(html_override, "html.parser")
        else:
            session = requests.Session()
            session.trust_env = False
            resp = session.get(SCHEDULE_URL, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")

        json_ld_blocks = _load_json_override("BARBICAN_JSON_LD_PATH")
        if json_ld_blocks is None and soup is not None:
            json_ld_blocks = _extract_json_ld(soup)
        if json_ld_blocks is None:
            json_ld_blocks = []
        event_nodes = _collect_event_nodes(json_ld_blocks)

        next_data = _load_next_data_override()
        if next_data is None and soup is not None:
            next_data = _extract_next_data(soup)
        if next_data:
            event_nodes.extend(_collect_events_from_next(next_data))
        if soup is not None:
            event_nodes.extend(_extract_events_from_html(soup))

        for event in event_nodes:
            title = _clean(event.get("name") or event.get("title") or event.get("headline") or "")
            if not title:
                continue

            start_value = event.get("startDate") or event.get("startTime")
            parsed_dt = _parse_iso_datetime(start_value)
            if not parsed_dt:
                continue

            show_date = parsed_dt.date()
            if not (TODAY <= show_date < TODAY + dt.timedelta(days=WINDOW_DAYS)):
                continue

            url_value = event.get("url") or event.get("path") or ""
            detail_url = urljoin(BASE_URL, url_value) if url_value else ""

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

        if not shows:
            print(f"[{CINEMA_NAME}] Note: No shows found. Page structure may need analysis.", file=sys.stderr)
            print(f"[{CINEMA_NAME}] URL: {SCHEDULE_URL}", file=sys.stderr)

    except requests.RequestException as e:
        print(f"[{CINEMA_NAME}] HTTP Error: {e}", file=sys.stderr)
        raise
    except Exception as e:
        print(f"[{CINEMA_NAME}] Error: {e}", file=sys.stderr)
        raise

    seen = set()
    unique_shows = []
    for s in shows:
        key = (s["movie_title"], s["date_text"], s["showtime"])
        if key not in seen:
            seen.add(key)
            unique_shows.append(s)

    return sorted(unique_shows, key=lambda x: (x["date_text"], x["showtime"], x["movie_title"]))


if __name__ == "__main__":
    data = scrape_barbican()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"\nTotal: {len(data)} showings")
