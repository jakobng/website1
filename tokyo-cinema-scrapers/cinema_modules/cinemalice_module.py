#!/usr/bin/env python3
# cinemalice_module.py — Rev-2 (2026-01-08)
#
# Scraper for シネマリス (CineMalice) - https://cinemalice.theater/
# A new mini-theater in Tokyo that opened December 2025.
#
# This scraper uses Selenium to render the JavaScript-based schedule page
# and extract actual showtimes. Falls back to date-range extraction if
# Selenium is not available.
# ---------------------------------------------------------------------

from __future__ import annotations

import datetime as dt
import re
import sys
import time
from typing import Dict, List, Optional

import requests

# Selenium imports (optional - graceful fallback if not available)
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        NoSuchElementException,
        TimeoutException,
        WebDriverException
    )
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

CINEMA_NAME = "シネマリス"
BASE_URL = "https://cinemalice.theater"
SCHEDULE_URL = f"{BASE_URL}/schedules"
HEADERS = {"User-Agent": "Mozilla/5.0 (CineMaliceScraper/2026)"}
TIMEOUT = 30
SELENIUM_TIMEOUT = 15
MAX_RETRIES = 3

TODAY = dt.date.today()
WINDOW_DAYS = 7


# ---------------------------------------------------------------------
# Selenium-based scraping (primary method)
# ---------------------------------------------------------------------

def _init_selenium_driver() -> "webdriver.Chrome":
    """Create a headless Chrome driver with sensible defaults."""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36")

    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(60)
    return driver


