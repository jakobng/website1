# The Harris, Preston (Museum, Art Gallery & Library)
from urllib.parse import urljoin
import re
import requests
from bs4 import BeautifulSoup
from ._utils import parse_date_range, norm

BASE_URL = "https://theharris.org.uk"
WHATS_ON_URL = "https://theharris.org.uk/whats-on"
VENUE_NAME = "The Harris"
VENUE_CITY = "Preston"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NorthArtExhibitions/1.0)", "Accept-Language": "en-GB,en;q=0.9"}
TIMEOUT = 25

def _parse_harris_date(text):
    m = re.search(r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\s*-\s*(\w+day)?\s*,?\s*(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})", text, re.I)
    if m:
        d1, mo1, y1, d2, mo2, y2 = m.groups()[0], m.groups()[1], m.groups()[2], m.groups()[4], m.groups()[5], m.groups()[6]
        months = "January February March April May June July August September October November December".split()
        try:
            m1 = months.index(mo1.capitalize()) + 1
            m2 = months.index(mo2.capitalize()) + 1
            return f"{y1}-{m1:02d}-{int(d1):02d}", f"{y2}-{m2:02d}-{int(d2):02d}"
        except (ValueError, IndexError):
            pass
    return None, None

def scrape_harris_preston():
    out = []
    try:
        r = requests.get(WHATS_ON_URL, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
    except Exception as e:
        raise RuntimeError("Failed to fetch " + WHATS_ON_URL + ": " + str(e)) from e
    soup = BeautifulSoup(r.text, "html.parser")
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if "/product/" not in href:
            continue
        full_url = urljoin(BASE_URL, href)
        title = norm(a.get_text())
        if not title:
            continue
        if "Exhibition" in title and "FREE" in title:
            title = title.replace("ExhibitionFREE", "").replace("Exhibition", "").strip()
        if not title or len(title) < 3:
            continue
        if title.lower() in ("book now", "see all", "find out more"):
            continue
        date_text = ""
        parent = a.parent
        for _ in range(5):
            if not parent:
                break
            date_text = parent.get_text(separator=" ")
            parent = parent.parent
        start_str, end_str = parse_date_range(date_text)
        if not start_str and not end_str:
            start_str, end_str = _parse_harris_date(date_text)
        out.append({"venue_name": VENUE_NAME, "venue_city": VENUE_CITY, "exhibition_title": title[:500], "start_date": start_str, "end_date": end_str, "detail_page_url": full_url, "description": None, "image_url": None})
    seen = set()
    unique = []
    for item in out:
        k = item["detail_page_url"]
        if k in seen:
            continue
        seen.add(k)
        tit = (item.get("exhibition_title") or "").lower()
        skip = any(x in tit for x in ("baby bounce", "rhyme", "egyptian balcony", "world book day", "celebrating world", "art and creative workshop"))
        if not skip:
            unique.append(item)
    return unique
