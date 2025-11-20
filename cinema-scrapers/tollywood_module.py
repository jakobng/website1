import sys
import time
from datetime import datetime, date
from typing import Dict, List

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

# -------------------------------------------------------------------
# Basic config
# -------------------------------------------------------------------

CINEMA_NAME = "下北沢トリウッド"
TOLLYWOOD_SCHEDULE_URL = "https://tollywood.jp/"

# How long to wait for elements to appear
DEFAULT_SELENIUM_TIMEOUT = 15

# How many “pages” of the calendar to scrape
# (1 page = one row of dates before clicking the 「>」 button)
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

def _init_selenium_driver() -> webdriver.Chrome:
    """Create a headless Chrome driver with sensible defaults."""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(60)
    return driver


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


def _wait_for_schedule_loaded(driver: webdriver.Chrome) -> None:
    """Wait until the schedule widget is present."""
    WebDriverWait(driver, DEFAULT_SELENIUM_TIMEOUT).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, DATE_ITEM_SELECTOR_CSS)
        )
    )
    WebDriverWait(driver, DEFAULT_SELENIUM_TIMEOUT).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, MOVIE_ITEM_BLOCK_SELECTOR_CSS)
        )
    )


# -------------------------------------------------------------------
# Core scraping
# -------------------------------------------------------------------

def _scrape_active_day(
    driver: webdriver.Chrome,
    date_iso: str,
) -> List[Dict]:
    """
    Scrape all movie blocks and showtimes for the currently active day
    in the schedule widget, and return a list of raw showtime dicts.
    """
    results: List[Dict] = []

    movie_blocks = driver.find_elements(By.CSS_SELECTOR, MOVIE_ITEM_BLOCK_SELECTOR_CSS)
    for block in movie_blocks:
        # Title
        try:
            title_el = block.find_element(By.CSS_SELECTOR, MOVIE_TITLE_IN_ITEM_BLOCK_SELECTOR_CSS)
            movie_title = title_el.text.strip()
        except NoSuchElementException:
            # Skip weird blocks with no title
            continue

        # Optional detail link ("もっとみる")
        detail_page_url = None
        try:
            link_el = block.find_element(By.CSS_SELECTOR, "h2 a[href]")
            href = link_el.get_attribute("href")
            if href:
                detail_page_url = href
        except NoSuchElementException:
            pass

        # Showtimes in the table
        rows = block.find_elements(By.CSS_SELECTOR, SHOWTIME_TABLE_ROWS_SELECTOR_CSS)
        for row in rows:
            slot_cells = row.find_elements(By.CSS_SELECTOR, SLOT_CELL_SELECTOR_CSS)
            for slot in slot_cells:
                # Empty slots have no <h2>
                try:
                    start_el = slot.find_element(By.CSS_SELECTOR, START_TIME_IN_SLOT_SELECTOR_CSS)
                except NoSuchElementException:
                    continue

                showtime = start_el.text.strip()
                if not showtime:
                    continue

                # We *could* also grab end time here if you ever want it:
                # try:
                #     end_el = slot.find_element(By.CSS_SELECTOR, END_TIME_IN_SLOT_SELECTOR_CSS)
                #     end_time = end_el.text.strip()
                # except NoSuchElementException:
                #     end_time = None

                results.append(
                    {
                        "movie_title_uncleaned": movie_title,
                        "date_text": date_iso,     # YYYY-MM-DD
                        "showtime": showtime,      # HH:MM
                        "detail_page_url": detail_page_url,
                    }
                )

    return results


def scrape_tollywood_raw() -> List[Dict]:
    """
    Drive the Tollywood schedule widget with Selenium and return
    raw showtime dicts with:
        movie_title_uncleaned, date_text, showtime, detail_page_url
    """
    driver = _init_selenium_driver()
    all_results: List[Dict] = []

    try:
        driver.get(TOLLYWOOD_SCHEDULE_URL)
        _wait_for_schedule_loaded(driver)

        last_date: date | None = None

        # Iterate over calendar pages
        for page_index in range(MAX_CALENDAR_PAGES):
            # Re-read date items for each page (they change when clicking "next")
            date_items = driver.find_elements(By.CSS_SELECTOR, DATE_ITEM_SELECTOR_CSS)
            if not date_items:
                break

            for idx in range(len(date_items)):
                # Re-fetch in case the DOM changed after previous click
                date_items = driver.find_elements(By.CSS_SELECTOR, DATE_ITEM_SELECTOR_CSS)
                if idx >= len(date_items):
                    break

                item = date_items[idx]

                # Date label like "11/20"
                try:
                    date_label_el = item.find_element(By.CSS_SELECTOR, DATE_VALUE_IN_ITEM_SELECTOR_CSS)
                    mmdd_text = date_label_el.text.strip()
                except NoSuchElementException:
                    continue

                current_date = _parse_date_label_mmdd(mmdd_text, last_date)
                last_date = current_date
                date_iso = current_date.isoformat()

                # Click this day to make it active
                driver.execute_script("arguments[0].click();", item)
                time.sleep(1.0)  # small pause for repaint

                day_results = _scrape_active_day(driver, date_iso)
                all_results.extend(day_results)

            # Try to go to the next “page” of days
            try:
                next_btn = driver.find_element(By.CSS_SELECTOR, NEXT_BUTTON_SELECTOR_CSS)
                # Some widgets disable the button instead of removing it
                if not next_btn.is_enabled():
                    break
                driver.execute_script("arguments[0].click();", next_btn)
                time.sleep(1.5)
            except NoSuchElementException:
                break

    finally:
        driver.quit()

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
        result.append(
            {
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
            }
        )

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
