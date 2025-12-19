# yebisu_garden_module.py
# Migrated from Selenium to Playwright for improved reliability.

from __future__ import annotations

import datetime as _dt
import json
import re
import sys
from typing import Dict, List

from bs4 import BeautifulSoup

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    sys.exit(
        "ERROR: Playwright not installed. Please run 'pip install playwright' and 'playwright install chromium'."
    )

# ----------------------------------------------------------------
CINEMA_NAME = "YEBISU GARDEN CINEMA"
BASE_URL = "https://www.unitedcinemas.jp/ygc"
DAILY_URL = BASE_URL + "/daily.php?date={}"
DAYS_AHEAD = 5
PLAYWRIGHT_TIMEOUT = 30000  # 30 seconds

_SCREEN_RE = re.compile(r"(\d)screen")
_YEAR_RE = re.compile(r"(\d{4})")
# Regex to find year in synopsis as a fallback.
_YEAR_IN_SYNOPSIS_RE = re.compile(r"(\d{4})年製作")

# ----------------------------------------------------------------
def _clean_title(text: str) -> str:
    """
    Cleans Yebisu titles by removing quotes, parentheses, and technical suffixes.
    """
    if not text: return ""

    # 1. Strip Technical Suffixes (Aggressive)
    patterns = [
        r"\s*4K.*$",               # Matches "4K", "4K レストア", "4K Restored"
        r"\s*デジタル.?リマスター.*$", # Matches "デジタルリマスター", "デジタル・リマスター版"
        r"\s*レストア.*$",           # Matches "レストア版"
        r"\s*完全版.*$",
        r"\s*ディレクターズ.?カット.*$"
    ]

    for pat in patterns:
        text = re.sub(pat, "", text, flags=re.IGNORECASE)

    # 2. Remove parentheses content (e.g. (字幕), (吹替))
    text = re.sub(r"\s*[（(].*?[)）]\s*", "", text)

    # 3. Clean up whitespace
    text = text.strip()

    # 4. Remove wrapping Japanese quotes
    if text.startswith("『") and text.endswith("』"):
        text = text[1:-1]

    # Remove standard double quotes just in case
    text = text.replace('"', '').strip()

    return text.strip()

# ----------------------------------------------------------------
def _parse_film_details(html: str) -> Dict:
    soup = BeautifulSoup(html, "html.parser")
    details = { "director": None, "synopsis": None, "year": None, "official_site": None }

    director_dt = soup.find("dt", string=re.compile("監督"))
    if director_dt and director_dt.find_next_sibling("dd"):
        details["director"] = director_dt.find_next_sibling("dd").get_text(strip=True)

    synopsis_tag = soup.select_one("div.movieDetailInfoFilm > p:not([class])")
    if synopsis_tag:
        details["synopsis"] = synopsis_tag.get_text(strip=True)

    # --- YEAR EXTRACTION LOGIC ---
    # Method 1: Check the copyright tag first (preferred method).
    copyright_tag = soup.select_one("span.copy")
    if copyright_tag:
        match = _YEAR_RE.search(copyright_tag.get_text())
        if match:
            details["year"] = match.group(1)

    # Method 2 (FALLBACK): If year not found, check the synopsis text.
    if not details["year"] and details["synopsis"]:
        match = _YEAR_IN_SYNOPSIS_RE.search(details["synopsis"])
        if match:
            details["year"] = match.group(1)
            print(f"INFO   : Found year '{details['year']}' in synopsis as fallback.")

    site_link_tag = soup.select_one("div#movieSubInfo a.btn.bt_s")
    if site_link_tag and site_link_tag.has_attr("href"):
        details["official_site"] = site_link_tag["href"]

    return details

