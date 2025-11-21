#!/usr/bin/env python3
# main_scraper.py (Fixed: Saves Images Correctly)

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
import uplink_kichijoji_module
import tollywood_module
import morc_asagaya_module

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
    cleaned_title = re.sub(r'^[\[\(（【][^\]\)）】]*[\]\)）】]', '', cleaned_title).strip()
    
    suffixes_to_remove = [
        r'\s*★トークショー付き', r'\s*35mmフィルム上映', r'\s*4Kレストア5\.1chヴァージョン', r'\s*4Kデジタルリマスター版',
        r'\s*4Kレストア版', r'\s*４Kレーザー上映', r'\s*４K版', r'\s*４K', r'\s*4K', r'\s*（字幕版）', r'\s*（字幕）', 
        r'\s*（吹替版）', r'\s*（吹替）', r'\s*THE MOVIE$', r'\s*\[受賞感謝上映］', r'\s*★上映後トーク付', 
        r'\s*トークイベント付き', r'\s*vol\.\s*\d+', r'\s*［[^］]+(?:ｲﾍﾞﾝﾄ|イベント)］', r'\s*ライブ音響上映', 
        r'\s*特別音響上映', r'\s*字幕付き上映', r'\s*デジタルリマスター版', r'\s*【完成披露試写会】', r'\s*Blu-ray発売記念上映',
        r'\s*公開記念舞台挨拶', r'\s*上映後舞台挨拶', r'\s*初日舞台挨拶', r'\s*２日目舞台挨拶', r'\s*トークショー', r'\s*一挙上映',
    ]
    for suffix_pattern in suffixes_to_remove:
        cleaned_title = re.sub(f'{suffix_pattern}$', '', cleaned_title, flags=re.IGNORECASE).strip()

    cleaned_title = re.sub(r'\s*[ァ-ヶА-я一-龠々]+公開版$', '', cleaned_title).strip()
    if cleaned_title:
        cleaned_title = cleaned_title.replace('：', ':').replace('　', ' ').strip()
        cleaned_title = re.sub(r'\s{2,}', ' ', cleaned_title)
    return cleaned_title.strip()

# --- TMDB Film Details Fetching Function ---
def get_tmdb_film_details(search_title, api_key, session, year=None, language_code=None):
    default_return = {
        "id": None, 
        "tmdb_title_jp": None, 
        "tmdb_title_en": None, 
        "tmdb_original_title": None, 
        "tmdb_backdrop_path": None,
        "tmdb_director": None,
        "tmdb_genres": [],
        "tmdb_runtime": None,
        "tmdb_year": None
    }
    
    if not search_title or not api_key: return default_return

    # 1. Search
    search_params = {'api_key': api_key, 'query': search_title, 'include_adult': 'false'}
    if year: search_params['primary_release_year'] = year
    if language_code: search_params['language'] = language_code
    
    search_url = f"{TMDB_API_BASE_URL}/search/movie"
    
    try:
        response = session.get(search_url, params=search_params, headers=REQUEST_HEADERS, timeout=10)
        time.sleep(TMDB_SEARCH_DELAY)
        response.raise_for_status()
        search_data = response.json()
    except Exception as e:
        print(f"Error during TMDB search for '{search_title}': {e}", file=sys.stderr)
        return default_return

    if not search_data or not search_data.get('results'):
        return default_return

    # (Simplified match logic: Take the first result that looks decent)
    best_match = search_data['results'][0]
    tmdb_id = best_match.get('id')
    backdrop_path = best_match.get('backdrop_path')
    
    print(f"   > Match Found: {tmdb_id} ('{best_match.get('title')}')")

    # 2. Fetch Full Details (Director, Genres, Official Titles)
    try:
        # A. Fetch in JAPANESE to get the official JP title
        url_jp = f"{TMDB_API_BASE_URL}/movie/{tmdb_id}?api_key={api_key}&language=ja-JP"
        resp_jp = session.get(url_jp, headers=REQUEST_HEADERS, timeout=10)
        data_jp = resp_jp.json()

        # B. Fetch in ENGLISH to get Director, original title, etc.
        url_en = f"{TMDB_API_BASE_URL}/movie/{tmdb_id}?api_key={api_key}&language=en-US&append_to_response=credits"
        resp_en = session.get(url_en, headers=REQUEST_HEADERS, timeout=10)
        data_en = resp_en.json()
        
        # Extract Director
        director = ""
        for person in data_en.get('credits', {}).get('crew', []):
            if person['job'] == 'Director':
                director = person['name']
                break
        
        # Extract Genres
        genres = [g['name'] for g in data_en.get('genres', [])[:2]]

        return {
            "id": tmdb_id,
            "tmdb_title_jp": data_jp.get('title'),        # Clean Official JP Title
            "tmdb_title_en": data_en.get('title'),        # English Title
            "tmdb_original_title": data_en.get('original_title'),
            "tmdb_backdrop_path": backdrop_path,
            "tmdb_director": director,
            "tmdb_genres": genres,
            "tmdb_runtime": data_en.get('runtime'),
            "tmdb_year": data_en.get('release_date', '')[:4]
        }

    except Exception as e:
        print(f"Error fetching details for ID {tmdb_id}: {e}")
        # Return partial data if detail fetch fails
        return {
            "id": tmdb_id, 
            "tmdb_title_jp": best_match.get('title'),
            "tmdb_backdrop_path": backdrop_path,
            "details_fetch_error": True
        }

