"""
Generate Instagram-ready image and caption for today's cinema showings.

VERSION 15 (FULLY DYNAMIC):
- Gradient: Adds a RANDOM OFFSET to the pulse logic. Every run produces
  a unique variation of the "Yellow Center / White Edge" theme.
- Logic: Keeps the "Smart Selection" (min 3 films) and bilingual support.
- Output: 4:5 Portrait (1080x1350) with grid-safe centering.
"""
from __future__ import annotations

import json
import math
import random
import re
import textwrap
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFont

try:  # Python 3.9+
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - fallback for older versions
    ZoneInfo = None  # type: ignore


BASE_DIR = Path(__file__).resolve().parent
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"
BOLD_FONT_PATH = BASE_DIR / "NotoSansJP-Bold.ttf"
REGULAR_FONT_PATH = BASE_DIR / "NotoSansJP-Regular.ttf"
OUTPUT_IMAGE_PATH = BASE_DIR / "post_image.png"
OUTPUT_CAPTION_PATH = BASE_DIR / "post_caption.txt"

# --- Configuration ---
MINIMUM_FILM_THRESHOLD = 3

# Layout (4:5 Portrait)
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350

# "Safe Zone" Logic (Center 1080x1080 square)
GRID_CROP_HEIGHT = (CANVAS_HEIGHT - CANVAS_WIDTH) // 2 
MARGIN = 60 
TEXT_BOX_MARGIN = 40
TITLE_WRAP_WIDTH = 30

# --- THEME COLORS ---
# Center Color (Deep Sunflower Yellow)
COLOR_CENTER = (255, 195, 11)
# Edge Color (Warm Off-White)
COLOR_EDGE = (255, 255, 250)

# Text & UI
TEXT_BG_COLOR = (255, 255, 255, 220) # Slightly opaque for readability
BLACK = (20, 20, 20)
GRAY = (80, 80, 80)

# --- Bilingual Cinema Address Database ---
CINEMA_ADDRESSES = {
    "Bunkamura ル・シネマ 渋谷宮下": "東京都渋谷区渋谷1-23-16 6F\n6F, 1-23-16 Shibuya, Shibuya-ku, Tokyo",
    "K's Cinema (ケイズシネマ)": "東京都新宿区新宿3-35-13 3F\n3F, 3-35-13 Shinjuku, Shinjuku-ku, Tokyo",
    "シネマート新宿": "東京都新宿区新宿3-13-3 6F\n6F, 3-13-3 Shinjuku, Shinjuku-ku, Tokyo",
    "新宿シネマカリテ": "東京都新宿区新宿3-37-12 5F\n5F, 3-37-12 Shinjuku, Shinjuku-ku, Tokyo",
    "新宿武蔵野館": "東京都新宿区新宿3-27-10 3F\n3F, 3-27-10 Shinjuku, Shinjuku-ku, Tokyo",
    "テアトル新宿": "東京都新宿区新宿3-14-20 7F\n7F, 3-14-20 Shinjuku, Shinjuku-ku, Tokyo",
    "早稲田松竹": "東京都新宿区高田馬場1-5-16\n1-5-16 Takadanobaba, Shinjuku-ku, Tokyo",
    "YEBISU GARDEN CINEMA": "東京都渋谷区恵比寿4-20-2\n4-20-2 Ebisu, Shibuya-ku, Tokyo",
    "シアター・イメージフォーラム": "東京都渋谷区渋谷2-10-2\n2-10-2 Shibuya, Shibuya-ku, Tokyo",
    "ユーロスペース": "東京都渋谷区円山町1-5 3F\n3F, 1-5 Maruyamacho, Shibuya-ku, Tokyo",
    "ヒューマントラストシネマ渋谷": "東京都渋谷区渋谷1-23-16 7F\n7F, 1-23-16 Shibuya, Shibuya-ku, Tokyo",
    "Stranger (ストレンジャー)": "東京都墨田区菊川3-7-1 1F\n1F, 3-7-1 Kikukawa, Sumida-ku, Tokyo",
    "新文芸坐": "東京都豊島区東池袋1-43-5 3F\n3F, 1-43-5 Higashi-Ikebukuro, Toshima-ku, Tokyo",
    "目黒シネマ": "東京都品川区上大崎2-24-15\n2-24-15 Kamiosaki, Shinagawa-ku, Tokyo",
    "ポレポレ東中野": "東京都中野区東中野4-4-1 1F\n1F, 4-4-1 Higashinakano, Nakano-ku, Tokyo",
    "K2 Cinema": "東京都世田谷区北沢2-21-22 2F\n2F, 2-21-22 Kitazawa, Setagaya-ku, Tokyo",
    "ヒューマントラストシネマ有楽町": "東京都千代田区有楽町2-7-1 8F\n8F, 2-7-1 Yurakucho, Chiyoda-ku, Tokyo",
    "ラピュタ阿佐ヶ谷": "東京都杉並区阿佐ヶ谷北2-12-21\n2-12-21 Asagayakita, Suginami-ku, Tokyo",
    "下高井戸シネマ": "東京都世田谷区松原3-30-15\n3-30-15 Matsubara, Setagaya-ku, Tokyo",
    "国立映画アーカイブ": "東京都中央区京橋3-7-6\n3-7-6 Kyobashi, Chuo-ku, Tokyo",
    "池袋シネマ・ロサ": "東京都豊島区西池袋1-37-12\n1-37-12 Nishi-Ikebukuro, Toshima-ku, Tokyo",
    "シネスイッチ銀座": "東京都中央区銀座4-4-5 3F\n3F, 4-4-5 Ginza, Chuo-ku, Tokyo",
    "シネマブルースタジオ": "東京都足立区千住3-92 2F\n2F, 3-92 Senju, Adachi-ku, Tokyo",
    "CINEMA Chupki TABATA": "東京都北区東田端2-14-4\n2-14-4 Higashitabata, Kita-ku, Tokyo",
    "シネクイント": "東京都渋谷区宇田川町20-11 8F\n8F, 20-11 Udagawacho, Shibuya-ku, Tokyo",
    "アップリンク吉祥寺": "東京都武蔵野市吉祥寺本町1-5-1 4F\n4F, 1-5-1 Kichijoji Honcho, Musashino-shi, Tokyo",
}