# ----------------------------------------------------------------
def _parse_daily_showtimes(html: str, date_obj: _dt.date) -> List[Dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: List[Dict] = []

    for film_li in soup.select("ul#dailyList li.clearfix"):
        link_tag = film_li.select_one("h3 span.movieTitle a")
        if not link_tag: continue

        raw_title = link_tag.get_text(strip=True)
        # Apply the new cleaning function
        title = _clean_title(raw_title)

        detail_url = None
        if link_tag.has_attr("href"):
            href = link_tag['href']
            base_href = href.split('?')[0]
            film_param = next((part for part in href.split('?') if part.startswith("film=")), None)

            clean_href = f"{base_href}?{film_param}" if film_param else base_href
            detail_url = f"{BASE_URL}/{clean_href}" if 'film.php' in clean_href else clean_href

        screen_alt = (film_li.select_one("p.screenNumber img[alt*='screen']") or {}).get("alt", "")
        m = _SCREEN_RE.search(screen_alt)
        screen = f"スクリーン{m.group(1)}" if m else "スクリーン"

        for st in film_li.select("li.startTime"):
            showtime = st.get_text(strip=True)
            if showtime:
                rows.append(dict(movie_title=title, date_text=str(date_obj), screen_name=screen, showtime=showtime, detail_page_url=detail_url))
    return rows

# ----------------------------------------------------------------
def scrape_yebisu_garden_cinema(days_ahead: int = DAYS_AHEAD) -> List[Dict]:
    all_showings: List[Dict] = []
    film_details_cache: Dict[str, Dict] = {}
    today = _dt.date.today()

    pw_instance = sync_playwright().start()
    try:
        print(f"INFO: [{CINEMA_NAME}] Launching Playwright browser...", file=sys.stderr)
        browser = pw_instance.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(PLAYWRIGHT_TIMEOUT)

        for offset in range(days_ahead):
            date_obj = today + _dt.timedelta(days=offset)
            url = DAILY_URL.format(date_obj.isoformat())
            print(f"INFO   : GET {url} for {CINEMA_NAME}")

            try:
                page.goto(url, wait_until="networkidle")
                # Wait for schedule to load
                page.wait_for_selector("ul#dailyList li.clearfix", timeout=PLAYWRIGHT_TIMEOUT)
            except PlaywrightTimeout:
                print(f"WARNING: Schedule not found or page timed out for {date_obj} at {CINEMA_NAME} - skipping day")
                continue

            daily_showings = _parse_daily_showtimes(page.content(), date_obj)

            urls_to_scrape = {s['detail_page_url'] for s in daily_showings if s.get('detail_page_url') and s['detail_page_url'] not in film_details_cache}

            if urls_to_scrape:
                print(f"INFO   : Found {len(urls_to_scrape)} new movie(s) to get details for.")

            for film_url in urls_to_scrape:
                print(f"INFO   : Scraping details from: {film_url}")
                try:
                    page.goto(film_url, wait_until="networkidle")
                    page.wait_for_selector("#detailBox", timeout=PLAYWRIGHT_TIMEOUT)
                    details = _parse_film_details(page.content())
                    film_details_cache[film_url] = details
                except PlaywrightTimeout:
                    print(f"WARNING: Could not load detail page {film_url} in time.")
                    film_details_cache[film_url] = {}  # Cache failure to avoid retries
                page.wait_for_timeout(500)

            for showing in daily_showings:
                if showing.get('detail_page_url') in film_details_cache:
                    showing.update(film_details_cache[showing['detail_page_url']])
                showing['cinema_name'] = CINEMA_NAME

            all_showings.extend(daily_showings)
            page.wait_for_timeout(700)

        browser.close()

    except Exception as e:
        print(f"ERROR: [{CINEMA_NAME}] An error occurred: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
    finally:
        pw_instance.stop()

    print(f"INFO   : Collected {len(all_showings)} showings total from {CINEMA_NAME}.")
    return all_showings

if __name__ == "__main__":
    data = scrape_yebisu_garden_cinema()

    if not data:
        print(f"No data collected for {CINEMA_NAME}.")
        sys.exit(1)

    output_filename = "yebisu_showtimes.json"
    print(f"INFO   : Writing {len(data)} records to {output_filename}...")
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print(f"INFO   : Successfully created {output_filename}.")
