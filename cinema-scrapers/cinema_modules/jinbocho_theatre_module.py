from __future__ import annotations

import re
import sys
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.shogakukan.co.jp/jinbocho-theater/program/"
FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
CIRCLED_DIGITS = {
    "①": 1,
    "②": 2,
    "③": 3,
    "④": 4,
    "⑤": 5,
    "⑥": 6,
    "⑦": 7,
    "⑧": 8,
    "⑨": 9,
    "⑩": 10,
    "⑪": 11,
    "⑫": 12,
    "⑬": 13,
    "⑭": 14,
    "⑮": 15,
    "⑯": 16,
    "⑰": 17,
    "⑱": 18,
    "⑲": 19,
    "⑳": 20,
}
CIRCLED_DIGIT_PATTERN = "".join(CIRCLED_DIGITS.keys())
CINEMA_NAME = "神保町シアター"


def clean_text(text: str) -> str:
    """Normalize whitespace."""
    return re.sub(r"\s+", " ", text).strip()


def _normalize_number_token(token: str) -> Optional[int]:
    if not token:
        return None
    if token in CIRCLED_DIGITS:
        return CIRCLED_DIGITS[token]
    normalized = token.translate(FULLWIDTH_DIGITS)
    if normalized.isdigit():
        return int(normalized)
    return None


def _extract_film_number_and_title(raw_title: str) -> tuple[Optional[int], str]:
    title = clean_text(raw_title)
    if not title:
        return None, ""

    first_char = title[0]
    if first_char in CIRCLED_DIGITS:
        number = CIRCLED_DIGITS[first_char]
        cleaned = title[1:].lstrip(" .．)）")
        return number, cleaned

    m = re.match(r"^\s*([0-9０-９]{1,2})[\.．)）]?\s*(.*)$", title)
    if m:
        number = _normalize_number_token(m.group(1))
        cleaned = m.group(2).strip()
        return number, cleaned

    return None, title


def _extract_program_year(text: str) -> Optional[int]:
    if not text:
        return None
    if m := re.search(r"(19|20)\d{2}", text):
        return int(m.group(0))
    return None


def _format_iso_date(year: Optional[int], month: int, day: int) -> str:
    if not year:
        return f"{month}月{day}日"
    return f"{year:04d}-{month:02d}-{day:02d}"


def _parse_dates_from_line(
    line: str,
    current_month: Optional[int],
) -> tuple[list[tuple[int, int]], Optional[int], Optional[int]]:
    dates: list[tuple[int, int]] = []
    line_year = _extract_program_year(line)

    for m in re.finditer(r"(\d{1,2})\s*月\s*(\d{1,2})\s*日", line):
        month = int(m.group(1))
        day = int(m.group(2))
        dates.append((month, day))
        current_month = month

    if not dates:
        for m in re.finditer(r"(\d{1,2})/(\d{1,2})", line):
            month = int(m.group(1))
            day = int(m.group(2))
            dates.append((month, day))
            current_month = month

    if not dates and current_month:
        for m in re.finditer(r"(\d{1,2})\s*日", line):
            day = int(m.group(1))
            dates.append((current_month, day))

    return dates, current_month, line_year


def _parse_showings_from_lines(lines: List[str], default_year: Optional[int]) -> List[Dict[str, str]]:
    showings: List[Dict[str, str]] = []
    current_month: Optional[int] = None

    for line in lines:
        line = clean_text(line)
        if not line or ":" not in line:
            continue

        times = re.findall(r"\d{1,2}:\d{2}", line)
        if not times:
            continue

        dates, current_month, line_year = _parse_dates_from_line(line, current_month)
        if not dates:
            continue

        use_year = line_year or default_year
        for month, day in dates:
            date_text = _format_iso_date(use_year, month, day)
            for show_time in times:
                showings.append({"date_text": date_text, "showtime": show_time})

    return showings


