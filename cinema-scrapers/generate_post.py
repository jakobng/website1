"""
Generate Instagram-ready image carousel and caption for today's cinema showings.

VERSION 20 (MAXIMALIST TILED GRADIENT):
- Design: Replaces smooth ribbon with a seamless tiled pattern background.
- Logic: Implements true dynamic slide splitting and consistent global slide numbering (1/N, 2/N, ...).
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
import glob
import os # Corrected: Added the missing os import

try:  
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore


BASE_DIR = Path(__file__).resolve().parent
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"
BOLD_FONT_PATH = BASE_DIR / "NotoSansJP-Bold.ttf"
REGULAR_FONT_PATH = BASE_DIR / "NotoSansJP-Regular.ttf"
OUTPUT_CAPTION_PATH = BASE_DIR / "post_caption.txt"

# --- Configuration ---
MINIMUM_FILM_THRESHOLD = 3
MAX_CAROUSEL_SLIDES = 6 # Max is 1 (Hero) + 5 (Cinemas)
MAX_LISTINGS_VERTICAL_SPACE = 900 # Max height for movie listings area in pixels on inner slides

# Layout (4:5 Portrait)
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350
MARGIN = 60 
TITLE_WRAP_WIDTH = 30

# --- THEME COLORS ---
# New Maximalist Hero Colors
GRADIENT_COLOR_1 = (255, 210, 100)  # Deep Yellow
GRADIENT_COLOR_2 = (255, 230, 0)   # Brighter Yellow
SOLID_SLIDE_COLOR = (255, 255, 255) # White for inner slides
BLACK = (20, 20, 20)
GRAY = (80, 80, 80)
LINE_THICKNESS = 40
AMPLITUDE_MIN = 0.2
AMPLITUDE_MAX = 0.8
TILE_SIZE = 120 # Size of the repeating unit

# --- Database (Included for completeness and functionality) ---
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

# --- Utility Functions (Updated) ---

def is_probably_not_japanese(text: str | None) -> bool:
    if not text: return False
    if not re.search(r'[a-zA-Z]', text): return False
    japanese_chars = re.findall(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', text)
    latin_chars = re.findall(r'[a-zA-Z]', text) # <-- FIXED: Corrected regex range from [a-Z] to [a-zA-Z]
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

def choose_multiple_cinemas(showings: List[Dict], max_cinemas: int = MAX_CAROUSEL_SLIDES - 1) -> List[Tuple[str, List[Dict]]]:
    """
    Selects the top N cinemas based on the number of unique films showing.
    
    Returns: List[(cinema_name: str, showings: List[Dict])]
    """
    grouped: Dict[str, List[Dict]] = defaultdict(list)
    for show in showings:
        cinema_name = show.get("cinema_name")
        if cinema_name: 
            grouped[cinema_name].append(show)

    if not grouped:
        return []

    candidates = []
    for cinema_name, cinema_showings in grouped.items():
        unique_titles = set(s.get('movie_title') for s in cinema_showings)
        if len(unique_titles) >= MINIMUM_FILM_THRESHOLD:
            candidates.append((cinema_name, len(unique_titles), cinema_showings))

    candidates.sort(key=lambda x: (-x[1], x[0]))
    
    selected_cinemas = []
    print(f"Candidate Pool ({len(candidates)}): {[c[0] for c in candidates]}")
    
    for i in range(min(max_cinemas, len(candidates))):
        name, _, showings_list = candidates[i]
        selected_cinemas.append((name, showings_list))
        print(f"Selected Cinema #{i+1}: {name}")

    return selected_cinemas

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

def get_ribbon_y_at_day_boundary(day_number: int) -> float:
    """
    Returns a deterministic Y-coordinate (normalized 0.0 to 1.0)
    for the ribbon cut-off point, ensuring grid continuity.
    """
    r = random.Random(day_number)
    return r.uniform(AMPLITUDE_MIN, AMPLITUDE_MAX)

def generate_tiled_background(day_number: int) -> Image.Image:
    """Generates the main background image with the repeating geometric tile pattern and ribbon boundary."""
    
    # 1. Create a 3x3 repeating pattern tile
    tile_img = Image.new("RGB", (TILE_SIZE, TILE_SIZE), GRADIENT_COLOR_1)
    tile_draw = ImageDraw.Draw(tile_img)

    # Use a fixed, complex pattern for a maximalist look (e.g., overlapping circles/lines)
    random.seed(day_number)
    
    # Draw dark geometric shapes
    tile_draw.ellipse([20, 20, TILE_SIZE - 20, TILE_SIZE - 20], fill=GRADIENT_COLOR_2, outline=BLACK, width=2)
    # Ensure lines are drawn using the entire TILE_SIZE
    tile_draw.line([0, 0, TILE_SIZE, TILE_SIZE], fill=BLACK, width=4)
    tile_draw.line([TILE_SIZE, 0, 0, TILE_SIZE], fill=BLACK, width=4)
    
    # 2. Tile the image onto the canvas size
    background = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT))
    for x in range(0, CANVAS_WIDTH, TILE_SIZE):
        for y in range(0, CANVAS_HEIGHT, TILE_SIZE):
            background.paste(tile_img, (x, y))

    # 3. Draw the continuous white ribbon boundary over the tiled background
    draw = ImageDraw.Draw(background)
    
    day_number = int(today_in_tokyo().timestamp() // 86400)
    
    y_left_norm = get_ribbon_y_at_day_boundary(day_number + 1)
    y_right_norm = get_ribbon_y_at_day_boundary(day_number)
    
    y_left = int(y_left_norm * CANVAS_HEIGHT)
    y_right = int(y_right_norm * CANVAS_HEIGHT)
    
    points = []
    steps = 100
    for i in range(steps + 1):
        t = i / steps
        smooth_t = (3 * t**2) - (2 * t**3)
        x = int(t * CANVAS_WIDTH)
        y = int(y_left * (1 - smooth_t) + y_right * smooth_t)
        points.append((x, y))
    
    # Draw the ribbon in solid white over the tile
    draw.line(points, fill=(255, 255, 255), width=LINE_THICKNESS) 
        
    return background

def draw_hero_slide(bilingual_date: str) -> Image.Image:
    """Generates the main title slide (post_image_00.png)."""
    day_number = int(today_in_tokyo().timestamp() // 86400)
    img = generate_tiled_background(day_number).convert("RGBA")

    overlay = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0,0,0,0))
    draw_ov = ImageDraw.Draw(overlay)
    
    # --- Load Fonts ---
    try:
        main_title_font = ImageFont.truetype(str(BOLD_FONT_PATH), 85)
        date_font = ImageFont.truetype(str(BOLD_FONT_PATH), 50)
        small_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 35)
        footer_font_small = ImageFont.truetype(str(REGULAR_FONT_PATH), 34)
    except Exception:
        raise

    # Use a large, clean white box in the center for contrast
    box_w = 980
    box_h = 450
    box_x = (CANVAS_WIDTH - box_w) // 2
    box_y = (CANVAS_HEIGHT - box_h) // 2
    
    draw_ov.rectangle([box_x, box_y, box_x + box_w, box_y + box_h], fill=(255, 255, 255, 255))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # --- Text on Hero Slide ---
    text_center_x = CANVAS_WIDTH // 2
    
    draw.text((text_center_x, box_y + 60), "東京ミニシアター", font=main_title_font, fill=BLACK, anchor="mm")
    draw.text((text_center_x, box_y + 160), "Tokyo Indie Cinema", font=date_font, fill=GRAY, anchor="mm")
    
    draw.text((text_center_x, box_y + 270), "本日の上映情報 Pick Up", font=date_font, fill=BLACK, anchor="mm")
    draw.text((text_center_x, box_y + 350), bilingual_date, font=small_font, fill=GRAY, anchor="mm")

    # Footer
    draw.text((text_center_x, CANVAS_HEIGHT - MARGIN - 30), "→ SWIPE FOR TODAY'S BEST PICKS →", font=footer_font_small, fill=BLACK, anchor="mm")

    return img.convert("RGB")

def draw_cinema_slide(cinema_name: str, cinema_name_en: str, listings: List[Dict[str, str | None]], slide_page_text: str) -> Image.Image:
    """Generates a single solid-white slide for a specific segment of a cinema's listings."""
    
    img = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), SOLID_SLIDE_COLOR)
    draw = ImageDraw.Draw(img)

    try:
        title_jp_font = ImageFont.truetype(str(BOLD_FONT_PATH), 50)
        title_en_font = ImageFont.truetype(str(BOLD_FONT_PATH), 30)
        regular_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 34)
        en_movie_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 28)
        small_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 28)
        page_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 24)
        footer_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 24)
    except Exception:
        raise

    content_left = MARGIN + 20
    y_pos = MARGIN + 20 
    
    # --- Paging Indicator ---
    draw.text((CANVAS_WIDTH - MARGIN - 20, MARGIN + 10), slide_page_text, font=page_font, fill=GRAY, anchor="ra")
    
    # --- Cinema Name & Address ---
    draw.text((content_left, y_pos), cinema_name, font=title_jp_font, fill=BLACK)
    y_pos += 60
    
    cinema_name_to_use = cinema_name_en or CINEMA_ENGLISH_NAMES.get(cinema_name, "")
    
    if cinema_name_to_use:
        draw.text((content_left, y_pos), cinema_name_to_use, font=title_en_font, fill=GRAY)
        y_pos += 45
    else:
        y_pos += 10
        
    address = CINEMA_ADDRESSES.get(cinema_name, "")
    address_lines = address.split("\n")
    if address_lines:
        draw.text((content_left, y_pos), address_lines[0], font=small_font, fill=GRAY)
        y_pos += 32
        if len(address_lines) > 1:
            draw.text((content_left, y_pos), address_lines[1], font=small_font, fill=GRAY)
            y_pos += 32
    y_pos += 30

    # --- Listings ---
    
    for listing in listings:
        # Draw Movie Title
        wrapped_title = textwrap.wrap(f"■ {listing['title']}", width=TITLE_WRAP_WIDTH) or [f"■ {listing['title']}"]
        for line in wrapped_title:
            draw.text((content_left, y_pos), line, font=regular_font, fill=BLACK)
            y_pos += 40
        
        # Draw English Title (smaller, indented)
        if listing["en_title"]:
            wrapped_en = textwrap.wrap(f"({listing['en_title']})", width=35)
            for line in wrapped_en:
                draw.text((content_left + 10, y_pos), line, font=en_movie_font, fill=GRAY)
                y_pos += 30
        
        # Draw Showtimes (indented)
        if listing['times']:
            draw.text((content_left + 40, y_pos), listing["times"], font=regular_font, fill=GRAY)
            y_pos += 55
    
    # Footer
    footer_text_final = "詳細は web / Details online: leonelki.com/cinemas"
    draw.text((content_left, CANVAS_HEIGHT - MARGIN - 20), footer_text_final, font=footer_font, fill=GRAY)

    return img.convert("RGB")