CINEMA_ENGLISH_NAMES = {
    "Bunkamura ル・シネマ 渋谷宮下": "Bunkamura Le Cinéma",
    "K's Cinema (ケイズシネマ)": "K's Cinema",
    "シネマート新宿": "Cinemart Shinjuku",
    "新宿シネマカリテ": "Shinjuku Cinema Qualite",
    "新宿武蔵野館": "Shinjuku Musashino-kan",
    "テアトル新宿": "Theatre Shinjuku",
    "早稲田松竹": "Waseda Shochiku",
    "YEBISU GARDEN CINEMA": "Yebisu Garden Cinema",
    "シアター・イメージフォーラム": "Theatre Image Forum",
    "ユーロスペース": "Eurospace",
    "ヒューマントラストシネマ渋谷": "Human Trust Cinema Shibuya",
    "Stranger (ストレンジャー)": "Stranger",
    "新文芸坐": "Shin-Bungeiza",
    "目黒シネマ": "Meguro Cinema",
    "ポレポレ東中野": "Pole Pole Higashi-Nakano",
    "K2 Cinema": "K2 Cinema",
    "ヒューマントラストシネマ有楽町": "Human Trust Cinema Yurakucho",
    "ラピュタ阿佐ヶ谷": "Laputa Asagaya",
    "下高井戸シネマ": "Shimotakaido Cinema",
    "国立映画アーカイブ": "National Film Archive of Japan",
    "池袋シネマ・ロサ": "Ikebukuro Cinema Rosa",
    "シネスイッチ銀座": "Cine Switch Ginza",
    "シネマブルースタジオ": "Cinema Blue Studio",
    "CINEMA Chupki TABATA": "Cinema Chupki Tabata",
    "シネクイント": "Cine Quinto Shibuya",
    "アップリンク吉祥寺": "Uplink Kichijoji",
}
# --- End of Database ---

