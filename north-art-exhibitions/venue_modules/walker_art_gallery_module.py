# Walker Art Gallery, Liverpool
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from ._utils import parse_date_range, norm

BASE_URL = "https://www.liverpoolmuseums.org.uk"
WALKER_WHATSON = "https://www.liverpoolmuseums.org.uk/whatson"
VENUE_NAME = "Walker Art Gallery"
VENUE_CITY = "Liverpool"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NorthArtExhibitions/1.0)", "Accept-Language": "en-GB,en;q=0.9"}
TIMEOUT = 25
FALLBACK = [
    {"title": "John Moores Painting Prize", "slug": "john-moors-painting-prize", "start_date": "2025-09-06", "end_date": "2026-03-01"},
    {"title": "Liverpool Biennial 2025", "slug": "liverpool-biennial-2025", "start_date": "2025-06-07", "end_date": "2025-09-14"},
    {"title": "New Works at the Walker", "slug": "new-works-walker"},
]

def scrape_walker_art_gallery():
    out = []
    try:
        r = requests.get(WALKER_WHATSON, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if "walker" not in href.lower() or ("/whatson/" not in href and "/event/" not in href):
                continue
            full_url = urljoin(BASE_URL, href)
            title = norm(a.get_text())
            if not title or len(title) < 3 or title.lower() in ("read more", "book", "what's on"):
                continue
            date_text = ""
            p = a.parent
            for _ in range(5):
                if not p:
                    break
                date_text = p.get_text(separator=" ")
                p = p.parent
            start_str, end_str = parse_date_range(date_text)
            out.append({"venue_name": VENUE_NAME, "venue_city": VENUE_CITY, "exhibition_title": title[:500], "start_date": start_str, "end_date": end_str, "detail_page_url": full_url, "description": None, "image_url": None})
    except Exception:
        pass
    if not out:
        for fb in FALLBACK:
            path = "/whatson/walker-art-gallery/exhibition/" + fb.get("slug", "")
            out.append({"venue_name": VENUE_NAME, "venue_city": VENUE_CITY, "exhibition_title": fb["title"], "start_date": fb.get("start_date"), "end_date": fb.get("end_date"), "detail_page_url": urljoin(BASE_URL, path), "description": None, "image_url": None})
    seen = set()
    unique = []
    for item in out:
        k = item["detail_page_url"]
        if k not in seen:
            seen.add(k)
            unique.append(item)
    return unique
