#!/usr/bin/env python3
# main_scraper.py (V4: Substring Matching, Deep Verification & Full Metadata)

import json
import sys
import traceback
import re
import requests
import time
import os
import difflib
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

# -----------------------------------------------------------------------------
# UTF-8 Output
# -----------------------------------------------------------------------------
if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        if stream.encoding.lower() != "utf-8":
            try: stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception: pass

# --- Configuration ---
# Define Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_API_BASE_URL = 'https://api.themoviedb.org/3'
# UPDATE: Point cache to data directory
TMDB_CACHE_FILE = os.path.join(DATA_DIR, "tmdb_cache.json")
LETTERBOXD_TMDB_BASE_URL = "https://letterboxd.com/tmdb/"

REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- Helper Functions ---
def normalize_string(s):
    if not s: return ""
    # Remove punctuation and spaces for stricter comparison
    return re.sub(r'\W+', '', str(s)).lower()

def get_similarity(a, b):
    """Returns a ratio (0.0-1.0) of how similar two strings are."""
    if not a or not b: return 0.0
    return difflib.SequenceMatcher(None, normalize_string(a), normalize_string(b)).ratio()

def is_substring_match(full_text, short_text):
    """Checks if short_text is contained in full_text (normalized)."""
    if not full_text or not short_text: return False
    norm_full = normalize_string(full_text)
    norm_short = normalize_string(short_text)
    if len(norm_short) < 3: return False # Too short to be meaningful
    return norm_short in norm_full

# --- Schema Normalization ---
def _normalize_eurospace_schema(listings: list) -> list:
    normalized = []
    for show in listings:
        normalized.append({
            "cinema_name": show.get("cinema"),
            "movie_title": show.get("title"),
            "date_text": show.get("date"),
            "showtime": show.get("time"),
            "detail_page_url": show.get("url"),
            "director": show.get("director"),
            "year": str(show["year"]) if show.get("year") else "",
            "country": show.get("country"),
            "runtime_min": str(show["runtime"]) if show.get("runtime") else "",
            "synopsis": "",
            "movie_title_en": "",
        })
    return normalized

# --- Cache Functions ---
def load_json_cache(cache_file_path, cache_name="Cache"):
    if os.path.exists(cache_file_path):
        try:
            with open(cache_file_path, "r", encoding="utf-8") as f: return json.load(f)
        except Exception: pass
    return {}

