#!/usr/bin/env python3
# main_scraper.py (v2: Robust TMDB Matching & Expanded Metadata)

import json
import sys
import traceback
import re
import requests
import time
import os
import urllib.parse
import difflib  # Required for fuzzy string matching
from bs4 import BeautifulSoup

# --- All cinema scraper modules ---
import bunkamura_module
import bluestudio_module
import cine_switch_ginza_module
import eurospace_module
import human_shibuya_module
import human_yurakucho_module
import image_forum_module
import ks_cinema_module
import laputa_asagaya_module
import meguro_cinema_module
import musashino_kan_module
import nfaj_calendar_module as nfaj_module
import polepole_module
import shin_bungeiza_module
import shimotakaido_module
import stranger_module
import theatre_shinjuku_module
import waseda_shochiku_module
import cinemart_shinjuku_module
import cinema_qualite_module
import cine_quinto_module
import yebisu_garden_module
import k2_cinema_module
import cinema_rosa_module
import chupki_module
import uplink_kichijoji_module
import tollywood_module
import morc_asagaya_module

# -----------------------------------------------------------------------------
# UTF-8 Output
# -----------------------------------------------------------------------------
if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        if stream.encoding.lower() != "utf-8":
            try: stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception: pass

# --- Configuration ---
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_API_BASE_URL = 'https://api.themoviedb.org/3'
TMDB_CACHE_FILE = "tmdb_cache.json"
LETTERBOXD_TMDB_BASE_URL = "https://letterboxd.com/tmdb/"

REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- Helper Functions ---
def python_is_predominantly_latin(text):
    if not text: return False
    if not re.search(r'[a-zA-Z]', text): return False
    japanese_chars = re.findall(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', text)
    latin_chars = re.findall(r'[a-zA-Z]', text)
    if not japanese_chars: return True
    if latin_chars:
        if len(latin_chars) > len(japanese_chars) * 2: return True
        if len(japanese_chars) <= 2 and len(latin_chars) > len(japanese_chars): return True
        return False
    return False

# --- Schema Normalization for Eurospace ---
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
            with open(cache_file_path, "r", encoding="utf-8") as f: cache = json.load(f)
            print(f"Loaded {len(cache)} items from {cache_name} ({cache_file_path}).")
            return cache
        except Exception as e: print(f"Error loading {cache_name}: {e}", file=sys.stderr)
    return {}

def save_json_cache(data, cache_file_path, cache_name="Cache"):
    try:
        with open(cache_file_path, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e: print(f"Error saving {cache_name}: {e}", file=sys.stderr)

# --- Title Cleaning Function ---
def clean_title_for_search(title):
    if not title: return ""
    cleaned_title = title
    
    # 1. Aggressive Bracket Removal (New!)
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
        r'\s*4Kレストア版', r'\s*4Kリマスター版', # Added this specific one for Perfect Blue
        r'\s*４Kレーザー上映', r'\s*４K版', r'\s*４K', r'\s*4K', 
        r'\s*（字幕版）', r'\s*（字幕）', r'\s*（吹替版）', r'\s*（吹替）', 
        r'\s*THE MOVIE$', r'\s*\[受賞感謝上映］', r'\s*★上映後トーク付', 
        r'\s*トークイベント付き', r'\s*vol\.\s*\d+', 
        r'\s*ライブ音響上映', r'\s*特別音響上映', r'\s*字幕付き上映', 
        r'\s*デジタルリマスター(?:版)?', r'\s*デジタルリマスター',
        r'\s*【完成披露試写会】', r'\s*Blu-ray発売記念上映',
        r'\s*公開記念舞台挨拶', r'\s*上映後舞台挨拶', r'\s*初日舞台挨拶', 
        r'\s*２日目舞台挨拶', r'\s*トークショー', r'\s*一挙上映',
        r'\s*超覚醒', # Added for "KILL 超覚醒"
        r'\s*完全版'
    ]
    
    for suffix_pattern in suffixes_to_remove:
        cleaned_title = re.sub(f'{suffix_pattern}$', '', cleaned_title, flags=re.IGNORECASE).strip()

    cleaned_title = re.sub(r'\s*[ァ-ヶА-я一-龠々]+公開版$', '', cleaned_title).strip()
    
    if cleaned_title:
        cleaned_title = cleaned_title.replace('：', ':').replace('　', ' ').strip()
        cleaned_title = re.sub(r'\s{2,}', ' ', cleaned_title)
        
    return cleaned_title.strip()

# --- Advanced TMDB Matching Logic ---

def normalize_string(s):
    """Lowercases and removes punctuation for comparison."""
    if not s: return ""
    return re.sub(r'\W+', '', str(s)).lower()

def get_similarity(a, b):
    """Returns a ratio (0.0-1.0) of how similar two strings are."""
    if not a or not b: return 0.0
    return difflib.SequenceMatcher(None, normalize_string(a), normalize_string(b)).ratio()

def calculate_match_score(tmdb_candidate, target_year, target_director):
    """
    Scores a TMDB candidate against our known data.
    Score range: 0 to 100.
    """
    score = 0
    
    # 1. YEAR CHECK (Weighted High)
    # If we have a target year, it must match closely.
    candidate_date = tmdb_candidate.get('release_date', '')
    candidate_year = int(candidate_date[:4]) if candidate_date and len(candidate_date) >= 4 else None
    
    target_year_int = None
    if target_year and str(target_year).isdigit():
        target_year_int = int(target_year)

    if target_year_int and candidate_year:
        diff = abs(target_year_int - candidate_year)
        if diff == 0: score += 40
        elif diff == 1: score += 30
        elif diff <= 2: score += 10
        else: score -= 20 # Major penalty for wrong era
    else:
        # If no year provided, we can't verify, so we give a neutral small bump
        score += 10

    # 2. POPULARITY BIAS
    # If we have no other data, slightly prefer popular films (likely the original, not a remake)
    pop = tmdb_candidate.get('popularity', 0)
    if pop > 10: score += 5

    return score, candidate_year

def fetch_full_metadata(tmdb_id, api_key, session):
    """
    Fetches the deep details: Loglines (JP/EN), Director, Runtime, Tagline, Genres, Countries.
    """
    # 1. Fetch Japanese Data (Title, Overview, Poster)
    url_jp = f"{TMDB_API_BASE_URL}/movie/{tmdb_id}?api_key={api_key}&language=ja-JP&append_to_response=credits,release_dates"
    try:
        resp_jp = session.get(url_jp, headers=REQUEST_HEADERS, timeout=10)
        if resp_jp.status_code != 200: return None
        data_jp = resp_jp.json()
    except: return None

    # 2. Fetch English Data (Original Title, English Overview)
    url_en = f"{TMDB_API_BASE_URL}/movie/{tmdb_id}?api_key={api_key}&language=en-US"
    try:
        resp_en = session.get(url_en, headers=REQUEST_HEADERS, timeout=10)
        data_en = resp_en.json() if resp_en.status_code == 200 else {}
    except: data_en = {}

    # Extract Director
    director = "Unknown"
    crew = data_jp.get('credits', {}).get('crew', [])
    for person in crew:
        if person.get('job') == 'Director':
            director = person.get('name')
            break
    
    # Extract Genres (List of strings, limit to top 3)
    genres = [g['name'] for g in data_jp.get('genres', [])[:3]]

    # Extract Production Countries (List of codes e.g. 'US')
    countries = [c['iso_3166_1'] for c in data_jp.get('production_countries', [])[:2]]

    return {
        "id": tmdb_id,
        # Titles
        "tmdb_title_jp": data_jp.get('title'),
        "tmdb_title_en": data_en.get('title'),
        "tmdb_original_title": data_en.get('original_title'),
        
        # Synopses & Taglines
        "tmdb_overview_jp": data_jp.get('overview'),
        "tmdb_overview_en": data_en.get('overview'),
        "tmdb_tagline_jp": data_jp.get('tagline'),
        "tmdb_tagline_en": data_en.get('tagline'),
        
        # Images
        "tmdb_poster_path": data_jp.get('poster_path'),
        "tmdb_backdrop_path": data_jp.get('backdrop_path'),
        
        # Metadata
        "tmdb_director": director,
        "tmdb_runtime": data_jp.get('runtime'),
        "tmdb_year": data_jp.get('release_date', '')[:4],
        "tmdb_release_date": data_jp.get('release_date'),
        "tmdb_genres": genres,
        "tmdb_countries": countries,
        "tmdb_vote_average": data_jp.get('vote_average'),
        "tmdb_vote_count": data_jp.get('vote_count')
    }

def advanced_tmdb_search(listing, api_key, session):
    """
    Tries multiple search strategies and strictly validates the results.
    """
    search_queries = []
    
    # Query 1: English Title (if exists) - Highest confidence usually
    if listing.get('movie_title_en'):
        search_queries.append(listing['movie_title_en'])
        
    # Query 2: Cleaned Japanese Title
    raw_jp = listing.get('movie_title')
    clean_jp = clean_title_for_search(raw_jp)
    if clean_jp:
        search_queries.append(clean_jp)
        
    # Query 3: Split JP Title (sometimes "Title: Subtitle" fails, but "Title" works)
    if clean_jp and (' ' in clean_jp or '　' in clean_jp):
        # Split by space and take the first long part
        parts = re.split(r'[ 　:：]', clean_jp)
        longest_part = max(parts, key=len)
        if len(longest_part) > 1:
            search_queries.append(longest_part)

    # --- EXECUTE SEARCHES ---
    candidates = {} # Map ID to candidate object to deduplicate
    
    search_endpoint = f"{TMDB_API_BASE_URL}/search/movie"
    
    for query in search_queries:
        if not query: continue
        params = {'api_key': api_key, 'query': query, 'include_adult': 'false', 'language': 'ja-JP'}
        try:
            # Sleep slightly to respect rate limits
            time.sleep(0.2)
            resp = session.get(search_endpoint, params=params, headers=REQUEST_HEADERS, timeout=10)
            if resp.status_code == 200:
                results = resp.json().get('results', [])
                for res in results[:5]: # Check top 5 results
                    candidates[res['id']] = res
        except Exception as e:
            print(f"Search error for '{query}': {e}")

    if not candidates:
        return None

    # --- VALIDATION & SCORING ---
    best_candidate = None
    highest_score = -100
    
    target_year = listing.get('year')
    # Scraper sometimes returns "2023 (estimated)" or similar trash, clean it
    if target_year:
        target_year = re.sub(r'\D', '', str(target_year))
        # If year is truncated or invalid, ignore it
        if len(target_year) != 4: target_year = None
        
    target_director = listing.get('director')

    print(f"   🔍 Evaluating {len(candidates)} candidates for '{listing.get('movie_title')}' (Year: {target_year}, Dir: {target_director})")

    for cand in candidates.values():
        score, cand_year = calculate_match_score(cand, target_year, target_director)
        
        # Title Similarity Check
        title_sim_jp = get_similarity(clean_jp, cand.get('title'))
        title_sim_orig = get_similarity(listing.get('movie_title_en'), cand.get('original_title'))
        
        # Boost for strong title matches
        if title_sim_jp > 0.8: score += 20
        if title_sim_orig > 0.8: score += 20

    for cand in candidates.values():
        score, cand_year = calculate_match_score(cand, target_year, target_director)
        
        # Title Similarity Check
        title_sim_jp = get_similarity(clean_jp, cand.get('title'))
        title_sim_orig = get_similarity(listing.get('movie_title_en'), cand.get('original_title'))
        
        # Boost for strong title matches
        if title_sim_jp > 0.8: score += 20
        if title_sim_orig > 0.8: score += 20
        
        # --- NEW LOGIC: The "Perfect Match" Rescue ---
        # If title is effectively identical, force high score even if year is missing/wrong
        if title_sim_jp >= 0.95 or title_sim_orig >= 0.95:
            score += 30 # Huge boost for exact text match
            
        if score > highest_score:
            highest_score = score
            best_candidate = cand       
        if score > highest_score:
            highest_score = score
            best_candidate = cand

    # THRESHOLD: If score is too low, reject it.
    if best_candidate:
        print(f"      Best Match: {best_candidate.get('title')} (Score: {highest_score})")
    else:
        print(f"      No viable match found.")

    if best_candidate and highest_score >= 25: # 25 allows for slight year mismatch if title is perfect
        return fetch_full_metadata(best_candidate['id'], api_key, session)
    
    return None

def enrich_listings_with_tmdb_links(all_listings, cache_data, session, tmdb_api_key):
    if not all_listings: return []

    # 1. Deduplicate work
    unique_films = {}
    for listing in all_listings:
        title = listing.get('movie_title')
        if not title: continue
        
        # Create a unique key based on Title + Cinema's declared Year
        year = listing.get('year')
        key = (title, year)
        
        if key not in unique_films:
            unique_films[key] = listing

    print(f"\n--- Starting Robust Enrichment for {len(unique_films)} unique films ---")
    
    enrichment_map = {}
    
    for key, listing in unique_films.items():
        clean_title = clean_title_for_search(listing.get('movie_title'))
        # Check Cache
        # We use a composite key for cache to handle the new 'year' sensitivity
        cache_key = f"{clean_title}|{key[1] if key[1] else ''}"
        
        if cache_key in cache_data:
            enrichment_map[key] = cache_data[cache_key]
            continue

        # Perform Search
        result = advanced_tmdb_search(listing, tmdb_api_key, session)
        
        if result:
            enrichment_map[key] = result
            cache_data[cache_key] = result
        else:
            # Cache the failure locally so we don't retry endlessly for this run
            enrichment_map[key] = {"not_found": True}

    save_json_cache(cache_data, TMDB_CACHE_FILE, "TMDB/Advanced Cache")

    # Apply back to listings
    for listing in all_listings:
        title = listing.get('movie_title')
        year = listing.get('year')
        key = (title, year)
        
        data = enrichment_map.get(key)
        if data and not data.get('not_found'):
            # Core ID
            listing['tmdb_id'] = data['id']
            # Images
            listing['tmdb_backdrop_path'] = data.get('tmdb_backdrop_path')
            listing['tmdb_poster_path'] = data.get('tmdb_poster_path')
            # Text Content
            listing['tmdb_overview_jp'] = data.get('tmdb_overview_jp')
            listing['tmdb_overview_en'] = data.get('tmdb_overview_en')
            listing['tmdb_tagline_jp'] = data.get('tmdb_tagline_jp')
            listing['tmdb_tagline_en'] = data.get('tmdb_tagline_en')
            # Clean Metadata
            listing['clean_title_jp'] = data.get('tmdb_title_jp')
            listing['movie_title_en'] = data.get('tmdb_title_en')
            listing['director'] = data.get('tmdb_director')
            listing['year'] = data.get('tmdb_year')
            listing['runtime'] = data.get('tmdb_runtime')
            listing['genres'] = data.get('tmdb_genres')
            listing['production_countries'] = data.get('tmdb_countries')
            listing['vote_average'] = data.get('tmdb_vote_average')
            # Links
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
    tmdb_cache = load_json_cache(TMDB_CACHE_FILE, "TMDB/Advanced Cache")
    api_session = requests.Session()
    
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

    # Use the new enrichment logic without Gemini
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