def segment_listings(listings: List[Dict[str, str | None]], cinema_name: str) -> List[List[Dict]]:
    """
    Segments a full list of movie listings into multiple lists (one for each slide).
    Ensures no single listing is split across slides.
    """
    
    SEGMENTED_LISTS = []
    current_segment = []
    current_height = 0
    
    MAX_LISTINGS_HEIGHT = MAX_LISTINGS_VERTICAL_SPACE 
    
    # Estimated height constants (Calibrated to match draw_cinema_slide output)
    JP_LINE_HEIGHT = 40
    EN_LINE_HEIGHT = 30
    TIMES_LINE_HEIGHT = 38
    
    for listing in listings:
        # Calculate height required for this specific listing
        required_height = JP_LINE_HEIGHT + TIMES_LINE_HEIGHT
        if listing.get('en_title'):
             required_height += EN_LINE_HEIGHT
        
        if current_height + required_height > MAX_LISTINGS_HEIGHT:
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

    if len(SEGMENTED_LISTS) > 1:
        print(f"   Note: {cinema_name} listings split into {len(SEGMENTED_LISTS)} slide(s).")
        
    return SEGMENTED_LISTS


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
            title = listing['title']
            times = listing['times']
            lines.append(f"• {title}: {times}")
        
    if all_featured_cinemas:
        first_cinema_name = all_featured_cinemas[0]['cinema_name']
        dynamic_hashtag = "".join(ch for ch in first_cinema_name if ch.isalnum() or "\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff")
    else:
        dynamic_hashtag = "IndieCinema"

    lines.extend([
        "\n詳細はウェブサイトでご確認いただけます / Full details online:",
        "leonelki.com/cinemas",
        f"\n#東京ミニシアター #映画 #映画館 #上映情報 #{dynamic_hashtag}",
        "#tokyocinema #arthousecinema"
    ])
    OUTPUT_CAPTION_PATH.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> None:
    today = today_in_tokyo().date()
    today_str = today.isoformat()
    
    date_jp = today.strftime("%Y年%m月%d日")
    date_en = today.strftime("%b %d, %Y")
    bilingual_date_str = f"{date_jp} / {date_en}"

    todays_showings = load_showtimes(today_str)
    if not todays_showings:
        print(f"No showings for today ({today_str}). Exiting.")
        return

    # --- 1. Select Multiple Cinemas ---
    selected_cinemas = choose_multiple_cinemas(todays_showings, max_cinemas=MAX_CAROUSEL_SLIDES - 1) 
    
    if not selected_cinemas:
        print("No cinemas with sufficient unique listings found today. Exiting.")
        return

    # --- 2. Generate Slides ---
    
    # Clean up previous runs
    for old_file in glob.glob(str(BASE_DIR / "post_image_*.png")):
        os.remove(old_file)
        
    # 0. Hero/Title Slide
    hero_slide = draw_hero_slide(bilingual_date_str)
    hero_slide.save(BASE_DIR / f"post_image_00.png")
    print(f"Saved hero slide to post_image_00.png")
    
    all_featured_cinemas = []
    
    # Calculate the total number of segments across all selected cinemas
    segments_by_cinema = []
    total_segments = 0

    for cinema_name, cinema_showings in selected_cinemas:
        listings = format_listings(cinema_showings)
        segmented = segment_listings(listings, cinema_name)
        segments_by_cinema.append({"name": cinema_name, "segments": segmented, "full_listings": listings})
        total_segments += len(segmented)
        
    total_slides = total_segments + 1 # Hero slide + all content slides
    slide_counter = 0

    # Iterate through the pre-segmented lists and generate slides
    for item in segments_by_cinema:
        cinema_name = item['name']
        all_featured_cinemas.append({"cinema_name": cinema_name, "listings": item['full_listings']})
        
        for segment_index, segment in enumerate(item['segments']):
            slide_counter += 1
            
            cinema_name_en = CINEMA_ENGLISH_NAMES.get(cinema_name, "")
            
            # Global Slide numbering (1/N, 2/N, ...)
            slide_page_text = f"Slide {slide_counter}/{total_slides}" 
            
            slide_img = draw_cinema_slide(
                cinema_name=cinema_name,
                cinema_name_en=cinema_name_en,
                listings=segment,
                slide_page_text=slide_page_text
            )
            
            # Save slide with two-digit number suffix (01, 02, 03, etc.)
            slide_path = BASE_DIR / f"post_image_{slide_counter:02}.png"
            slide_img.save(slide_path)
            print(f"Saved slide to {slide_path}")
            
    # --- 3. Generate Caption for All Cinemas ---
    write_caption_for_multiple_cinemas(today_str, all_featured_cinemas)
    
    print(f"Generated {slide_counter + 1} total slides and caption.")

if __name__ == "__main__":
    main()
