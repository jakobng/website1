from __future__ import annotations

import re
import sys
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.shogakukan.co.jp/jinbocho-theater/program/"
CINEMA_NAME = "神保町シアター"


def clean_text(text: str) -> str:
    """Normalize whitespace."""
    return re.sub(r"\s+", " ", text).strip()


def fetch_soup(url: str, *, encoding: str = "shift_jis") -> Optional[BeautifulSoup]:
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

    # Each film block
    for film in list_soup.select("div.data2_film"):
        # --- Basic metadata ---
        h4 = film.select_one(".data2_title h4")
        movie_title = ""
        if h4:
            # Remove leading "1." etc.
            movie_title = clean_text(re.sub(r"^\d+\.\s*", "", h4.get_text()))

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
            for line in sche_tag.get_text("\n").splitlines():
                line = clean_text(line)
                if not line or not re.search(r"\d", line):
                    continue
                # Example lines:
                #   11月1日（土）11:00
                #   11月3日（祝・月）15:30
                m = re.match(r"(\d+月\d+日[^\d]*)(\d{1,2}:\d{2})", line)
                if m:
                    show_date, show_time = m.groups()
                    showings.append(
                        {
                            "date_text": show_date,
                            "showtime": show_time,
                        }
                    )

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


def scrape_jinbocho() -> List[Dict]:
    """
    Public entry point used by main_scraper.

    Currently hard-coded to the 'fujimura' program page.
    If you later want to support multiple slugs, you can
    extend this to loop over a list of program slugs.
    """
    return _parse_program_page("fujimura")


if __name__ == "__main__":
    data = scrape_jinbocho()
    print(f"{len(data)} showings found")
    for d in data[:3]:
        print(d)
