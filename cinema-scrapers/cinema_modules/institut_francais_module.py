from __future__ import annotations

import re
import sys
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://culture.institutfrancais.jp/event?taxonomy=cinema"
CINEMA_NAME = "アンスティチュ・フランセ東京"


def clean_text(text: str) -> str:
    """Normalize whitespace."""
    return re.sub(r"\s+", " ", text).strip()


def fetch_soup(url: str) -> Optional[BeautifulSoup]:
    """Fetch a URL and return a BeautifulSoup object, or None on error."""
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as e:
        print(f"ERROR: [{CINEMA_NAME}] Could not fetch {url}: {e}", file=sys.stderr)
        return None


def parse_peatix_link_text(text: str) -> Optional[tuple[str, str]]:
    """
    Parse text like '1月16日(金) 16:00'
    Returns (date_iso, time_str)
    """
    # Pattern: MM月DD日... HH:MM
    match = re.search(r"(\d+)月(\d+)日.*?(\d{1,2}:\d{2})", text)
    if not match:
        return None

    month, day, time_str = match.groups()
    current_year = datetime.now().year
    
    # Heuristic for year transition
    if int(month) < datetime.now().month and datetime.now().month > 10:
        year = current_year + 1
    else:
        year = current_year

    date_iso = f"{year:04d}-{int(month):02d}-{int(day):02d}"
    return date_iso, time_str


def scrape_event_page(url: str, event_title: str) -> List[Dict]:
    """
    Extract specific screenings from an event detail page.
    """
    results = []
    soup = fetch_soup(url)
    if not soup:
        return results

    # Specific screenings are often in 'text-box' or 'detail-box'
    # and usually linked to Peatix.
    peatix_links = soup.find_all("a", href=lambda h: h and "peatix.com" in h)
    
    for link in peatix_links:
        link_text = clean_text(link.get_text())
        parsed = parse_peatix_link_text(link_text)
        if not parsed:
            continue
        
        date_iso, time_str = parsed
        
        # Try to find the movie title. It's often in the nearest preceding H3.
        movie_title = event_title # Default to event title
        
        # Look back for H3
        prev_h3 = link.find_previous("h3")
        if prev_h3:
            h3_text = clean_text(prev_h3.get_text())
            # Sometimes H3 is "【作品紹介】" or similar, ignore those
            if "作品紹介" not in h3_text and h3_text:
                movie_title = h3_text

        # Clean movie title (often has French title attached)
        # e.g. "気のいい女たち　Les Bonnes femmes"
        # We'll keep it as is or try to split if needed.
        
        results.append({
            "cinema_name": CINEMA_NAME,
            "movie_title": movie_title,
            "movie_title_en": None,
            "director": None,
            "year": None,
            "country": None,
            "runtime_min": None,
            "date_text": date_iso,
            "showtime": time_str,
            "detail_page_url": url,
            "program_title": event_title,
            "purchase_url": link["href"],
        })

    return results


def scrape_institut_francais() -> List[Dict]:
    """
    Scrape Institut Français Tokyo screenings.
    """
    results: List[Dict] = []
    soup = fetch_soup(BASE_URL)
    if soup is None:
        return results

    # Find all event items
    articles = soup.select(".article-item")
    for article in articles:
        # Check location
        location_tag = article.select_one(".location")
        if location_tag and "東京" not in location_tag.get_text():
            continue
        
        title_tag = article.select_one(".title-main")
        if not title_tag:
            continue
        
        event_title = clean_text(title_tag.get_text())
        event_url = article.get("href")
        if not event_url:
            continue
        
        # Detailed scraping of each event page
        event_results = scrape_event_page(event_url, event_title)
        results.extend(event_results)

    return results


if __name__ == "__main__":
    data = scrape_institut_francais()
    print(f"{len(data)} showings found")
    for d in data[:5]:
        print(d)
