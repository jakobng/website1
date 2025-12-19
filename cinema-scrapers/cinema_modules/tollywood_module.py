# tollywood_module.py
# Migrated from Selenium to Playwright for improved reliability.

import sys
from datetime import date
from typing import Dict, List

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    sys.exit(
        "ERROR: Playwright not installed. Please run 'pip install playwright' and 'playwright install chromium'."
    )

# -------------------------------------------------------------------
# Basic config
# -------------------------------------------------------------------

CINEMA_NAME = "下北沢トリウッド"
TOLLYWOOD_SCHEDULE_URL = "https://tollywood.jp/"

# How long to wait for elements to appear (in milliseconds)
PLAYWRIGHT_TIMEOUT = 30000

# How many "pages" of the calendar to scrape
# (1 page = one row of dates before clicking the ">" button)
MAX_CALENDAR_PAGES = 3  # 3 * 7 = up to 21 days


# -------------------------------------------------------------------
# CSS selectors (eigaland widget structure)
# -------------------------------------------------------------------

# Calendar
DATE_ITEM_SELECTOR_CSS = ".calendar-head.component .calender-head-item"
DATE_VALUE_IN_ITEM_SELECTOR_CSS = ".date"

# Movie blocks
MOVIE_ITEM_BLOCK_SELECTOR_CSS = ".movie-schedule-body .movie-schedule-item"
MOVIE_TITLE_IN_ITEM_BLOCK_SELECTOR_CSS = "h2 span"

# Showtimes table inside each movie block
SHOWTIME_TABLE_ROWS_SELECTOR_CSS = ".schedule-table tbody tr"
PLACE_CELL_SELECTOR_CSS = "td.place"
SLOT_CELL_SELECTOR_CSS = "td.slot"

START_TIME_IN_SLOT_SELECTOR_CSS = "h2"        # e.g. <h2>14:50</h2>
END_TIME_IN_SLOT_SELECTOR_CSS = "p"          # e.g. <p>16:36</p> (unused for now)

NEXT_BUTTON_SELECTOR_CSS = ".calendar-head.component button.next"


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _parse_date_label_mmdd(mmdd_text: str, last_date: date | None) -> date:
    """
    Convert an 'MM/DD' string from the calendar into a date object.
    Handles year rollover (Dec -> Jan) using last_date as reference.
    """
    mmdd_text = mmdd_text.strip()
    try:
        month_str, day_str = mmdd_text.split("/")
        month = int(month_str)
        day = int(day_str)
    except Exception:
        raise ValueError(f"Unexpected date label format: {mmdd_text!r}")

    today = date.today()
    if last_date is None:
        base_year = today.year
    else:
        base_year = last_date.year

    candidate = date(base_year, month, day)

    # If we already had a date and this new one is "earlier" in the calendar,
    # assume we crossed into the next year (e.g., Dec -> Jan).
    if last_date is not None and candidate < last_date:
        candidate = date(base_year + 1, month, day)

    return candidate


# -------------------------------------------------------------------
# Core scraping
# -------------------------------------------------------------------

def _scrape_active_day(page, date_iso: str) -> List[Dict]:
    """
    Scrape all movie blocks and showtimes for the currently active day
    in the schedule widget, and return a list of raw showtime dicts.
    """
    results: List[Dict] = []

    movie_blocks = page.query_selector_all(MOVIE_ITEM_BLOCK_SELECTOR_CSS)
    for block in movie_blocks:
        # Title
        title_el = block.query_selector(MOVIE_TITLE_IN_ITEM_BLOCK_SELECTOR_CSS)
        if not title_el:
            continue
        movie_title = (title_el.text_content() or "").strip()

        # Optional detail link ("もっとみる")
        detail_page_url = None
        link_el = block.query_selector("h2 a[href]")
        if link_el:
            href = link_el.get_attribute("href")
            if href:
                detail_page_url = href

        # Showtimes in the table
        rows = block.query_selector_all(SHOWTIME_TABLE_ROWS_SELECTOR_CSS)
        for row in rows:
            slot_cells = row.query_selector_all(SLOT_CELL_SELECTOR_CSS)
            for slot in slot_cells:
                # Empty slots have no <h2>
                start_el = slot.query_selector(START_TIME_IN_SLOT_SELECTOR_CSS)
                if not start_el:
                    continue

                showtime = (start_el.text_content() or "").strip()
                if not showtime:
                    continue

                results.append({
                    "movie_title_uncleaned": movie_title,
                    "date_text": date_iso,     # YYYY-MM-DD
                    "showtime": showtime,      # HH:MM
                    "detail_page_url": detail_page_url,
                })

    return results


