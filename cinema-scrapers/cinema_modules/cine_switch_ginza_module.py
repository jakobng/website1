"""
cine_switch_ginza_module.py - Playwright-based scraper
Migrated from Selenium to Playwright for improved reliability and automatic browser management.
"""

from __future__ import annotations
import datetime as dt
import json
import re
import sys
import unicodedata
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    sys.exit(
        "ERROR: Playwright not installed. Please run 'pip install playwright' and 'playwright install chromium'."
    )

# [FIX] Added to handle SSL handshake issues with the target server
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)


# --- Constants ---
CSG_BASE_URL = "https://cineswitch.com"
CSG_DETAIL_PAGES = [urljoin(CSG_BASE_URL, "/movie_now"), urljoin(CSG_BASE_URL, "/movie_soon")]
EIGALAND_BASE_URL = "https://schedule.eigaland.com/schedule?webKey=5c896e66-aaf7-4003-b4ff-1d8c9bf9c0fc"
CINEMA_NAME = "シネスイッチ銀座"
PLAYWRIGHT_TIMEOUT = 30000  # 30 seconds in milliseconds
DAYS_TO_SCRAPE = 7

# --- Eigaland Selectors ---
DATE_CALENDAR_AREA_SELECTOR_CSS = "div.calendar-head.component"
DATE_ITEM_SELECTOR_CSS = ".calender-head-item"
DATE_VALUE_IN_ITEM_SELECTOR_CSS = "p.date"
MOVIE_ITEM_BLOCK_SELECTOR_CSS = "div.movie-schedule-item"
MOVIE_TITLE_IN_ITEM_BLOCK_SELECTOR_CSS = "span[style*='font-weight: 700']"
SHOWTIME_TABLE_ROWS_SELECTOR_CSS = ".schedule-table tr"
SCREEN_IN_TABLE_ROW_SELECTOR_CSS = "td.place span.name"
SLOT_CELL_SELECTOR_CSS = "td.slot"
START_TIME_IN_SLOT_SELECTOR_CSS = "h2"


# --- Helper Functions ---

def _clean_title_for_matching(title: str) -> str:
    """Cleans a movie title for reliable matching between different sources."""
    if not title: return ""
    normalized_title = unicodedata.normalize('NFKC', title)
    return normalized_title.lower().strip().replace(" ", "").replace("　", "")

