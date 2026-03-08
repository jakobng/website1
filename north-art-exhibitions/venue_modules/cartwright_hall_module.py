#!/usr/bin/env python3
# Cartwright Hall Art Gallery, Bradford - exhibitions

from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ._utils import parse_date_range, norm

BASE_URL = "https://www.bradfordmuseums.org"
VENUE_NAME = "Cartwright Hall Art Gallery"
VENUE_CITY = "Bradford"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NorthArtExhibitions/1.0)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}
TIMEOUT = 25


def scrape_cartwright_hall():
    """Return list of exhibition dicts for Cartwright Hall (Bradford). Only Cartwright Hall exhibitions."""
    out = []
    urls_to_try = [
        f"{BASE_URL}/venues/cartwright-hall",
        f"{BASE_URL}/whats-on",
    ]
    for page_url in urls_to_try:
        try:
            r = requests.get(page_url, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            r.encoding = r.apparent_encoding or "utf-8"
        except Exception:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if "/event/" not in href:
                continue
            full_url = urljoin(BASE_URL, href)
            title = norm(a.get_text())
            if not title or len(title) < 3:
                continue
            if title.lower() in ("learn more", "view all", "what's on"):
                continue
            parent = a.parent
            date_text = ""
            for _ in range(8):
                if not parent:
                    break
                block_text = parent.get_text(separator=" ")
                if "Cartwright Hall" in block_text and (title in block_text or title[:20] in block_text):
                    date_text = block_text
                    break
                parent = parent.parent
            if not date_text:
                date_text = a.get_text(separator=" ")
            start_str, end_str = parse_date_range(date_text)
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
