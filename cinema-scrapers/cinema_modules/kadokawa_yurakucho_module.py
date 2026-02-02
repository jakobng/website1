# -*- coding: utf-8 -*-
import sys
import os
import time
import re
from datetime import datetime, date
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

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

CINEMA_NAME_KY = "Kadokawa Cinema Yurakucho (角川シネマ有楽町)"
URL_KY = "https://www.kadokawa-cinema.jp/theaters/yurakucho/"

def clean_text(text):
    if not text: return ""
    return re.sub(r'\s+', ' ', text).strip()

def get_headless_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1280,1000")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    return webdriver.Chrome(options=chrome_options)

def _parse_date_mmdd(text, today):
    if not text:
        return ""
    match = re.search(r'(\d{1,2})/(\d{1,2})', text)
    if not match:
        return ""
    month, day_val = int(match.group(1)), int(match.group(2))
    year = today.year
    if month < today.month and (today.month - month) > 6:
        year += 1
    elif month > today.month and (month - today.month) > 6:
        year -= 1
    return f"{year}-{month:02d}-{day_val:02d}"

def _collect_date_tabs(driver):
    selectors = [
        ".schedule-swiper__item",
        ".schedule-swiper .swiper-slide",
        ".schedule-date-item",
        ".schedule-tab__item",
    ]
    best = []
    for selector in selectors:
        items = driver.find_elements(By.CSS_SELECTOR, selector)
        if len(items) > len(best):
            best = items
    if best:
        return best
    return driver.find_elements(By.XPATH, "//*[contains(@class,'date') and contains(text(),'/')]")

def _extract_title_from_block(block):
    for selector in ["a.title", ".item-title .title", ".title", "h3", "h4", "a[href*='/movie/']"]:
        title_tag = block.select_one(selector)
        if not title_tag:
            continue
        title = clean_text(title_tag.get_text())
        if title:
            return title
    return ""

def _extract_times_from_block(block):
    times = []
    for selector in [".schedule-item .time span", ".schedule-item .time", ".time span", ".time", "time"]:
        for node in block.select(selector):
            text = clean_text(node.get_text())
            for h, m in re.findall(r"(\d{1,2}):(\d{2})", text):
                t = f"{int(h):02d}:{m}"
                if t not in times:
                    times.append(t)
    if times:
        return times
    text = clean_text(block.get_text(" ", strip=True))
    for h, m in re.findall(r"(\d{1,2}):(\d{2})", text):
        t = f"{int(h):02d}:{m}"
        if t not in times:
            times.append(t)
    return times

def _parse_showings_from_soup(soup, date_str):
    showings = []
    year_val = date_str.split("-")[0] if date_str else ""
    block_selectors = [
        ".tab_content-wrap .content-item",
        ".tab-content-wrap .content-item",
        ".content-item",
        ".movie-schedule-item",
    ]
    blocks = []
    for selector in block_selectors:
        blocks = soup.select(selector)
        if blocks:
            break
    for block in blocks:
        title = _extract_title_from_block(block)
        if not title:
            continue
        for showtime in _extract_times_from_block(block):
            showings.append({
                "cinema_name": CINEMA_NAME_KY,
                "date_text": date_str,
                "movie_title": title,
                "showtime": showtime,
                "year": year_val,
                "detail_page_url": URL_KY
            })
    return showings

def scrape_kadokawa_yurakucho():
    showings = []
    driver = None
    try:
        driver = get_headless_driver()
        driver.get(URL_KY)
        
        wait = WebDriverWait(driver, 20)
        # Wait for schedule swiper and content to appear
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".schedule-swiper__item, .schedule-swiper .swiper-slide, .tab_content-wrap, .tab-content-wrap")))
        
        # 1. Find Date Tabs
        date_tabs = _collect_date_tabs(driver)
        print(f"Found {len(date_tabs)} date tabs.")
        
        today = date.today()
        if not date_tabs:
            soup = BeautifulSoup(driver.page_source, "html.parser")
            date_str = _parse_date_mmdd(soup.get_text(" ", strip=True), today)
            if date_str:
                showings.extend(_parse_showings_from_soup(soup, date_str))
            date_tabs = []
        
        for i in range(len(date_tabs)):
            # Re-find tabs to avoid stale element exception
            tabs = _collect_date_tabs(driver)
            if i >= len(tabs):
                break
            tab = tabs[i]
            
            # Extract date from tab
            try:
                try:
                    day_text = tab.find_element(By.CLASS_NAME, "day").text.strip() # "01/14"
                except Exception:
                    day_text = tab.text.strip()
                date_str = _parse_date_mmdd(day_text, today)
                if not date_str:
                    date_str = _parse_date_mmdd(tab.text.strip(), today)
                if not date_str:
                    continue

                print(f"Processing {date_str}...")

                # Click the tab
                driver.execute_script("arguments[0].click();", tab)
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".tab_content-wrap, .tab-content-wrap, .content-item, .movie-schedule-item"))
                    )
                except Exception:
                    pass
                time.sleep(1) # Allow any lazy content to settle

                # Parse current page content
                soup = BeautifulSoup(driver.page_source, "html.parser")
                showings.extend(_parse_showings_from_soup(soup, date_str))
            except Exception as e:
                print(f"Error processing tab {i}: {e}")
                continue
                
    except Exception as e:
        print(f"Error in scrape_kadokawa_yurakucho: {e}")
    finally:
        if driver:
            driver.quit()
            
    # Deduplicate
    unique_showings = []
    seen = set()
    for s in showings:
        tup = (s['date_text'], s['movie_title'], s['showtime'])
        if tup not in seen:
            unique_showings.append(s)
            seen.add(tup)
            
    return unique_showings

if __name__ == "__main__":
    results = scrape_kadokawa_yurakucho()
    for s in sorted(results, key=lambda x: (x['date_text'], x['showtime'])):
        print(f"{s['date_text']} | {s['showtime']} | {s['movie_title']}")