def get_movie_details_from_cineswitch() -> Dict[str, Dict]:
    """Scrapes cineswitch.com for movie details."""
    print("--- [Cine Switch] Fetching Movie Details from cineswitch.com ---", file=sys.stderr)
    details_cache: Dict[str, Dict] = {}

    for page in CSG_DETAIL_PAGES:
        try:
            # [FIX] Added verify=False to bypass SSL handshake errors
            response = requests.get(page, timeout=15, verify=False)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            movie_links = soup.select("article.poster_wrap div.p_img a")

            for link in movie_links:
                detail_url = urljoin(CSG_BASE_URL, link.get("href", ""))
                if not detail_url: continue
                try:
                    # [FIX] Added verify=False to bypass SSL handshake errors
                    detail_resp = requests.get(detail_url, timeout=15, verify=False)
                    detail_resp.raise_for_status()
                    detail_soup = BeautifulSoup(detail_resp.content, "html.parser")

                    details: Dict[str, any] = {"detail_page_url": detail_url}
                    title_tag = detail_soup.select_one(".movie_title h1")
                    if not title_tag: continue

                    title_jp = title_tag.text.strip()
                    cleaned_title = _clean_title_for_matching(title_jp)
                    details["movie_title"] = title_jp
                    details["movie_title_en"] = detail_soup.select_one(".movie_title p").text.strip() if detail_soup.select_one(".movie_title p") else ""
                    details["year"] = "N/A" # Not available on page
                    details["director"] = None
                    details["country"] = None
                    details["runtime_min"] = 0
                    details["synopsis"] = detail_soup.select_one(".movie_commentary p").get_text(separator="\n").strip() if detail_soup.select_one(".movie_commentary p") else ""

                    if info_table := detail_soup.select_one(".production_info table"):
                        for row in info_table.find_all("tr"):
                            cells = row.find_all("td")
                            if len(cells) == 2:
                                key, value = cells[0].text.strip(), cells[1].text.strip()
                                if "監督" in key: details["director"] = value
                                elif "制作国" in key: details["country"] = value

                    if screening_info_div := detail_soup.find("div", class_="screenig_info"):
                        for info in screening_info_div.find_all("div", class_="info"):
                            if info.find("span", string="上映時間"):
                                runtime_tag = info.find("div", class_="info_data")
                                if runtime_tag:
                                    if runtime_match := re.search(r'\d+', runtime_tag.text):
                                        details["runtime_min"] = int(runtime_match.group(0))

                    details_cache[cleaned_title] = details
                except requests.RequestException as e:
                    print(f"  ERROR [Cine Switch]: Could not fetch detail page {detail_url}: {e}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"ERROR [Cine Switch]: Could not fetch list page {page}: {e}", file=sys.stderr)
    return details_cache

def _get_current_year() -> int:
    return dt.date.today().year

def _parse_date_from_eigaland(date_str: str, current_year: int) -> Optional[dt.date]:
    match = re.match(r"(\d{1,2})/(\d{1,2})", date_str)
    if match:
        month, day = map(int, match.groups())
        try:
            return dt.date(current_year, month, day)
        except ValueError:
            return None
    return None


def scrape_eigaland_schedule() -> List[Dict]:
    """Scrapes movie showtimes from the Eigaland platform page using Playwright."""
    print("--- [Cine Switch] Fetching Showtimes from Eigaland (Playwright) ---", file=sys.stderr)
    showtimes: List[Dict] = []
    url = EIGALAND_BASE_URL

    pw_instance = sync_playwright().start()
    try:
        print(f"INFO: [{CINEMA_NAME}] Launching Playwright browser...", file=sys.stderr)
        browser = pw_instance.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(PLAYWRIGHT_TIMEOUT)

        print(f"INFO: [{CINEMA_NAME}] Navigating to Eigaland schedule: {url}", file=sys.stderr)
        page.goto(url, wait_until="networkidle")

        # Wait for the calendar to be visible
        print(f"INFO: [{CINEMA_NAME}] Waiting for calendar to load...", file=sys.stderr)
        try:
            page.wait_for_selector(DATE_CALENDAR_AREA_SELECTOR_CSS, timeout=PLAYWRIGHT_TIMEOUT)
        except PlaywrightTimeout:
            print(f"ERROR: [{CINEMA_NAME}] Calendar did not load within timeout.", file=sys.stderr)
            browser.close()
            return []

        # Give Vue a moment to fully hydrate
        page.wait_for_timeout(2000)

        date_item_elements = page.query_selector_all(DATE_ITEM_SELECTOR_CSS)
        year_for_schedule = _get_current_year()

        for date_idx in range(min(len(date_item_elements), DAYS_TO_SCRAPE)):
            # Re-fetch elements to avoid stale references
            current_page_date_items = page.query_selector_all(DATE_ITEM_SELECTOR_CSS)
            if date_idx >= len(current_page_date_items):
                break

            date_element_to_click = current_page_date_items[date_idx]
            try:
                date_label = date_element_to_click.query_selector(DATE_VALUE_IN_ITEM_SELECTOR_CSS)
                if not date_label:
                    continue
                date_str_mm_dd = (date_label.text_content() or "").strip()

                date_element_to_click.click()

                # Wait for schedule content to update
                page.wait_for_timeout(1500)
                page.wait_for_selector(MOVIE_ITEM_BLOCK_SELECTOR_CSS, timeout=PLAYWRIGHT_TIMEOUT)

                parsed_date_obj = _parse_date_from_eigaland(date_str_mm_dd, year_for_schedule)
                if not parsed_date_obj:
                    continue

                print(f"INFO: [{CINEMA_NAME}] Processing date {parsed_date_obj.isoformat()}...", file=sys.stderr)

                movie_item_blocks = page.query_selector_all(MOVIE_ITEM_BLOCK_SELECTOR_CSS)
                for item_block in movie_item_blocks:
                    try:
                        title_tag = item_block.query_selector(MOVIE_TITLE_IN_ITEM_BLOCK_SELECTOR_CSS)
                        if not title_tag:
                            continue
                        movie_title = (title_tag.text_content() or "").strip()

                        table_rows = item_block.query_selector_all(SHOWTIME_TABLE_ROWS_SELECTOR_CSS)
                        for tr_element in table_rows:
                            slot_cells = tr_element.query_selector_all(SLOT_CELL_SELECTOR_CSS)
                            for slot_cell in slot_cells:
                                showtime_tag = slot_cell.query_selector(START_TIME_IN_SLOT_SELECTOR_CSS)
                                if not showtime_tag:
                                    continue
                                showtime_text = (showtime_tag.text_content() or "").strip()
                                if showtime_text:
                                    showtimes.append({
                                        "movie_title_uncleaned": movie_title,
                                        "date_text": parsed_date_obj.isoformat(),
                                        "showtime": showtime_text,
                                    })
                    except Exception:
                        continue
            except Exception as e:
                print(f"  ERROR [Cine Switch] processing date {date_idx}: {e}", file=sys.stderr)

        browser.close()

    except Exception as e:
        print(f"FATAL: [{CINEMA_NAME}] An error occurred during Playwright browsing: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
    finally:
        pw_instance.stop()

    return showtimes


# --- Refactored Main Functions ---

def scrape_cine_switch_ginza() -> List[Dict]:
    """
    This is the new main function to be called by other scripts.
    It performs the full scrape and returns the data as a list of dictionaries.
    """
    # PART 1: Get movie details from cineswitch.com
    details_cache = get_movie_details_from_cineswitch()

    # PART 2: Get showtimes from Eigaland
    showings = scrape_eigaland_schedule()

    # PART 3: Merge the data
    print("--- [Cine Switch] Merging Details and Showtimes ---", file=sys.stderr)
    final_results = []
    unmatched_titles = set()

    for show in showings:
        cleaned_show_title = _clean_title_for_matching(show["movie_title_uncleaned"])
        details = details_cache.get(cleaned_show_title)

        if details:
            final_show = {
                "cinema_name": CINEMA_NAME,
                "movie_title": details.get("movie_title", show["movie_title_uncleaned"]),
                "movie_title_en": details.get("movie_title_en"),
                "date_text": show["date_text"],
                "showtime": show["showtime"],
                "director": details.get("director"),
                "year": details.get("year"),
                "country": details.get("country"),
                "runtime_min": details.get("runtime_min"),
                "synopsis": details.get("synopsis"),
                "detail_page_url": details.get("detail_page_url")
            }
            final_results.append(final_show)
        else:
            unmatched_titles.add(show["movie_title_uncleaned"])

    if unmatched_titles:
        print(f"WARNING [Cine Switch]: Could not find details for: {', '.join(sorted(list(unmatched_titles)))}", file=sys.stderr)

    final_results.sort(key=lambda x: (x["date_text"], x["movie_title"], x["showtime"]))
    return final_results

def run_full_scrape_and_save():
    """
    This function is for running the module standalone. It scrapes and saves the file.
    The main scraper will NOT use this function anymore.
    """
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except Exception: pass

    results = scrape_cine_switch_ginza()

    output_filename = "cineswitch_showtimes.json"
    print(f"\n--- [Cine Switch] Writing {len(results)} showtimes to {output_filename} ---", file=sys.stderr)
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    print(f"\n✅ [Cine Switch] Done. Output saved to {output_filename}")


if __name__ == "__main__":
    # This allows the module to be run by itself to generate its file, for testing.
    run_full_scrape_and_save()
