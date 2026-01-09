#!/usr/bin/env python3
# main_scraper.py
# London Cinema Scraper - V1.0
# Adapted from Tokyo cinema scraper for London independent cinemas

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
import unicodedata
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from pathlib import Path
from bs4 import BeautifulSoup

# --- All cinema scraper modules ---
from cinema_modules import (
    bfi_southbank_module,
    prince_charles_module,
    garden_cinema_module,
    nickel_module,
    barbican_module,
    genesis_module,
    ica_module,
    close_up_module,
    phoenix_cinema_module,
    castle_cinema_module,
    electric_cinema_module,
    # rio_cinema_module,
    # curzon_module,
    # cine_lumiere_module,
    # electric_cinema_module,
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
        print("SCRAPE HEALTH REPORT")
        print("="*50)

        failures = []
        warnings = []

        # Header
        print(f"{'STATUS':<4} | {'CINEMA':<30} | {'COUNT':<5} | {'NOTES'}")
        print("-" * 70)

        for r in self.results:
            # Logic: If SUCCESS but 0 showings, treat as WARNING
            if r['status'] == 'SUCCESS' and r['count'] == 0:
                r['status'] = 'WARNING'
                warnings.append(r)
            elif r['status'] == 'FAILURE':
                failures.append(r)

            # Console Output Icons
            icon = "[OK]"
            if r['status'] == 'WARNING': icon = "[!!]"
            if r['status'] == 'FAILURE': icon = "[XX]"

            error_msg = f"{r['error']}" if r['error'] else ""
            if r['status'] == 'WARNING' and not error_msg:
                error_msg = "0 showings found"

            print(f"{icon:<4} | {r['cinema']:<30} | {r['count']:<5} | {error_msg}")

        print("-" * 70)
        print(f"Total Showings Collected: {self.total_showings}")
        return failures, warnings

    def send_email_alert(self, failures, warnings):
        """Sends an email if things went wrong."""
        if not failures and not warnings:
            return

        # 1. Gather Credentials
        smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.environ.get("SMTP_PORT", 465))
        sender_email = os.environ.get("SMTP_EMAIL")
        sender_password = os.environ.get("SMTP_PASSWORD")
        recipient_email = os.environ.get("ALERT_RECIPIENT_EMAIL")

        if not (sender_email and sender_password and recipient_email):
            print("Skipping email alert: Missing SMTP credentials.")
            return

        # 2. Build Content
        subject = f"London Scraper Alert: {len(failures)} Crashes, {len(warnings)} Empty"

        body_lines = ["The London Cinema Scraper encountered issues:\n"]

        if failures:
            body_lines.append(f"CRITICAL FAILURES ({len(failures)}):")
            for f in failures:
                body_lines.append(f"- {f['cinema']}: {f['error']}")
            body_lines.append("\n")

        if warnings:
            body_lines.append(f"POTENTIAL ISSUES (0 Showings Found):")
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
            print("Alert email sent successfully.")
        except Exception as e:
            print(f"Failed to send email alert: {e}")

# Initialize Global Report
report = ScrapeReport()

# --- TMDB Utilities ---

