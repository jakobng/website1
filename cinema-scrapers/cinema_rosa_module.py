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

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException

# --- Constants ---
CINEMA_NAME = "池袋シネマ・ロサ"
DEFAULT_SELENIUM_TIMEOUT = 25
# Limit the loop to the first 7 days, which are always visible
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
    """A more aggressive cleaning function to create a reliable key for matching."""
    if not text:
        return ""
    text = unicodedata.normalize('NFKC', text)
    text = text.replace('映画 ', '').replace(' ', '')
    text = re.sub(r'[【『「《\(（].*?[】』」》\)）]', '', text)
    text = re.sub(r'[<【『「]', '', text)
    return text.strip().lower() # Use lowercase for matching

def _clean_text(text: Optional[str]) -> str:
    """Normalizes whitespace for display text."""
    if not text: return ""
    return ' '.join(text.strip().split())

def _init_selenium_driver() -> webdriver.Chrome:
    """Initializes a headless Chrome WebDriver."""
    print(f"INFO: [{CINEMA_NAME}] Initializing headless Chrome driver...", file=sys.stderr)
    chrome_options = ChromeOptions()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Add options to make browser appear less like automation
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    
    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(DEFAULT_SELENIUM_TIMEOUT * 2)
        print(f"INFO: [{CINEMA_NAME}] WebDriver initialized.", file=sys.stderr)
        return driver
    except Exception as e:
        print(f"FATAL: [{CINEMA_NAME}] Failed to initialize WebDriver: {e}", file=sys.stderr)
        print("Please ensure Chrome is installed and webdriver-manager can download the driver.", file=sys.stderr)
        raise

def _fetch_soup(url: str) -> Optional[BeautifulSoup]:
    """Fetches a static URL and returns a BeautifulSoup object."""
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
        response.raise_for_status()
        return BeautifulSoup(response.content, 'html.parser')
    except requests.RequestException as e:
        print(f"ERROR: [{CINEMA_NAME}] Could not fetch static page {url}: {e}", file=sys.stderr)
        return None

def _parse_date_from_eigaland(date_str: str, current_year: int) -> Optional[dt.date]:
    """Parses date strings like '6/23' from the Eigaland calendar."""
    if match := re.match(r"(\d{1,2})/(\d{1,2})", date_str):
        month, day = map(int, match.groups())
        try:
            # Fix potential year wrap-around issue
            today = dt.date.today()
            year = current_year
            if month < today.month - 6: # If date is >6 months in past, assume next year
                year = current_year + 1
            elif month > today.month + 6: # If date is >6 months in future, assume last year
                 year = current_year - 1
            return dt.date(year, month, day)
        except ValueError: return None
    return None

def _parse_rosa_detail_page(soup: BeautifulSoup) -> Dict[str, Optional[str]]:
    """
    Parses a movie detail page from cinemarosa.net.
    FIXED: More precise selectors for director and synopsis.
    """
    details = {"director": None, "year": None, "runtime_min": None, "country": None, "synopsis": None}
    
    # Get Year, Runtime, Country
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
                    # Find the part that is not the year, not the runtime, and not digits
                    if (part != details["year"] 
                        and '分' not in part 
                        and not part.isdigit()
                        and '時間' not in part):
                        details["country"] = part.split(' ')[0] # Clean up country
                        break

    if film_txt_div := soup.select_one("div.film_txt"):
        # Get Director
        director_found = False
        for p_tag in film_txt_div.find_all('p'):
            p_text = p_tag.get_text(strip=True)
            if "監督" in p_text:
                # More robust cleaning
                # Remove "監督", "脚本", colons, etc.
                clean_p = re.sub(r'監督|脚本|：|:', '', p_text).strip("・ ")
                # Take the first name
                details["director"] = clean_p.split(' ')[0].split('／')[0].split('(')[0].strip()
                director_found = True
                break
        
        # Get Synopsis - more specific search
        synopsis_p = None
        if free_area_div := film_txt_div.select_one("div.free_area"):
            # Try to find the <p> with 【STORY】
            for p_tag in free_area_div.find_all('p', recursive=False): # Only direct children
                if "【STORY】" in p_tag.get_text(strip=True):
                    synopsis_p = p_tag
                    break
            
            if synopsis_p:
                # Clone the tag to avoid modifying the original
                synopsis_clone = BeautifulSoup(str(synopsis_p), 'html.parser')
                # Remove the <br> tag and the "【STORY】" part
                if story_br := synopsis_clone.find('br'):
                    story_br.replace_with(" ") # Replace <br> with a space
                
                synopsis_text = _clean_text(synopsis_clone.get_text(strip=True))
                details["synopsis"] = synopsis_text.replace("【STORY】", "").strip()
            else:
                # Fallback: Find the first <p> that is NOT an announcement
                for p_tag in free_area_div.find_all('p', recursive=False):
                    p_text = p_tag.get_text(strip=True)
                    # Check if it's not an announcement and has a reasonable length
                    if p_text and not p_text.startswith('☆') and '詳細はこちら' not in p_text and len(p_text) > 10:
                        details["synopsis"] = _clean_text(p_text)
                        break # Found it

    return details

