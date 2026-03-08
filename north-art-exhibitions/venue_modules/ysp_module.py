#!/usr/bin/env python3
# Yorkshire Sculpture Park - exhibitions scraper

from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ._utils import parse_date_range, norm

BASE_URL = "https://ysp.org.uk"
EXHIBITIONS_URL = f"{BASE_URL}/exhibitions"

VENUE_NAME = "Yorkshire Sculpture Park"
VENUE_CITY = "West Bretton"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NorthArtExhibitions/1.0)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}
TIMEOUT = 25


def scrape_ysp():
    """Return list of exhibition dicts for Yorkshire Sculpture Park."""
    out = []
    try:
        r = requests.get(EXHIBITIONS_URL, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
    except Exception as e:
        raise RuntimeError(f"Failed to fetch {EXHIBITIONS_URL}: {e}") from e

    soup = BeautifulSoup(r.text, "html.parser")

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href or "/exhibitions/" not in href:
            continue
        full_url = urljoin(BASE_URL, href)
        if full_url.rstrip("/") == EXHIBITIONS_URL.rstrip("/"):
            continue
        if "/past-exhibitions" in href or href.rstrip("/").endswith("/past-exhibitions"):
            continue
        title = norm(a.get_text())
        if not title or len(title) < 3:
            continue
        if title.lower() in ("read more", "exhibitions", "view all"):
            continue

        date_text = ""
        start_str, end_str = None, None
        parent = a.parent
        for _ in range(6):
            if not parent:
                break
            date_text = parent.get_text(separator=" ")
            start_str, end_str = parse_date_range(date_text)
            if start_str or end_str:
                break
            parent = parent.parent

        if not start_str and not end_str:
            start_str, end_str = parse_date_range(date_text or a.get_text())

        out.append({
            "venue_name": VENUE_NAME,
            "venue_city": VENUE_CITY,
            "exhibition_title": title[:500],
            "start_date": start_str,
            "end_date": end_str,
            "detail_page_url": full_url,
            "description": None,
            "image_url": None,
        })

    seen = set()
    unique = []
    for item in out:
        key = item["detail_page_url"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    return unique
