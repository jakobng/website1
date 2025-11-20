#!/usr/bin/env python3
# main_scraper.py (Enhanced Version: Smart Enrichment & Image Fetching)

import json
import sys
import traceback
import re
import requests
import time
import os
import urllib.parse
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

# --- Google Gemini API Import ---
try:
    import google.generativeai as genai
except ImportError:
    print("google-generativeai library not installed. Gemini functionality will be disabled.", file=sys.stderr)
    genai = None

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
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
# ---
GEMINI_MODEL_NAME = 'gemini-2.5-flash'
gemini_model = None
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
TMDB_SEARCH_DELAY = 0.3
TMDB_DETAILS_DELAY = 0.3
TMDB_ALT_TITLES_DELAY = 0.3
GEMINI_DELAY = 1.0
LETTERBOXD_SCRAPE_DELAY = 0.5

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
    """Converts the unique schema from Eurospace to the standard project schema."""
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

# --- Improved Title Cleaning Function ---
def clean_title_for_search(title):
    """Aggressively cleans titles to remove marketing fluff for better TMDB matching."""
    if not title: return ""
    cleaned_title = title
    
    # 1. Remove standard brackets
    cleaned_title = re.sub(r'^[\[\(（【][^\]\)）】]*[\]\)）】]', '', cleaned_title).strip()

    # 2. Remove specific marketing suffixes (Expanded list)
    suffixes_to_remove = [
        r'\s*★トークショー付き', r'\s*35mmフィルム上映', r'\s*4Kレストア5\.1chヴァージョン', 
        r'\s*4Kデジタルリマスター版', r'\s*4Kレストア版', r'\s*４Kレーザー上映', r'\s*４K版', 
        r'\s*４K', r'\s*4K', r'\s*2K', r'\s*（字幕版）', r'\s*（字幕）', 
        r'\s*（吹替版）', r'\s*（吹替）', r'\s*THE MOVIE$', r'\s*\[受賞感謝上映］', 
        r'\s*★上映後トーク付', r'\s*トークイベント付き', r'\s*vol\.\s*\d+', 
        r'\s*［[^］]+(?:ｲﾍﾞﾝﾄ|イベント)］', r'\s*ライブ音響上映', r'\s*特別音響上映', 
        r'\s*字幕付き上映', r'\s*デジタルリマスター版', r'\s*【完成披露試写会】', 
        r'\s*Blu-ray発売記念上映', r'\s*公開記念舞台挨拶', r'\s*上映後舞台挨拶', 
        r'\s*初日舞台挨拶', r'\s*２日目舞台挨拶', r'\s*トークショー', r'\s*一挙上映',
        r'\s*ディレクターズカット', r'\s*完全版', r'\s*IMAX'
    ]
    
    for suffix_pattern in suffixes_to_remove:
        cleaned_title = re.sub(f'{suffix_pattern}$', '', cleaned_title, flags=re.IGNORECASE).strip()

    # 3. Remove text in parens that looks like year or format e.g. (2024)
    cleaned_title = re.sub(r'[\(（]\d{4}[\)）]', '', cleaned_title)

    cleaned_title = re.sub(r'\s*[ァ-ヶА-я一-龠々]+公開版$', '', cleaned_title).strip()
    if cleaned_title:
        cleaned_title = cleaned_title.replace('：', ':').replace('　', ' ').strip()
        cleaned_title = re.sub(r'\s{2,}', ' ', cleaned_title)
        
    return cleaned_title.strip()