def scrape_tollywood_raw() -> List[Dict]:
    """
    Drive the Tollywood schedule widget with Playwright and return
    raw showtime dicts with:
        movie_title_uncleaned, date_text, showtime, detail_page_url
    """
    all_results: List[Dict] = []

    pw_instance = sync_playwright().start()
    try:
        print(f"INFO: [{CINEMA_NAME}] Launching Playwright browser...", file=sys.stderr)
        browser = pw_instance.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(PLAYWRIGHT_TIMEOUT)

        print(f"INFO: [{CINEMA_NAME}] Navigating to {TOLLYWOOD_SCHEDULE_URL}...", file=sys.stderr)
        page.goto(TOLLYWOOD_SCHEDULE_URL, wait_until="networkidle")

        # Wait for schedule to load
        try:
            page.wait_for_selector(DATE_ITEM_SELECTOR_CSS, timeout=PLAYWRIGHT_TIMEOUT)
            page.wait_for_selector(MOVIE_ITEM_BLOCK_SELECTOR_CSS, timeout=PLAYWRIGHT_TIMEOUT)
        except PlaywrightTimeout:
            print(f"ERROR: [{CINEMA_NAME}] Schedule did not load within timeout.", file=sys.stderr)
            browser.close()
            return []

        # Give Vue a moment to hydrate
        page.wait_for_timeout(2000)

        last_date: date | None = None

        # Iterate over calendar pages
        for page_index in range(MAX_CALENDAR_PAGES):
            # Re-read date items for each page (they change when clicking "next")
            date_items = page.query_selector_all(DATE_ITEM_SELECTOR_CSS)
            if not date_items:
                break

            for idx in range(len(date_items)):
                # Re-fetch in case the DOM changed after previous click
                date_items = page.query_selector_all(DATE_ITEM_SELECTOR_CSS)
                if idx >= len(date_items):
                    break

                item = date_items[idx]

                # Date label like "11/20"
                date_label_el = item.query_selector(DATE_VALUE_IN_ITEM_SELECTOR_CSS)
                if not date_label_el:
                    continue

                mmdd_text = (date_label_el.text_content() or "").strip()
                if not mmdd_text:
                    continue

                try:
                    current_date = _parse_date_label_mmdd(mmdd_text, last_date)
                except ValueError:
                    continue

                last_date = current_date
                date_iso = current_date.isoformat()

                print(f"  -> Processing date: {date_iso}", file=sys.stderr)

                # Click this day to make it active
                item.click()
                page.wait_for_timeout(1000)  # small pause for repaint

                day_results = _scrape_active_day(page, date_iso)
                all_results.extend(day_results)

            # Try to go to the next "page" of days
            next_btn = page.query_selector(NEXT_BUTTON_SELECTOR_CSS)
            if not next_btn:
                break

            # Some widgets disable the button instead of removing it
            is_disabled = next_btn.get_attribute("disabled")
            if is_disabled is not None:
                break

            next_btn.click()
            page.wait_for_timeout(1500)

        browser.close()

    except Exception as e:
        print(f"ERROR: [{CINEMA_NAME}] An error occurred: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
    finally:
        pw_instance.stop()

    return all_results


# -------------------------------------------------------------------
# Public API matching your other modules
# -------------------------------------------------------------------

def scrape_tollywood() -> List[Dict]:
    """
    Return Tollywood showtimes in the same schema as other cinema modules:
        cinema_name, movie_title, movie_title_en, director, year,
        country, runtime_min, date_text, showtime, detail_page_url,
        program_title, purchase_url
    """
    raw = scrape_tollywood_raw()
    result: List[Dict] = []

    for r in raw:
        result.append({
            "cinema_name": CINEMA_NAME,
            "movie_title": r.get("movie_title_uncleaned", "").strip() or None,
            "movie_title_en": None,
            "director": None,
            "year": None,
            "country": None,
            "runtime_min": None,
            "date_text": r.get("date_text"),
            "showtime": r.get("showtime"),
            "detail_page_url": r.get("detail_page_url"),
            "program_title": None,
            "purchase_url": None,
        })

    return result


# -------------------------------------------------------------------
# CLI test
# -------------------------------------------------------------------

if __name__ == "__main__":
    # Make Windows console behave with Japanese output
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    showtimes = scrape_tollywood()
    for row in showtimes:
        print(row)