def is_probably_not_japanese(text: str | None) -> bool:
    if not text: return False
    if not re.search(r'[a-zA-Z]', text): return False
    japanese_chars = re.findall(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', text)
    latin_chars = re.findall(r'[a-zA-Z]', text)
    if not japanese_chars: return True
    if latin_chars:
        if len(latin_chars) > len(japanese_chars) * 2: return True
        if len(japanese_chars) <= 2 and len(latin_chars) > len(japanese_chars): return True
    return False

def find_best_english_title(showing: Dict) -> str | None:
    jp_title = showing.get('movie_title', '').lower()
    
    def get_clean_title(title_key: str) -> str | None:
        title = showing.get(title_key)
        if not is_probably_not_japanese(title): return None
        cleaned_title = title.split(' (')[0].strip()
        if cleaned_title.lower() in jp_title: return None
        return cleaned_title

    if en_title := get_clean_title('letterboxd_english_title'): return en_title
    if en_title := get_clean_title('tmdb_display_title'): return en_title
    if en_title := get_clean_title('movie_title_en'): return en_title

    tmdb_orig_title = showing.get('tmdb_original_title')
    if is_probably_not_japanese(tmdb_orig_title) and tmdb_orig_title.lower() != jp_title:
        return tmdb_orig_title.split(' (')[0].strip()
    return None

def today_in_tokyo() -> datetime:
    if ZoneInfo is not None:
        try: return datetime.now(ZoneInfo("Asia/Tokyo"))
        except Exception: return datetime.now()
    return datetime.now()

def load_showtimes(today_str: str) -> List[Dict]:
    try:
        with SHOWTIMES_PATH.open("r", encoding="utf-8") as handle:
            all_showings = json.load(handle)
    except FileNotFoundError:
        print(f"showtimes.json not found at {SHOWTIMES_PATH}")
        raise
    except json.JSONDecodeError as exc:
        print("Unable to decode showtimes.json")
        raise exc
    todays_showings = [show for show in all_showings if show.get("date_text") == today_str]
    return todays_showings

def choose_cinema(showings: List[Dict]) -> Tuple[str, List[Dict]]:
    grouped: Dict[str, List[Dict]] = defaultdict(list)
    for show in showings:
        cinema_name = show.get("cinema_name")
        if cinema_name: grouped[cinema_name].append(show)

    if not grouped: return "", []

    candidates = []
    for cinema_name, cinema_showings in grouped.items():
        unique_titles = set(s.get('movie_title') for s in cinema_showings)
        candidates.append((cinema_name, len(unique_titles)))

    good_pool = [c[0] for c in candidates if c[1] >= MINIMUM_FILM_THRESHOLD]
    if not good_pool: good_pool = [c[0] for c in candidates if c[1] >= 2]
    if not good_pool: good_pool = [c[0] for c in candidates if c[1] >= 1]
    
    if not good_pool:
        print("No cinemas found with any films.")
        return "", []

    # Shuffle and pick
    random.shuffle(good_pool)
    chosen_cinema_name = random.choice(good_pool)
    
    print(f"Candidate Pool ({len(good_pool)}): {good_pool}")
    print(f"Selected Cinema: {chosen_cinema_name}")
    
    return chosen_cinema_name, grouped[chosen_cinema_name]

def format_listings(showings: List[Dict]) -> List[Dict[str, str | None]]:
    movies: Dict[Tuple[str, str | None], List[str]] = defaultdict(list)
    title_map: Dict[str, str | None] = {}
    for show in showings:
        title = show.get("movie_title") or "タイトル未定"
        if title not in title_map:
            title_map[title] = find_best_english_title(show)

    for show in showings:
        title = show.get("movie_title") or "タイトル未定"
        en_title = title_map[title]
        time_str = show.get("showtime") or ""
        if time_str: movies[(title, en_title)].append(time_str)

    formatted = []
    for (title, en_title) in sorted(movies.keys(), key=lambda k: k[0]):
        times_sorted = sorted(movies[(title, en_title)], key=lambda t: t)
        times_text = ", ".join(times_sorted)
        formatted.append({"title": title, "en_title": en_title, "times": times_text})
    return formatted

def generate_gradient_background() -> Image.Image:
    """
    Generates a radial gradient with a RANDOMIZED OFFSET.
    This ensures the image is unique every time it runs, while keeping the theme.
    """
    width, height = CANVAS_WIDTH, CANVAS_HEIGHT
    img = Image.new("RGB", (width, height), COLOR_EDGE)
    draw = ImageDraw.Draw(img)

    # Base pulse on day of year (slow evolution)
    day_of_year = datetime.now().timetuple().tm_yday
    base_pulse = (math.sin(day_of_year / 10.0) + 1) / 2 
    
    # Add a RANDOM offset (fast variation)
    # This makes every single generation distinct
    random_offset = random.uniform(-0.5, 0.5)
    
    # Combine them (clamped 0.0 to 1.0)
    final_pulse = max(0.0, min(1.0, base_pulse + random_offset))
    
    # Center
    cx, cy = width // 2, height // 2
    max_dist = math.sqrt(cx**2 + cy**2)
    
    # Calculate spread based on the randomized pulse
    spread_factor = 3.5 - (final_pulse * 2.0) # Varies between 1.5 (Wide) and 3.5 (Tight)
    
    print(f"Generating Gradient with Spread Factor: {spread_factor:.2f}")

    for r in range(int(max_dist), 0, -2):
        dist_norm = r / max_dist
        t = dist_norm ** spread_factor
        t = max(0, min(1, t))
        
        r_val = int(COLOR_CENTER[0] * (1-t) + COLOR_EDGE[0] * t)
        g_val = int(COLOR_CENTER[1] * (1-t) + COLOR_EDGE[1] * t)
        b_val = int(COLOR_CENTER[2] * (1-t) + COLOR_EDGE[2] * t)
        
        color = (r_val, g_val, b_val)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color, outline=color)
        
    return img

