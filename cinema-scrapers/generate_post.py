"""
Generate Instagram-ready image carousel and caption.

VERSION 41: DECOUPLED PAGINATION
- Fix: 'segment_listings' now accepts a max_height parameter.
- Feature: Feed images use strict height limits (800px).
- Feature: Story images use relaxed height limits (1350px) to fit more films per slide.
- Result: Consolidates multi-slide cinemas into single story slides where possible.
"""
from __future__ import annotations

import json
import math
import random
import re
import textwrap
import os
import requests
import glob
import time
import colorsys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, ImageFilter

try:  
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"
BOLD_FONT_PATH = BASE_DIR / "NotoSansJP-Bold.ttf"
REGULAR_FONT_PATH = BASE_DIR / "NotoSansJP-Regular.ttf"
OUTPUT_CAPTION_PATH = BASE_DIR / "post_caption.txt"

TMDB_API_KEY = os.environ.get("TMDB_API_KEY")
MINIMUM_FILM_THRESHOLD = 3
INSTAGRAM_SLIDE_LIMIT = 10 
# Vertical space limits (Pixels)
MAX_FEED_VERTICAL_SPACE = 800 
MAX_STORY_VERTICAL_SPACE = 1350 # Much taller for 9:16 stories

# Layout
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350
STORY_CANVAS_HEIGHT = 1920
MARGIN = 60 
TITLE_WRAP_WIDTH = 30

# --- THEME COLORS ---
CONTENT_BG_COLOR = (255, 253, 245) # Warm Cream
BLACK = (20, 20, 20)
GRAY = (80, 80, 80)
WHITE = (255, 255, 255)

# --- Database (Cinemas) ---
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

# --- Utility Functions ---
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

def clean_search_title(title: str) -> str:
    if not title: return ""
    title = re.sub(r'[\(（].*?[\)）]', '', title)
    title = re.sub(r'[\[【].*?[\]】]', '', title)
    keywords = ["4K", "2K", "3D", "IMAX", "Dolby", "Atmos", "レストア", "デジタル", "リマスター", "完全版", "ディレクターズカット", "劇場版", "特別上映", "特集", "上映後トーク", "舞台挨拶"]
    for kw in keywords:
        title = title.replace(kw, "")
    return title.strip()

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

def segment_listings(listings: List[Dict[str, str | None]], max_height: int) -> List[List[Dict]]:
    """Segments listings based on a dynamic vertical height limit."""
    SEGMENTED_LISTS = []
    current_segment = []
    current_height = 0
    
    JP_LINE_HEIGHT = 40
    EN_LINE_HEIGHT = 30
    TIMES_LINE_HEIGHT = 55 

    for listing in listings:
        required_height = JP_LINE_HEIGHT + TIMES_LINE_HEIGHT
        if listing.get('en_title'):
             required_height += EN_LINE_HEIGHT
        
        if current_height + required_height > max_height:
            if current_segment:
                SEGMENTED_LISTS.append(current_segment)
                current_segment = [listing]
                current_height = required_height
            else:
                 SEGMENTED_LISTS.append([listing])
                 current_height = 0
        else:
            current_segment.append(listing)
            current_height += required_height
    
    if current_segment:
        SEGMENTED_LISTS.append(current_segment)
    return SEGMENTED_LISTS

def get_recently_featured(caption_path: Path) -> List[str]:
    if not caption_path.exists(): return []
    try:
        content = caption_path.read_text(encoding="utf-8")
        names = re.findall(r"--- 【(.*?)】 ---", content)
        return names
    except Exception as e:
        print(f"   [WARN] Could not read previous caption: {e}")
        return []

# --- IMAGE GENERATORS ---

