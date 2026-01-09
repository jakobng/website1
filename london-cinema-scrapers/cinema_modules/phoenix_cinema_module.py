#!/usr/bin/env python3
# phoenix_cinema_module.py
# Scraper for Phoenix Cinema (East Finchley)
# https://www.phoenixcinema.co.uk/
#
# Structure: Movie pages include SEO markup with showtime links like:
# <h1>Showtimes</h1><h2><a href="/checkout/showing/...">January 8, 4:45 pm</a></h2>

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from typing import Dict, List, Optional
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.phoenixcinema.co.uk"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
CINEMA_NAME = "Phoenix Cinema"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}
TIMEOUT = 30

TODAY = dt.date.today()
WINDOW_DAYS = 14

FALLBACK_LISTING_URLS = [
    f"{BASE_URL}/now-playing",
    f"{BASE_URL}/coming-soon",
    f"{BASE_URL}/movies",
]


def _read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _load_html_override() -> Optional[str]:
    path = os.getenv("PHOENIX_HTML_PATH")
    if path:
        return _read_text_file(path)
    return None


def _clean(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip())


def _parse_showtime_text(text: str) -> Optional[dt.datetime]:
    cleaned = _clean(text)
    if not cleaned:
        return None

    formats = [
        "%B %d, %Y, %I:%M %p",
        "%B %d, %Y, %I %p",
        "%B %d, %I:%M %p",
        "%B %d, %I %p",
    ]

    for fmt in formats:
        try:
            parsed = dt.datetime.strptime(cleaned, fmt)
            if "%Y" not in fmt:
                parsed = parsed.replace(year=TODAY.year)
                if parsed.date() < TODAY - dt.timedelta(days=30):
                    parsed = parsed.replace(year=TODAY.year + 1)
            return parsed
        except ValueError:
            continue

    return None


def _parse_iso_duration(duration: str) -> str:
    if not duration:
        return ""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", duration)
    if not match:
        return ""
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    total_minutes = hours * 60 + minutes
    return str(total_minutes) if total_minutes else ""


def _extract_movie_metadata(soup: BeautifulSoup) -> Dict[str, str]:
    metadata = {
        "title": "",
        "director": "",
        "year": "",
        "runtime_min": "",
        "synopsis": "",
    }

    for script in soup.select("script[type='application/ld+json']"):
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue

        if isinstance(data, list):
            nodes = data
        else:
            nodes = [data]

        for node in nodes:
            if not isinstance(node, dict):
                continue
            if node.get("@type") != "Movie":
                continue
            metadata["title"] = node.get("name", "")
            metadata["synopsis"] = node.get("description", "")
            metadata["runtime_min"] = _parse_iso_duration(node.get("duration", ""))
            date_created = node.get("dateCreated", "")
            if isinstance(date_created, str) and len(date_created) >= 4:
                metadata["year"] = date_created[:4]
            directors = node.get("director")
            if isinstance(directors, list) and directors:
                director_name = directors[0].get("name") if isinstance(directors[0], dict) else ""
                metadata["director"] = director_name or ""
            elif isinstance(directors, dict):
                metadata["director"] = directors.get("name", "")
            return metadata

    title_el = soup.select_one("[data-test-id='movie-title'], .movie-info .text-h6")
    if title_el:
        metadata["title"] = _clean(title_el.get_text())

    return metadata


def _extract_showtime_links(soup: BeautifulSoup) -> List[Dict[str, str]]:
    showtimes = []
    for link in soup.select("a[href*='/checkout/showing/']"):
        showtime_text = _clean(link.get_text())
        if not showtime_text:
            continue
        href = link.get("href", "")
        if href and not href.startswith("http"):
            href = urljoin(BASE_URL, href)
        showtimes.append({"text": showtime_text, "booking_url": href})
    return showtimes


