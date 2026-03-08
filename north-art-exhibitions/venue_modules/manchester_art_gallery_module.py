#!/usr/bin/env python3
# Manchester Art Gallery - exhibitions/events scraper
# We use this venue's own website (manchesterartgallery.org). The site is behind Cloudflare and returns
# 403 for both the listing and individual event pages, so we try requests/Playwright first, then a
# curated fallback list so Manchester Art Gallery still appears on the site.

from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ._utils import parse_date_range, norm

BASE_URL = "https://manchesterartgallery.org"
EVENTS_URL = f"{BASE_URL}/event/"
EXHIBITIONS_URL = f"{BASE_URL}/exhibitions/"

VENUE_NAME = "Manchester Art Gallery"
VENUE_CITY = "Manchester"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://www.google.com/",
}
TIMEOUT = 20

# Fallback when the site returns 403 (Cloudflare). Update periodically from manchesterartgallery.org/event/
FALLBACK_EXHIBITIONS = [
    {"title": "Holly Graham: The Warp / The Weft / The Wake", "slug": "holly-graham", "end_date": "2026-09-06"},
    {"title": "Splendours of the Sikh Raj: Arms and Armour", "slug": "splendours-of-the-sikh-raj", "end_date": "2026-11-29"},
    {"title": "Won't Sit Still", "slug": "wont-sit-still", "start_date": "2026-03-26", "end_date": "2027-03-28"},
    {"title": "WORN: the life within clothes", "slug": "worn-the-life-within-clothes", "start_date": "2026-03-26", "end_date": "2028-02-13"},
    {"title": "What's New? Collecting for Manchester", "slug": "whats-new", "start_date": "2023-02-07", "end_date": "2025-12-31"},
    {"title": "Out of the Crate", "slug": "out-of-the-crate", "start_date": "2019-11-07", "end_date": "2025-12-31"},
    {"title": "Rethinking the Grand Tour", "slug": "rethinking-the-grand-tour", "start_date": "2022-11-24", "end_date": "2025-12-31"},
    {"title": "Unpicking Couture", "slug": "unpicking-couture", "start_date": "2023-07-21", "end_date": "2025-01-12"},
]


def _fetch_with_playwright(url):
    """Fetch page HTML using Playwright (bypasses Cloudflare). Returns HTML or None."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            html = page.content()
            browser.close()
        return html
    except Exception:
        return None


def _parse_listing_html(html, page_url):
    """Parse event/exhibition listing HTML; yield (title, detail_url, date_text)."""
    if not html:
        return
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href.startswith("/event/") and not href.startswith("/exhibitions/"):
            continue
        full_url = urljoin(BASE_URL, href)
        if full_url.rstrip("/") in (EVENTS_URL.rstrip("/"), EXHIBITIONS_URL.rstrip("/"), BASE_URL.rstrip("/")):
            continue
        if href.strip() in ("/event/", "/event", "/exhibitions/", "/exhibitions"):
            continue
        title = norm(a.get_text())
        if not title or len(title) < 3:
            continue
        if title.lower() in ("read more", "book now", "more info", "events", "exhibitions", "what's on", "view all"):
            continue
        date_text = ""
        parent = a.parent
        for _ in range(6):
            if not parent:
                break
            date_text = parent.get_text(separator=" ")
            parent = parent.parent
        yield title, full_url, date_text or a.get_text(separator=" ")


def scrape_manchester_art_gallery():
    """Return list of exhibition/event dicts for Manchester Art Gallery."""
    out = []
    urls_to_try = [EVENTS_URL, EXHIBITIONS_URL]
    html_used = None

    for page_url in urls_to_try:
        try:
            r = requests.get(page_url, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 403 or (r.status_code == 200 and "Just a moment" in r.text):
                html_used = _fetch_with_playwright(page_url)
                if html_used:
                    for title, full_url, date_text in _parse_listing_html(html_used, page_url):
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
                break
            r.raise_for_status()
            r.encoding = r.apparent_encoding or "utf-8"
            for title, full_url, date_text in _parse_listing_html(r.text, page_url):
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
        except Exception:
            if html_used is None:
                html_used = _fetch_with_playwright(page_url)
                if html_used:
                    for title, full_url, date_text in _parse_listing_html(html_used, page_url):
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
                    break
            continue

    seen = set()
    unique = []
    for item in out:
        key = item["detail_page_url"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    if not unique:
        for fb in FALLBACK_EXHIBITIONS:
            url = f"{BASE_URL}/event/{fb['slug']}/"
            unique.append({
                "venue_name": VENUE_NAME,
                "venue_city": VENUE_CITY,
                "exhibition_title": fb["title"],
                "start_date": fb.get("start_date"),
                "end_date": fb.get("end_date"),
                "detail_page_url": url,
                "description": None,
                "image_url": None,
            })

    return unique