# --- Main Scraping Logic ---

def scrape_cinema_rosa() -> List[Dict[str, str]]:
    # 1. Build cache of movie details from cinemarosa.net
    details_cache: Dict[str, Dict] = {}
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
                continue # Skip external links
                
            detail_soup = _fetch_soup(detail_url)
            if detail_soup:
                print(f"  Scraping details for '{raw_title}'...", file=sys.stderr)
                details = _parse_rosa_detail_page(detail_soup)
                details["detail_page_url"] = detail_url
                details_cache[title_key] = details
                
    print(f"INFO: [{CINEMA_NAME}] Built cache for {len(details_cache)} movies.", file=sys.stderr)

    # 2. Fetch schedule from Eigaland using Selenium
    showings = []
    driver = None
    try:
        driver = _init_selenium_driver()
        print(f"INFO: [{CINEMA_NAME}] Navigating to Eigaland schedule: {EIGALAND_URL}", file=sys.stderr)
        driver.get(EIGALAND_URL)
        
        # Try to find and click a cookie/consent banner
        print(f"INFO: [{CINEMA_NAME}] Page loaded. Looking for cookie/consent banners...", file=sys.stderr)
        try:
            possible_button_texts = ["同意する", "すべて同意", "Accept All", "Allow All", "OK"]
            button_found = False
            for text in possible_button_texts:
                try:
                    consent_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, f"//button[contains(., '{text}')] | //a[contains(., '{text}')]"))
                    )
                    print(f"INFO: [{CINEMA_NAME}] Found and clicking consent button with text: '{text}'", file=sys.stderr)
                    driver.execute_script("arguments[0].click();", consent_button)
                    button_found = True
                    time.sleep(2) # Wait for banner to disappear
                    break
                except TimeoutException:
                    continue # This text didn't match, try the next one
            
            if not button_found:
                print(f"INFO: [{CINEMA_NAME}] No common consent banners found (or timed out). Continuing...", file=sys.stderr)
                
        except Exception as e:
            print(f"WARN: [{CINEMA_NAME}] Error while checking for consent banner: {e}. Continuing...", file=sys.stderr)
        
        print(f"INFO: [{CINEMA_NAME}] Waiting for calendar to load...", file=sys.stderr)
        WebDriverWait(driver, DEFAULT_SELENIUM_TIMEOUT).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, DATE_ITEM_SELECTOR_CSS))
        )
        time.sleep(2) # Give it a moment to settle
        
        date_elements = driver.find_elements(By.CSS_SELECTOR, DATE_ITEM_SELECTOR_CSS)
        if not date_elements:
            print(f"ERROR: [{CINEMA_NAME}] Could not find any date elements after page load.", file=sys.stderr)
            return []
            
        num_dates_to_click = min(len(date_elements), DAYS_TO_SCRAPE)
        print(f"INFO: [{CINEMA_NAME}] Found {len(date_elements)} date elements. Will process first {num_dates_to_click}.", file=sys.stderr)
        
        for i in range(num_dates_to_click):
            parsed_date = None
            try:
                date_element = driver.find_elements(By.CSS_SELECTOR, DATE_ITEM_SELECTOR_CSS)[i]
                
                date_p = date_element.find_element(By.CSS_SELECTOR, "p.date")
                date_str = _clean_text(date_p.text)
                parsed_date = _parse_date_from_eigaland(date_str, dt.date.today().year)
                
                if not parsed_date:
                    print(f"WARN: [{CINEMA_NAME}] Could not parse date from '{date_str}' at index {i}. Skipping.", file=sys.stderr)
                    continue
                
                if parsed_date < dt.date.today():
                    print(f"INFO: [{CINEMA_NAME}] Skipping past date {parsed_date.isoformat()}", file=sys.stderr)
                    continue
                
                print(f"INFO: [{CINEMA_NAME}] Clicking date {parsed_date.isoformat()} ({date_str})...", file=sys.stderr)
                driver.execute_script("arguments[0].click();", date_element)
                
                WebDriverWait(driver, DEFAULT_SELENIUM_TIMEOUT).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, MOVIE_SCHEDULE_SELECTOR_CSS))
                )
                time.sleep(1.5) 

                for item_block in driver.find_elements(By.CSS_SELECTOR, MOVIE_SCHEDULE_SELECTOR_CSS):
                    try:
                        raw_title_elem = item_block.find_element(By.CSS_SELECTOR, MOVIE_TITLE_EIGALAND_CSS)
                        raw_title = _clean_text(raw_title_elem.text)
                        if not raw_title: 
                            continue
                        
                        title_key = _clean_title_for_matching(raw_title)
                        details = details_cache.get(title_key, {})
                        
                        if not details:
                            for cache_key, cache_details in details_cache.items():
                                if cache_key in title_key or title_key in cache_key:
                                    details = cache_details
                                    break
                                    
                        for schedule_info in item_block.find_elements(By.CSS_SELECTOR, SHOWTIME_BLOCK_CSS):
                            showtime = _clean_text(schedule_info.find_element(By.CSS_SELECTOR, SHOWTIME_TIME_CSS).text)
                            screen = _clean_text(schedule_info.find_element(By.CSS_SELECTOR, SHOWTIME_SCREEN_CSS).text)
                            purchase_url_tag = schedule_info.find_elements(By.CSS_SELECTOR, 'a[href*="app.eigaland.com"]')
                            
                            showings.append({
                                "cinema_name": CINEMA_NAME, "movie_title": raw_title,
                                "date_text": parsed_date.isoformat(), "showtime": showtime,
                                "screen_name": screen, **details,
                                "purchase_url": purchase_url_tag[0].get_attribute('href') if purchase_url_tag else None
                            })
                    except Exception as inner_e:
                        print(f"WARN: [{CINEMA_NAME}] Error parsing a specific movie block on {date_str}: {inner_e}", file=sys.stderr)

            except (TimeoutException, StaleElementReferenceException) as e:
                print(f"WARN: [{CINEMA_NAME}] Problem processing date index {i} ({date_str}). Page might not have loaded correctly. {e}", file=sys.stderr)
            except Exception as e:
                 print(f"ERROR: [{CINEMA_NAME}] Unexpected error on date index {i}: {e}", file=sys.stderr)
                 
    except Exception as e:
        print(f"FATAL: [{CINEMA_NAME}] An error occurred during Selenium browsing: {e}", file=sys.stderr)
    finally:
        if driver:
            driver.quit()
            print(f"INFO: [{CINEMA_NAME}] WebDriver closed.", file=sys.stderr)

    # De-duplicate and sort
    unique = { (s["date_text"], s["movie_title"], s["showtime"], s["screen_name"]): s for s in showings }
    final_list = sorted(list(unique.values()), key=lambda r: (r.get("date_text", ""), r.get("showtime", "")))
    print(f"INFO: [{CINEMA_NAME}] Collected {len(final_list)} unique showings.")
    return final_list

if __name__ == '__main__':
    if sys.platform == "win32": 
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
            
    showings = scrape_cinema_rosa()
    if showings:
        output_filename = "cinema_rosa_showtimes.json"
        print(f"\nINFO: Writing {len(showings)} records to {output_filename}...")
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(showings, f, ensure_ascii=False, indent=2)
        print(f"INFO: Successfully created {output_filename}.")
        print("\n--- Sample of First Showing ---")
        from pprint import pprint
        pprint(showings[0])
    else:
        print(f"\nNo showings found for {CINEMA_NAME}.")