def _extract_sitemap_locs(xml_text: str) -> List[str]:
    try:
        root = ET.fromstring(xml_text)
        return [loc.text.strip() for loc in root.iter() if loc.tag.endswith("loc") and loc.text]
    except ET.ParseError:
        soup = BeautifulSoup(xml_text, "xml")
        return [loc.get_text(strip=True) for loc in soup.find_all("loc")]


def _fetch_movie_urls(session: requests.Session) -> List[str]:
    movie_urls: List[str] = []

    try:
        resp = session.get(SITEMAP_URL, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        locs = _extract_sitemap_locs(resp.text)
        sitemap_urls = []
        for url_text in locs:
            if "/movie/" in url_text:
                movie_urls.append(url_text)
            elif url_text.endswith(".xml") or "sitemap" in url_text:
                sitemap_urls.append(url_text)

        for sitemap_url in sitemap_urls:
            try:
                sitemap_resp = session.get(sitemap_url, headers=HEADERS, timeout=TIMEOUT)
                sitemap_resp.raise_for_status()
                for url_text in _extract_sitemap_locs(sitemap_resp.text):
                    if "/movie/" in url_text:
                        movie_urls.append(url_text)
            except requests.RequestException as exc:
                print(f"[{CINEMA_NAME}] Child sitemap fetch failed ({sitemap_url}): {exc}", file=sys.stderr)
    except requests.RequestException as exc:
        print(f"[{CINEMA_NAME}] Sitemap fetch failed: {exc}", file=sys.stderr)

    if movie_urls:
        return sorted(set(movie_urls))

    for listing_url in FALLBACK_LISTING_URLS:
        try:
            resp = session.get(listing_url, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for link in soup.select("a[href*='/movie/']"):
                href = link.get("href", "")
                if href and not href.startswith("http"):
                    href = urljoin(BASE_URL, href)
                if "/movie/" in href:
                    movie_urls.append(href)
        except requests.RequestException as exc:
            print(f"[{CINEMA_NAME}] Listing fetch failed ({listing_url}): {exc}", file=sys.stderr)

    return sorted(set(movie_urls))


def scrape_phoenix_cinema() -> List[Dict]:
    """
    Scrape Phoenix Cinema showtimes from individual movie pages.

    Returns a list of showtime records with standard schema.
    """
    shows: List[Dict] = []

    try:
        html_override = _load_html_override()
        session = requests.Session()

        if html_override:
            movie_pages = [("", html_override)]
        else:
            movie_urls = _fetch_movie_urls(session)
            movie_pages = []
            for movie_url in movie_urls:
                resp = session.get(movie_url, headers=HEADERS, timeout=TIMEOUT)
                resp.raise_for_status()
                movie_pages.append((movie_url, resp.text))

        for movie_url, html in movie_pages:
            soup = BeautifulSoup(html, "html.parser")
            metadata = _extract_movie_metadata(soup)
            title = metadata["title"]

            if not title:
                continue

            for showtime in _extract_showtime_links(soup):
                parsed_dt = _parse_showtime_text(showtime["text"])
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
                    "detail_page_url": movie_url or "",
                    "booking_url": showtime["booking_url"],
                    "director": metadata["director"],
                    "year": metadata["year"],
                    "country": "",
                    "runtime_min": metadata["runtime_min"],
                    "synopsis": metadata["synopsis"],
                    "format_tags": [],
                })

        print(f"[{CINEMA_NAME}] Found {len(shows)} showings", file=sys.stderr)

    except requests.RequestException as exc:
        print(f"[{CINEMA_NAME}] HTTP Error: {exc}", file=sys.stderr)
        raise
    except Exception as exc:
        print(f"[{CINEMA_NAME}] Error: {exc}", file=sys.stderr)
        raise

    return shows


if __name__ == "__main__":
    data = scrape_phoenix_cinema()
    print(f"\n[INFO] Total: {len(data)} showings", file=sys.stderr)
    for s in data[:5]:
        print(s)