def _parse_schedule_map_from_lines(
    lines: List[str],
    default_year: Optional[int],
) -> Dict[int, List[Dict[str, str]]]:
    schedule_map: Dict[int, List[Dict[str, str]]] = {}
    current_month: Optional[int] = None

    for line in lines:
        line = clean_text(line)
        if not line or ":" not in line:
            continue

        dates, current_month, line_year = _parse_dates_from_line(line, current_month)
        if not dates:
            continue

        pairs = set()
        time_first = re.findall(
            rf"(\d{{1,2}}:\d{{2}})\s*[（(]?\s*([0-9０-９]|[{CIRCLED_DIGIT_PATTERN}])\s*[)）]?",
            line,
        )
        for time_text, number_text in time_first:
            film_number = _normalize_number_token(number_text)
            if film_number:
                pairs.add((film_number, time_text))

        number_first = re.findall(
            rf"([0-9０-９]|[{CIRCLED_DIGIT_PATTERN}])\s*[)）]?\s*(\d{{1,2}}:\d{{2}})",
            line,
        )
        for number_text, time_text in number_first:
            film_number = _normalize_number_token(number_text)
            if film_number:
                pairs.add((film_number, time_text))

        if not pairs:
            continue

        use_year = line_year or default_year
        for month, day in dates:
            date_text = _format_iso_date(use_year, month, day)
            for film_number, time_text in pairs:
                schedule_map.setdefault(film_number, []).append(
                    {"date_text": date_text, "showtime": time_text}
                )

    return schedule_map


def fetch_soup(url: str, *, encoding: str = "utf-8") -> Optional[BeautifulSoup]:
    """Fetch a URL and return a BeautifulSoup object, or None on error."""
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"ERROR: [{CINEMA_NAME}] Could not fetch {url}: {e}", file=sys.stderr)
        return None

    if encoding:
        resp.encoding = encoding
    return BeautifulSoup(resp.text, "html.parser")


def extract_year(text: str) -> Optional[str]:
    """
    Extract and convert Japanese era notation to Gregorian year.

    Handles typical patterns from this site, e.g.:
      S38('63)／大映京都／白黒／1時間36分
      S42('67)／...
      H10('98)／...
      H12(2000)／...
      R2('20)／...

    Priority:
      1. If there is an explicit 4-digit year in parentheses → use that.
      2. Otherwise, look for [SHR]<number> and convert era year → Gregorian.
    """
    # 1) Explicit 4-digit year, e.g. H12(2000)
    m4 = re.search(r"\((\d{4})\)", text)
    if m4:
        return m4.group(1)

    # 2) Era notation like S38, H10, R2
    m = re.search(r"([SHR])\s*(\d+)", text)
    if not m:
        return None

    era = m.group(1)
    era_year = int(m.group(2))

    if era == "S":  # Shōwa 1926–1989
        gregorian = 1925 + era_year
    elif era == "H":  # Heisei 1989–2019
        gregorian = 1988 + era_year
    elif era == "R":  # Reiwa 2019–
        gregorian = 2018 + era_year
    else:
        return None

    return str(gregorian)


