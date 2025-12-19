# stranger_module.py
# Migrated from Selenium to Playwright for improved reliability.

import re
import sys
import traceback
from datetime import date
from typing import List, Dict

from bs4 import BeautifulSoup

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    sys.exit(
        "ERROR: Playwright not installed. Please run 'pip install playwright' and 'playwright install chromium'."
    )

# --- Start: Configure stdout and stderr for UTF-8 on Windows ---
if __name__ == "__main__" and sys.platform == "win32":
    try:
        if sys.stdout.encoding != 'utf-8':
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if sys.stderr.encoding != 'utf-8':
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
# --- End: Configure stdout and stderr ---

CINEMA_NAME_ST = "Stranger (ストレンジャー)"
URL_ST = "https://stranger.jp/"

# Define timeouts
PLAYWRIGHT_TIMEOUT = 30000  # 30 seconds

def clean_text(text):
    if not text:
        return ""
    # Replace weird spaces and non-breaking spaces
    text = text.replace('\xa0', ' ').replace('\u3000', ' ')
    return re.sub(r'\s+', ' ', text).strip()

def parse_time_str(t_str):
    """
    Parses '09:30' -> matching strict format
    """
    t_str = clean_text(t_str).replace('～', '~').replace('〜', '~')
    # Extract HH:MM
    match = re.search(r'(\d{1,2})[:：](\d{2})', t_str)
    if match:
        return f"{int(match.group(1))}:{match.group(2)}"
    return ""

def scrape_stranger() -> List[Dict]:
    """
    Scrapes Stranger Tokyo using Playwright.
    Structure: .movie-schedule-item -> Title (h2 span) -> Slots (.slot h2)
    """
    final_showings = []

    print(f"Debug ({CINEMA_NAME_ST}): Initializing Playwright.")

    pw_instance = sync_playwright().start()
    try:
        print(f"Debug ({CINEMA_NAME_ST}): Launching browser...")
        browser = pw_instance.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(PLAYWRIGHT_TIMEOUT)

        print(f"Debug ({CINEMA_NAME_ST}): Loading {URL_ST}...")
        page.goto(URL_ST, wait_until="networkidle")

        # Wait for body to be present
        page.wait_for_selector("body", timeout=PLAYWRIGHT_TIMEOUT)

        # Scroll down to ensure lazy elements load
        page.evaluate("window.scrollTo(0, 800)")
        page.wait_for_timeout(2000)

        # Find Date Tabs (Heuristic based on text)
        print(f"Debug ({CINEMA_NAME_ST}): Scanning for date tabs...")

        # Get all potential date elements
        potential_dates = page.query_selector_all("//*[contains(text(), '/') or contains(text(), '月')]")

        date_map = {}
        today = date.today()

        for elem in potential_dates:
            try:
                txt = (elem.text_content() or "").strip()
                if len(txt) > 20:
                    continue

                # Regex for 12/19 or 12月19日
                match = re.search(r'(\d{1,2})[/\.](\d{1,2})', txt)
                if not match:
                    match = re.search(r'(\d{1,2})月(\d{1,2})日', txt)

                if match:
                    m, d = int(match.group(1)), int(match.group(2))

                    year = today.year
                    # Handle year rollover
                    if m < today.month and (today.month - m) > 6:
                        year += 1
                    elif m > today.month and (m - today.month) > 6:
                        year -= 1

                    date_obj = date(year, m, d)
                    date_str = date_obj.strftime("%Y-%m-%d")

                    if elem.is_visible():
                        if date_str not in date_map:
                            date_map[date_str] = elem
            except Exception:
                continue

        sorted_dates = sorted(date_map.keys())
        print(f"Debug ({CINEMA_NAME_ST}): Found {len(sorted_dates)} potential dates: {sorted_dates}")

        if not sorted_dates:
            print("Warning: No date tabs found. Site layout might be radically different.")
            browser.close()
            return []

        # Iterate through dates
        for date_text in sorted_dates:
            print(f"   > Processing {date_text}...")

            try:
                elem = date_map[date_text]
                elem.scroll_into_view_if_needed()
                page.wait_for_timeout(500)
                elem.click()

                # Wait for content to stabilize
                page.wait_for_timeout(1500)
            except Exception as e:
                print(f"     Error clicking date {date_text}: {e}")
                continue

            # Parse content using specific DOM classes
            soup = BeautifulSoup(page.content(), 'html.parser')

            # Find all movie blocks
            movie_blocks = soup.find_all("div", class_="movie-schedule-item")

            for block in movie_blocks:
                # --- A. Extract Title ---
                # The title is typically in an h2 -> div -> span structure
                title_span = block.select_one("h2 div span")

                if not title_span:
                    # Fallback: Check just the h2 (sometimes structure varies)
                    title_h2 = block.find("h2")
                    if title_h2:
                        # Clean "More" or other link text if present
                        raw_t = title_h2.get_text()
                        # Simple split to remove likely noise
                        title_text = raw_t.split("もっと")[0].strip()
                    else:
                        continue
                else:
                    title_text = clean_text(title_span.get_text())

                # Clean up title
                title_text = re.sub(r'\s+', ' ', title_text)

                # --- B. Extract Showtimes ---
                # Showtimes are in <td class="slot"> inside <h2> tags
                slot_times = block.select(".slot h2")

                for time_el in slot_times:
                    start_time = parse_time_str(time_el.get_text())
                    if not start_time:
                        continue

                    # Append Data
                    final_showings.append({
                        "cinema_name": CINEMA_NAME_ST,
                        "date_text": date_text,
                        "movie_title": title_text,
                        "showtime": start_time,
                        "year": str(today.year),
                        "detail_page_url": URL_ST
                    })

        browser.close()

    except Exception as e:
        print(f"An unexpected error in scrape_stranger: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return []
    finally:
        pw_instance.stop()

    # Deduplicate
    unique_showings = []
    seen = set()
    for s in final_showings:
        tup = (s['date_text'], s['movie_title'], s['showtime'])
        if tup not in seen:
            unique_showings.append(s)
            seen.add(tup)

    return unique_showings

if __name__ == '__main__':
    print(f"Testing {CINEMA_NAME_ST} scraper module (Playwright)...")
    showings_data = scrape_stranger()
    if showings_data:
        print(f"\nFound {len(showings_data)} unique showings for {CINEMA_NAME_ST}:")
        # Sort
        showings_data.sort(key=lambda x: (x.get('date_text', ''), x.get('showtime', '')))
        for showing in showings_data:
            print(f"  {showing['date_text']} | {showing['showtime']} | {showing['movie_title']}")
    else:
        print("No showings found.")
