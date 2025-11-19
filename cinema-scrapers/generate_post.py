"""
Generate Instagram-ready image carousel and caption for today's cinema showings.

VERSION 19 (THE WIDE RIBBON):
- Design: A continuous White Line flowing across a Deep Yellow background (Hero Slide). 
- Carousel Logic: The post features a Title Slide followed by a dedicated slide for 
  each of the top N cinemas showing films today.
- Grid Logic: The ribbon's exit point (Right) on yesterday's post should match 
  the entry point (Left) of today's Title Slide.
- Layout: 4:5 Portrait (1080x1350) per slide with grid-safe text.
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
OUTPUT_IMAGE_PATH = BASE_DIR / "post_image.png" # This is a placeholder now, slides are numbered
OUTPUT_CAPTION_PATH = BASE_DIR / "post_caption.txt"

# --- Configuration ---
MINIMUM_FILM_THRESHOLD = 3
MAX_CAROUSEL_SLIDES = 5

# Layout (4:5 Portrait)
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350

# "Safe Zone" Logic (Center 1080x1080 square)
GRID_CROP_HEIGHT = (CANVAS_HEIGHT - CANVAS_WIDTH) // 2 
MARGIN = 60 
TEXT_BOX_MARGIN = 40
TITLE_WRAP_WIDTH = 30

# --- THEME COLORS ---
BG_COLOR = (255, 195, 11)       # Deep Yellow
LINE_COLOR = (255, 255, 255)    # White Ribbon
TEXT_BG_COLOR = (255, 255, 255, 230) 
SOLID_SLIDE_COLOR = (255, 255, 255) # White for inner slides
BLACK = (20, 20, 20)
GRAY = (80, 80, 80)

# Ribbon Settings
LINE_THICKNESS = 40  # Bold line
AMPLITUDE_MIN = 0.2  # Min height (20% from top)
AMPLITUDE_MAX = 0.8  # Max height (80% from top)

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
    jp_title = (showing.get('movie_title') or '').lower()
    
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
        # Return empty list instead of raising to allow graceful failure
        return []
    except json.JSONDecodeError as exc:
        print("Unable to decode showtimes.json")
        raise exc
    todays_showings = [show for show in all_showings if show.get("date_text") == today_str]
    return todays_showings

# --- MODIFIED SELECTION LOGIC FOR CAROUSEL ---
def choose_multiple_cinemas(showings: List[Dict], max_cinemas: int = MAX_CAROUSEL_SLIDES) -> List[Tuple[str, List[Dict]]]:
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
        # Filter: Only include cinemas meeting the minimum threshold
        if len(unique_titles) >= MINIMUM_FILM_THRESHOLD:
            candidates.append((cinema_name, len(unique_titles), cinema_showings))

    # Sort by the number of unique titles (descending) and then by name (ascending)
    candidates.sort(key=lambda x: (-x[1], x[0]))
    
    selected_cinemas = []
    print(f"Candidate Pool ({len(candidates)}): {[c[0] for c in candidates]}")
    
    # Select the top N
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

# --- IMAGE GENERATION FUNCTIONS FOR CAROUSEL SLIDES ---

def get_ribbon_y_at_day_boundary(day_number: int) -> float:
    """
    Returns a deterministic Y-coordinate (normalized 0.0 to 1.0)
    for the boundary between two days.
    Seed ensures Right(N) == Left(N-1).
    """
    r = random.Random(day_number)
    # Keep it somewhat centered so it doesn't go off screen
    return r.uniform(AMPLITUDE_MIN, AMPLITUDE_MAX)

def generate_ribbon_background(seed_day: int) -> Image.Image:
    """Generates the flowing ribbon background."""
    img = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    
    # Left Height (Start of Today) -> Connects to Tomorrow (N+1)
    y_left_norm = get_ribbon_y_at_day_boundary(seed_day + 1)
    
    # Right Height (End of Today) -> Connects to Yesterday (N)
    y_right_norm = get_ribbon_y_at_day_boundary(seed_day)
    
    y_left = int(y_left_norm * CANVAS_HEIGHT)
    y_right = int(y_right_norm * CANVAS_HEIGHT)
    
    # Draw smoothed curve (using fixed points for simplicity in image generation)
    points = []
    steps = 100
    for i in range(steps + 1):
        t = i / steps # 0.0 to 1.0
        
        # 3t^2 - 2t^3 is a standard smoothstep function
        smooth_t = (3 * t**2) - (2 * t**3)
        
        x = int(t * CANVAS_WIDTH)
        y = int(y_left * (1 - smooth_t) + y_right * smooth_t)
        points.append((x, y))
    
    draw.line(points, fill=LINE_COLOR, width=LINE_THICKNESS)
    return img

def draw_hero_slide(bilingual_date: str) -> Image.Image:
    """Generates the main title slide with the Yellow Ribbon aesthetic."""
    day_number = int(datetime.now().timestamp() // 86400)
    try:
        img = generate_ribbon_background(day_number).convert("RGBA")
    except Exception as e:
        print(f"Error generating background: {e}")
        img = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), BG_COLOR)

    overlay = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0,0,0,0))
    draw_ov = ImageDraw.Draw(overlay)
    
    # Use a transparent box for contrast in the center
    box_w = 900
    box_h = 400
    box_x = (CANVAS_WIDTH - box_w) // 2
    box_y = (CANVAS_HEIGHT - box_h) // 2
    # Slight shadow/transparency to let ribbon show
    draw_ov.rectangle([box_x, box_y, box_x + box_w, box_y + box_h], fill=(255, 255, 255, 200))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # --- Load Fonts ---
    try:
        main_title_font = ImageFont.truetype(str(BOLD_FONT_PATH), 80)
        date_font = ImageFont.truetype(str(BOLD_FONT_PATH), 45)
        small_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 30)
    except Exception:
        raise

    # --- Text on Hero Slide ---
    
    # Title
    title_text = "東京ミニシアター"
    draw.text((CANVAS_WIDTH // 2, box_y + 50), title_text, font=main_title_font, fill=BLACK, anchor="mm")
    title_text_en = "Tokyo Indie Cinema"
    draw.text((CANVAS_WIDTH // 2, box_y + 140), title_text_en, font=date_font, fill=GRAY, anchor="mm")
    
    # Subtitle
    subtitle = "本日の上映情報 Pick Up"
    draw.text((CANVAS_WIDTH // 2, box_y + 240), subtitle, font=date_font, fill=BLACK, anchor="mm")
    
    # Date
    draw.text((CANVAS_WIDTH // 2, box_y + 320), bilingual_date, font=small_font, fill=GRAY, anchor="mm")
    
    # Footer
    footer_text = "→ SWIPE FOR TODAY'S BEST PICKS →"
    footer_font_small = ImageFont.truetype(str(REGULAR_FONT_PATH), 30)
    draw.text((CANVAS_WIDTH // 2, CANVAS_HEIGHT - MARGIN - 20), footer_text, font=footer_font_small, fill=BLACK, anchor="mm")


    return img.convert("RGB") # Convert to RGB for saving PNG without alpha layer for simpler IG upload

def draw_cinema_slide(slide_index: int, total_slides: int, cinema_name: str, cinema_name_en: str, listings: List[Dict[str, str | None]]) -> Image.Image:
    """Generates a single solid-white slide for a specific cinema's listings."""
    
    img = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), SOLID_SLIDE_COLOR)
    draw = ImageDraw.Draw(img)

    # Fonts
    try:
        title_jp_font = ImageFont.truetype(str(BOLD_FONT_PATH), 50)
        title_en_font = ImageFont.truetype(str(BOLD_FONT_PATH), 30)
        regular_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 34)
        en_movie_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 28)
        small_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 28)
        page_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 24)
    except Exception:
        raise

    # Text Content Area
    content_left = MARGIN + 20
    y_pos = MARGIN + 20 
    
    # --- Paging Indicator ---
    page_text = f"Slide {slide_index}/{total_slides}"
    draw.text((CANVAS_WIDTH - MARGIN - 20, MARGIN + 10), page_text, font=page_font, fill=GRAY, anchor="ra")
    
    # --- Cinema Name & Address ---
    draw.text((content_left, y_pos), cinema_name, font=title_jp_font, fill=BLACK)
    y_pos += 60
    
    cinema_name_to_use = cinema_name_en or cinema_name
    
    if cinema_name_en:
        draw.text((content_left, y_pos), cinema_name_en, font=title_en_font, fill=GRAY)
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
    max_text_y = CANVAS_HEIGHT - MARGIN - 40 # Stop well before the bottom
    
    for listing in listings:
        if y_pos > max_text_y:
            draw.text((content_left, y_pos), "...", font=regular_font, fill=BLACK)
            break

        # Draw Movie Title
        wrapped_title = textwrap.wrap(f"■ {listing['title']}", width=TITLE_WRAP_WIDTH) or [f"■ {listing['title']}"]
        for line in wrapped_title:
            if y_pos > max_text_y: break
            draw.text((content_left, y_pos), line, font=regular_font, fill=BLACK)
            y_pos += 40
        
        # Draw English Title (smaller, indented)
        if listing["en_title"]:
            if y_pos > max_text_y: break
            wrapped_en = textwrap.wrap(f"({listing['en_title']})", width=35)
            for line in wrapped_en:
                if y_pos > max_text_y: break
                draw.text((content_left + 10, y_pos), line, font=en_movie_font, fill=GRAY)
                y_pos += 30
        
        # Draw Showtimes (indented)
        if listing['times']:
            if y_pos > max_text_y: break
            draw.text((content_left + 40, y_pos), listing["times"], font=regular_font, fill=GRAY)
            y_pos += 50
    
    # Footer
    footer_text = "詳細は web / Details online: leonelki.com/cinemas"
    draw.text((content_left, CANVAS_HEIGHT - MARGIN - 20), footer_text, font=page_font, fill=GRAY)

    return img.convert("RGB")