def generate_fallback_burst() -> Image.Image:
    day_number = int(datetime.now().timestamp() // 86400)
    hue_degrees = (45 + (day_number // 3) * 12) % 360
    hue_norm = hue_degrees / 360.0
    r, g, b = colorsys.hsv_to_rgb(hue_norm, 1.0, 1.0)
    center_color = (int(r*255), int(g*255), int(b*255))
    img = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    center_x, center_y = CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2
    max_radius = int(math.sqrt((CANVAS_WIDTH/2)**2 + (CANVAS_HEIGHT/2)**2))
    for r in range(max_radius, 0, -2):
        t = r / max_radius
        t_adj = t ** 0.6
        red = int(center_color[0] * (1 - t_adj) + 255 * t_adj)
        green = int(center_color[1] * (1 - t_adj) + 255 * t_adj)
        blue = int(center_color[2] * (1 - t_adj) + 255 * t_adj)
        draw.ellipse([center_x - r, center_y - r, center_x + r, center_y + r], fill=(red, green, blue))
    return img

def process_image_bytes(img_content: bytes) -> Image.Image:
    """Helper to resize and crop image to canvas."""
    img = Image.open(BytesIO(img_content)).convert("RGB")
    target_ratio = CANVAS_WIDTH / CANVAS_HEIGHT
    img_ratio = img.width / img.height
    if img_ratio > target_ratio:
        new_width = int(img.height * target_ratio)
        left = (img.width - new_width) // 2
        img = img.crop((left, 0, left + new_width, img.height))
    else:
        new_height = int(img.width / target_ratio)
        top = (img.height - new_height) // 2
        img = img.crop((0, top, img.width, top + new_height))
    return img.resize((CANVAS_WIDTH, CANVAS_HEIGHT), Image.Resampling.LANCZOS)

def fetch_direct_backdrop(backdrop_path: str) -> Image.Image | None:
    """Fetches image directly using the path found by the scraper."""
    try:
        url = f"https://image.tmdb.org/t/p/w1280{backdrop_path}"
        print(f"   [DIRECT] Fetching pre-found image: {url}")
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return process_image_bytes(response.content)
    except Exception as e:
        print(f"   [WARN] Failed to fetch direct image: {e}")
    return None

def fetch_tmdb_backdrop_fallback(movie_title: str) -> Tuple[Image.Image, str] | None:
    if not TMDB_API_KEY: return None
    try:
        search_url = f"https://api.themoviedb.org/3/search/movie"
        params = {"api_key": TMDB_API_KEY, "query": movie_title, "language": "ja-JP"}
        time.sleep(0.1) 
        response = requests.get(search_url, params=params)
        data = response.json()
        if not data.get("results"):
             params.pop("language")
             response = requests.get(search_url, params=params)
             data = response.json()
        if not data.get("results"): return None
        
        movie = None
        for res in data["results"]:
            if res.get("backdrop_path"):
                movie = res
                break
        if not movie: return None
            
        image_url = f"https://image.tmdb.org/t/p/w1280{movie['backdrop_path']}"
        print(f"   [API SEARCH] Found Image for: {movie_title}")
        img_response = requests.get(image_url)
        resized_img = process_image_bytes(img_response.content)
        
        found_title = movie.get('title') or movie.get('original_title') or movie_title
        return resized_img, found_title
    except Exception:
        return None

def apply_cinematic_overlay(img: Image.Image) -> Image.Image:
    overlay = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0,0,0,0))
    draw = ImageDraw.Draw(overlay)
    for y in range(600):
        alpha = int(200 * (1 - (y / 600))) 
        draw.line([(0, y), (CANVAS_WIDTH, y)], fill=(0, 0, 0, alpha))
    for y in range(CANVAS_HEIGHT - 500, CANVAS_HEIGHT):
        alpha = int(200 * ((y - (CANVAS_HEIGHT - 500)) / 500))
        draw.line([(0, y), (CANVAS_WIDTH, y)], fill=(0, 0, 0, alpha))
    draw.rectangle([0, 0, CANVAS_WIDTH, CANVAS_HEIGHT], fill=(0, 0, 0, 80))
    img = img.convert("RGBA")
    return Image.alpha_composite(img, overlay).convert("RGB")

def draw_hero_slide(bilingual_date: str, hero_image: Image.Image, movie_title: str) -> Image.Image:
    img = apply_cinematic_overlay(hero_image)
    overlay = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0,0,0,0))
    draw_ov = ImageDraw.Draw(overlay)
    try:
        title_font = ImageFont.truetype(str(BOLD_FONT_PATH), 110)
        subtitle_font = ImageFont.truetype(str(BOLD_FONT_PATH), 55)
        date_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 40)
        footer_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 30)
        credit_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 24) 
    except Exception:
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
        date_font = ImageFont.load_default()
        footer_font = ImageFont.load_default()
        credit_font = ImageFont.load_default()

    text_center_x = CANVAS_WIDTH // 2
    center_y = CANVAS_HEIGHT // 2
    def draw_centered_text(y, text, font, color=WHITE):
        draw_ov.text((text_center_x, y), text, font=font, fill=color, anchor="mm")

    draw_centered_text(center_y - 120, "TOKYO", title_font)
    draw_centered_text(center_y + 20, "MINI THEATER", title_font)
    draw_centered_text(center_y + 160, "本日の上映情報", subtitle_font, (220, 220, 220))
    draw_centered_text(center_y + 240, bilingual_date, date_font, (220, 220, 220))
    draw_centered_text(CANVAS_HEIGHT - MARGIN - 40, "→ SWIPE FOR TODAY'S SELECTION →", footer_font, (255, 210, 0)) 
    if movie_title:
        draw_ov.text((CANVAS_WIDTH - 20, CANVAS_HEIGHT - 15), f"Image: {movie_title}", font=credit_font, fill=(180, 180, 180), anchor="rb")
    img = img.convert("RGBA")
    return Image.alpha_composite(img, overlay).convert("RGB")

