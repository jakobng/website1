#!/usr/bin/env python3
# main_scraper.py
# V5: Robust Monitoring, Email Alerts, and Smart Title Cleaning

import json
import sys
import traceback
import re
import requests
import time
import os
import difflib
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from bs4 import BeautifulSoup

# --- All cinema scraper modules ---
from cinema_modules import (
    bunkamura_module,
    bluestudio_module,
    cine_switch_ginza_module,
    eurospace_module,
    human_shibuya_module,
    human_yurakucho_module,
    image_forum_module,
    ks_cinema_module,
    laputa_asagaya_module,
    meguro_cinema_module,
    musashino_kan_module,
    nfaj_calendar_module as nfaj_module,
    polepole_module,
    shin_bungeiza_module,
    shimotakaido_module,
    stranger_module,
    theatre_shinjuku_module,
    waseda_shochiku_module,
    cinemart_shinjuku_module,
    cinema_qualite_module,
    cine_quinto_module,
    yebisu_garden_module,
    k2_cinema_module,
    cinema_rosa_module,
    chupki_module,
    uplink_kichijoji_module,
    tollywood_module,
    morc_asagaya_module
)

# --- Configuration ---
DATA_DIR = "data"
OUTPUT_JSON = os.path.join(DATA_DIR, "showtimes.json")
TMDB_CACHE_FILE = os.path.join(DATA_DIR, "tmdb_cache.json")

# Ensure data directory exists
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# --- Monitor & Alert System ---
class ScrapeReport:
    def __init__(self):
        self.results = []
        self.total_showings = 0

    def add(self, cinema_name, status, count, error=None):
        self.results.append({
            "cinema": cinema_name,
            "status": status,
            "count": count,
            "error": str(error) if error else None
        })
        if count:
            self.total_showings += count

    def print_summary(self):
        print("\n" + "="*50)
        print("📊 SCRAPE HEALTH REPORT")
        print("="*50)
        
        failures = []
        warnings = []

        # Header
        print(f"{'STATUS':<4} | {'CINEMA':<25} | {'COUNT':<5} | {'NOTES'}")
        print("-" * 65)

        for r in self.results:
            # Logic: If SUCCESS but 0 showings, treat as WARNING
            if r['status'] == 'SUCCESS' and r['count'] == 0:
                r['status'] = 'WARNING'
                warnings.append(r)
            elif r['status'] == 'FAILURE':
                failures.append(r)

            # Console Output Icons
            icon = "✅"
            if r['status'] == 'WARNING': icon = "⚠️ "
            if r['status'] == 'FAILURE': icon = "❌"
            
            error_msg = f"{r['error']}" if r['error'] else ""
            if r['status'] == 'WARNING' and not error_msg:
                error_msg = "0 showings found"

            print(f"{icon:<4} | {r['cinema']:<25} | {r['count']:<5} | {error_msg}")

        print("-" * 65)
        print(f"Total Showings Collected: {self.total_showings}")
        return failures, warnings

    def send_email_alert(self, failures, warnings):
        """Sends an email if things went wrong."""
        if not failures and not warnings:
            return

        # 1. Gather Credentials
        smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
        # SSL port is usually 465
        smtp_port = int(os.environ.get("SMTP_PORT", 465))
        sender_email = os.environ.get("SMTP_EMAIL")
        sender_password = os.environ.get("SMTP_PASSWORD")
        recipient_email = os.environ.get("ALERT_RECIPIENT_EMAIL")

        if not (sender_email and sender_password and recipient_email):
            print("ℹ️ Skipping email alert: Missing SMTP credentials.")
            return

        # 2. Build Content
        subject = f"🚨 Scraper Alert: {len(failures)} Crashes, {len(warnings)} Empty"
        
        body_lines = ["The Cinema Scraper encountered issues:\n"]
        
        if failures:
            body_lines.append(f"❌ CRITICAL FAILURES ({len(failures)}):")
            for f in failures:
                body_lines.append(f"- {f['cinema']}: {f['error']}")
            body_lines.append("\n")

        if warnings:
            body_lines.append(f"⚠️ POTENTIAL ISSUES (0 Showings Found):")
            for w in warnings:
                body_lines.append(f"- {w['cinema']}")
        
        body_lines.append("\nCheck the GitHub Actions logs for full details.")

        msg = EmailMessage()
        msg.set_content("\n".join(body_lines))
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = recipient_email

        # 3. Send
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
                server.login(sender_email, sender_password)
                server.send_message(msg)
            print("📧 Alert email sent successfully.")
        except Exception as e:
            print(f"❌ Failed to send email alert: {e}")