def write_caption_for_multiple_cinemas(date_str: str, featured_cinemas: List[Dict]) -> None:
    header = f"🗓️ 本日の東京ミニシアター上映情報 / Today's Featured Showtimes ({date_str})\n"
    lines = [header]

    for item in featured_cinemas:
        cinema_name = item['cinema_name']
        address = CINEMA_ADDRESSES.get(cinema_name, "")
        
        lines.append(f"\n--- 【{cinema_name}】 ---")
        if address:
            # Use only the Japanese address part for conciseness in the caption body
            jp_address = address.split(chr(10))[0]
            lines.append(f"📍 {jp_address}") 
        
        # Group listings for the caption
        for listing in item['listings']:
            title = listing['title']
            times = listing['times']
            lines.append(f"• {title}")
            # lines.append(f"  {times}") # Keep times concise/grouped
        
    lines.extend([
        "\n詳細はウェブサイトでご確認いただけます / Full details online!",
        "leonelki.com/cinemas",
        "\n#東京ミニシアター #映画 #映画館 #上映情報 #tokyocinema #arthousecinema"
    ])
    OUTPUT_CAPTION_PATH.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> None:
    today = today_in_tokyo().date()
    today_str = today.isoformat()
    
    # --- LIVE MODE DATE FORMATTING ---
    date_jp = today.strftime("%Y年%m月%d日")
    date_en = today.strftime("%b %d, %Y")
    bilingual_date_str = f"{date_jp} / {date_en}"

    todays_showings = load_showtimes(today_str)
    if not todays_showings:
        print(f"No showings for today ({today_str}). Exiting.")
        return

    # --- STEP 1: Select Multiple Cinemas ---
    selected_cinemas = choose_multiple_cinemas(todays_showings, max_cinemas=MAX_CAROUSEL_SLIDES - 1) # -1 for the hero slide
    
    if not selected_cinemas:
        print("No cinemas with sufficient unique listings found today. Exiting.")
        return

    # --- STEP 2: Generate Slides ---
    
    # 0. Hero/Title Slide
    hero_slide = draw_hero_slide(bilingual_date_str)
    hero_slide.save(BASE_DIR / f"post_image_00.png") # Start with index 00
    print(f"Saved hero slide to post_image_00.png")
    
    # 1. Subsequent Slides: Cinema Listings
    all_listings_for_caption = []
    
    for i, (cinema_name, cinema_showings) in enumerate(selected_cinemas):
        # The index is i+1 because the hero slide is index 0
        slide_index = i + 1
        total_slides = len(selected_cinemas) + 1
        
        listings = format_listings(cinema_showings)
        
        # Collect all data for the final caption
        all_listings_for_caption.append({
            "cinema_name": cinema_name,
            "listings": listings
        })
        
        cinema_name_en = CINEMA_ENGLISH_NAMES.get(cinema_name, "")
        
        slide_img = draw_cinema_slide(
            slide_index=slide_index,
            total_slides=total_slides,
            cinema_name=cinema_name,
            cinema_name_en=cinema_name_en,
            listings=listings
        )
        
        # Save each slide with a two-digit number suffix (01, 02, etc.)
        slide_path = BASE_DIR / f"post_image_{slide_index:02}.png"
        slide_img.save(slide_path)
        print(f"Saved slide to {slide_path}")

    # --- STEP 3: Generate Caption for Multiple Cinemas ---
    write_caption_for_multiple_cinemas(today_str, all_listings_for_caption)
    
    print(f"Generated {len(selected_cinemas) + 1} slides and caption for {len(selected_cinemas)} featured cinemas.")

if __name__ == "__main__":
    main()