# --- TMDB Film Details Fetching Function (ENHANCED) ---
def get_tmdb_film_details(search_title, api_key, session, year=None, language_code=None):
    default_return = {
        "id": None, 
        "tmdb_title": None, 
        "tmdb_original_title": None,
        "tmdb_backdrop_path": None
    }
    
    if not search_title or not api_key:
        return default_return

    # Dynamically build search params
    search_params = {'api_key': api_key, 'query': search_title, 'include_adult': 'false'}
    
    # If language is specified, use it. Otherwise allow default (English/All)
    if language_code:
        search_params['language'] = language_code
    
    # Note: We intentionally DO NOT filter by year in the API call (primary_release_year)
    # because TMDB years often differ by 1-2 years from Japanese release dates.
    # We will score the year manually below.
    
    search_url = f"{TMDB_API_BASE_URL}/search/movie"
    lang_info = f" (Lang: {language_code})" if language_code else " (Lang: Auto)"
    
    try:
        response = session.get(search_url, params=search_params, headers=REQUEST_HEADERS, timeout=10)
        time.sleep(TMDB_SEARCH_DELAY)
        response.raise_for_status()
        search_data = response.json()
    except Exception as e:
        print(f"   [Error] TMDB search '{search_title}': {e}", file=sys.stderr)
        return default_return

    if not search_data or not search_data.get('results'):
        return default_return

    best_match = None
    highest_score = -1
    st_lower = search_title.lower()

    # --- Scoring Logic ---
    for result in search_data['results'][:10]:
        score = 0
        res_title_ja = (result.get('title') or "").lower()
        res_title_orig = (result.get('original_title') or "").lower()
        
        # Exact match boost
        if st_lower == res_title_ja or st_lower == res_title_orig:
            score += 100
        elif st_lower in res_title_ja or st_lower in res_title_orig:
            score += 50
        
        # Year match boost
        release_date = result.get('release_date', '')
        if year and release_date:
            try:
                release_year = int(release_date.split('-')[0])
                target_year = int(year)
                # Allow +/- 2 years difference
                if abs(release_year - target_year) <= 2:
                    score += 50
                elif abs(release_year - target_year) > 5:
                    # Severe penalty for vastly different years (remakes vs originals)
                    score -= 100
            except (ValueError, IndexError):
                pass
        
        # Image availability boost (We prefer movies with backdrops)
        if result.get('backdrop_path'):
            score += 20
            
        # Popularity tie-breaker
        score += result.get('popularity', 0) / 1000

        if score > highest_score:
            highest_score = score
            best_match = result

    if not best_match or highest_score < 10: # Minimum confidence threshold
        return default_return

    # --- Success ---
    tmdb_id = best_match.get('id')
    print(f"   [TMDB] Match: '{search_title}' -> '{best_match.get('title')}' (ID: {tmdb_id})")

    return {
        "id": tmdb_id,
        "tmdb_title": best_match.get('title'),
        "tmdb_original_title": best_match.get('original_title'),
        "tmdb_backdrop_path": best_match.get('backdrop_path')
    }