def _scrape_with_selenium() -> List[Dict]:
    """
    Scrape CineMalice schedule using Selenium to render the React page.
    Returns list of showtime dictionaries.
    """
    if not SELENIUM_AVAILABLE:
        print(f"WARNING: [{CINEMA_NAME}] Selenium not available, skipping browser-based scraping",
              file=sys.stderr)
        return []

    driver = None
    results: List[Dict] = []

    try:
        print(f"{CINEMA_NAME}: Initializing Selenium driver...")
        driver = _init_selenium_driver()

        print(f"{CINEMA_NAME}: Loading schedule page...")
        driver.get(SCHEDULE_URL)

        # Wait for the page to load (look for date picker or schedule content)
        wait = WebDriverWait(driver, SELENIUM_TIMEOUT)

        # Wait for the date picker to appear
        time.sleep(3)  # Initial wait for React hydration

        # Try to find the date selector buttons
        # CineMalice uses a calendar-style date picker
        date_buttons = driver.find_elements(By.CSS_SELECTOR,
            '[class*="date"], [class*="calendar"] button, [class*="day"]')

        if not date_buttons:
            # Try alternative selectors
            date_buttons = driver.find_elements(By.XPATH,
                "//button[contains(text(), '/')]|//div[contains(@class, 'date')]//button")

        print(f"{CINEMA_NAME}: Found {len(date_buttons)} date buttons")

        # If we found date buttons, click each one and extract schedule
        dates_processed = set()

        for btn in date_buttons[:WINDOW_DAYS + 2]:  # Limit to our window
            try:
                btn_text = btn.text.strip()
                if not btn_text or btn_text in dates_processed:
                    continue

                # Click the date button
                btn.click()
                time.sleep(1.5)  # Wait for schedule to load
                dates_processed.add(btn_text)

                # Extract the current date from the button text (format: "1/8" or "8")
                date_match = re.search(r'(\d{1,2})/(\d{1,2})|^(\d{1,2})$', btn_text)
                if date_match:
                    if date_match.group(1):
                        month = int(date_match.group(1))
                        day = int(date_match.group(2))
                    else:
                        month = TODAY.month
                        day = int(date_match.group(3))

                    # Determine year
                    year = TODAY.year
                    if month < TODAY.month:
                        year += 1

                    date_str = f"{year}-{month:02d}-{day:02d}"
                else:
                    continue

                # Extract movie schedules for this date
                schedule_items = driver.find_elements(By.CSS_SELECTOR,
                    '[class*="schedule"], [class*="movie"], [class*="screening"]')

                # Also try to find movie titles and times in any visible content
                page_text = driver.find_element(By.TAG_NAME, 'body').text

                # Look for patterns like "10:00" followed by movie titles
                # Or movie titles followed by times
                time_patterns = re.findall(
                    r'(\d{1,2}:\d{2})\s*[〜～\-]?\s*([^\d\n]{2,50})|([^\d\n]{2,50})\s+(\d{1,2}:\d{2})',
                    page_text
                )

                for match in time_patterns:
                    if match[0]:  # time then title
                        showtime = match[0]
                        title = match[1].strip()
                    else:  # title then time
                        title = match[2].strip()
                        showtime = match[3]

                    # Skip if it looks like a timestamp or invalid time
                    hour = int(showtime.split(':')[0])
                    if hour < 9 or hour > 23:
                        continue

                    # Skip if title looks invalid
                    if len(title) < 2 or title.isdigit():
                        continue

                    results.append({
                        "cinema_name": CINEMA_NAME,
                        "movie_title": title,
                        "movie_title_en": "",
                        "date_text": date_str,
                        "showtime": showtime,
                        "director": "",
                        "year": "",
                        "country": "",
                        "runtime_min": None,
                        "synopsis": "",
                        "detail_page_url": SCHEDULE_URL,
                    })

            except Exception as e:
                print(f"WARNING: [{CINEMA_NAME}] Error processing date button: {e}", file=sys.stderr)
                continue

        # If no results from date buttons, try to extract from the page directly
        if not results:
            print(f"{CINEMA_NAME}: No results from date picker, trying direct extraction...")
            page_text = driver.find_element(By.TAG_NAME, 'body').text

            # Look for showtime patterns in the full page
            all_times = re.findall(r'(\d{1,2}:\d{2})', page_text)
            valid_times = [t for t in all_times if 9 <= int(t.split(':')[0]) <= 23]

            if valid_times:
                print(f"{CINEMA_NAME}: Found {len(valid_times)} potential showtimes in page")

        print(f"{CINEMA_NAME}: Selenium scraping found {len(results)} showings")
        return results

    except TimeoutException:
        print(f"ERROR: [{CINEMA_NAME}] Selenium timed out loading page", file=sys.stderr)
        return []
    except WebDriverException as e:
        print(f"ERROR: [{CINEMA_NAME}] Selenium WebDriver error: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"ERROR: [{CINEMA_NAME}] Selenium scraping failed: {e}", file=sys.stderr)
        return []
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


# ---------------------------------------------------------------------
# Fallback: RSC payload extraction (date ranges only)
# ---------------------------------------------------------------------

def _fetch_page(url: str) -> Optional[str]:
    """Fetch page HTML content."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        resp.encoding = 'utf-8'
        return resp.text
    except requests.RequestException as e:
        print(f"ERROR: [{CINEMA_NAME}] Could not fetch {url}: {e}", file=sys.stderr)
        return None


def _extract_screenings_data(html: str) -> List[Dict]:
    """
    Extract movie data from the React Server Component payload.
    The data is embedded as escaped JSON in the page.
    """
    idx = html.find('cmsScreeningsData')
    if idx == -1:
        print(f"ERROR: [{CINEMA_NAME}] Could not find cmsScreeningsData in page", file=sys.stderr)
        return []

    chunk = html[idx:idx+100000]
    movies = []

    # Pattern for escaped JSON
    escaped_pattern = '\\"title\\"' in chunk

    if escaped_pattern:
        title_matches = re.findall(r'\\"title\\":\\"([^\\]+)\\"', chunk)
        director_matches = re.findall(r'\\"director\\":\\"([^\\]*)\\"', chunk)
        runtime_matches = re.findall(r'\\"screeningTimes\\":\\"([^\\]*)\\"', chunk)
        date_from_matches = re.findall(r'\\"releaseDateFrom\\":\\"([^\\]+)\\"', chunk)
        date_to_matches = re.findall(r'\\"releaseDateTo\\":\\"([^\\]+)\\"', chunk)
        website_matches = re.findall(r'\\"website\\":\\"([^\\]*)\\"', chunk)
        slug_matches = re.findall(r'\\"slug\\":\\"([^\\]+)\\"', chunk)
    else:
        title_matches = re.findall(r'"title":"([^"]+)"', chunk)
        director_matches = re.findall(r'"director":"([^"]*)"', chunk)
        runtime_matches = re.findall(r'"screeningTimes":"([^"]*)"', chunk)
        date_from_matches = re.findall(r'"releaseDateFrom":"([^"]+)"', chunk)
        date_to_matches = re.findall(r'"releaseDateTo":"([^"]+)"', chunk)
        website_matches = re.findall(r'"website":"([^"]*)"', chunk)
        slug_matches = re.findall(r'"slug":"([^"]+)"', chunk)

    for i, title in enumerate(title_matches):
        movie = {'title': title}
        if i < len(director_matches):
            movie['director'] = director_matches[i]
        if i < len(runtime_matches):
            movie['runtime'] = runtime_matches[i]
        if i < len(date_from_matches):
            movie['date_from'] = date_from_matches[i]
        if i < len(date_to_matches):
            movie['date_to'] = date_to_matches[i]
        if i < len(website_matches):
            movie['website'] = website_matches[i]
        if i < len(slug_matches):
            movie['slug'] = slug_matches[i]
        movies.append(movie)

    return movies


def _parse_runtime(runtime_str: str) -> Optional[str]:
    """Extract numeric runtime from string like '106分'."""
    if not runtime_str:
        return None
    match = re.search(r'(\d+)', runtime_str)
    return match.group(1) if match else None


def _generate_daily_entries(movie: Dict) -> List[Dict]:
    """
    Generate showtime entries for each day within the movie's screening period.
    Used as fallback when Selenium can't get actual showtimes.
    """
    entries = []

    if 'date_from' not in movie or 'date_to' not in movie:
        return entries

    try:
        date_from = dt.date.fromisoformat(movie['date_from'])
        date_to = dt.date.fromisoformat(movie['date_to'])
    except ValueError:
        return entries

    window_end = TODAY + dt.timedelta(days=WINDOW_DAYS)
    current_date = max(date_from, TODAY)
    end_date = min(date_to, window_end)

    while current_date <= end_date:
        entry = {
            "cinema_name": CINEMA_NAME,
            "movie_title": movie.get('title', ''),
            "movie_title_en": "",
            "date_text": current_date.isoformat(),
            "showtime": "スケジュール確認",  # Fallback: "Check schedule"
            "director": movie.get('director', ''),
            "year": "",
            "country": "",
            "runtime_min": _parse_runtime(movie.get('runtime', '')),
            "synopsis": "",
            "detail_page_url": movie.get('website', '') or f"{BASE_URL}/movie/{movie.get('slug', '')}",
        }
        entries.append(entry)
        current_date += dt.timedelta(days=1)

    return entries


def _scrape_fallback() -> List[Dict]:
    """Fallback scraper using RSC payload extraction (date ranges only)."""
    html = _fetch_page(SCHEDULE_URL)
    if not html:
        return []

    movies = _extract_screenings_data(html)
    if not movies:
        print(f"WARNING: [{CINEMA_NAME}] No movies found in schedule", file=sys.stderr)
        return []

    all_entries = []
    for movie in movies:
        entries = _generate_daily_entries(movie)
        all_entries.extend(entries)

    return all_entries


# ---------------------------------------------------------------------
# Main scraper
# ---------------------------------------------------------------------

def scrape_cinemalice(max_days: int = 7) -> List[Dict[str, str]]:
    """
    Scrape シネマリス (CineMalice) schedule.

    Primary: Uses Selenium to render JavaScript and extract actual showtimes.
    Fallback: Extracts date ranges from RSC payload if Selenium unavailable.

    Returns a list of showtime dictionaries with standard schema.
    """
    global WINDOW_DAYS, TODAY
    WINDOW_DAYS = max_days
    TODAY = dt.date.today()

    all_entries = []

    # Try Selenium first for actual showtimes
    if SELENIUM_AVAILABLE:
        for attempt in range(MAX_RETRIES):
            try:
                all_entries = _scrape_with_selenium()
                if all_entries:
                    break
            except Exception as e:
                print(f"WARNING: [{CINEMA_NAME}] Selenium attempt {attempt + 1} failed: {e}",
                      file=sys.stderr)
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2)

    # Fall back to RSC payload extraction if Selenium didn't work
    if not all_entries:
        print(f"{CINEMA_NAME}: Falling back to date-range extraction...")
        all_entries = _scrape_fallback()

    # Deduplicate (same movie, same date, same time)
    seen = set()
    unique_entries = []
    for entry in all_entries:
        key = (entry["movie_title"], entry["date_text"], entry.get("showtime", ""))
        if key not in seen:
            seen.add(key)
            unique_entries.append(entry)

    # Sort by date, then time, then title
    unique_entries.sort(key=lambda x: (
        x.get("date_text", ""),
        x.get("showtime", "ZZZ"),  # Put "スケジュール確認" at end
        x.get("movie_title", "")
    ))

    print(f"{CINEMA_NAME}: Returning {len(unique_entries)} showings")
    return unique_entries


# ---------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------

if __name__ == "__main__":
    import json as json_module
    from pathlib import Path

    showings = scrape_cinemalice()
    if showings:
        out_path = Path(__file__).with_name("cinemalice_schedule_TEST.json")
        out_path.write_text(json_module.dumps(showings, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Test run successful. Saved {len(showings)} showtimes → {out_path}")
    else:
        print("No showtimes found.")
