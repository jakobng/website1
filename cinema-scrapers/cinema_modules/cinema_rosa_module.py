from __future__ import annotations

import datetime as dt
import json
import re
import sys
import time
import unicodedata
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

try:
    from playwright.sync_api import sync_playwright, Page, Error, TimeoutError
except ImportError:
    sys.exit(
        "ERROR: Playwright not installed. Please run 'pip install playwright' and 'playwright install chromium'."
    )

# --- Constants ---
CINEMA_NAME = "池袋シネマ・ロサ"
PLAYWRIGHT_TIMEOUT = 30000  # 30 seconds
DAYS_TO_SCRAPE = 7

# Eigaland (for schedule)
EIGALAND_URL = "https://schedule.eigaland.com/schedule?webKey=c34cee0e-5a5e-4b99-8978-f04879a82299"
DATE_ITEM_SELECTOR_CSS = "div.calender-head-item"
MOVIE_SCHEDULE_SELECTOR_CSS = "div.movie-schedule"
MOVIE_TITLE_EIGALAND_CSS = "h2.text-center"
SHOWTIME_BLOCK_CSS = ".movie-schedule-info.flex-row"
SHOWTIME_TIME_CSS = ".time h2"
SHOWTIME_SCREEN_CSS = ".room .name"

# Cinema Rosa site (for details)
ROSA_BASE_URL = "https://www.cinemarosa.net/"
ROSA_NOWSHOWING_URL = urljoin(ROSA_BASE_URL, "/nowshowing/")
ROSA_INDIES_URL = urljoin(ROSA_BASE_URL, "/indies/")


def _clean_title_for_matching(text: Optional[str]) -> str:
    if not text:
        return ""
    text = unicodedata.normalize('NFKC', text)
    text = text.replace('映画 ', '').replace(' ', '')
    text = re.sub(r'[【『「《\(（].*?[】』」》\)）]', '', text)
    text = re.sub(r'[<【『「]', '', text)
    return text.strip().lower()

def _clean_text(text: Optional[str]) -> str:
    if not text: return ""
    return ' '.join(text.strip().split())

def _fetch_soup(url: str) -> Optional[BeautifulSoup]:
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
        response.raise_for_status()
        return BeautifulSoup(response.content, 'html.parser')
    except requests.RequestException as e:
        print(f"ERROR: [{CINEMA_NAME}] Could not fetch static page {url}: {e}", file=sys.stderr)
        return None

def _parse_date_from_eigaland(date_str: str, current_year: int) -> Optional[dt.date]:
    if match := re.match(r"(\d{1,2})/(\d{1,2})", date_str):
        month, day = map(int, match.groups())
        try:
            today = dt.date.today()
            year = current_year
            if month < today.month - 6:
                year = current_year + 1
            elif month > today.month + 6:
                 year = current_year - 1
            return dt.date(year, month, day)
        except ValueError: return None
    return None

def _parse_rosa_detail_page(soup: BeautifulSoup) -> Dict[str, Optional[str]]:
    details = {"director": None, "year": None, "runtime_min": None, "country": None, "synopsis": None}

    if info_p := soup.select_one("p.film_info"):
        film_info_text = ' '.join(info_p.get_text(separator=' ').split())
        if match := re.search(r"(\d{4})\s*/", film_info_text): details["year"] = match.group(1)
        if match := re.search(r"(\d+時間)?\s*(\d+)分", film_info_text):
            h = int(re.sub(r'\D', '', match.group(1))) if match.group(1) else 0
            m = int(match.group(2))
            details["runtime_min"] = str(h * 60 + m)
        if parts := [p.strip() for p in film_info_text.split('/') if p]:
            if len(parts) > 1 and details["year"]:
                for part in parts:
                    if (part != details["year"]
                        and '分' not in part
                        and not part.isdigit()
                        and '時間' not in part):
                        details["country"] = part.split(' ')[0]
                        break

    if film_txt_div := soup.select_one("div.film_txt"):
        for p_tag in film_txt_div.find_all('p'):
            p_text = p_tag.get_text(strip=True)
            if "監督" in p_text:
                clean_p = re.sub(r'監督|脚本|：|:', '', p_text).strip("・ ")
                details["director"] = clean_p.split(' ')[0].split('／')[0].split('(')[0].strip()
                break

        synopsis_p = None
        if free_area_div := film_txt_div.select_one("div.free_area"):
            for p_tag in free_area_div.find_all('p', recursive=False):
                if "【STORY】" in p_tag.get_text(strip=True):
                    synopsis_p = p_tag
                    break

            if synopsis_p:
                synopsis_clone = BeautifulSoup(str(synopsis_p), 'html.parser')
                if story_br := synopsis_clone.find('br'):
                    story_br.replace_with(" ")

                synopsis_text = _clean_text(synopsis_clone.get_text(strip=True))
                details["synopsis"] = synopsis_text.replace("【STORY】", "").strip()
            else:
                for p_tag in free_area_div.find_all('p', recursive=False):
                    p_text = p_tag.get_text(strip=True)
                    if p_text and not p_text.startswith('☆') and '詳細はこちら' not in p_text and len(p_text) > 10:
                        details["synopsis"] = _clean_text(p_text)
                        break

    return details

