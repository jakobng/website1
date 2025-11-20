import requests
from bs4 import BeautifulSoup, NavigableString
from urllib.parse import urljoin
from datetime import date, timedelta
import re
from typing import List, Dict, Optional, Tuple


BASE_URL = "https://www.morc-asagaya.com"
LIST_URL = f"{BASE_URL}/film_date/film_now/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0 Safari/537.36"
    )
}


def fetch_soup(url: str) -> Optional[BeautifulSoup]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"[Morc阿佐ヶ谷] Error fetching {url}: {e}")
        return None


def fetch_film_listing() -> List[Dict[str, str]]:
    """
    Get all film entries from /film_date/film_now/ (both '上映中' and '近日上映予定').
    """
    soup = fetch_soup(LIST_URL)
    if not soup:
        return []

    films: List[Dict[str, str]] = []

    # section id="tp_flim" contains both tabs (pg_film_now and pg_film_plan)
    section = soup.find("section", id="tp_flim")
    if not section:
        print("[Morc阿佐ヶ谷] Could not find film listing section #tp_flim")
        return films

    for film_block in section.find_all("div", class_="tpf_main"):
        for li in film_block.select("li.tpf_list"):
            a = li.find("a", href=True)
            if not a:
                continue
            href = a["href"]
            film_url = urljoin(BASE_URL, href)
            h2 = a.find("h2")
            title = h2.get_text(strip=True) if h2 else a.get_text(strip=True)
            films.append(
                {
                    "title": title,
                    "url": film_url,
                }
            )

    # Deduplicate by URL in case of overlap
    seen = set()
    unique_films: List[Dict[str, str]] = []
    for f in films:
        if f["url"] not in seen:
            seen.add(f["url"])
            unique_films.append(f)

    return unique_films


def parse_year_runtime_country(soup: BeautifulSoup) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """
    Parse '2025年／61分／日本' style line.
    """
    text = soup.get_text("\n", strip=True)
    m = re.search(r"(\d{4})年／(\d+)分／([^\n]+)", text)
    if not m:
        return None, None, None
    year_str = m.group(1)
    runtime_str = m.group(2)
    country_str = m.group(3).strip()
    try:
        runtime_min = int(runtime_str)
    except ValueError:
        runtime_min = None
    return year_str, runtime_min, country_str


def parse_director(soup: BeautifulSoup) -> Optional[str]:
    """
    Parse director from something like:
    '■監督：ガクカワサキ ■出演：...'
    """
    text = soup.get_text("\n", strip=True)
    m = re.search(r"監督：([^■\n]+)", text)
    if not m:
        return None
    director = m.group(1).strip()
    return director or None


def parse_date_range(text: str, year: int) -> Optional[Tuple[date, date]]:
    """
    Parse strings like:
    - '11/21(金)〜12/4(木)'
    - '11/27(木)'
    - '9/19(金)〜終了日未定'
    Return (start_date, end_date) inclusive.
    For '終了日未定', we expand to start_date + 13 days (2 weeks total).
    """
    # Find all month/day pairs
    pairs = re.findall(r"(\d{1,2})/(\d{1,2})", text)
    if not pairs:
        return None

    if len(pairs) == 1:
        m1, d1 = map(int, pairs[0])
        start = date(year, m1, d1)

        # '〜終了日未定' case
        if "終了日未定" in text and "〜" in text:
            end = start + timedelta(days=13)
        else:
            end = start
        return start, end

    # Two explicit dates
    (m1, d1), (m2, d2) = map(lambda x: (int(x[0]), int(x[1])), pairs[:2])
    start = date(year, m1, d1)
    end_year = year

    # Handle year rollover if necessary (e.g. 12/28〜1/5)
    if m2 < m1:
        end_year = year + 1
    end = date(end_year, m2, d2)

    return start, end