def clean_title_for_tmdb(title: str) -> str:
    """
    Strips common suffixes that confuse TMDB fuzzy matching.
    """
    if not title:
        return ""

    # Common UK release suffixes/prefixes to strip
    patterns = [
        r"4K Restor.*",                     # 4K Restore...
        r"4K Digital Remaster.*",           # 4K Digital Remaster
        r"Director's Cut",                  # Director's Cut
        r"Extended Edition",                # Extended Edition
        r"Anniversary Edition",             # Anniversary Edition
        r"Special Edition",                 # Special Edition
        r"Remastered",                      # Remastered
        r"\d+th Anniversary.*",             # 50th Anniversary...
        r"Double Bill.*",                   # Double Bill...
        r"Double Feature.*",                # Double Feature...
        r"\(\s*(U|PG|12A|12|15|18|R)\s*\)$", # UK/US rating suffixes
        r"\(\s*\d{4}\s*\)$",                # (1990)
        r"\(.*?version\)",                  # (XXX version)
        r"\[.*?\]",                         # [XXX]
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

def normalize_title_for_match(title: str) -> str:
    if not title:
        return ""
    normalized = unicodedata.normalize("NFKD", title)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized

def parse_year_value(raw_year):
    if not raw_year:
        return None
    try:
        year = int(str(raw_year).strip())
    except ValueError:
        return None
    current_year = datetime.now().year
    if 1880 <= year <= current_year + 3:
        return year
    return None

def extract_year_from_title(title: str):
    if not title:
        return None
    for match in re.findall(r"\((\d{4})\)", title):
        year = parse_year_value(match)
        if year:
            return year
    return None

def truncate_noisy_title(title: str) -> str:
    if not title:
        return ""
    if len(title) < 80:
        return title
    for keyword in ["doors", "film", "certificate", "digital", "book here", "not for the easily"]:
        match = re.search(re.escape(keyword), title, flags=re.IGNORECASE)
        if match:
            return title[:match.start()].strip()
    return title

def strip_event_prefix(title: str) -> str:
    if not title or ":" not in title:
        return title

    prefix, rest = title.split(":", 1)
    prefix_norm = normalize_title_for_match(prefix)
    prefix_keywords = [
        "presents",
        "presented by",
        "relaxed screening",
        "senior free matinee",
        "seniors free matinee",
        "philosophical screens",
        "deleted scenes",
        "scanners inc",
        "evolution of horror",
        "narrow margin",
        "pitchblack playback",
        "film quiz",
        "in conversation",
    ]
    if any(k in prefix_norm for k in prefix_keywords):
        return rest.strip()
    return title

def strip_event_suffix(title: str) -> str:
    if not title:
        return ""
    suffix_patterns = [
        r"\s*\+\s*(intro|discussion|q\s*&\s*a|qa|panel|talk|shorts|live score|live music|director|presented by|hosted by).*$",
        r"\s*-\s*.*(intro|discussion|q\s*&\s*a|qa|panel|talk|live|presented by|hosted by|with).*$",
    ]
    cleaned = title
    for pat in suffix_patterns:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned

def build_search_queries(title: str):
    if not title:
        return []

    queries = []
    base = truncate_noisy_title(title.strip())
    base = strip_event_prefix(base)
    base = strip_event_suffix(base)

    bracket_alts = re.findall(r"\[([^\]]+)\]", base)
    aka_alts = []
    for alt in bracket_alts:
        aka_match = re.search(r"\baka\s+(.*)", alt, flags=re.IGNORECASE)
        aka_alts.append(aka_match.group(1).strip() if aka_match else alt.strip())

    cleaned = clean_title_for_tmdb(base)
    base = base.strip(" .,:;")
    cleaned = cleaned.strip(" .,:;")

    if base:
        queries.append(base)
    if cleaned and cleaned not in queries:
        queries.append(cleaned)
    for alt in aka_alts:
        alt_clean = clean_title_for_tmdb(alt).strip(" .,:;")
        if alt_clean and alt_clean not in queries:
            queries.append(alt_clean)

    if " + " in base or " & " in base:
        parts = re.split(r"\s*(?:\+|&)\s*", base)
        for part in parts:
            part = strip_event_suffix(part.strip())
            part = clean_title_for_tmdb(part).strip(" .,:;")
            if part and part not in queries:
                queries.append(part)

    return queries

def score_tmdb_result(query: str, result: dict, query_year=None) -> float:
    query_norm = normalize_title_for_match(query)
    if not query_norm:
        return 0.0

    title_norm = normalize_title_for_match(result.get("title", ""))
    original_norm = normalize_title_for_match(result.get("original_title", ""))

    ratios = []
    if title_norm:
        ratios.append(difflib.SequenceMatcher(None, query_norm, title_norm).ratio())
    if original_norm and original_norm != title_norm:
        ratios.append(difflib.SequenceMatcher(None, query_norm, original_norm).ratio())
    if not ratios:
        return 0.0

    best_ratio = max(ratios)

    query_tokens = set(query_norm.split())
    title_tokens = set(title_norm.split()) if title_norm else set()
    if not title_tokens and original_norm:
        title_tokens = set(original_norm.split())
    token_overlap = 0.0
    if query_tokens and title_tokens:
        token_overlap = len(query_tokens & title_tokens) / len(query_tokens | title_tokens)

    score = (0.7 * best_ratio) + (0.3 * token_overlap)

    result_year = None
    release_date = result.get("release_date")
    if release_date:
        try:
            result_year = int(release_date.split("-")[0])
        except ValueError:
            result_year = None

    if query_year and result_year:
        if result_year == query_year:
            score += 0.1
        elif abs(result_year - query_year) <= 1:
            score += 0.05
        else:
            score -= 0.1

    if len(query_norm.split()) <= 2 and best_ratio < 0.85:
        score -= 0.05

    return score

def is_cache_match_ok(title: str, cached: dict, query_year=None) -> bool:
    if not cached:
        return False
    pseudo_result = {
        "title": cached.get("tmdb_title") or "",
        "original_title": cached.get("tmdb_original_title") or "",
        "release_date": cached.get("release_date") or "",
    }
    score = score_tmdb_result(title, pseudo_result, query_year=query_year)
    return score >= 0.62

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

def fetch_tmdb_details(movie_title, session, api_key, movie_year=None):
    """
    Searches TMDB for movie_title.
    1. Tries exact English match.
    2. If no result, tries a 'cleaned' version (stripping 4K/Remaster suffixes).
    """
    search_url = "https://api.themoviedb.org/3/search/movie"

    query_year = parse_year_value(movie_year) or extract_year_from_title(movie_title)
    queries = build_search_queries(movie_title)

    try:
        best = None
        best_score = 0.0
        best_query = None
        seen_ids = set()

        for query in queries:
            if query != movie_title:
                print(f"   Using cleaned title: '{query}'")
            params = {
                "api_key": api_key,
                "query": query,
                "language": "en-GB",
                "include_adult": "false"
            }
            if query_year:
                params["year"] = query_year

            resp = session.get(search_url, params=params, timeout=5)
            data = resp.json()
            results = data.get("results", [])

            for result in results:
                result_id = result.get("id")
                if not result_id or result_id in seen_ids:
                    continue
                seen_ids.add(result_id)

                score = score_tmdb_result(query, result, query_year=query_year)
                if score > best_score:
                    best = result
                    best_score = score
                    best_query = query

            if best_score >= 0.92:
                break

        if best and best_score >= 0.72:
            # Fetch full details
            detail_url = f"https://api.themoviedb.org/3/movie/{best['id']}"
            d_params = {
                "api_key": api_key,
                "language": "en-GB",
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

            if best_query and best_query != movie_title:
                print(f"   Best match via: '{best_query}' (score {best_score:.2f})")

            return {
                "tmdb_id": best["id"],
                "tmdb_title": d_data.get("title"),
                "tmdb_original_title": d_data.get("original_title"),
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
    print(f"\n--- Starting Enrichment for {len(listings)} listings ---")

    # Group by movie title to avoid duplicate API calls
    unique_titles = list(set(item["movie_title"] for item in listings))
    title_years = {}
    for item in listings:
        title = item.get("movie_title")
        if not title:
            continue
        if title in title_years and title_years[title]:
            continue
        year = parse_year_value(item.get("year"))
        title_years[title] = year
    print(f"   Unique films to process: {len(unique_titles)}")

    updated_cache = False

    for title in unique_titles:
        cached = cache.get(title)
        title_year = title_years.get(title)
        if cached and not is_cache_match_ok(title, cached, query_year=title_year):
            cached = None
            cache.pop(title, None)

        if title not in cache:
            # If we haven't checked this title before
            print(f"   Searching TMDB for: {title}")
            details = fetch_tmdb_details(title, session, api_key, movie_year=title_year)

            if details:
                cache[title] = details
                updated_cache = True
                print(f"      Found: {details['tmdb_title']} (ID: {details['tmdb_id']})")
            else:
                cache[title] = None # Mark as not found so we don't retry immediately
                print(f"      Not found.")

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
                item["tmdb_overview"] = d["overview"]
                item["runtime"] = d["runtime"]
                item["genres"] = d["genres"]
                item["vote_average"] = d["vote_average"]

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

def _run_scraper(name, func, listings_list, normalize_func=None):
    """
    Runs a scraper function with robust error handling and reporting.
    """
    print(f"\nScraping {name} ...")
    try:
        # Run the scraper
        rows = func() or []

        # Apply normalization if needed
        if normalize_func and rows:
            rows = normalize_func(rows)

        count = len(rows)
        print(f"-> {count} showings from {name}.")
        listings_list.extend(rows)

        # Report Success
        report.add(name, "SUCCESS", count)

    except Exception as e:
        # Report Failure but DO NOT CRASH main execution
        print(f"Error in {name}: {e}")
        traceback.print_exc()
        report.add(name, "FAILURE", 0, error=e)

# --- Main Execution ---

def main():
    # --- TIMEZONE SAFETY CHECK ---
    # Use UK timezone (GMT/BST - automatically handles daylight saving)
    # Note: For simplicity, we use UTC and let UK dates handle themselves
    # In production, consider using pytz for proper BST handling
    UK_OFFSET = timezone(timedelta(hours=0))  # Base GMT, adjust for BST as needed
    now_utc = datetime.now(timezone.utc)
    now_uk = now_utc.astimezone(UK_OFFSET)
    today_uk = now_uk.date()

    print(f"Scraper Start Time:")
    print(f"   UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"   UK:  {now_uk.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"   Today (UK): {today_uk.isoformat()}")
    print(f"   System timezone: {time.tzname}")
    print()

    tmdb_key = os.environ.get("TMDB_API_KEY")
    if not tmdb_key:
        print("Warning: TMDB_API_KEY not found. Metadata enrichment will be skipped.")

    # Prepare TMDB session
    api_session = requests.Session()
    tmdb_cache = load_tmdb_cache()

    listings = []

    # 1. DEFINE SCRAPERS TO RUN
    # Format: (Display Name, Function Object, Optional Normalizer)
    scrapers_to_run = [
        ("BFI Southbank", bfi_southbank_module.scrape_bfi_southbank, None),
        ("Prince Charles Cinema", prince_charles_module.scrape_prince_charles, None),
        ("The Garden Cinema", garden_cinema_module.scrape_garden_cinema, None),
        ("The Nickel", nickel_module.scrape_nickel, None),
        ("Barbican Cinema", barbican_module.scrape_barbican, None),
        ("Genesis Cinema", genesis_module.scrape_genesis, None),
        # ("ICA Cinema", ica_module.scrape_ica, None),
        ("ICA Cinema", ica_module.scrape_ica, None),
        ("Close-Up Film Centre", close_up_module.scrape_close_up, None),
        ("Phoenix Cinema", phoenix_cinema_module.scrape_phoenix_cinema, None),
        ("The Castle Cinema", castle_cinema_module.scrape_castle_cinema, None),
        ("Electric Cinema", electric_cinema_module.scrape_electric_cinema, None),
        # ("Genesis Cinema", genesis_module.scrape_genesis, None),
        # ("Rio Cinema", rio_cinema_module.scrape_rio, None),
        # ("Curzon", curzon_module.scrape_curzon, None),
        # ("Cine Lumiere", cine_lumiere_module.scrape_cine_lumiere, None),
    ]

    print("Starting all scrapers...")

    # 2. RUN SCRAPERS
    for item in scrapers_to_run:
        name = item[0]
        func = item[1]
        norm = item[2] if len(item) > 2 else None

        _run_scraper(name, func, listings, normalize_func=norm)

    # 3. ENRICHMENT
    print(f"\nCollected a total of {len(listings)} showings.")

    if tmdb_key:
        listings = enrich_listings_with_tmdb_links(listings, tmdb_cache, api_session, tmdb_key)

    # 4. SAVE OUTPUT
    print(f"Saving to {OUTPUT_JSON}...")

    # --- DATE VALIDATION ---
    today_count = sum(1 for item in listings if item.get("date_text") == today_uk.isoformat())
    all_dates = set(item.get("date_text") for item in listings if item.get("date_text"))

    print(f"\nData Summary:")
    print(f"   Total listings: {len(listings)}")
    print(f"   Listings for today ({today_uk.isoformat()}): {today_count}")
    print(f"   Unique dates in data: {sorted(all_dates)[:10]}")

    if today_count == 0 and listings:
        print(f"\n   WARNING: No listings found for today ({today_uk.isoformat()})!")
        print(f"   Cinema websites may not have updated their schedules yet.")

    try:
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(listings, f, ensure_ascii=False, indent=2)
        print("Done.")
    except Exception as e:
        print(f"Critical Error saving JSON: {e}")
        sys.exit(1)

    # 5. REPORTING & ALERTS
    failures, warnings = report.print_summary()

    # Send email if configured
    report.send_email_alert(failures, warnings)

if __name__ == "__main__":
    main()
