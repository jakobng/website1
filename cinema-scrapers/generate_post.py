"""
Generate Instagram-ready image carousel (V2.2 - "Proportional Story Cover").
- Cover (Feed): 4:5 collage with inpainting.
- Cover (Story): Dedicated 9:16 collage with inpainting for correct proportions.
- Slides: Full-Bleed Cinema Photo + Blur + Light Overlay.
- Text: Minimalist white typography with drop shadows.
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
import difflib
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops, ImageOps

try:  
    from zoneinfo import ZoneInfo
    JST = ZoneInfo("Asia/Tokyo")
except ImportError:
    ZoneInfo = None
    JST = timezone(timedelta(hours=9))

# --- API Setup ---
try:
    import replicate
    REPLICATE_AVAILABLE = True
except ImportError:
    print("⚠️ Replicate library not found. Run: pip install replicate")
    REPLICATE_AVAILABLE = False

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
FONTS_DIR = BASE_DIR / "fonts"
OUTPUT_DIR = BASE_DIR / "ig_posts"

# Ensure output directory exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Path Updates
SHOWTIMES_PATH = DATA_DIR / "showtimes.json"
ASSETS_DIR = BASE_DIR / "cinema_assets" # Assuming this folder is still at root
OUTPUT_CAPTION_PATH = OUTPUT_DIR / "post_caption.txt"

# Font Updates
BOLD_FONT_PATH = FONTS_DIR / "NotoSansJP-Bold.ttf"
REGULAR_FONT_PATH = FONTS_DIR / "NotoSansJP-Regular.ttf"

# Secrets
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")

# --- Constants (PRESERVED) ---
MINIMUM_FILM_THRESHOLD = 3
INSTAGRAM_SLIDE_LIMIT = 10 
MAX_FEED_VERTICAL_SPACE = 750 
MAX_STORY_VERTICAL_SPACE = 1150
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350
STORY_CANVAS_HEIGHT = 1920
MARGIN = 60 
TITLE_WRAP_WIDTH = 30

# --- GLOBAL COLORS ---
WHITE = (255, 255, 255)
OFF_WHITE = (240, 240, 240)
LIGHT_GRAY = (230, 230, 230) 
DARK_SHADOW = (0, 0, 0, 180) # Soft shadow color

# --- Database (Cinemas) ---
CINEMA_ADDRESSES = {
    "Bunkamura ル・シネマ 渋谷宮下": "東京都渋谷区渋谷1-23-16 6F",
    "K's Cinema (ケイズシネマ)": "東京都新宿区新宿3-35-13 3F",
    "シネマート新宿": "東京都新宿区新宿3-13-3 6F",
    "新宿シネマカリテ": "東京都新宿区新宿3-37-12 5F",
    "新宿武蔵野館": "東京都新宿区新宿3-27-10 3F",
    "テアトル新宿": "東京都新宿区新宿3-14-20 7F",
    "早稲田松竹": "東京都新宿区高田馬場1-5-16",
    "YEBISU GARDEN CINEMA": "東京都渋谷区恵比寿4-20-2",
    "シアター・イメージフォーラム": "東京都渋谷区渋谷2-10-2",
    "ユーロスペース": "東京都渋谷区円山町1-5 3F",
    "ヒューマントラストシネマ渋谷": "東京都渋谷区渋谷1-23-16 7F",
    "Stranger (ストレンジャー)": "東京都墨田区菊川3-7-1 1F",
    "新文芸坐": "東京都豊島区東池袋1-43-5 3F",
    "目黒シネマ": "東京都品川区上大崎2-24-15",
    "ポレポレ東中野": "東京都中野区東中野4-4-1 1F",
    "K2 Cinema": "東京都世田谷区北沢2-21-22 2F",
    "ヒューマントラストシネマ有楽町": "東京都千代田区有楽町2-7-1 8F",
    "ラピュタ阿佐ヶ谷": "東京都杉並区阿佐ヶ谷北2-12-21",
    "下高井戸シネマ": "東京都世田谷区松原3-30-15",
    "国立映画アーカイブ": "東京都中央区京橋3-7-6",
    "池袋シネマ・ロサ": "東京都豊島区西池袋1-37-12",
    "シネスイッチ銀座": "東京都中央区銀座4-4-5 3F",
    "シネマブルースタジオ": "東京都足立区千住3-92 2F",
    "CINEMA Chupki TABATA": "東京都北区東田端2-14-4",
    "シネクイント": "東京都渋谷区宇田川町20-11 8F",
    "アップリンク吉祥寺": "東京都武蔵野市吉祥寺本町1-5-1 4F",
    "Tollywood": "東京都世田谷区代沢5-32-5 2F",
    "Morc阿佐ヶ谷": "東京都杉並区阿佐谷北2-12-19 B1F"
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
    "Morc阿佐ヶ谷": "Morc Asagaya",
    "Tollywood": "Tollywood"
}

CINEMA_FILENAME_OVERRIDES = {
    "国立映画アーカイブ": "nfaj",
    "109シネマズプレミアム新宿": "109cinemaspremiumshinjuku",
    "TOHOシネマズ 新宿": "tohoshinjuku",
    "TOHOシネマズ 日比谷": "tohohibiya",
    "新宿ピカデリー": "shinjukupiccadilly"
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

def find_best_english_title(showing: dict) -> str | None:
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
    return None

def today_in_tokyo() -> datetime:
    return datetime.now(JST)

def load_showtimes(today_str: str) -> list[dict]:
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

def format_listings(showings: list[dict]) -> list[dict[str, str | None]]:
    movies: defaultdict[tuple[str, str | None], list[str]] = defaultdict(list)
    title_map: dict[str, str | None] = {}
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

def segment_listings(listings: list[dict[str, str | None]], max_height: int, spacing: dict[str, int]) -> list[list[dict]]:
    SEGMENTED_LISTS = []
    current_segment = []
    current_height = 0
    for listing in listings:
        required_height = spacing['jp_line'] + spacing['time_line']
        if listing.get('en_title'):
             required_height += spacing['en_line']
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

def get_recently_featured(caption_path: Path) -> list[str]:
    if not caption_path.exists(): return []
    try:
        content = caption_path.read_text(encoding="utf-8")
        names = re.findall(r"--- 【(.*?)】 ---", content)
        return names
    except Exception as e:
        print(f"   [WARN] Could not read previous caption: {e}")
        return []

# --- ASSET & REPLICATE LOGIC ---

def normalize_name(s):
    s = str(s).lower()
    return re.sub(r'[^a-z0-9]', '', s)

def get_cinema_image_path(cinema_name: str) -> Path | None:
    if not ASSETS_DIR.exists(): return None
    
    # 1. Try explicit override first
    if cinema_name in CINEMA_FILENAME_OVERRIDES:
        target = CINEMA_FILENAME_OVERRIDES[cinema_name]
    else:
        # 2. Try normalized English Name
        english_name = CINEMA_ENGLISH_NAMES.get(cinema_name, "")
        if english_name:
            target = normalize_name(english_name)
        else:
            target = normalize_name(cinema_name)

    if not target: return None

    candidates = list(ASSETS_DIR.glob("*"))
    best_match = None
    highest_ratio = 0.0
    
    for f in candidates:
        if f.suffix.lower() not in ['.jpg', '.jpeg', '.png']: continue
        f_name = normalize_name(f.stem)
        if f_name in target or target in f_name:
            return f
        ratio = difflib.SequenceMatcher(None, target, f_name).ratio()
        if ratio > highest_ratio:
            highest_ratio = ratio
            best_match = f
            
    if highest_ratio > 0.4:
        return best_match
    return None

def remove_background_replicate(pil_img: Image.Image) -> Image.Image:
    if not REPLICATE_AVAILABLE or not REPLICATE_API_TOKEN: 
        return pil_img.convert("RGBA")
    try:
        temp_in = BASE_DIR / "temp_rembg_in.png"
        pil_img.save(temp_in, format="PNG")
        output = replicate.run(
            "lucataco/remove-bg:95fcc2a26d3899cd6c2691c900465aaeff466285a65c14638cc5f36f34befaf1",
            input={"image": open(temp_in, "rb")}
        )
        if temp_in.exists(): os.remove(temp_in)
        if output:
            resp = requests.get(str(output))
            if resp.status_code == 200:
                img = Image.open(BytesIO(resp.content)).convert("RGBA")
                extrema = img.getextrema()
                if extrema[3][1] == 0: return pil_img.convert("RGBA")
                return img
    except Exception as e:
        print(f"   ⚠️ Rembg failed: {e}. Using original.")
    return pil_img.convert("RGBA")

def create_layout_and_mask(cinemas: list[tuple[str, Path]], target_width: int, target_height: int) -> tuple[Image.Image, Image.Image, Image.Image]:
    """
    Arranges 5 cutouts in a CHAOTIC layout for given dimensions.
    """
    width = target_width
    height = target_height
    
    layout_rgba = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    layout_rgb = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    mask = Image.new("L", (width, height), 255)
    
    imgs_to_process = cinemas[:5]
    if len(imgs_to_process) < 5:
        imgs_to_process = (imgs_to_process * 3)[:5]
        
    random.shuffle(imgs_to_process)
    
    anchors = [
        (int(width * 0.3), int(height * 0.25)),
        (int(width * 0.7), int(height * 0.25)),
        (int(width * 0.5), int(height * 0.50)),
        (int(width * 0.3), int(height * 0.75)),
        (int(width * 0.7), int(height * 0.75)),
    ]
    
    for i, (name, path) in enumerate(imgs_to_process):
        try:
            raw = Image.open(path).convert("RGBA")
            cutout = remove_background_replicate(raw)
            bbox = cutout.getbbox()
            if bbox: cutout = cutout.crop(bbox)
            
            scale_variance = random.uniform(0.7, 1.2)
            max_dim = int(550 * scale_variance)
            cutout.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            
            cx, cy = anchors[i]
            cx += random.randint(-100, 100)
            cy += random.randint(-100, 100)
            
            x = cx - (cutout.width // 2)
            y = cy - (cutout.height // 2)
            
            layout_rgba.paste(cutout, (x, y), mask=cutout)
            layout_rgb.paste(cutout, (x, y), mask=cutout)
            
            alpha = cutout.split()[3]
            mask.paste(0, (x, y), mask=alpha)
            
        except Exception as e:
            print(f"Error processing cutout {name}: {e}")

    mask = mask.filter(ImageFilter.MaxFilter(11)) 
    return layout_rgba, layout_rgb.convert("RGB"), mask

def inpaint_gaps(layout_img: Image.Image, mask_img: Image.Image) -> Image.Image:
    if not REPLICATE_AVAILABLE or not REPLICATE_API_TOKEN:
        print("   ⚠️ Replicate not available. Skipping Inpaint.")
        return layout_img

    print("   🎨 Inpainting gaps (Stability AI)...")
    try:
        temp_img_path = BASE_DIR / "temp_inpaint_img.png"
        temp_mask_path = BASE_DIR / "temp_inpaint_mask.png"
        
        layout_img.save(temp_img_path, format="PNG")
        mask_img.save(temp_mask_path, format="PNG")
        
        output = replicate.run(
            "stability-ai/stable-diffusion-inpainting:c28b92a7ecd66eee4aefcd8a94eb9e7f6c3805d5f06038165407fb5cb355ba67",
            input={
                "image": open(temp_img_path, "rb"),
                "mask": open(temp_mask_path, "rb"),
                "prompt": "surreal architectural mashup, single unified dream structure, seamless wide angle shot, concrete texture, cinematic lighting, neutral tones, 8k",
                "negative_prompt": "grid, split screen, triptych, borders, frames, dividing lines, collage, multiple views, text, watermark",
                "num_inference_steps": 30,
                "guidance_scale": 7.5,
                "strength": 0.85 
            }
        )
        
        if temp_img_path.exists(): os.remove(temp_img_path)
        if temp_mask_path.exists(): os.remove(temp_mask_path)
        
        if output:
            url = output[0] if isinstance(output, list) else output
            resp = requests.get(url)
            if resp.status_code == 200:
                img = Image.open(BytesIO(resp.content)).convert("RGB")
                return img.resize(layout_img.size, Image.Resampling.LANCZOS)
    except Exception as e:
        print(f"   ⚠️ Inpainting failed: {e}. Using raw layout.")
    return layout_img

# --- BACKGROUND GENERATION (BLURRED VIBRANCE) ---

def create_blurred_cinema_bg(cinema_name: str, width: int, height: int) -> Image.Image:
    """
    Creates a 'Vibrant Blur' background.
    """
    full_path = get_cinema_image_path(cinema_name)
    
    # Fallback base
    base = Image.new("RGB", (width, height), (30, 30, 30))
    
    if not full_path or not full_path.exists():
        return base

    try:
        img = Image.open(full_path).convert("RGB")
        
        # Aspect Fill
        target_ratio = width / height
        img_ratio = img.width / img.height
        
        if img_ratio > target_ratio:
            new_width = int(img.height * target_ratio)
            left = (img.width - new_width) // 2
            img = img.crop((left, 0, left + new_width, img.height))
        else:
            new_height = int(img.width / target_ratio)
            top = (img.height - new_height) // 2
            img = img.crop((0, top, img.width, top + new_height))
        
        img = img.resize((width, height), Image.Resampling.LANCZOS)
        
        # Apply Blur
        img = img.filter(ImageFilter.GaussianBlur(8))
        
        # Light Dark Overlay for Contrast (approx 45% black)
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 120))
        img = img.convert("RGBA")
        img = Image.alpha_composite(img, overlay).convert("RGB")
        
        return img

    except Exception as e:
        print(f"Error creating background for {cinema_name}: {e}")
        return base

def draw_text_with_shadow(draw, xy, text, font, fill, shadow_color=DARK_SHADOW, offset=(3,3), anchor=None):
    """Helper to draw text with a drop shadow."""
    x, y = xy
    # Shadow
    draw.text((x + offset[0], y + offset[1]), text, font=font, fill=shadow_color, anchor=anchor)
    # Main Text
    draw.text((x, y), text, font=font, fill=fill, anchor=anchor)

def draw_cover_overlay(bg_img: Image.Image, bilingual_date: str) -> Image.Image:
    """
    MINIMALIST HERO OVERLAY.
    No boxes, no yellow lines. Just clean, centered typography with drop shadows.
    """
    img = bg_img.convert("RGBA")
    draw = ImageDraw.Draw(img)
    
    try:
        title_jp_font = ImageFont.truetype(str(BOLD_FONT_PATH), 85)
        title_en_font = ImageFont.truetype(str(BOLD_FONT_PATH), 40)
        date_font = ImageFont.truetype(str(BOLD_FONT_PATH), 35)
    except:
        title_jp_font = ImageFont.load_default()
        title_en_font = ImageFont.load_default()
        date_font = ImageFont.load_default()
        
    center_x = img.width // 2
    center_y = int(img.height * 0.45) 
    
    # 1. Japanese Title
    jp_text = "本日の上映セレクション"
    draw_text_with_shadow(draw, (center_x, center_y), jp_text, title_jp_font, WHITE, anchor="mm")
    
    # 2. English Title
    en_text = "TODAY'S CINEMA SELECTION"
    draw_text_with_shadow(draw, (center_x, center_y + 100), en_text, title_en_font, LIGHT_GRAY, anchor="mm")
    
    # 3. Date
    draw_text_with_shadow(draw, (center_x, center_y + 180), bilingual_date, date_font, WHITE, anchor="mm")
    
    return img.convert("RGB")

# --- SLIDES (UPDATED) ---

def draw_story_slide(cinema_name: str, cinema_name_en: str, listings: list[dict[str, str | None]], bg_template: Image.Image) -> Image.Image:
    img = bg_template.copy()
    draw = ImageDraw.Draw(img)
    try:
        header_font = ImageFont.truetype(str(BOLD_FONT_PATH), 70)
        subhead_font = ImageFont.truetype(str(BOLD_FONT_PATH), 40)
        movie_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 42)
        en_movie_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 30)
        time_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 36)
        footer_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 30)
    except Exception:
        header_font = ImageFont.load_default()
        subhead_font = ImageFont.load_default()
        movie_font = ImageFont.load_default()
        en_movie_font = ImageFont.load_default()
        time_font = ImageFont.load_default()
        footer_font = ImageFont.load_default()
        
    center_x = CANVAS_WIDTH // 2
    y_pos = 150 
    
    draw_text_with_shadow(draw, (center_x, y_pos), cinema_name, header_font, WHITE, anchor="mm")
    y_pos += 80
    
    cinema_name_to_use = cinema_name_en or CINEMA_ENGLISH_NAMES.get(cinema_name, "")
    if cinema_name_to_use:
        draw_text_with_shadow(draw, (center_x, y_pos), cinema_name_to_use, subhead_font, LIGHT_GRAY, anchor="mm")
        y_pos += 100
    else:
        y_pos += 60
    
    draw.line([(100, y_pos), (CANVAS_WIDTH - 100, y_pos)], fill=WHITE, width=4)
    y_pos += 80
    
    for listing in listings:
        wrapped_title = textwrap.wrap(listing['title'], width=24)
        for line in wrapped_title:
            draw_text_with_shadow(draw, (center_x, y_pos), line, movie_font, WHITE, anchor="mm")
            y_pos += 55
        if listing["en_title"]:
            wrapped_en = textwrap.wrap(f"({listing['en_title']})", width=40)
            for line in wrapped_en:
                draw_text_with_shadow(draw, (center_x, y_pos), line, en_movie_font, LIGHT_GRAY, anchor="mm")
                y_pos += 45
        if listing['times']:
            draw_text_with_shadow(draw, (center_x, y_pos), listing["times"], time_font, LIGHT_GRAY, anchor="mm")
            y_pos += 80
        else:
            y_pos += 40
            
    draw_text_with_shadow(draw, (center_x, STORY_CANVAS_HEIGHT - 100), "Full Schedule Link in Bio", footer_font, WHITE, anchor="mm")
    return img

def draw_cinema_slide(cinema_name: str, cinema_name_en: str, listings: list[dict[str, str | None]], bg_template: Image.Image) -> Image.Image:
    img = bg_template.copy()
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
    
    # Title Block
    draw_text_with_shadow(draw, (content_left, y_pos), cinema_name, title_jp_font, WHITE)
    y_pos += 70
    
    cinema_name_to_use = cinema_name_en or CINEMA_ENGLISH_NAMES.get(cinema_name, "")
    if cinema_name_to_use:
        draw_text_with_shadow(draw, (content_left, y_pos), cinema_name_to_use, title_en_font, LIGHT_GRAY)
        y_pos += 50
    else:
        y_pos += 20
        
    address = CINEMA_ADDRESSES.get(cinema_name, "")
    if address:
        jp_addr = address.split("\n")[0]
        draw_text_with_shadow(draw, (content_left, y_pos), f"📍 {jp_addr}", small_font, LIGHT_GRAY)
        y_pos += 60
    else:
        y_pos += 30
        
    draw.line([(MARGIN, y_pos), (CANVAS_WIDTH - MARGIN, y_pos)], fill=WHITE, width=3)
    y_pos += 40
    
    for listing in listings:
        wrapped_title = textwrap.wrap(f"■ {listing['title']}", width=TITLE_WRAP_WIDTH) or [f"■ {listing['title']}"]
        for line in wrapped_title:
            draw_text_with_shadow(draw, (content_left, y_pos), line, regular_font, WHITE)
            y_pos += 40
        if listing["en_title"]:
            wrapped_en = textwrap.wrap(f"({listing['en_title']})", width=35)
            for line in wrapped_en:
                draw_text_with_shadow(draw, (content_left + 10, y_pos), line, en_movie_font, LIGHT_GRAY)
                y_pos += 30
        if listing['times']:
            draw_text_with_shadow(draw, (content_left + 40, y_pos), listing["times"], regular_font, LIGHT_GRAY)
            y_pos += 55
            
    footer_text_final = "詳細は web / Details online: leonelki.com/cinemas"
    draw_text_with_shadow(draw, (CANVAS_WIDTH // 2, CANVAS_HEIGHT - MARGIN - 20), footer_text_final, footer_font, LIGHT_GRAY, anchor="mm")
    return img.convert("RGB")

# --- MAIN ---

def write_caption_for_multiple_cinemas(date_str: str, all_featured_cinemas: list[dict]) -> None:
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

    footer = f"""