def parse_schedule_block(soup: BeautifulSoup, year_str: Optional[str]) -> List[Tuple[date, str]]:
    """
    Parse schedule from the '上映日時' section on a film detail page.
    Returns list of (date_obj, 'HH:MM').
    """
    showings: List[Tuple[date, str]] = []
    if not year_str:
        return showings

    try:
        base_year = int(year_str)
    except ValueError:
        return showings

    # Find heading with '上映日時'
    heading = None
    for tag in soup.find_all(["h2", "h3", "h4"]):
        if "上映日時" in tag.get_text():
            heading = tag
            break

    if not heading:
        return showings

    # Collect text lines between '上映日時' heading and next heading containing 'Ticket'
    lines: List[str] = []
    for sibling in heading.next_siblings:
        if isinstance(sibling, NavigableString):
            text = str(sibling).strip()
            if text:
                for part in re.split(r"[\r\n]+", text):
                    pt = part.strip()
                    if pt:
                        lines.append(pt)
            continue

        if getattr(sibling, "name", None) in ["h2", "h3", "h4"]:
            if "Ticket" in sibling.get_text():
                break

        text = sibling.get_text("\n", strip=True)
        if text:
            for part in re.split(r"[\r\n]+", text):
                pt = part.strip()
                if pt:
                    lines.append(pt)

    if not lines:
        return showings

    # Classify lines as date-only, time-only, or combined.
    date_only_lines: List[str] = []
    time_only_lines: List[str] = []

    for line in lines:
        has_date = bool(re.search(r"\d{1,2}/\d{1,2}", line))
        has_time = bool(re.search(r"\d{1,2}:\d{2}", line))

        if has_date and has_time:
            # Handle lines that already contain both date and time (not common on Morc but possible).
            # Example hypothetical: "11/21(金) 19:30-21:20"
            date_match = re.search(r"(\d{1,2}/\d{1,2})", line)
            time_match = re.search(r"(\d{1,2}:\d{2})", line)
            if date_match and time_match:
                dr = parse_date_range(date_match.group(1), base_year)
                if dr:
                    start, end = dr
                    current = start
                    while current <= end:
                        showings.append((current, time_match.group(1)))
                        current += timedelta(days=1)
        elif has_date:
            date_only_lines.append(line)
        elif has_time:
            time_only_lines.append(line)
        else:
            # Ignore purely descriptive lines
            continue

    # If number of date-only lines matches time-only lines, pair by index.
    # This matches the current Morc pattern: [range_line], [time_line].
    n_pairs = min(len(date_only_lines), len(time_only_lines))
    for i in range(n_pairs):
        dline = date_only_lines[i]
        tline = time_only_lines[i]

        dr = parse_date_range(dline, base_year)
        if not dr:
            continue
        start, end = dr

        tmatch = re.search(r"(\d{1,2}:\d{2})", tline)
        if not tmatch:
            continue
        time_str = tmatch.group(1)

        current = start
        while current <= end:
            showings.append((current, time_str))
            current += timedelta(days=1)

    return showings


def fetch_showings_for_film(film: Dict[str, str]) -> List[Dict]:
    """
    Given {'title': ..., 'url': ...}, fetch the detail page and build showing dicts.
    """
    url = film["url"]
    title = film["title"]

    soup = fetch_soup(url)
    if not soup:
        return []

    year_str, runtime_min, country = parse_year_runtime_country(soup)
    director = parse_director(soup)
    schedule = parse_schedule_block(soup, year_str)

    results: List[Dict] = []
    for d, time_str in schedule:
        results.append(
            {
                "cinema_name": "Morc阿佐ヶ谷",
                "movie_title": title,
                "movie_title_en": None,
                "director": director,
                "year": year_str,
                "country": country,
                "runtime_min": runtime_min,
                "date_text": d.isoformat(),  # 'YYYY-MM-DD'
                "showtime": time_str,
                "detail_page_url": url,
                "program_title": None,
                "purchase_url": None,
            }
        )

    return results


def fetch_morc_asagaya_showings() -> List[Dict]:
    """
    High-level entry point: fetch all films from listing and expand to showings.
    """
    films = fetch_film_listing()
    all_showings: List[Dict] = []

    for film in films:
        film_showings = fetch_showings_for_film(film)
        all_showings.extend(film_showings)

    return all_showings


if __name__ == "__main__":
    showings = fetch_morc_asagaya_showings()
    film_titles = {s["movie_title"] for s in showings}
    print(f"{len(showings)} showings found across {len(film_titles)} films")
    for s in showings[:50]:  # avoid flooding stdout
        print(s)