def _parse_program_page(program_slug: str = "fujimura") -> List[Dict]:
    """
    Parse a single program (e.g. 'fujimura') and return a list of showings.
    """
    results: List[Dict] = []

    program_url = urljoin(BASE_URL, f"{program_slug}.html")
    soup = fetch_soup(program_url)
    if soup is None:
        return results

    # Program title (including any subtitle/series label)
    title_block = soup.select_one("#program_top h3")
    if title_block:
        program_title = clean_text(title_block.get_text(" ", strip=True))
    else:
        program_title = ""

    # Overall period text, e.g. "2025年11月1日（土）～28日（金）"
    schedule_tag = soup.select_one("p.schedule")
    program_period_text = clean_text(schedule_tag.get_text()) if schedule_tag else ""
    program_year = _extract_program_year(program_period_text) or _extract_program_year(
        soup.get_text(" ", strip=True)
    )

    # Find the detailed list page (e.g. fujimura_list.html)
    list_href = None
    for a in soup.find_all("a", href=True):
        if a["href"].endswith("_list.html"):
            list_href = a["href"]
            break

    if list_href is None:
        # Fallback: assume <slug>_list.html
        list_href = f"{program_slug}_list.html"

    list_url = urljoin(BASE_URL, list_href)
    list_soup = fetch_soup(list_url)
    if list_soup is None:
        return results

    schedule_lines = [
        line for line in soup.get_text("\n").splitlines() if ":" in line
    ]
    schedule_map = _parse_schedule_map_from_lines(schedule_lines, program_year)

    # Each film block
    for film in list_soup.select("div.data2_film"):
        # --- Basic metadata ---
        h4 = film.select_one(".data2_title h4")
        movie_title = ""
        film_number = None
        if h4:
            film_number, movie_title = _extract_film_number_and_title(h4.get_text())

        text_blocks = [
            clean_text(p.get_text(" ", strip=True)) for p in film.select(".data2_text")
        ]
        meta_text = " ".join(text_blocks)

        # Year from Japanese era notation
        year = extract_year(meta_text)

        # Director
        director_match = re.search(r"監督[:：]\s*([^\s■／]+)", meta_text)
        director = director_match.group(1) if director_match else None

        # --- Showtimes ---
        sche_tag = film.select_one(".data2_sche")
        showings: List[Dict[str, Optional[str]]] = []

        if sche_tag:
            showings = _parse_showings_from_lines(
                sche_tag.get_text("\n").splitlines(),
                program_year,
            )

        if not showings and film_number and film_number in schedule_map:
            showings = list(schedule_map.get(film_number, []))

        # If for some reason no per-line showings parsed, fall back to program period
        if not showings:
            showings.append(
                {
                    "date_text": program_period_text,
                    "showtime": None,
                }
            )

        # --- Assemble standardized entries ---
        for s in showings:
            results.append(
                {
                    "cinema_name": CINEMA_NAME,
                    "movie_title": movie_title,
                    "movie_title_en": None,
                    "director": director,
                    "year": year,
                    "country": None,
                    "runtime_min": None,
                    "date_text": s["date_text"],
                    "showtime": s["showtime"],
                    "detail_page_url": list_url,
                    "program_title": program_title,
                    "purchase_url": None,
                }
            )

    return results


def _get_current_program_urls() -> List[str]:
    """
    Scrape the main page to find current and upcoming program URLs.
    Returns a list of absolute URLs to program pages.
    """
    site_root = BASE_URL.replace("program/", "") # https://www.shogakukan.co.jp/jinbocho-theater/
    soup = fetch_soup(site_root)
    if soup is None:
        return []

    program_urls = set()
    
    # Look for links in the "Now Showing" and "Coming Soon" sections
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # normalize to absolute URL using the site root, not the program base
        full_url = urljoin(site_root, href)
        
        # Check if it looks like a program page
        if "/program/" in full_url and full_url.endswith(".html") and "index.html" not in full_url and "coming.html" not in full_url:
             program_urls.add(full_url)

    return list(program_urls)


def scrape_jinbocho() -> List[Dict]:
    """
    Public entry point used by main_scraper.
    Dynamically finds program pages from the homepage.
    """
    all_showings = []
    
    # 1. Get program URLs from main page
    program_urls = _get_current_program_urls()
    print(f"DEBUG: Found program URLs: {program_urls}", file=sys.stderr)

    # 2. Parse each program page
    for url in program_urls:
        # Extract slug from URL for the _parse_program_page function if we want to keep using it as is,
        # OR better, modify _parse_program_page to handle the URL directly. 
        # But _parse_program_page constructs URL from slug: 
        # program_url = urljoin(BASE_URL, f"{program_slug}.html")
        
        # Let's extract the slug:
        # .../program/slug.html -> slug
        match = re.search(r"/program/([^/]+)\.html$", url)
        if match:
            slug = match.group(1)
            # Avoid re-scraping list pages directly (though the logic handles it, usually we want the parent program page)
            if "_list" in slug:
                continue
                
            print(f"DEBUG: Scraping program: {slug}", file=sys.stderr)
            showings = _parse_program_page(slug)
            all_showings.extend(showings)
            
    return all_showings


if __name__ == "__main__":
    data = scrape_jinbocho()
    print(f"{len(data)} showings found")
    
    with_times = [d for d in data if d['showtime']]
    print(f"Showings with times: {len(with_times)}")
    
    for d in with_times[:3]:
        print(d)
