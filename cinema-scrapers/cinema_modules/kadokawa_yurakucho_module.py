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
URL_KY = "http://www.kadokawa-cinema.jp/yurakucho/"

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

def scrape_kadokawa_yurakucho():
    showings = []
    driver = None
    try:
        driver = get_headless_driver()
        driver.get(URL_KY)
        
        wait = WebDriverWait(driver, 20)
        # Wait for schedule swiper to appear
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "schedule-swiper__item")))
        
        # 1. Find Date Tabs
        date_tabs = driver.find_elements(By.CLASS_NAME, "schedule-swiper__item")
        print(f"Found {len(date_tabs)} date tabs.")
        
        today = date.today()
        
        for i in range(len(date_tabs)):
            # Re-find tabs to avoid stale element exception
            tabs = driver.find_elements(By.CLASS_NAME, "schedule-swiper__item")
            tab = tabs[i]
            
            # Extract date from tab
            try:
                day_text = tab.find_element(By.CLASS_NAME, "day").text.strip() # "01/14"
                match = re.search(r'(\d{1,2})/(\d{1,2})', day_text)
                if not match: continue
                
                month, day_val = int(match.group(1)), int(match.group(2))
                year = today.year
                if month < today.month and (today.month - month) > 6: year += 1
                elif month > today.month and (month - today.month) > 6: year -= 1
                date_str = f"{year}-{month:02d}-{day_val:02d}"
                
                print(f"Processing {date_str}...")
                
                # Click the tab
                driver.execute_script("arguments[0].click();", tab)
                time.sleep(2) # Wait for content to update
                
                # Parse current page content
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                # Each movie is in .content-item
                movie_blocks = soup.select('.tab_content-wrap .content-item')
                for block in movie_blocks:
                    title_a = block.select_one('a.title')
                    if not title_a: 
                        # Fallback for some blocks where title isn't a link
                        title_div = block.select_one('.item-title .title')
                        if not title_div: continue
                        title = clean_text(title_div.get_text())
                    else:
                        title = clean_text(title_a.get_text())
                    
                    # Times are in .schedule-item
                    for s_item in block.select('.schedule-item'):
                        # Check if it's disabled (finished or sales period over)
                        # We still want to scrape past times if they are shown
                        time_span = s_item.select_one('.time span')
                        if not time_span: continue
                        
                        start_time_raw = clean_text(time_span.get_text()) # "10:30〜"
                        time_match = re.search(r'(\d{1,2}):(\d{2})', start_time_raw)
                        if time_match:
                            start_time = f"{int(time_match.group(1)):02d}:{time_match.group(2)}"
                            
                            showings.append({
                                "cinema_name": CINEMA_NAME_KY,
                                "date_text": date_str,
                                "movie_title": title,
                                "showtime": start_time,
                                "year": str(year),
                                "detail_page_url": URL_KY
                            })
                            
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