# --- Letterboxd Title Scraping Function ---
def scrape_letterboxd_title(letterboxd_url, session):
    if not letterboxd_url: return None
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
    except Exception: return None

# --- Gemini Function ---
def get_alternative_title_with_gemini(cleaned_film_title, original_title_for_context, session, year=None, director=None, country=None):
    global gemini_model
    if not gemini_model: return None
    if not cleaned_film_title and not original_title_for_context: return None
    
    title_to_use_for_prompt = original_title_for_context or cleaned_film_title
    context_parts = []
    if year: context_parts.append(f"released in or around {year}")
    if director: context_parts.append(f"directed by {director}")
    if country: context_parts.append(f"from {country}")
    context_str = f" ({', '.join(context_parts)})" if context_parts else ""

    prompt = (
        f"What is the official English title OR the original language title (e.g. French, German) for the film '{title_to_use_for_prompt}'{context_str}?\n"
        "If it's an English-language film, return its original English title.\n"
        "Respond with ONLY the single most common title. If you cannot determine a title, return the exact phrase 'NO_TITLE_FOUND'."
    )

    try:
        response = gemini_model.generate_content(prompt)
        alt_title = response.text.strip().replace('"', '')
        if alt_title and "NO_TITLE_FOUND" not in alt_title.upper() and len(alt_title) > 1:
            print(f"Gemini: Found for '{title_to_use_for_prompt}': '{alt_title}'")
            return alt_title
        return "NO_TITLE_FOUND"
    except Exception as e:
        print(f"Error querying Gemini: {e}", file=sys.stderr)
        return None

