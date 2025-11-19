"""
Generate Instagram-ready image carousel and caption for today's cinema showings.

VERSION 23 (BUG FIX & FINAL POLISH):
- Fixed: TypeError regarding 'slide_page_text'.
- Design: Maximalist Tiled Hero Slide + Cream-colored Content Slides.
- Logic: Dynamic splitting, smart limits (max 10 slides), no slide numbering.
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
import os

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
INSTAGRAM_SLIDE_LIMIT = 10 # Hard limit by Instagram
MAX_LISTINGS_VERTICAL_SPACE = 840 # Height for movie listings

# Layout (4:5 Portrait)
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350
MARGIN = 60 
TITLE_WRAP_WIDTH = 30

# --- THEME COLORS ---
# Hero Gradient Colors
GRADIENT_COLOR_1 = (255, 195, 11)  # Deep Yellow
GRADIENT_COLOR_2 = (255, 230, 80)  # Lighter/Brighter Yellow for contrast
# Content Slide Background (Subtle Cream)
CONTENT_BG_COLOR = (253, 251, 247) 
BLACK = (20, 20, 20)
GRAY = (80, 80, 80)

# Tiling Settings
TILE_SIZE = 150 # Size of the repeating geometric pattern

# --- Database ---
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

def segment_listings(listings: List[Dict[str, str | None]], cinema_name: str) -> List[List[Dict]]:
    """
    Segments a full list of movie listings into multiple lists (one for each slide).
    Uses conservative height check to prevent crowding.
    """
    SEGMENTED_LISTS = []
    current_segment = []
    current_height = 0
    MAX_LISTINGS_HEIGHT = MAX_LISTINGS_VERTICAL_SPACE 
    
    # Estimated height constants 
    JP_LINE_HEIGHT = 40
    EN_LINE_HEIGHT = 30
    TIMES_LINE_HEIGHT = 55 
    
    for listing in listings:
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

    return SEGMENTED_LISTS

# --- MAXIMALIST HERO DESIGN ---

def generate_maximalist_background(day_number: int) -> Image.Image:
    """Generates a maximalist tiled background pattern."""
    
    # 1. Create a repeating pattern tile (Geometric Cross/Circle)
    tile_img = Image.new("RGB", (TILE_SIZE, TILE_SIZE), GRADIENT_COLOR_1)
    tile_draw = ImageDraw.Draw(tile_img)

    random.seed(day_number) # Consistent daily pattern
    
    # Draw geometric shapes (Black bold lines)
    padding = 10
    tile_draw.rectangle([padding, padding, TILE_SIZE-padding, TILE_SIZE-padding], outline=BLACK, width=4)
    tile_draw.line([0, 0, TILE_SIZE, TILE_SIZE], fill=BLACK, width=3)
    tile_draw.line([TILE_SIZE, 0, 0, TILE_SIZE], fill=BLACK, width=3)
    
    # 2. Tile the image onto the canvas size
    background = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT))
    for x in range(0, CANVAS_WIDTH, TILE_SIZE):
        for y in range(0, CANVAS_HEIGHT, TILE_SIZE):
            background.paste(tile_img, (x, y))

    # 3. Apply a heavy gradient overlay to unify the busy pattern
    overlay = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0,0,0,0))
    draw_ov = ImageDraw.Draw(overlay)
    for y in range(CANVAS_HEIGHT):
        # Gradient alpha: Top (Transparent) -> Bottom (More opaque yellow)
        alpha = int(100 + 100 * (y / CANVAS_HEIGHT))
        draw_ov.line([(0, y), (CANVAS_WIDTH, y)], fill=(GRADIENT_COLOR_2[0], GRADIENT_COLOR_2[1], GRADIENT_COLOR_2[2], alpha))
    
    background = background.convert("RGBA")
    background = Image.alpha_composite(background, overlay)
    return background.convert("RGB")

def draw_hero_slide(bilingual_date: str) -> Image.Image:
    """Generates the main title slide."""
    day_number = int(today_in_tokyo().timestamp() // 86400)
    img = generate_maximalist_background(day_number).convert("RGBA")

    overlay = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0,0,0,0))
    draw_ov = ImageDraw.Draw(overlay)
    
    # Fonts
    try:
        title_font = ImageFont.truetype(str(BOLD_FONT_PATH), 110)
        subtitle_font = ImageFont.truetype(str(BOLD_FONT_PATH), 55)
        date_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 40)
    except Exception:
        raise

    # Large White Card in Center
    box_w = 900
    box_h = 600
    box_x = (CANVAS_WIDTH - box_w) // 2
    box_y = (CANVAS_HEIGHT - box_h) // 2
    
    # Deep Black Shadow for the box
    shadow_offset = 20
    draw_ov.rectangle([box_x + shadow_offset, box_y + shadow_offset, box_x + box_w + shadow_offset, box_y + box_h + shadow_offset], fill=BLACK)
    draw_ov.rectangle([box_x, box_y, box_x + box_w, box_y + box_h], fill=(255, 255, 255, 255))
    
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # --- Text ---
    text_center_x = CANVAS_WIDTH // 2
    center_y = box_y + (box_h // 2)
    
    draw.text((text_center_x, center_y - 120), "TOKYO", font=title_font, fill=BLACK, anchor="mm")
    draw.text((text_center_x, center_y), "INDIE CINEMA", font=title_font, fill=BLACK, anchor="mm")
    
    draw.text((text_center_x, center_y + 120), "本日の上映情報", font=subtitle_font, fill=GRAY, anchor="mm")
    draw.text((text_center_x, center_y + 200), bilingual_date, font=date_font, fill=GRAY, anchor="mm")

    return img.convert("RGB")

def draw_cinema_slide(cinema_name: str, cinema_name_en: str, listings: List[Dict[str, str | None]]) -> Image.Image:
    """Generates a content slide with cream background and clean layout."""
    
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
    
    # --- Cinema Name Header ---
    draw.text((content_left, y_pos), cinema_name, font=title_jp_font, fill=BLACK)
    y_pos += 70
    
    cinema_name_to_use = cinema_name_en or CINEMA_ENGLISH_NAMES.get(cinema_name, "")
    if cinema_name_to_use:
        draw.text((content_left, y_pos), cinema_name_to_use, font=title_en_font, fill=GRAY)
        y_pos += 50
    else:
        y_pos += 20
        
    # Address Line
    address = CINEMA_ADDRESSES.get(cinema_name, "")
    if address:
        jp_addr = address.split("\n")[0]
        draw.text((content_left, y_pos), f"📍 {jp_addr}", font=small_font, fill=GRAY)
        y_pos += 60
    else:
        y_pos += 30

    # --- Listings ---
    # Draw a divider line
    draw.line([(MARGIN, y_pos), (CANVAS_WIDTH - MARGIN, y_pos)], fill=BLACK, width=2)
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
    
    # Footer
    footer_text_final = "詳細は web / Details online: leonelki.com/cinemas"
    draw.text((CANVAS_WIDTH // 2, CANVAS_HEIGHT - MARGIN - 20), footer_text_final, font=footer_font, fill=GRAY, anchor="mm")

    return img.convert("RGB")

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

    # --- 1. Select & Segment Candidates ---
    # First, group all valid cinemas and calculate their required slides
    grouped: Dict[str, List[Dict]] = defaultdict(list)
    for show in todays_showings:
        if show.get("cinema_name"):
            grouped[show.get("cinema_name")].append(show)

    candidates = []
    for cinema_name, showings in grouped.items():
        unique_titles = set(s.get('movie_title') for s in showings)
        if len(unique_titles) >= MINIMUM_FILM_THRESHOLD:
            # Pre-calculate segments to know size
            listings = format_listings(showings)
            segments = segment_listings(listings, cinema_name)
            candidates.append({
                "name": cinema_name,
                "listings": listings,
                "segments": segments,
                "unique_count": len(unique_titles)
            })

    # Sort by popularity (number of films)
    candidates.sort(key=lambda x: (-x['unique_count'], x['name']))
    
    # --- 2. Fill Carousel up to Limit ---
    # We have 1 Hero Slide, so we can add up to 9 Content Slides (Total 10)
    MAX_CONTENT_SLIDES = INSTAGRAM_SLIDE_LIMIT - 1 
    
    final_selection = []
    current_slide_count = 0
    
    for cand in candidates:
        needed = len(cand['segments'])
        if current_slide_count + needed <= MAX_CONTENT_SLIDES:
            final_selection.append(cand)
            current_slide_count += needed
            print(f"Selected {cand['name']} ({needed} slides)")
        else:
            print(f"Skipping {cand['name']} (needs {needed} slides, only {MAX_CONTENT_SLIDES - current_slide_count} left)")
            
    if not final_selection:
        print("No cinemas selected. Exiting.")
        return

    # --- 3. Generate Images ---
    
    # Clean up
    for old_file in glob.glob(str(BASE_DIR / "post_image_*.png")):
        os.remove(old_file) 
        
    # 0. Hero Slide
    hero_slide = draw_hero_slide(bilingual_date_str)
    hero_slide.save(BASE_DIR / f"post_image_00.png")
    print(f"Saved hero slide to post_image_00.png")

    # Content Slides
    slide_counter = 0
    all_featured_cinemas = []
    
    for item in final_selection:
        cinema_name = item['name']
        all_featured_cinemas.append({"cinema_name": cinema_name, "listings": item['listings']})
        
        for i, segment in enumerate(item['segments']):
            slide_counter += 1
            cinema_name_en = CINEMA_ENGLISH_NAMES.get(cinema_name, "")
            
            # CORRECTED: Removed the 'slide_page_text' argument from the call
            slide_img = draw_cinema_slide(
                cinema_name=cinema_name,
                cinema_name_en=cinema_name_en,
                listings=segment
            )
            
            slide_path = BASE_DIR / f"post_image_{slide_counter:02}.png"
            slide_img.save(slide_path)
            print(f"Saved slide to {slide_path}")
            
    # --- 4. Caption ---
    write_caption_for_multiple_cinemas(today_str, all_featured_cinemas)
    print(f"Generated {slide_counter + 1} total slides.")

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
            # Simplified caption to avoid length limits
    
    dynamic_hashtag = "IndieCinema"
    if all_featured_cinemas:
         first_cinema_name = all_featured_cinemas[0]['cinema_name']
         dynamic_hashtag = "".join(ch for ch in first_cinema_name if ch.isalnum() or "\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff")

    lines.extend([
        "\n詳細はウェブサイトでご確認いただけます / Full details online:",
        "leonelki.com/cinemas",
        f"\n#東京ミニシアター #映画 #映画館 #上映情報 #{dynamic_hashtag}",
        "#tokyocinema #arthousecinema"
    ])
    OUTPUT_CAPTION_PATH.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