# --- Letterboxd Title Scraping Function ---
def scrape_letterboxd_title(letterboxd_url, session):
    if not letterboxd_url: return None
    # Lightweight scrape just to get the clean English title from metadata
    try:
        response = session.get(letterboxd_url, headers=REQUEST_HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        meta_title_tag = soup.find('meta', property='og:title')
        if meta_title_tag and meta_title_tag.get('content'):
            title = meta_title_tag['content'].strip()
            title = re.sub(r'\s+–\s+Letterboxd$', '', title, flags=re.IGNORECASE).strip()
            title = re.sub(r'\s+\([^)]*directed by[^)]*\)$', '', title, flags=re.IGNORECASE).strip()
            return title
        return None
    except Exception:
        return None

# --- Gemini Function ---
def get_alternative_title_with_gemini(cleaned_film_title, original_title_for_context, session, year=None, director=None, country=None):
    global gemini_model
    if not gemini_model:
        return None
    
    title_to_use_for_prompt = original_title_for_context or cleaned_film_title
    
    context_parts = []
    if year: context_parts.append(f"released around {year}")
    if director: context_parts.append(f"directed by {director}")
    
    context_str = f" ({', '.join(context_parts)})" if context_parts else ""

    prompt = (
        f"What is the official English title OR the original language title for the film '{title_to_use_for_prompt}'{context_str}?\n"
        "Respond with ONLY the single most common title. If unknown, return 'NO_TITLE_FOUND'."
    )

    try:
        response = gemini_model.generate_content(prompt)
        alt_title = response.text.strip().replace('"', '')
        if alt_title and "NO_TITLE_FOUND" not in alt_title:
            print(f"   [Gemini] Suggests: '{alt_title}'")
            return alt_title
        return None
    except Exception:
        return None

# --- Main Enrichment Function (REVISED) ---
def enrich_listings_with_tmdb_links(all_listings, cache_data, session, tmdb_api_key, gemini_is_enabled):
    """
    Iterates through listings, cleaning titles and querying TMDB to populate metadata.
    Persists results to 'showtimes.json' via the return object.
    """
    if not all_listings:
        return []

    print(f"\n--- Starting Enrichment Process for {len(all_listings)} listings ---")

    # Deduplicate work: Process by (CleanTitle, Year) key
    unique_films = {}
    for listing in all_listings:
        raw_title = (listing.get('movie_title') or listing.get('title') or "").strip()
        if not raw_title: continue
        
        # Clean the title for better caching key
        cleaned_title = clean_title_for_search(raw_title)
        
        # Extract Year
        year_str = str(listing.get('year', '')).strip()
        year_match = re.search(r'\b(19[7-9]\d|20[0-2]\d|203\d)\b', year_str)
        year = year_match.group(0) if year_match else 'N/A'

        film_key = (cleaned_title, year)
        
        # Store metadata for the first occurrence of this film
        if film_key not in unique_films:
            unique_films[film_key] = {
                "original_raw_title": raw_title,
                "english_title": listing.get("movie_title_en"),
                "director": listing.get("director"),
                "country": listing.get("country"),
            }

    enrichment_map = {}
    
    for film_key, film_info in unique_films.items():
        cleaned_title, year = film_key
        
        # Composite Cache Key
        cache_key = f"{cleaned_title}|{year}"
        
        # 1. Check Cache
        if cache_key in cache_data:
            enrichment_map[film_key] = cache_data[cache_key]
            continue
        
        tmdb_result = {}
        search_year = year if year != 'N/A' else None

        # 2. Priority Search: English Title (if available)
        if tmdb_api_key and film_info.get("english_title"):
            tmdb_result = get_tmdb_film_details(
                clean_title_for_search(film_info["english_title"]), 
                tmdb_api_key, session, search_year, language_code=None
            )

        # 3. Fallback Search: Cleaned Japanese Title
        if tmdb_api_key and (not tmdb_result or not tmdb_result.get("id")):
            tmdb_result = get_tmdb_film_details(
                cleaned_title, tmdb_api_key, session, search_year, language_code='ja-JP'
            )
            
        # 4. Last Resort: Gemini
        if gemini_is_enabled and (not tmdb_result or not tmdb_result.get("id")):
            alt_title = get_alternative_title_with_gemini(
                cleaned_title, film_info["original_raw_title"], session,
                year=search_year, director=film_info["director"]
            )
            time.sleep(GEMINI_DELAY)
            
            if alt_title:
                tmdb_result = get_tmdb_film_details(
                    alt_title, tmdb_api_key, session, search_year, language_code=None
                )

        # 5. Letterboxd Link Generation
        current_enrichment_data = {}
        if tmdb_result and tmdb_result.get("id"):
            current_enrichment_data.update(tmdb_result)
            # Build the LB link
            lb_url = f"{LETTERBOXD_TMDB_BASE_URL}{current_enrichment_data['id']}"
            current_enrichment_data["letterboxd_link"] = lb_url
            
            # Optional: Scrape LB for "pure" English title if we only have JP title
            # (Skipped to save time, rely on TMDB title)

        enrichment_map[film_key] = current_enrichment_data
        cache_data[cache_key] = current_enrichment_data
    
    # Save updated cache
    save_json_cache(cache_data, TMDB_CACHE_FILE, "TMDB/Extended Cache")

    # Apply enriched data back to all listings
    for listing in all_listings:
        raw_title = (listing.get('movie_title') or listing.get('title') or "").strip()
        cleaned_title = clean_title_for_search(raw_title)
        
        year_str = str(listing.get('year', '')).strip()
        year_match = re.search(r'\b(19[7-9]\d|20[0-2]\d|203\d)\b', year_str)
        year = year_match.group(0) if year_match else 'N/A'
            
        film_key = (cleaned_title, year)
        enriched_data = enrichment_map.get(film_key, {})
        
        if enriched_data.get("id"):
            listing['letterboxd_link'] = enriched_data.get("letterboxd_link")
            listing['tmdb_display_title'] = enriched_data.get('tmdb_title')
            listing['tmdb_original_title'] = enriched_data.get('tmdb_original_title')
            # CRITICAL: Save the backdrop path so generator doesn't have to search again
            listing['tmdb_backdrop_path'] = enriched_data.get('tmdb_backdrop_path')
    
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
    
    # Execute all modules
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
    all_listings += _run_scraper("Uplink Kichijoji", lambda: []) # Placeholder if module incomplete

    print(f"\nCollected a total of {len(all_listings)} showings from regular scrapers.")
    return all_listings

def save_to_json(data, filename="showtimes.json"):
    try:
        with open(filename, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ Saved to {filename}")
    except Exception as e: print(f"⚠️ Failed to save {filename}: {e}", file=sys.stderr)

if __name__ == "__main__":
    # 1. Setup Gemini
    gemini_enabled = False
    if genai and GEMINI_API_KEY and 'YOUR_GEMINI_API_KEY' not in (GEMINI_API_KEY or ''):
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            gemini_model = genai.GenerativeModel(GEMINI_MODEL_NAME)
            gemini_enabled = True
            print(f"Gemini AI model '{GEMINI_MODEL_NAME}' initialized successfully.")
        except Exception as e:
            print(f"Could not initialize Gemini model: {e}", file=sys.stderr)
    else:
        print("--- WARNING: Gemini API key is missing. Gemini functions will be disabled. ---")

    # 2. Load Cache & Setup TMDB
    tmdb_cache = load_json_cache(TMDB_CACHE_FILE, "TMDB/Extended Cache")
    api_session = requests.Session()
    
    tmdb_key = TMDB_API_KEY
    if not tmdb_key or 'YOUR_TMDB_API_KEY' in tmdb_key:
        print("ERROR: TMDB API key not found.", file=sys.stderr)
        sys.exit(1)

    # 3. Run Standalone Scrapers (like Cine Switch Ginza which writes its own JSON)
    try:
        print("\nRunning Cine Switch Ginza module standalone...")
        cine_switch_ginza_module.run_full_scrape_and_save()
    except Exception as e:
        print(f"Error running cine_switch_ginza_module: {e}", file=sys.stderr)

    # 4. Run Main Scrapers
    listings = run_all_scrapers()
    
    # 5. Merge Standalone JSONs
    try:
        with open("cineswitch_showtimes.json", "r", encoding="utf-8") as f:
            csg_showings = json.load(f)
            print(f"→ {len(csg_showings)} showings from Cine Switch Ginza (loaded from JSON).")
            listings.extend(csg_showings)
    except FileNotFoundError:
        print("WARNING: cineswitch_showtimes.json not found, skipping.", file=sys.stderr)
    except Exception as e:
        print(f"Error loading cineswitch_showtimes.json: {e}", file=sys.stderr)

    # 6. ENRICH DATA (The "Smart Search" Step)
    enriched_listings = enrich_listings_with_tmdb_links(
        listings, tmdb_cache, api_session, tmdb_key, gemini_enabled
    )
    
    # 7. Sort and Save
    try:
        enriched_listings.sort(key=lambda x: (
            x.get("cinema_name") or x.get("cinema", ""), x.get("date_text", ""), x.get("showtime", "")
        ))
    except Exception as e: print(f"Warning: Could not sort listings: {e}", file=sys.stderr)

    save_to_json(enriched_listings)
    print("\nEnrichment process complete.")