def draw_cinema_slide(cinema_name: str, cinema_name_en: str, listings: List[Dict[str, str | None]]) -> Image.Image:
    img = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), CONTENT_BG_COLOR)
    draw = ImageDraw.Draw(img)
    try:
        title_jp_font = ImageFont.truetype(str(BOLD_FONT_PATH), 55)
        title_en_font = ImageFont.truetype(str(BOLD_FONT_PATH), 32)
        regular_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 34)
        en_movie_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 28)
        small_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 28)
        footer_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 24)
    except Exception:
        raise
    content_left = MARGIN + 20
    y_pos = MARGIN + 40
    draw.text((content_left, y_pos), cinema_name, font=title_jp_font, fill=BLACK)
    y_pos += 70
    cinema_name_to_use = cinema_name_en or CINEMA_ENGLISH_NAMES.get(cinema_name, "")
    if cinema_name_to_use:
        draw.text((content_left, y_pos), cinema_name_to_use, font=title_en_font, fill=GRAY)
        y_pos += 50
    else:
        y_pos += 20
    address = CINEMA_ADDRESSES.get(cinema_name, "")
    if address:
        jp_addr = address.split("\n")[0]
        draw.text((content_left, y_pos), f"📍 {jp_addr}", font=small_font, fill=GRAY)
        y_pos += 60
    else:
        y_pos += 30
    draw.line([(MARGIN, y_pos), (CANVAS_WIDTH - MARGIN, y_pos)], fill=BLACK, width=3)
    y_pos += 40
    for listing in listings:
        wrapped_title = textwrap.wrap(f"■ {listing['title']}", width=TITLE_WRAP_WIDTH) or [f"■ {listing['title']}"]
        for line in wrapped_title:
            draw.text((content_left, y_pos), line, font=regular_font, fill=BLACK)
            y_pos += 40
        if listing["en_title"]:
            wrapped_en = textwrap.wrap(f"({listing['en_title']})", width=35)
            for line in wrapped_en:
                draw.text((content_left + 10, y_pos), line, font=en_movie_font, fill=GRAY)
                y_pos += 30
        if listing['times']:
            draw.text((content_left + 40, y_pos), listing["times"], font=regular_font, fill=GRAY)
            y_pos += 55
    footer_text_final = "詳細は web / Details online: leonelki.com/cinemas"
    draw.text((CANVAS_WIDTH // 2, CANVAS_HEIGHT - MARGIN - 20), footer_text_final, font=footer_font, fill=GRAY, anchor="mm")
    return img.convert("RGB")

def draw_story_slide(cinema_name: str, cinema_name_en: str, listings: List[Dict[str, str | None]]) -> Image.Image:
    """Generates a 9:16 vertical Story slide."""
    img = Image.new("RGB", (CANVAS_WIDTH, STORY_CANVAS_HEIGHT), CONTENT_BG_COLOR)
    draw = ImageDraw.Draw(img)
    
    try:
        header_font = ImageFont.truetype(str(BOLD_FONT_PATH), 70)
        subhead_font = ImageFont.truetype(str(BOLD_FONT_PATH), 40)
        movie_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 42)
        time_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 36)
        footer_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 30)
    except Exception:
        header_font = ImageFont.load_default()
        subhead_font = ImageFont.load_default()
        movie_font = ImageFont.load_default()
        time_font = ImageFont.load_default()
        footer_font = ImageFont.load_default()

    center_x = CANVAS_WIDTH // 2
    y_pos = 150 

    draw.text((center_x, y_pos), cinema_name, font=header_font, fill=BLACK, anchor="mm")
    y_pos += 80
    
    cinema_name_to_use = cinema_name_en or CINEMA_ENGLISH_NAMES.get(cinema_name, "")
    if cinema_name_to_use:
        draw.text((center_x, y_pos), cinema_name_to_use, font=subhead_font, fill=GRAY, anchor="mm")
        y_pos += 100
    else:
        y_pos += 60

    draw.line([(100, y_pos), (CANVAS_WIDTH - 100, y_pos)], fill=BLACK, width=4)
    y_pos += 80

    for listing in listings:
        wrapped_title = textwrap.wrap(listing['title'], width=24)
        for line in wrapped_title:
            draw.text((center_x, y_pos), line, font=movie_font, fill=BLACK, anchor="mm")
            y_pos += 55
        
        if listing['times']:
            draw.text((center_x, y_pos), listing["times"], font=time_font, fill=GRAY, anchor="mm")
            y_pos += 80
        else:
            y_pos += 40

    draw.text((center_x, STORY_CANVAS_HEIGHT - 150), "Full Schedule Link in Bio", font=footer_font, fill=BLACK, anchor="mm")
    return img

