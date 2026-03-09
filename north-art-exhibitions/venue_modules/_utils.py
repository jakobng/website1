# Shared helpers for venue scrapers
import re
from datetime import date
from urllib.parse import urljoin

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
MONTH_MAP = {m: i for i, m in enumerate(MONTHS.split("|"), 1)}

# e.g. "25 July 2025 – 5 July 2026" or "13 February–31 May 2026" or "22 November 2025 – 4 May 2026"
DATE_RANGE_RE = re.compile(
    r"(\d{1,2})\s+(" + MONTHS + r")\s+(\d{4})\s*[–\-]\s*(\d{1,2})\s+(" + MONTHS + r")\s+(\d{4})",
    re.IGNORECASE
)
# Single date e.g. "14 March 2026"
SINGLE_DATE_RE = re.compile(r"(\d{1,2})\s+(" + MONTHS + r")\s+(\d{4})", re.IGNORECASE)
# "February 7, 2023" or "March 14, 2025 - March 15, 2026"
MONTH_FIRST_RE = re.compile(
    r"(" + MONTHS + r")\s+(\d{1,2}),?\s+(\d{4})\s*[–\-]\s*(" + MONTHS + r")\s+(\d{1,2}),?\s+(\d{4})",
    re.IGNORECASE
)
MONTH_FIRST_SINGLE_RE = re.compile(r"(" + MONTHS + r")\s+(\d{1,2}),?\s+(\d{4})", re.IGNORECASE)


def parse_date_range(text):
    """Parse date range from text. Returns (start_date_str, end_date_str) or (None, None)."""
    if not text:
        return None, None
    text = re.sub(r"\s+", " ", text.strip())
    m = DATE_RANGE_RE.search(text)
    if m:
        d1, mo1, y1, d2, mo2, y2 = m.groups()
        try:
            start = date(int(y1), MONTH_MAP[mo1.capitalize()], int(d1))
            end = date(int(y2), MONTH_MAP[mo2.capitalize()], int(d2))
            return start.isoformat(), end.isoformat()
        except (ValueError, KeyError):
            pass
    m = SINGLE_DATE_RE.search(text)
    if m:
        d, mo, y = m.groups()
        try:
            single = date(int(y), MONTH_MAP[mo.capitalize()], int(d))
            return single.isoformat(), single.isoformat()
        except (ValueError, KeyError):
            pass
    m = MONTH_FIRST_RE.search(text)
    if m:
        mo1, d1, y1, mo2, d2, y2 = m.groups()
        try:
            start = date(int(y1), MONTH_MAP[mo1.capitalize()], int(d1))
            end = date(int(y2), MONTH_MAP[mo2.capitalize()], int(d2))
            return start.isoformat(), end.isoformat()
        except (ValueError, KeyError):
            pass
    m = MONTH_FIRST_SINGLE_RE.search(text)
    if m:
        mo, d, y = m.groups()
        try:
            single = date(int(y), MONTH_MAP[mo.capitalize()], int(d))
            return single.isoformat(), single.isoformat()
        except (ValueError, KeyError):
            pass
    if "ongoing" in text.lower() or "permanent" in text.lower():
        today = date.today().isoformat()
        return today, None  # no end date
    return None, None


def norm(text):
    """Normalize whitespace."""
    if not text:
        return ""
    return " ".join(str(text).split()).strip()


def get_page_meta(url, headers=None, timeout=15):
    """
    Fetch a page and return og:title, og:image, og:description (or fallbacks).
    Returns dict with keys: title, image_url, description (values may be None).
    """
    try:
        import requests
        from bs4 import BeautifulSoup
        h = headers or {}
        r = requests.get(url, headers=h, timeout=timeout)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
        out = {"title": None, "image_url": None, "description": None}
        # og: tags
        for meta in soup.find_all("meta", property=True):
            p = (meta.get("property") or "").lower()
            c = (meta.get("content") or "").strip()
            if p == "og:title" and c:
                out["title"] = norm(c)
            elif p == "og:image" and c:
                out["image_url"] = c if c.startswith("http") else urljoin(url, c)
            elif p == "og:description" and c:
                out["description"] = norm(c)[:1000]
        # Fallback: h1 for title
        if not out["title"]:
            h1 = soup.find("h1")
            if h1:
                out["title"] = norm(h1.get_text())
        return out
    except Exception:
        return {"title": None, "image_url": None, "description": None}
