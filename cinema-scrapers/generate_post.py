"""
Generate Instagram-ready image carousel and caption for today's cinema showings.

VERSION 24 (TOTAL STYLE RESET):
- Visual language rebuilt around "Neon Night Atlas" aesthetic.
- Hero: dreamlike aurora gradient, orbital discs, vertical date strap.
- Content slides: split dark layout with cinema info column + luminous listing capsules.
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
# Hero Gradient + accents
HERO_GRADIENT_TOP = (24, 14, 50)
HERO_GRADIENT_BOTTOM = (22, 82, 132)
ACCENT_ELECTRIC = (0, 255, 196)
ACCENT_CORAL = (255, 103, 140)
ACCENT_SUN = (255, 213, 92)

# Content slide palette
CANVAS_NIGHT = (7, 8, 24)
CONTENT_PANEL_DARK = (20, 24, 62)
LISTING_BG = (31, 36, 78)
LISTING_BG_ALT = (44, 48, 98)
TEXT_LIGHT = (236, 241, 255)
TEXT_MUTED = (173, 183, 214)

BLACK = (10, 10, 18)
GRAY = (120, 126, 154)

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

def _lerp_color(color_a: Tuple[int, int, int], color_b: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    return tuple(int(color_a[i] + (color_b[i] - color_a[i]) * t) for i in range(3))


def generate_neon_background(day_number: int) -> Image.Image:
    """Create a dreamlike aurora gradient with floating neon discs."""

    random.seed(day_number)
    base = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), HERO_GRADIENT_BOTTOM)
    draw = ImageDraw.Draw(base)

    for y in range(CANVAS_HEIGHT):
        t = y / max(1, CANVAS_HEIGHT - 1)
        draw.line([(0, y), (CANVAS_WIDTH, y)], fill=_lerp_color(HERO_GRADIENT_TOP, HERO_GRADIENT_BOTTOM, t))

    overlay = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    for _ in range(4):
        radius = random.randint(350, 620)
        cx = random.randint(-200, CANVAS_WIDTH)
        cy = random.randint(-200, CANVAS_HEIGHT)
        color = random.choice([ACCENT_ELECTRIC, ACCENT_CORAL, ACCENT_SUN])
        alpha = random.randint(70, 140)
        overlay_draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=color + (alpha,))

    for idx in range(12):
        y = idx * (CANVAS_HEIGHT // 11)
        offset = random.randint(-120, 120)
        overlay_draw.line([(-200, y + offset), (CANVAS_WIDTH + 200, y + offset + random.randint(-80, 80))], fill=(255, 255, 255, 26), width=3)

    img = Image.alpha_composite(base.convert("RGBA"), overlay)
    img_draw = ImageDraw.Draw(img)
    for _ in range(160):
        x = random.randint(0, CANVAS_WIDTH - 1)
        y = random.randint(0, CANVAS_HEIGHT - 1)
        size = random.randint(1, 2)
        brightness = random.randint(170, 255)
        img_draw.ellipse((x - size, y - size, x + size, y + size), fill=(brightness, brightness, brightness, 200))

    return img.convert("RGB")


def draw_hero_slide(bilingual_date: str) -> Image.Image:
    """Generate the new dreamwave-inspired hero slide."""

    day_number = int(today_in_tokyo().timestamp() // 86400)
    img = generate_neon_background(day_number).convert("RGBA")

    overlay = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)

    try:
        title_font = ImageFont.truetype(str(BOLD_FONT_PATH), 120)
        secondary_font = ImageFont.truetype(str(BOLD_FONT_PATH), 70)
        accent_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 42)
        date_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 34)
    except Exception:
        raise

    # Orbital glow
    orb_radius = 430
    orb_box = (CANVAS_WIDTH // 2 - orb_radius, 140, CANVAS_WIDTH // 2 + orb_radius, 140 + orb_radius * 2)
    draw_ov.ellipse(orb_box, fill=ACCENT_ELECTRIC + (90,))
    inner_box = (CANVAS_WIDTH // 2 - 280, 260, CANVAS_WIDTH // 2 + 280, 900)
    draw_ov.ellipse(inner_box, outline=ACCENT_CORAL + (255,), width=10)

    # Vertical strap for the date
    strap_width = 220
    strap_x0 = CANVAS_WIDTH - strap_width - MARGIN // 2
    strap_y0 = MARGIN
    strap_y1 = CANVAS_HEIGHT - MARGIN
    draw_ov.rectangle((strap_x0, strap_y0, strap_x0 + strap_width, strap_y1), fill=ACCENT_SUN + (230,))

    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    strap_text = bilingual_date.upper()
    draw.text((strap_x0 + strap_width / 2, (strap_y0 + strap_y1) / 2), strap_text, font=date_font, fill=BLACK, anchor="mm", spacing=6)

    title_left = MARGIN + 40
    draw.text((title_left, CANVAS_HEIGHT / 2 - 160), "TOKYO", font=title_font, fill=TEXT_LIGHT, anchor="lm")
    draw.text((title_left, CANVAS_HEIGHT / 2), "MICRO CINEMA", font=title_font, fill=TEXT_LIGHT, anchor="lm")
    draw.text((title_left, CANVAS_HEIGHT / 2 + 150), "本日の上映情報", font=secondary_font, fill=ACCENT_ELECTRIC, anchor="lm")

    body_lines = [
        "Night Atlas for independent houses.",
        "Curated showtimes, bilingual listings.",
    ]
    body_y = CANVAS_HEIGHT / 2 + 240
    for line in body_lines:
        draw.text((title_left, body_y), line, font=accent_font, fill=TEXT_MUTED, anchor="lm")
        body_y += 56

    return img.convert("RGB")

def draw_cinema_slide(cinema_name: str, cinema_name_en: str, listings: List[Dict[str, str | None]]) -> Image.Image:
    """Create the split dark layout for each cinema."""

    img = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), CANVAS_NIGHT)
    draw = ImageDraw.Draw(img)

    try:
        title_jp_font = ImageFont.truetype(str(BOLD_FONT_PATH), 68)
        label_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 30)
        title_en_font = ImageFont.truetype(str(BOLD_FONT_PATH), 34)
        listing_title_font = ImageFont.truetype(str(BOLD_FONT_PATH), 44)
        listing_en_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 30)
        listing_time_font = ImageFont.truetype(str(BOLD_FONT_PATH), 32)
        footer_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 26)
    except Exception:
        raise

    left_column_width = 340
    draw.rectangle((0, 0, left_column_width, CANVAS_HEIGHT), fill=CONTENT_PANEL_DARK)

    left_x = left_column_width // 2
    y_pos = MARGIN
    draw.text((left_x, y_pos), "FEATURED HOUSE", font=label_font, fill=TEXT_MUTED, anchor="ma")
    y_pos += 80
    draw.text((left_x, y_pos), cinema_name, font=title_jp_font, fill=TEXT_LIGHT, anchor="ma", spacing=6)
    y_pos += 120

    cinema_name_to_use = cinema_name_en or CINEMA_ENGLISH_NAMES.get(cinema_name, "")
    if cinema_name_to_use:
        draw.text((left_x, y_pos), cinema_name_to_use, font=title_en_font, fill=ACCENT_ELECTRIC, anchor="ma")
        y_pos += 70

    address = CINEMA_ADDRESSES.get(cinema_name, "")
    if address:
        jp_addr = address.split("\n")[0]
        wrapped_addr = textwrap.wrap(jp_addr, width=9)
        for line in wrapped_addr:
            draw.text((left_x, y_pos), line, font=label_font, fill=TEXT_MUTED, anchor="ma")
            y_pos += 38

    draw.line((left_column_width - 5, MARGIN, left_column_width - 5, CANVAS_HEIGHT - MARGIN), fill=ACCENT_CORAL, width=4)

    right_x = left_column_width + 50
    usable_width = CANVAS_WIDTH - right_x - MARGIN
    y_cursor = MARGIN

    def render_listing_block(listing: Dict[str, str | None], index: int, y_start: float) -> float:
        block_padding = 30
        lines_jp = textwrap.wrap(listing['title'], width=22) or [listing['title']]
        lines_en = textwrap.wrap(listing['en_title'] or "", width=26) if listing['en_title'] else []
        lines_times = textwrap.wrap(listing['times'] or "", width=32) if listing['times'] else []

        line_count = len(lines_jp) + len(lines_en) + (1 if lines_times else 0)
        block_height = block_padding * 2 + line_count * 46

        bg_color = LISTING_BG if index % 2 == 0 else LISTING_BG_ALT
        draw.rounded_rectangle((right_x, y_start, right_x + usable_width, y_start + block_height), radius=38, fill=bg_color)

        text_y = y_start + block_padding
        for line in lines_jp:
            draw.text((right_x + 40, text_y), f"◎ {line}", font=listing_title_font, fill=TEXT_LIGHT)
            text_y += 46

        for line in lines_en:
            draw.text((right_x + 70, text_y), line, font=listing_en_font, fill=TEXT_MUTED)
            text_y += 40

        if lines_times:
            pill_text = " / ".join(lines_times)
            text_bbox = draw.textbbox((0, 0), pill_text, font=listing_time_font)
            pill_width = text_bbox[2] - text_bbox[0] + 40
            pill_height = text_bbox[3] - text_bbox[1] + 18
            pill_x = right_x + usable_width - pill_width - 40
            pill_y = y_start + block_height - pill_height - 20
            draw.rounded_rectangle((pill_x, pill_y, pill_x + pill_width, pill_y + pill_height), radius=pill_height // 2, fill=ACCENT_ELECTRIC)
            draw.text((pill_x + pill_width / 2, pill_y + pill_height / 2), pill_text, font=listing_time_font, fill=BLACK, anchor="mm")

        return block_height + 26

    for idx, listing in enumerate(listings):
        block_height = render_listing_block(listing, idx, y_cursor)
        y_cursor += block_height

    footer_text = "詳細 / Full details: leonelki.com/cinemas"
    draw.text((CANVAS_WIDTH - MARGIN, CANVAS_HEIGHT - MARGIN - 10), footer_text, font=footer_font, fill=TEXT_MUTED, anchor="rd")

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