def draw_hero_story(bilingual_date: str, hero_image: Image.Image, movie_title: str) -> Image.Image:
    """Creates a 9:16 version of the Hero Image."""
    img_ratio = hero_image.width / hero_image.height
    target_ratio = CANVAS_WIDTH / STORY_CANVAS_HEIGHT
    
    if img_ratio > target_ratio:
        new_width = int(hero_image.height * target_ratio)
        left = (hero_image.width - new_width) // 2
        hero_crop = hero_image.crop((left, 0, left + new_width, hero_image.height))
    else:
        hero_crop = hero_image
        
    hero_crop = hero_crop.resize((CANVAS_WIDTH, STORY_CANVAS_HEIGHT), Image.Resampling.LANCZOS)
    
    overlay = Image.new("RGBA", (CANVAS_WIDTH, STORY_CANVAS_HEIGHT), (0,0,0,0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle([0, 0, CANVAS_WIDTH, STORY_CANVAS_HEIGHT], fill=(0, 0, 0, 100))
    
    try:
        title_font = ImageFont.truetype(str(BOLD_FONT_PATH), 120)
        date_font = ImageFont.truetype(str(BOLD_FONT_PATH), 60)
    except:
        title_font = ImageFont.load_default()
        date_font = ImageFont.load_default()

    center_x = CANVAS_WIDTH // 2
    center_y = STORY_CANVAS_HEIGHT // 2

    draw.text((center_x, center_y - 100), "TOKYO\nINDIE\nGUIDE", font=title_font, fill=WHITE, anchor="mm", align="center")
    draw.text((center_x, center_y + 200), bilingual_date, font=date_font, fill=(255, 210, 0), anchor="mm")

    hero_crop = hero_crop.convert("RGBA")
    return Image.alpha_composite(hero_crop, overlay).convert("RGB")

def main() -> None:
    # 1. Basic Setup
    today = today_in_tokyo().date()
    today_str = today.isoformat()
    date_jp = today.strftime("%Y年%m月%d日")
    date_en = today.strftime("%b %d, %Y")
    bilingual_date_str = f"{date_jp} / {date_en}"

    # 2. Cleanup
    for old_file in glob.glob(str(BASE_DIR / "post_image_*.png")): os.remove(old_file) 
    for old_file in glob.glob(str(BASE_DIR / "story_image_*.png")): os.remove(old_file)

    todays_showings = load_showtimes(today_str)
    if not todays_showings:
        print(f"No showings for today ({today_str}). Exiting.")
        return

    # 3. Group Cinemas
    grouped: Dict[str, List[Dict]] = defaultdict(list)
    for show in todays_showings:
        if show.get("cinema_name"):
            grouped[show.get("cinema_name")].append(show)

    all_candidates_raw = []
    for cinema_name, showings in grouped.items():
        unique_titles = set(s.get('movie_title') for s in showings if s.get('movie_title'))
        
        known_backdrops = []
        all_searchable_titles = []
        
        for s in showings:
            if s.get('tmdb_backdrop_path'):
                display_title = s.get('tmdb_display_title') or s.get('tmdb_original_title') or s.get('movie_title')
                known_backdrops.append((s.get('tmdb_backdrop_path'), display_title))

            if s.get('tmdb_original_title'): all_searchable_titles.append(s.get('tmdb_original_title'))
            if s.get('tmdb_display_title'): all_searchable_titles.append(s.get('tmdb_display_title'))
            if s.get('movie_title'): all_searchable_titles.append(clean_search_title(s.get('movie_title')))
            if s.get('movie_title_en'): all_searchable_titles.append(clean_search_title(s.get('movie_title_en')))

        if len(unique_titles) >= MINIMUM_FILM_THRESHOLD:
            listings = format_listings(showings)
            
            # PRE-CALCULATE SEGMENTS FOR FEED ONLY (Used for Selection Logic)
            feed_segments = segment_listings(listings, MAX_FEED_VERTICAL_SPACE)

            all_candidates_raw.append({
                "name": cinema_name,
                "listings": listings,
                "feed_segments": feed_segments, # Only used for checking slide counts
                "unique_count": len(unique_titles),
                "titles": list(set(all_searchable_titles)),
                "backdrops": list(set(known_backdrops))
            })

    # 4. Rotation & Randomization
    recent_cinemas = get_recently_featured(OUTPUT_CAPTION_PATH)
    fresh_candidates = []
    recent_candidates = []
    for cand in all_candidates_raw:
        if cand['name'] in recent_cinemas:
            recent_candidates.append(cand)
        else:
            fresh_candidates.append(cand)
    random.shuffle(fresh_candidates)
    random.shuffle(recent_candidates)
    all_candidates = fresh_candidates + recent_candidates
    
    # 5. Selection Logic (Based on FEED Constraints)
    MAX_CONTENT_SLIDES = INSTAGRAM_SLIDE_LIMIT - 1 
    final_selection = []
    current_slide_count = 0
    remaining_candidates = []
    
    for cand in all_candidates:
        needed = len(cand['feed_segments']) # We use Feed segments to determine "fit"
        if current_slide_count + needed <= MAX_CONTENT_SLIDES:
            final_selection.append(cand)
            current_slide_count += needed
        else:
            remaining_candidates.append(cand)

    if not final_selection:
        print("No cinemas selected. Exiting.")
        return

    # 6. HERO IMAGE SEARCH
    print("--- Phase 1: Searching Standard Candidates for Hero Image ---")
    hero_image = None
    hero_title = ""
    valid_hero_options = []

    for cand in final_selection:
        if cand['backdrops']:
            path, title = random.choice(cand['backdrops'])
            img = fetch_direct_backdrop(path)
            if img:
                valid_hero_options.append((img, title))
                continue
        
        titles_to_check = cand['titles']
        random.shuffle(titles_to_check)
        for title in titles_to_check[:3]:
            if not title: continue
            res = fetch_tmdb_backdrop_fallback(title)
            if res:
                valid_hero_options.append(res)
                break 
    
    if valid_hero_options:
        hero_image, hero_title = random.choice(valid_hero_options)
    else:
        print("   [WARNING] No Hero images found in standard selection.")

    # 7. RESCUE PROTOCOL
    if not hero_image:
        print("--- Phase 2: RESCUE PROTOCOL - Searching Remaining Cinemas ---")
        rescue_candidates = []
        for cand in remaining_candidates:
            if cand['backdrops']:
                path, title = random.choice(cand['backdrops'])
                img = fetch_direct_backdrop(path)
                if img:
                    rescue_candidates.append({"candidate": cand, "image_data": (img, title)})
                    continue

            titles_to_check = cand['titles']
            random.shuffle(titles_to_check)
            for title in titles_to_check[:3]:
                res = fetch_tmdb_backdrop_fallback(title)
                if res:
                    rescue_candidates.append({"candidate": cand, "image_data": res})
                    break 
        
        if rescue_candidates:
            winner = random.choice(rescue_candidates)
            rescue_cand = winner["candidate"]
            hero_image, hero_title = winner["image_data"]
            
            rescue_needed = len(rescue_cand['feed_segments'])
            while final_selection and (current_slide_count + rescue_needed > MAX_CONTENT_SLIDES):
                removed = final_selection.pop()
                current_slide_count -= len(removed['feed_segments'])
            final_selection.append(rescue_cand)

    # 8. Fallback
    if not hero_image:
        hero_image = generate_fallback_burst()
        hero_title = ""

    # 9. DRAW SLIDES (Decoupled Loops)
    
    # --- A. HERO SLIDES ---
    hero_slide = draw_hero_slide(bilingual_date_str, hero_image, hero_title)
    hero_slide.save(BASE_DIR / f"post_image_00.png")
    story_hero = draw_hero_story(bilingual_date_str, hero_image, hero_title)
    story_hero.save(BASE_DIR / f"story_image_00.png")
    print("Saved Hero Slides.")

    # --- B. FEED SLIDES (Strict 800px Limit) ---
    print("Generatinng Feed Images (Strict Height)...")
    feed_counter = 0
    all_featured_for_caption = []
    
    for item in final_selection:
        cinema_name = item['name']
        cinema_name_en = CINEMA_ENGLISH_NAMES.get(cinema_name, "")
        listings = item['listings']
        
        all_featured_for_caption.append({"cinema_name": cinema_name, "listings": listings})

        # Calculate segments specifically for Feed
        feed_segments = segment_listings(listings, MAX_FEED_VERTICAL_SPACE)
        
        for segment in feed_segments:
            feed_counter += 1
            slide_img = draw_cinema_slide(cinema_name, cinema_name_en, segment)
            slide_img.save(BASE_DIR / f"post_image_{feed_counter:02}.png")
            print(f"   Saved Feed Slide {feed_counter} ({cinema_name})")

    # --- C. STORY SLIDES (Relaxed 1350px Limit) ---
    print("Generatinng Story Images (Relaxed Height)...")
    story_counter = 0
    
    for item in final_selection:
        cinema_name = item['name']
        cinema_name_en = CINEMA_ENGLISH_NAMES.get(cinema_name, "")
        listings = item['listings']

        # Calculate segments specifically for Stories
        # This allows Yebisu Garden Cinema (2 Feed slides) to fit on 1 Story slide
        story_segments = segment_listings(listings, MAX_STORY_VERTICAL_SPACE)
        
        for segment in story_segments:
            story_counter += 1
            slide_img = draw_story_slide(cinema_name, cinema_name_en, segment)
            slide_img.save(BASE_DIR / f"story_image_{story_counter:02}.png")
            print(f"   Saved Story Slide {story_counter} ({cinema_name})")

    # 10. Caption
    write_caption_for_multiple_cinemas(today_str, all_featured_for_caption)

def write_caption_for_multiple_cinemas(date_str: str, all_featured_cinemas: List[Dict]) -> None:
    header = f"🗓️ 本日の東京ミニシアター上映情報 / Today's Featured Showtimes ({date_str})\n"
    lines = [header]
    for item in all_featured_cinemas:
        cinema_name = item['cinema_name']
        address = CINEMA_ADDRESSES.get(cinema_name, "")
        lines.append(f"\n--- 【{cinema_name}】 ---")
        if address:
            jp_address = address.split("\n")[0]
            lines.append(f"📍 {jp_address}") 
        for listing in item['listings']:
            lines.append(f"• {listing['title']}")
    
    dynamic_hashtag = "IndieCinema"
    if all_featured_cinemas:
         first_cinema_name = all_featured_cinemas[0]['cinema_name']
         dynamic_hashtag = "".join(ch for ch in first_cinema_name if ch.isalnum() or "\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff")

    lines.extend([
        "\n詳細はウェブサイトでご確認いただけます / Full details online:",
        "leonelki.com/cinemas",
        f"\n#東京ミニシアター #映画 #映画館 #上映情報 #tokyo #{dynamic_hashtag}",
        "#tokyocinema #arthousecinema"
    ])
    OUTPUT_CAPTION_PATH.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