#TokyoIndieCinema #{dynamic_hashtag} #MiniTheater #MovieLog
Check Bio for Full Schedule / 詳細はリンクへ
"""
    lines.append(footer)
    
    with OUTPUT_CAPTION_PATH.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def main() -> None:
    # 1. Basic Setup
    today = today_in_tokyo().date()
    today_str = today.isoformat()
    date_jp = today.strftime("%Y.%m.%d")
    date_en = today.strftime("%a")
    bilingual_date_str = f"{date_jp} {date_en.upper()}"

    # Clean up output in NEW folder
    for old_file in OUTPUT_DIR.glob("post_image_*.png"): os.remove(old_file) 
    for old_file in OUTPUT_DIR.glob("story_image_*.png"): os.remove(old_file)

    todays_showings = load_showtimes(today_str)
    if not todays_showings:
        print("No showings found for today.")
        return

    # 3. Group Cinemas
    grouped: defaultdict[str, list[dict]] = defaultdict(list)
    for show in todays_showings:
        if show.get("cinema_name"):
            grouped[show.get("cinema_name")].append(show)
            
    # 4. Selection Logic
    featured_names = get_recently_featured(OUTPUT_CAPTION_PATH)
    
    valid_cinemas = []
    for c_name, shows in grouped.items():
        if len(shows) >= MINIMUM_FILM_THRESHOLD:
             valid_cinemas.append(c_name)
             
    candidates = [c for c in valid_cinemas if c not in featured_names]
    if not candidates:
        candidates = valid_cinemas
        
    random.shuffle(candidates)
    selected_cinemas = candidates[:INSTAGRAM_SLIDE_LIMIT]
    
    if not selected_cinemas:
        print("No cinemas met criteria.")
        return

    # 5. Generate Images
    print(f"Generating for: {selected_cinemas}")
    
    # COVER
    cinema_images = []
    for c in selected_cinemas:
        if path := get_cinema_image_path(c):
            cinema_images.append((c, path))
            
    if cinema_images:
        layout_rgba, layout_rgb, mask = create_layout_and_mask(cinema_images, CANVAS_WIDTH, CANVAS_HEIGHT)
        cover_bg = inpaint_gaps(layout_rgb, mask)
        final_cover = draw_cover_overlay(cover_bg, bilingual_date_str)
        final_cover.save(OUTPUT_DIR / "post_image_00.png")
        
        # Story Cover (9:16)
        s_layout_rgba, s_layout_rgb, s_mask = create_layout_and_mask(cinema_images, CANVAS_WIDTH, STORY_CANVAS_HEIGHT)
        s_cover_bg = inpaint_gaps(s_layout_rgb, s_mask)
        s_final_cover = draw_cover_overlay(s_cover_bg, bilingual_date_str)
        s_final_cover.save(OUTPUT_DIR / "story_image_00.png")

    # SLIDES
    slide_counter = 0
    story_counter = 0
    all_featured_for_caption = []
    
    for cinema_name in selected_cinemas:
        shows = grouped[cinema_name]
        listings = format_listings(shows)
        
        # Feed Slides
        segmented = segment_listings(listings, MAX_FEED_VERTICAL_SPACE, spacing={'jp_line': 40, 'time_line': 55, 'en_line': 30})
        
        cinema_name_en = CINEMA_ENGLISH_NAMES.get(cinema_name, "")
        bg_img = create_blurred_cinema_bg(cinema_name, CANVAS_WIDTH, CANVAS_HEIGHT)
        story_bg_img = create_blurred_cinema_bg(cinema_name, CANVAS_WIDTH, STORY_CANVAS_HEIGHT)
        
        # Record for caption
        all_featured_for_caption.append({
            'cinema_name': cinema_name, 
            'listings': [l for sublist in segmented for l in sublist]
        })

        for segment in segmented:
            slide_counter += 1
            slide_img = draw_cinema_slide(cinema_name, cinema_name_en, segment, bg_img)
            slide_img.save(OUTPUT_DIR / f"post_image_{slide_counter:02}.png")
            
        # Story Slides
        story_segments = segment_listings(listings, MAX_STORY_VERTICAL_SPACE, spacing={'jp_line': 55, 'time_line': 80, 'en_line': 45})
        
        for segment in story_segments:
            story_counter += 1
            slide_img = draw_story_slide(cinema_name, cinema_name_en, segment, story_bg_img)
            slide_img.save(OUTPUT_DIR / f"story_image_{story_counter:02}.png")

    write_caption_for_multiple_cinemas(today_str, all_featured_for_caption)
    print("Done. Generated V1 posts.")

if __name__ == "__main__":
    main()