# Initialize Global Report
report = ScrapeReport()

# --- TMDB Utilities ---

def clean_title_for_tmdb(title: str) -> str:
    """
    Aggressively strips 'noise' suffixes that confuse TMDB fuzzy matching.
    """
    if not title:
        return ""
    
    # Common Japanese release suffixes/prefixes to strip
    patterns = [
        r"４[ＫK]デジタルリマスター版?",      # 4K Digital Remaster
        r"デジタルリマスター版?",             # Digital Remaster
        r"（.*?版）",                       # (XXX Version)
        r"【.*?】",                          # [XXX] (e.g., [Screening])
        r"4K Restor.*",                     # 4K Restore...
        r"Director's Cut",                  # Director's Cut
        r"ディレクターズ・?カット.*",         # Director's Cut (JP)
        r"完全版",                          # Complete Version
        r"発声可能上映",                     # Cheering Screening
        r"製作\d+周年記念",                  # XXth Anniversary
    ]
    
    cleaned = title
    for pat in patterns:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE)
    
    # Cleanup whitespace
    cleaned = cleaned.strip()
    
    # If cleaning removed everything (unlikely), revert
    if not cleaned:
        return title
        
    return cleaned

def load_tmdb_cache():
    if os.path.exists(TMDB_CACHE_FILE):
        try:
            with open(TMDB_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_tmdb_cache(cache):
    with open(TMDB_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def fetch_tmdb_details(movie_title, session, api_key):
    """
    Searches TMDB for movie_title. 
    1. Tries exact Japanese match.
    2. If no result, tries a 'cleaned' version (stripping 4K/Remaster suffixes).
    """
    search_url = "https://api.themoviedb.org/3/search/movie"
    
    # 1. Primary Search (As Is)
    params = {
        "api_key": api_key,
        "query": movie_title,
        "language": "ja-JP",
        "include_adult": "false"
    }
    
    try:
        resp = session.get(search_url, params=params, timeout=5)
        data = resp.json()
        results = data.get("results", [])
        
        # 2. Fallback: Clean Title Search
        if not results:
            clean_title = clean_title_for_tmdb(movie_title)
            if clean_title != movie_title:
                print(f"   Using cleaned title: '{clean_title}'")
                params["query"] = clean_title
                resp = session.get(search_url, params=params, timeout=5)
                data = resp.json()
                results = data.get("results", [])

        if results:
            # Pick the most popular/relevant one
            # Simple heuristic: exact title match or first result
            best = results[0] 
            # We could do fuzzy matching here if needed, but usually top result is good
            
            # Fetch full details for runtime, credits, etc.
            detail_url = f"https://api.themoviedb.org/3/movie/{best['id']}"
            d_params = {
                "api_key": api_key,
                "language": "ja-JP",
                "append_to_response": "credits,images"
            }
            d_resp = session.get(detail_url, params=d_params, timeout=5)
            d_data = d_resp.json()
            
            # Extract Director
            director = ""
            crew = d_data.get("credits", {}).get("crew", [])
            for c in crew:
                if c.get("job") == "Director":
                    director = c.get("name")
                    break
            
            return {
                "tmdb_id": best["id"],
                "tmdb_title_jp": d_data.get("title"),
                "tmdb_title_en": d_data.get("original_title"), # fallback
                "overview": d_data.get("overview"),
                "poster_path": d_data.get("poster_path"),
                "backdrop_path": d_data.get("backdrop_path"),
                "release_date": d_data.get("release_date"),
                "director": director,
                "runtime": d_data.get("runtime"),
                "genres": [g["name"] for g in d_data.get("genres", [])],
                "vote_average": d_data.get("vote_average")
            }
            
    except Exception as e:
        print(f"   TMDB Error for '{movie_title}': {e}")
    
    return None

def enrich_listings_with_tmdb_links(listings, cache, session, api_key):
    """
    Iterates over listings, checks TMDB for metadata/images.
    Updates listings in-place and updates cache.
    """
    print(f"\n--- Starting Robust Enrichment for {len(listings)} listings ---")
    
    # Group by movie title to avoid duplicate API calls
    unique_titles = list(set(item["movie_title"] for item in listings))
    print(f"   Unique films to process: {len(unique_titles)}")
    
    updated_cache = False
    
    for title in unique_titles:
        if title not in cache:
            # If we haven't checked this title before
            print(f"   🔍 Searching TMDB for: {title}")
            details = fetch_tmdb_details(title, session, api_key)
            
            if details:
                cache[title] = details
                updated_cache = True
                print(f"      ✅ Found: {details['tmdb_title_jp']} (ID: {details['tmdb_id']})")
            else:
                cache[title] = None # Mark as not found so we don't retry immediately
                print(f"      ❌ Not found.")
            
            time.sleep(0.3) # Rate limiting
            
    # Apply cached data to listings
    for item in listings:
        t = item["movie_title"]
        if t in cache and cache[t]:
            d = cache[t]
            # Merge fields if missing in scraper data
            if not item.get("tmdb_id"):
                item["tmdb_id"] = d["tmdb_id"]
                item["tmdb_backdrop_path"] = d["backdrop_path"]
                item["tmdb_poster_path"] = d["poster_path"]
                item["tmdb_overview_jp"] = d["overview"]
                item["tmdb_tagline_jp"] = "" # Could add if fetched
                item["tmdb_tagline_en"] = ""
                item["clean_title_jp"] = d["tmdb_title_jp"]
                item["runtime"] = d["runtime"]
                item["genres"] = d["genres"]
                item["vote_average"] = d["vote_average"]
                
                # If scraper didn't provide English title, use original_title (might be EN)
                if not item.get("movie_title_en"):
                    item["movie_title_en"] = d["tmdb_title_en"]
                
                # If scraper didn't provide Director
                if not item.get("director"):
                    item["director"] = d["director"]
                    
                # If scraper didn't provide Year
                if not item.get("year") and d["release_date"]:
                    item["year"] = d["release_date"].split("-")[0]

    if updated_cache:
        save_tmdb_cache(cache)
        
    return listings

# --- Scraper Runner Wrapper ---

def _run_scraper(name, func, listings_list):
    """
    Runs a scraper function with robust error handling and reporting.
    """
    print(f"\nScraping {name} ...")
    try:
        # Run the scraper
        rows = func() or []
        
        count = len(rows)
        print(f"→ {count} showings from {name}.")
        listings_list.extend(rows)
        
        # Report Success
        report.add(name, "SUCCESS", count)
        
    except Exception as e:
        # Report Failure but DO NOT CRASH main execution
        print(f"⚠️ Error in {name}: {e}")
        # traceback.print_exc() # Uncomment for deep debugging
        report.add(name, "FAILURE", 0, error=e)

# --- Main Execution ---

def main():
    tmdb_key = os.environ.get("TMDB_API_KEY")
    if not tmdb_key:
        print("⚠️ Warning: TMDB_API_KEY not found. Metadata enrichment will be skipped.")

    # Prepare TMDB session
    api_session = requests.Session()
    tmdb_cache = load_tmdb_cache()

    listings = []

    # 1. DEFINE SCRAPERS TO RUN
    # Note: Stranger is included but wrapped in safety block now.
    scrapers_to_run = [
        ("Bunkamura", bunkamura_module.scrape_bunkamura),
        ("K's Cinema", ks_cinema_module.scrape_ks_cinema),
        ("Shin-Bungeiza", shin_bungeiza_module.scrape_shin_bungeiza),
        ("Shimotakaido Cinema", shimotakaido_module.scrape_shimotakaido),
        ("Stranger", stranger_module.scrape_stranger),
        ("Meguro Cinema", meguro_cinema_module.scrape_meguro_cinema),
        ("Image Forum", image_forum_module.scrape_image_forum),
        ("Theatre Shinjuku", theatre_shinjuku_module.scrape_ttcg_schedule),
        ("Pole Pole Higashi-Nakano", polepole_module.scrape_pole2),
        ("Cinema Blue Studio", bluestudio_module.scrape_blue_studio),
        ("Human Trust Cinema Shibuya", human_shibuya_module.scrape_ttcg_human_shibuya),
        ("Human Trust Cinema Yurakucho", human_yurakucho_module.scrape_ttcg_human_yurakucho),
        ("Laputa Asagaya", laputa_asagaya_module.scrape_laputa),
        ("Shinjuku Musashino-kan", musashino_kan_module.scrape_musashino_kan),
        ("Waseda Shochiku", waseda_shochiku_module.scrape_waseda_shochiku),
        ("National Film Archive", nfaj_module.scrape_nfaj_calendar),
        ("Cinemart Shinjuku", cinemart_shinjuku_module.scrape_cinemart_shinjuku),
        ("Cinema Qualite", cinema_qualite_module.scrape_cinema_qualite),
        ("Cine Quinto", cine_quinto_module.scrape_cine_quinto),
        ("Yebisu Garden Cinema", yebisu_garden_module.scrape_yebisu_garden),
        ("K2 Cinema", k2_cinema_module.scrape_k2_cinema),
        ("Cinema Rosa", cinema_rosa_module.scrape_cinema_rosa),
        ("Chupki", chupki_module.scrape_chupki),
        ("Uplink Kichijoji", uplink_kichijoji_module.scrape_uplink_kichijoji),
        ("Tollywood", tollywood_module.scrape_tollywood),
        ("Morc Asagaya", morc_asagaya_module.scrape_morc),
        ("Eurospace", eurospace_module.scrape_eurospace),
    ]

    print("Starting all scrapers…")

    # 2. RUN SCRAPERS
    for name, func in scrapers_to_run:
        _run_scraper(name, func, listings)

    # 3. SPECIAL HANDLING: CINE SWITCH GINZA (Standalone)
    # This module often runs independently in the workflow, but we load its result here.
    print("\n--- [Cine Switch] Check for existing standalone output ---")
    csg_filename = "cineswitch_showtimes.json"
    
    # Logic to find the file if it was just generated
    if os.path.exists(csg_filename):
        try:
            with open(csg_filename, "r", encoding="utf-8") as f:
                csg_showings = json.load(f)
                print(f"→ {len(csg_showings)} showings from Cine Switch Ginza.")
                listings.extend(csg_showings)
                report.add("Cine Switch Ginza", "SUCCESS", len(csg_showings))
        except Exception as e:
            print(f"Error loading cineswitch_showtimes.json: {e}")
            report.add("Cine Switch Ginza", "FAILURE", 0, error=e)
    else:
        # It's not a failure if the file doesn't exist (maybe it wasn't run)
        # But we can log a note
        print("No standalone Cine Switch file found.")
    
    # 4. ENRICHMENT
    print(f"\nCollected a total of {len(listings)} showings.")
    
    if tmdb_key:
        listings = enrich_listings_with_tmdb_links(listings, tmdb_cache, api_session, tmdb_key)
    
    # 5. SAVE OUTPUT
    print(f"Saving to {OUTPUT_JSON}...")
    try:
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(listings, f, ensure_ascii=False, indent=2)
        print("✅ Done.")
    except Exception as e:
        print(f"❌ Critical Error saving JSON: {e}")
        sys.exit(1)

    # 6. REPORTING & ALERTS
    failures, warnings = report.print_summary()
    
    # Send email if configured
    report.send_email_alert(failures, warnings)

if __name__ == "__main__":
    main()