# --- Main Enrichment Function (CORRECTED) ---
def enrich_listings_with_tmdb_links(all_listings, cache_data, session, tmdb_api_key, gemini_is_enabled):
    if not all_listings:
        return []

    # 1. Identify unique films
    unique_films = {}
    for listing in all_listings:
        original_title = (listing.get('movie_title') or listing.get('title') or "").strip()
        if not original_title or original_title.lower() in ["unknown title", "unknown film", "n/a"]:
            continue
        
        cleaned_title = clean_title_for_search(original_title)
        if not cleaned_title: continue

        year_from_listing = str(listing.get('year', '')).strip()
        if not year_from_listing or year_from_listing.upper() == 'N/A':
            year = 'N/A'
        else:
            year = (re.search(r'\b(19[7-9]\d|20[0-2]\d|203\d)\b', year_from_listing) or ['N/A'])[0]

        film_key = (cleaned_title, year)
        if film_key not in unique_films:
            unique_films[film_key] = {
                "original_title": original_title,
                "english_title": listing.get("movie_title_en"),
                "director": listing.get("director"),
                "country": listing.get("country"),
            }

    print(f"\n--- Starting Enrichment Process for {len(all_listings)} listings ({len(unique_films)} unique films) ---")

    enrichment_map = {}
    
    # 2. Process each unique film
    for film_key, film_info in unique_films.items():
        cleaned_title, year = film_key
        # Cache key logic
        cache_key = f"{cleaned_title}|{year if year != 'N/A' else ''}|{film_info.get('director') or ''}"
        
        if cache_key in cache_data:
            enrichment_map[film_key] = cache_data[cache_key]
            continue
        
        tmdb_result = {}
        search_year = year if year != 'N/A' else None

        # A. Search by English title provided by cinema
        english_title_from_scrape = film_info.get("english_title")
        if tmdb_api_key and english_title_from_scrape:
            tmdb_result = get_tmdb_film_details(english_title_from_scrape, tmdb_api_key, session, search_year)

        # B. Search by Cleaned Japanese title
        if tmdb_api_key and (not tmdb_result or not tmdb_result.get("id")):
            tmdb_result = get_tmdb_film_details(cleaned_title, tmdb_api_key, session, search_year, language_code='ja-JP')
            
        # C. Gemini Fallback
        if gemini_is_enabled and (not tmdb_result or not tmdb_result.get("id")):
            alt_title = get_alternative_title_with_gemini(
                cleaned_title, film_info["original_title"], session,
                year=search_year, director=film_info["director"], country=film_info["country"]
            )
            time.sleep(GEMINI_DELAY)
            if alt_title and "NO_TITLE_FOUND" not in alt_title:
                tmdb_result_from_alt = get_tmdb_film_details(alt_title, tmdb_api_key, session, year=search_year)
                if tmdb_result_from_alt and tmdb_result_from_alt.get("id"):
                    tmdb_result = tmdb_result_from_alt

        enrichment_map[film_key] = tmdb_result
        cache_data[cache_key] = tmdb_result
    
    save_json_cache(cache_data, TMDB_CACHE_FILE, "TMDB/Extended Cache")

    # 3. Apply back to all listings
    for listing in all_listings:
        original_title = (listing.get('movie_title') or listing.get('title') or "").strip()
        cleaned_title = clean_title_for_search(original_title)
        
        year_from_listing = str(listing.get('year', '')).strip()
        if not year_from_listing or year_from_listing.upper() == 'N/A':
            year = 'N/A'
        else:
            year = (re.search(r'\b(19[7-9]\d|20[0-2]\d|203\d)\b', year_from_listing) or ['N/A'])[0]
            
        film_key = (cleaned_title, year)
        enriched_data = enrichment_map.get(film_key, {})
        
        if enriched_data.get("id"):
            # --- KEY CHANGE: SAVE ALL METADATA TO JSON ---
            listing['tmdb_id'] = enriched_data.get('id')
            listing['tmdb_backdrop_path'] = enriched_data.get('tmdb_backdrop_path')
            
            # Overwrite details with official TMDB data
            if enriched_data.get('tmdb_title_jp'):
                listing['clean_title_jp'] = enriched_data.get('tmdb_title_jp')
            if enriched_data.get('tmdb_title_en'):
                listing['movie_title_en'] = enriched_data.get('tmdb_title_en')
            if enriched_data.get('tmdb_director'):
                listing['director'] = enriched_data.get('tmdb_director')
            if enriched_data.get('tmdb_genres'):
                listing['genres'] = enriched_data.get('tmdb_genres')
            if enriched_data.get('tmdb_runtime'):
                listing['runtime'] = enriched_data.get('tmdb_runtime')
            if enriched_data.get('tmdb_year'):
                listing['year'] = enriched_data.get('tmdb_year')
            
            listing['letterboxd_link'] = f"{LETTERBOXD_TMDB_BASE_URL}{enriched_data['id']}"
    
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

    tmdb_cache = load_json_cache(TMDB_CACHE_FILE, "TMDB/Extended Cache")
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

    enriched_listings = enrich_listings_with_tmdb_links(
        listings, tmdb_cache, api_session, tmdb_key, gemini_enabled
    )
    
    try:
        enriched_listings.sort(key=lambda x: (
            x.get("cinema_name") or x.get("cinema", ""), x.get("date_text", ""), x.get("showtime", "")
        ))
    except Exception as e: print(f"Warning: Could not sort listings: {e}", file=sys.stderr)

    save_to_json(enriched_listings)
    print("\nEnrichment process complete.")