def draw_image(cinema_name: str, cinema_name_en: str, address_lines: list, bilingual_date: str, listings: List[Dict[str, str | None]]) -> None:
    try:
        img = generate_gradient_background().convert("RGBA")
    except Exception as e:
        print(f"Error generating background: {e}")
        img = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (255, 255, 255))

    try:
        title_jp_font = ImageFont.truetype(str(BOLD_FONT_PATH), 55)
        title_en_font = ImageFont.truetype(str(BOLD_FONT_PATH), 32)
        address_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 26)
        date_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 28)
        regular_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 36)
        en_movie_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 30)
        small_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 28)
        footer_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 24)
    except Exception:
        print("Error loading fonts.")
        raise

    overlay = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0,0,0,0))
    draw_ov = ImageDraw.Draw(overlay)
    
    # Safe Zone Box
    box_x0 = MARGIN
    box_y0 = GRID_CROP_HEIGHT + MARGIN
    box_x1 = CANVAS_WIDTH - MARGIN
    box_y1 = CANVAS_HEIGHT - GRID_CROP_HEIGHT - MARGIN
    
    draw_ov.rectangle([box_x0, box_y0, box_x1, box_y1], fill=TEXT_BG_COLOR)
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # Text Content
    content_left = MARGIN + TEXT_BOX_MARGIN
    y_pos = GRID_CROP_HEIGHT + MARGIN + TEXT_BOX_MARGIN + 10
    
    # Cinema Names
    draw.text((content_left, y_pos), cinema_name, font=title_jp_font, fill=BLACK)
    y_pos += 65
    if cinema_name_en:
        draw.text((content_left, y_pos), cinema_name_en, font=title_en_font, fill=BLACK)
        y_pos += 50
    else:
        y_pos += 10

    # Address
    if address_lines:
        draw.text((content_left, y_pos), address_lines[0], font=address_font, fill=GRAY)
        y_pos += 32
        if len(address_lines) > 1:
            draw.text((content_left, y_pos), address_lines[1], font=address_font, fill=GRAY)
            y_pos += 32
    y_pos += 20

    # Date
    draw.text((content_left, y_pos), bilingual_date, font=date_font, fill=GRAY)
    y_pos += 60

    # Listings
    max_text_y = CANVAS_HEIGHT - GRID_CROP_HEIGHT - MARGIN - TEXT_BOX_MARGIN - 60
    
    for listing in listings:
        if y_pos > max_text_y:
            draw.text((content_left, y_pos), "...", font=regular_font, fill=GRAY)
            break

        wrapped_title = textwrap.wrap(listing["title"], width=TITLE_WRAP_WIDTH) or [listing["title"]]
        for line in wrapped_title:
            if y_pos > max_text_y: break
            draw.text((content_left, y_pos), line, font=regular_font, fill=BLACK)
            y_pos += 44
        
        if listing["en_title"]:
            if y_pos > max_text_y: break
            wrapped_en = textwrap.wrap(f"({listing['