def scrape_cinema_rosa() -> List[Dict[str, str]]:
    details_cache: Dict[str, Dict] = {}

    # Step 1: Build details cache from Cinema Rosa website
    for start_url in [ROSA_NOWSHOWING_URL, ROSA_INDIES_URL]:
        print(f"INFO: [{CINEMA_NAME}] Fetching movie list from {start_url}", file=sys.stderr)
        soup = _fetch_soup(start_url)
        if not soup:
            continue

        for link in soup.select(".show_box a"):
            title_node = link.select_one(".show_title")
            if not title_node:
                continue

            raw_title = _clean_text(title_node.text)
            title_key = _clean_title_for_matching(raw_title)
            if title_key in details_cache:
                continue

            detail_url = urljoin(ROSA_BASE_URL, link.get('href', ''))
            if not detail_url.startswith(ROSA_BASE_URL):
                continue

            detail_soup = _fetch_soup(detail_url)
            if detail_soup:
                print(f"  Scraping details for '{raw_title}'...", file=sys.stderr)
                details = _parse_rosa_detail_page(detail_soup)
                details["detail_page_url"] = detail_url
                details_cache[title_key] = details

    print(f"INFO: [{CINEMA_NAME}] Built cache for {len(details_cache)} movies.", file=sys.stderr)

    # Step 2: Scrape schedule from Eigaland using Playwright
    showings = []

    pw_instance = sync_playwright().start()
    try:
        print(f"INFO: [{CINEMA_NAME}] Launching Playwright browser...", file=sys.stderr)
        browser = pw_instance.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(PLAYWRIGHT_TIMEOUT)

        print(f"INFO: [{CINEMA_NAME}] Navigating to Eigaland schedule: {EIGALAND_URL}", file=sys.stderr)
        page.goto(EIGALAND_URL, wait_until="networkidle")

        # Wait for the calendar to be visible
        print(f"INFO: [{CINEMA_NAME}] Waiting for calendar to load...", file=sys.stderr)
        try:
            page.wait_for_selector(DATE_ITEM_SELECTOR_CSS, timeout=PLAYWRIGHT_TIMEOUT)
        except TimeoutError:
            print(f"ERROR: [{CINEMA_NAME}] Calendar did not load within timeout.", file=sys.stderr)
            browser.close()
            return []

        # Give Vue a moment to fully hydrate
        page.wait_for_timeout(2000)

        # Get all date elements
        date_elements = page.query_selector_all(DATE_ITEM_SELECTOR_CSS)
        if not date_elements:
            print(f"ERROR: [{CINEMA_NAME}] Could not find any date elements.", file=sys.stderr)
            browser.close()
            return []

        num_dates_to_click = min(len(date_elements), DAYS_TO_SCRAPE)
        print(f"INFO: [{CINEMA_NAME}] Found {len(date_elements)} date elements. Will process first {num_dates_to_click}.", file=sys.stderr)

        for i in range(num_dates_to_click):
            try:
                # Refetch date elements to avoid stale references
                date_elements = page.query_selector_all(DATE_ITEM_SELECTOR_CSS)
                if i >= len(date_elements):
                    break

                date_element = date_elements[i]

                # Get the date text
                date_p = date_element.query_selector("p.date")
                if not date_p:
                    continue

                date_str = _clean_text(date_p.text_content() or "")
                parsed_date = _parse_date_from_eigaland(date_str, dt.date.today().year)

                if not parsed_date:
                    print(f"WARN: [{CINEMA_NAME}] Could not parse date from '{date_str}' at index {i}. Skipping.", file=sys.stderr)
                    continue

                # Skip past dates
                if parsed_date < dt.date.today() - dt.timedelta(days=1):
                    print(f"INFO: [{CINEMA_NAME}] Skipping past date {parsed_date.isoformat()}", file=sys.stderr)
                    continue

                print(f"INFO: [{CINEMA_NAME}] Clicking date {parsed_date.isoformat()} ({date_str})...", file=sys.stderr)
                date_element.click()

                # Wait for schedule to update
                page.wait_for_timeout(2000)

                # Parse the schedule blocks
                schedule_blocks = page.query_selector_all(MOVIE_SCHEDULE_SELECTOR_CSS)

                for item_block in schedule_blocks:
                    try:
                        raw_title_elem = item_block.query_selector(MOVIE_TITLE_EIGALAND_CSS)
                        if not raw_title_elem:
                            continue

                        raw_title = _clean_text(raw_title_elem.text_content() or "")
                        if not raw_title:
                            continue

                        title_key = _clean_title_for_matching(raw_title)
                        details = details_cache.get(title_key, {})

                        # Fuzzy match if exact match fails
                        if not details:
                            for cache_key, cache_details in details_cache.items():
                                if cache_key in title_key or title_key in cache_key:
                                    details = cache_details
                                    break

                        # Get all showtimes for this movie
                        for schedule_info in item_block.query_selector_all(SHOWTIME_BLOCK_CSS):
                            time_el = schedule_info.query_selector(SHOWTIME_TIME_CSS)
                            screen_el = schedule_info.query_selector(SHOWTIME_SCREEN_CSS)

                            if not time_el or not screen_el:
                                continue

                            showtime = _clean_text(time_el.text_content() or "")
                            screen = _clean_text(screen_el.text_content() or "")

                            # Look for purchase URL
                            purchase_link = schedule_info.query_selector('a[href*="app.eigaland.com"]')
                            purchase_url = purchase_link.get_attribute('href') if purchase_link else None

                            showings.append({
                                "cinema_name": CINEMA_NAME,
                                "movie_title": raw_title,
                                "date_text": parsed_date.isoformat(),
                                "showtime": showtime,
                                "screen_name": screen,
                                **details,
                                "purchase_url": purchase_url
                            })
                    except Exception as e:
                        print(f"WARN: [{CINEMA_NAME}] Error parsing movie block: {e}", file=sys.stderr)
                        continue

            except Exception as e:
                print(f"ERROR: [{CINEMA_NAME}] Unexpected error on date index {i}: {e}", file=sys.stderr)
                continue

        browser.close()

    except Exception as e:
        print(f"FATAL: [{CINEMA_NAME}] An error occurred during Playwright browsing: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
    finally:
        pw_instance.stop()

    # Deduplicate and sort
    unique = { (s["date_text"], s["movie_title"], s["showtime"], s["screen_name"]): s for s in showings }
    final_list = sorted(list(unique.values()), key=lambda r: (r.get("date_text", ""), r.get("showtime", "")))
    print(f"INFO: [{CINEMA_NAME}] Collected {len(final_list)} unique showings.")
    return final_list

if __name__ == '__main__':
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except Exception: pass

    showings = scrape_cinema_rosa()
    if showings:
        output_filename = "cinema_rosa_showtimes.json"
        print(f"\nINFO: Writing {len(showings)} records to {output_filename}...")
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(showings, f, ensure_ascii=False, indent=2)
        print(f"INFO: Successfully created {output_filename}.")
    else:
        print(f"\nNo showings found for {CINEMA_NAME}.")