def save_json_cache(data, cache_file_path, cache_name="Cache"):
    try:
        with open(cache_file_path, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception: pass

# --- Title Cleaning Function ---
def clean_title_for_search(title):
    if not title: return ""
    cleaned_title = title
    
    # 1. Aggressive Bracket Removal
    # Removes 【...】, [...], (...), <...> and anything inside them
    cleaned_title = re.sub(r'【.*?】', '', cleaned_title)
    cleaned_title = re.sub(r'\[.*?\]', '', cleaned_title)
    cleaned_title = re.sub(r'\(.*?\)', '', cleaned_title)
    cleaned_title = re.sub(r'（.*?）', '', cleaned_title)
    cleaned_title = re.sub(r'<.*?>', '', cleaned_title)
    cleaned_title = re.sub(r'＜.*?＞', '', cleaned_title)

    # 2. Specific Suffix Removal
    suffixes_to_remove = [
        r'\s*★トークショー付き', r'\s*35mmフィルム上映', 
        r'\s*4Kレストア5\.1chヴァージョン', r'\s*4Kデジタルリマスター版',
        r'\s*4Kレストア版', r'\s*4Kリマスター版', r'\s*４Kレーザー上映', r'\s*４K版', r'\s*４K', r'\s*4K', 
        r'\s*（字幕版）', r'\s*（字幕）', r'\s*（吹替版）', r'\s*（吹替）', 
        r'\s*THE MOVIE$', r'\s*\[受賞感謝上映］', r'\s*★上映後トーク付', 
        r'\s*トークイベント付き', r'\s*vol\.\s*\d+', 
        r'\s*ライブ音響上映', r'\s*特別音響上映', r'\s*字幕付き上映', 
        r'\s*デジタルリマスター(?:版)?', r'\s*デジタルリマスター', 
        r'\s*【完成披露試写会】', r'\s*Blu-ray発売記念上映',
        r'\s*公開記念舞台挨拶', r'\s*上映後舞台挨拶', r'\s*初日舞台挨拶', 
        r'\s*２日目舞台挨拶', r'\s*トークショー', r'\s*一挙上映',
        r'\s*超覚醒', r'\s*完全版', r'\s*【再上映】', r'\s*（再）', r'\s*再上映'
    ]
    
    for suffix_pattern in suffixes_to_remove:
        cleaned_title = re.sub(f'{suffix_pattern}$', '', cleaned_title, flags=re.IGNORECASE).strip()

    cleaned_title = re.sub(r'\s*[ァ-ヶА-я一-龠々]+公開版$', '', cleaned_title).strip()
    
    if cleaned_title:
        cleaned_title = cleaned_title.replace('：', ':').replace('　', ' ').strip()
        cleaned_title = re.sub(r'\s{2,}', ' ', cleaned_title)
        
    return cleaned_title.strip()

# --- TMDB Fetching Logic ---

def fetch_director_from_credits(tmdb_id, api_key, session):
    """Fetches the director name (in Japanese) for a specific ID."""
    url = f"{TMDB_API_BASE_URL}/movie/{tmdb_id}/credits?api_key={api_key}&language=ja-JP"
    try:
        resp = session.get(url, timeout=5)
        data = resp.json()
        for crew in data.get('crew', []):
            if crew['job'] == 'Director':
                return crew['name']
    except: pass
    return None

def calculate_match_score(tmdb_candidate, target_year, target_director=None, deep_director_check=None):
    """
    Scores a TMDB candidate against known data. Score range: -100 to 100+.
    """
    score = 0
    
    # 1. YEAR CHECK
    cand_date = tmdb_candidate.get('release_date', '')
    cand_year = int(cand_date[:4]) if cand_date and len(cand_date) >= 4 else None
    
    target_year_int = None
    if target_year and str(target_year).isdigit():
        target_year_int = int(target_year)

    if target_year_int and cand_year:
        diff = abs(target_year_int - cand_year)
        if diff == 0: score += 40
        elif diff == 1: score += 30 # Allow +/- 1 year variance
        elif diff <= 2: score += 10
        else: score -= 30 # Severe penalty for wrong era
    else:
        # If year is missing, neutral score (reliant on title match)
        score += 10

    # 2. DIRECTOR CHECK (Deep Verification)
    # If we performed a 'deep check' (fetched credits), use it.
    if deep_director_check and target_director:
        tmdb_dir = deep_director_check
        sim = get_similarity(target_director, tmdb_dir)
        if sim > 0.6: 
            score += 50 # Massive boost for confirmed director
            print(f"      [Director Match] '{target_director}' == '{tmdb_dir}' (+50)")
        # If we have a director and it DOESN'T match, small penalty?
        # No, usually spelling differences are huge in JP.

    # 3. POPULARITY BIAS
    if tmdb_candidate.get('popularity', 0) > 10: score += 5

    return score

def fetch_full_metadata(tmdb_id, api_key, session):
    """
    Fetches the deep details: Loglines, Director, Runtime, Tagline, Genres, Countries, Vote.
    """
    # 1. Fetch Japanese Data
    url_jp = f"{TMDB_API_BASE_URL}/movie/{tmdb_id}?api_key={api_key}&language=ja-JP&append_to_response=credits,release_dates"
    try:
        resp_jp = session.get(url_jp, headers=REQUEST_HEADERS, timeout=10)
        if resp_jp.status_code != 200: return None
        data_jp = resp_jp.json()
    except: return None

    # 2. Fetch English Data
    url_en = f"{TMDB_API_BASE_URL}/movie/{tmdb_id}?api_key={api_key}&language=en-US"
    try:
        resp_en = session.get(url_en, headers=REQUEST_HEADERS, timeout=10)
        data_en = resp_en.json() if resp_en.status_code == 200 else {}
    except: data_en = {}

    director = "Unknown"
    for person in data_jp.get('credits', {}).get('crew', []):
        if person.get('job') == 'Director':
            director = person.get('name')
            break
    
    genres = [g['name'] for g in data_jp.get('genres', [])[:3]]
    countries = [c['iso_3166_1'] for c in data_jp.get('production_countries', [])[:2]]

    return {
        "id": tmdb_id,
        "tmdb_title_jp": data_jp.get('title'),
        "tmdb_title_en": data_en.get('title'),
        "tmdb_original_title": data_en.get('original_title'),
        "tmdb_overview_jp": data_jp.get('overview'),
        "tmdb_overview_en": data_en.get('overview'),
        "tmdb_tagline_jp": data_jp.get('tagline'),
        "tmdb_tagline_en": data_en.get('tagline'),
        "tmdb_poster_path": data_jp.get('poster_path'),
        "tmdb_backdrop_path": data_jp.get('backdrop_path'),
        "tmdb_director": director,
        "tmdb_runtime": data_jp.get('runtime'),
        "tmdb_year": data_jp.get('release_date', '')[:4],
        "tmdb_genres": genres,
        "tmdb_countries": countries,
        "tmdb_vote_average": data_jp.get('vote_average'),
    }

def advanced_tmdb_search(listing, api_key, session):
    """
    Tries multiple search strategies and strictly validates the results.
    """
    raw_jp = listing.get('movie_title')
    clean_jp = clean_title_for_search(raw_jp)
    target_director = listing.get('director')
    
    search_queries = []
    # 1. English Title (Highest confidence)
    if listing.get('movie_title_en'):
        search_queries.append(listing['movie_title_en'])
        
    # 2. Cleaned Japanese Title
    if clean_jp:
        search_queries.append(clean_jp)
        
    # 3. Split Title (If it looks like "JpTitle EnTitle" or "Title Subtitle")
    if clean_jp and (' ' in clean_jp or '　' in clean_jp):
        parts = re.split(r'[ 　:：]', clean_jp)
        longest_part = max(parts, key=len)
        if len(longest_part) > 1:
            search_queries.append(longest_part)

    # --- EXECUTE SEARCHES ---
    candidates = {} 
    search_endpoint = f"{TMDB_API_BASE_URL}/search/movie"
    
    for query in search_queries:
        if not query: continue
        params = {'api_key': api_key, 'query': query, 'include_adult': 'false', 'language': 'ja-JP'}
        try:
            time.sleep(0.2)
            resp = session.get(search_endpoint, params=params, headers=REQUEST_HEADERS, timeout=10)
            if resp.status_code == 200:
                results = resp.json().get('results', [])
                for res in results[:5]: 
                    candidates[res['id']] = res
        except Exception as e:
            print(f"Search error for '{query}': {e}")

    if not candidates: return None

    # --- VALIDATION & SCORING ---
    best_candidate = None
    highest_score = -100
    
    target_year = listing.get('year')
    if target_year:
        target_year = re.sub(r'\D', '', str(target_year))
        if len(target_year) != 4: target_year = None

    # Check if we need DEEP verification (Short title or specific Director present)
    needs_deep_check = False
    if len(clean_jp) < 5: needs_deep_check = True 
    
    print(f"   🔍 Evaluating {len(candidates)} candidates for '{clean_jp}' (Year: {target_year}, Dir: {target_director})")

    for cand in candidates.values():
        # Base Score
        score = calculate_match_score(cand, target_year)
        
        # --- STRING MATCHING (Updated for V4) ---
        cand_title = cand.get('title', '')
        cand_orig = cand.get('original_title', '')
        
        # 1. Fuzzy Similarity
        sim_jp = get_similarity(clean_jp, cand_title)
        sim_orig = get_similarity(listing.get('movie_title_en'), cand_orig)
        
        # 2. Substring Matching (Fix for "Sky Crawlers")
        # Checks if "Sky Crawlers" is inside "スカイ・クロラ The Sky Crawlers"
        is_sub_jp = is_substring_match(clean_jp, cand_title) or is_substring_match(cand_title, clean_jp)
        
        # Boost Logic
        if sim_jp > 0.9 or sim_orig > 0.9: 
            score += 30 # Exact Fuzzy Match
        elif is_sub_jp:
            score += 30 # Substring Match (New Boost!)
            
        # --- DEEP DIRECTOR VERIFICATION ---
        # Only run if score is decent OR needs_deep_check, to save API calls
        if target_director and (needs_deep_check or score > 10):
             cand_director = fetch_director_from_credits(cand['id'], api_key, session)
             score += calculate_match_score(cand, target_year, target_director, deep_director_check=cand_director)
        
        if score > highest_score:
            highest_score = score
            best_candidate = cand

    if best_candidate:
        print(f"      Best Match: {best_candidate.get('title')} (Score: {highest_score})")

    # Threshold check
    if best_candidate and highest_score >= 25:
        return fetch_full_metadata(best_candidate['id'], api_key, session)
    
    return None

def enrich_listings_with_tmdb_links(all_listings, cache_data, session, tmdb_api_key):
    if not all_listings: return []

    unique_films = {}
    for listing in all_listings:
        title = listing.get('movie_title')
        if not title: continue
        year = listing.get('year')
        key = (title, year)
        if key not in unique_films:
            unique_films[key] = listing

    print(f"\n--- Starting Robust Enrichment for {len(unique_films)} unique films ---")
    
    enrichment_map = {}
    
    for key, listing in unique_films.items():
        clean_title = clean_title_for_search(listing.get('movie_title'))
        cache_key = f"{clean_title}|{key[1] if key[1] else ''}"
        
        if cache_key in cache_data:
            enrichment_map[key] = cache_data[cache_key]
            continue

        result = advanced_tmdb_search(listing, tmdb_api_key, session)
        
        if result:
            enrichment_map[key] = result
            cache_data[cache_key] = result
        else:
            enrichment_map[key] = {"not_found": True}

    save_json_cache(cache_data, TMDB_CACHE_FILE, "TMDB/Advanced Cache")

    for listing in all_listings:
        title = listing.get('movie_title')
        year = listing.get('year')
        key = (title, year)
        
        data = enrichment_map.get(key)
        if data and not data.get('not_found'):
            listing['tmdb_id'] = data['id']
            listing['tmdb_backdrop_path'] = data.get('tmdb_backdrop_path')
            listing['tmdb_poster_path'] = data.get('tmdb_poster_path')
            listing['tmdb_overview_jp'] = data.get('tmdb_overview_jp')
            listing['tmdb_overview_en'] = data.get('tmdb_overview_en')
            listing['tmdb_tagline_jp'] = data.get('tmdb_tagline_jp')
            listing['tmdb_tagline_en'] = data.get('tmdb_tagline_en')
            listing['clean_title_jp'] = data.get('tmdb_title_jp')
            listing['movie_title_en'] = data.get('tmdb_title_en')
            listing['director'] = data.get('tmdb_director')
            listing['year'] = data.get('tmdb_year')
            listing['runtime'] = data.get('tmdb_runtime')
            listing['genres'] = data.get('tmdb_genres')
            listing['production_countries'] = data.get('tmdb_countries')
            listing['vote_average'] = data.get('tmdb_vote_average')
            listing['letterboxd_link'] = f"{LETTERBOXD_TMDB_BASE_URL}{data['id']}"

    return all_listings

# --- Scraper Invocation & Main Block ---
def _run_scraper(label: str, func, normalize_func=None):
    print(f"\nScraping {label} …")
    try:
        rows = func() or []
        if normalize_func:
            rows = normalize_func(rows)
        print(f"→ {len(rows)} showings from {label}.")
        return rows
    except Exception as e:
        print(f"⚠️ Error in {label}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return []

def run_all_scrapers():
    print("Starting all scrapers…")
    all_listings = []
    
    all_listings += _run_scraper("Bunkamura", bunkamura_module.scrape_bunkamura)
    all_listings += _run_scraper("K's Cinema", ks_cinema_module.scrape_ks_cinema)
    all_listings += _run_scraper("Shin-Bungeiza", shin_bungeiza_module.scrape_shin_bungeiza)
    all_listings += _run_scraper("Shimotakaido Cinema", shimotakaido_module.scrape_shimotakaido)
    all_listings += _run_scraper("Stranger", stranger_module.scrape_stranger)
    all_listings += _run_scraper("Meguro Cinema", meguro_cinema_module.scrape_meguro_cinema)
    all_listings += _run_scraper("Image Forum", image_forum_module.scrape)
    all_listings += _run_scraper("Theatre Shinjuku", theatre_shinjuku_module.scrape_theatre_shinjuku)
    all_listings += _run_scraper("Pole Pole Higashi-Nakano", polepole_module.scrape_polepole)
    all_listings += _run_scraper("Cinema Blue Studio", bluestudio_module.scrape_bluestudio)
    all_listings += _run_scraper("Human Trust Cinema Shibuya", human_shibuya_module.scrape_human_shibuya)
    all_listings += _run_scraper("Human Trust Cinema Yurakucho", human_yurakucho_module.scrape_human_yurakucho)
    all_listings += _run_scraper("Laputa Asagaya", laputa_asagaya_module.scrape_laputa_asagaya)
    all_listings += _run_scraper("Shinjuku Musashino-kan", musashino_kan_module.scrape_musashino_kan)
    all_listings += _run_scraper("Waseda Shochiku", waseda_shochiku_module.scrape_waseda_shochiku)
    all_listings += _run_scraper("National Film Archive", nfaj_module.scrape_nfaj_calendar)
    all_listings += _run_scraper("Eurospace", eurospace_module.scrape, normalize_func=_normalize_eurospace_schema)
    all_listings += _run_scraper("Cinemart Shinjuku", cinemart_shinjuku_module.scrape_cinemart_shinjuku)
    all_listings += _run_scraper("Cinema Qualite", cinema_qualite_module.scrape_cinema_qualite)
    all_listings += _run_scraper("Cine Quinto", cine_quinto_module.scrape_cine_quinto)
    all_listings += _run_scraper("Yebisu Garden Cinema", yebisu_garden_module.scrape_yebisu_garden_cinema)
    all_listings += _run_scraper("K2 Cinema", k2_cinema_module.scrape_k2_cinema)
    all_listings += _run_scraper("Cinema Rosa", cinema_rosa_module.scrape_cinema_rosa)
    all_listings += _run_scraper("Chupki", chupki_module.scrape_chupki)
    all_listings += _run_scraper("Uplink Kichijoji", uplink_kichijoji_module.scrape_uplink_kichijoji)
    all_listings += _run_scraper("Tollywood", tollywood_module.scrape_tollywood)
    all_listings += _run_scraper("Morc Asagaya", morc_asagaya_module.fetch_morc_asagaya_showings)

    print(f"\nCollected a total of {len(all_listings)} showings from regular scrapers.")
    return all_listings

def save_to_json(data, filename="showtimes.json"):
    try:
        with open(filename, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ Saved to {filename}")
    except Exception as e: print(f"⚠️ Failed to save {filename}: {e}", file=sys.stderr)

if __name__ == "__main__":
    # Define Data Directory
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # UPDATE: Save to DATA_DIR
    with open(os.path.join(DATA_DIR, "showtimes.json"), "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=2, ensure_ascii=False)
        
    # UPDATE: Save Cache to DATA_DIR
    with open(os.path.join(DATA_DIR, "tmdb_cache.json"), "w", encoding="utf-8") as f:
        json.dump(tmdb_cache, f, indent=2, ensure_ascii=False)
    
    tmdb_key = TMDB_API_KEY
    if not tmdb_key or 'YOUR_TMDB_API_KEY' in tmdb_key:
        print("ERROR: TMDB API key not found.", file=sys.stderr)
        sys.exit(1)

    try:
        print("\nRunning Cine Switch Ginza module standalone to generate its JSON...")
        cine_switch_ginza_module.run_full_scrape_and_save()
    except Exception as e:
        print(f"Error running cine_switch_ginza_module: {e}", file=sys.stderr)

    listings = run_all_scrapers()
    
    try:
        with open("cineswitch_showtimes.json", "r", encoding="utf-8") as f:
            csg_showings = json.load(f)
            print(f"→ {len(csg_showings)} showings from Cine Switch Ginza (loaded from JSON).")
            listings.extend(csg_showings)
    except FileNotFoundError:
        print("WARNING: cineswitch_showtimes.json not found, skipping.", file=sys.stderr)
    except Exception as e:
        print(f"Error loading cineswitch_showtimes.json: {e}", file=sys.stderr)

    enriched_listings = enrich_listings_with_tmdb_links(
        listings, tmdb_cache, api_session, tmdb_key
    )
    
    try:
        enriched_listings.sort(key=lambda x: (
            x.get("cinema_name") or x.get("cinema", ""), x.get("date_text", ""), x.get("showtime", "")
        ))
    except Exception as e: print(f"Warning: Could not sort listings: {e}", file=sys.stderr)

    save_to_json(enriched_listings)
    print("\nEnrichment process complete.")



