"""
Generate Instagram-ready image carousel (V1 - "The Cinema Reel" + Sunburst Slides).
UPDATED: 
- Cover Image: "Cinema Reel" Montage (Cinema photos stacked & glitched).
- Tech: Gemini 2.5 (Crop composition) + Replicate (Upscaling/Enhancement).
- Slides: Retained Sunburst Gradient style.
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
from datetime import datetime
from pathlib import Path
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops, ImageEnhance

try:  
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

# --- API Setup ---
try:
    import replicate
    REPLICATE_AVAILABLE = True
except ImportError:
    print("⚠️ Replicate library not found. Run: pip install replicate")
    REPLICATE_AVAILABLE = False

try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    print("⚠️ Google GenAI library not found. Run: pip install google-genai")
    GEMINI_AVAILABLE = False

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"
ASSETS_DIR = BASE_DIR / "cinema_assets"  # New folder for cinema JPGs
BOLD_FONT_PATH = BASE_DIR / "NotoSansJP-Bold.ttf"
REGULAR_FONT_PATH = BASE_DIR / "NotoSansJP-Regular.ttf"
OUTPUT_CAPTION_PATH = BASE_DIR / "post_caption.txt"

# Secrets
TMDB_API_KEY = os.environ.get("TMDB_API_KEY")
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

MINIMUM_FILM_THRESHOLD = 3
INSTAGRAM_SLIDE_LIMIT = 10 
MAX_FEED_VERTICAL_SPACE = 750 
MAX_STORY_VERTICAL_SPACE = 1150
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350
STORY_CANVAS_HEIGHT = 1920
MARGIN = 60 
TITLE_WRAP_WIDTH = 30

# --- THEME COLORS ---
SUNBURST_CENTER = (255, 210, 0) 
SUNBURST_OUTER = (255, 255, 255)
BLACK = (20, 20, 20)
GRAY = (30, 30, 30) 
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
    "Tollywood": "東京都世田谷区代沢5-32-5 2F\n2F, 5-32-5 Daizawa, Setagaya-ku, Tokyo",
    "Morc阿佐ヶ谷": "東京都杉並区阿佐谷北2-12-19 B1F\nB1F, 2-12-19 Asagayakita, Suginami-ku, Tokyo"
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

def segment_listings(listings: List[Dict[str, str | None]], max_height: int, spacing: Dict[str, int]) -> List[List[Dict]]:
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

def get_recently_featured(caption_path: Path) -> List[str]:
    if not caption_path.exists(): return []
    try:
        content = caption_path.read_text(encoding="utf-8")
        names = re.findall(r"--- 【(.*?)】 ---", content)
        return names
    except Exception as e:
        print(f"   [WARN] Could not read previous caption: {e}")
        return []

# --- ASSET MANAGEMENT ---

def get_cinema_image_path(cinema_name: str) -> Path | None:
    """Finds a local image file matching the cinema name."""
    if not ASSETS_DIR.exists(): return None
    
    # Simple normalization for matching
    target = normalize_name(cinema_name)
    
    candidates = list(ASSETS_DIR.glob("*"))
    best_match = None
    highest_ratio = 0.0
    
    for f in candidates:
        if f.suffix.lower() not in ['.jpg', '.jpeg', '.png']: continue
        f_name = normalize_name(f.stem)
        
        # Direct check
        if f_name in target or target in f_name:
            # Prefer exact containment
            return f
            
        # Fuzzy check
        ratio = difflib.SequenceMatcher(None, target, f_name).ratio()
        if ratio > highest_ratio:
            highest_ratio = ratio
            best_match = f
            
    if highest_ratio > 0.4: # Threshold
        return best_match
    return None

def normalize_name(s):
    s = str(s).lower()
    return re.sub(r'[^a-z0-9]', '', s)

def upscale_image_replicate(pil_img: Image.Image) -> Image.Image:
    """Uses Replicate to upscale/fix low-quality cinema assets."""
    if not REPLICATE_AVAILABLE or not REPLICATE_API_TOKEN: 
        return pil_img

    print("   ✨ Enhancing cinema asset with Replicate...")
    try:
        # Save temp file
        temp_in = BASE_DIR / "temp_upscale_in.png"
        pil_img.save(temp_in, format="PNG")
        
        # Run Real-ESRGAN
        output = replicate.run(
            "nightmareai/real-esrgan:42fed1c4974146d4d2414e2be2c5277c7fcf05fcc3a73ab41b2ee43ad40a7214",
            input={"image": open(temp_in, "rb"), "scale": 2, "face_enhance": False}
        )
        
        if temp_in.exists(): os.remove(temp_in)
        
        if output:
            resp = requests.get(str(output))
            if resp.status_code == 200:
                return Image.open(BytesIO(resp.content)).convert("RGB")
    except Exception as e:
        print(f"   ⚠️ Upscale failed: {e}. Using original.")
    return pil_img

def ask_gemini_for_slice(pil_img: Image.Image) -> float:
    """Asks Gemini where the most interesting vertical center (0.0-1.0) is."""
    if not GEMINI_AVAILABLE or not GEMINI_API_KEY:
        return 0.5

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = """
        Analyze this image of a cinema. I need to crop a horizontal strip from it.
        Return ONLY a JSON object with a single key "center_y" (float between 0.0 and 1.0).
        "center_y" should be the vertical center of the most interesting visual feature (e.g., a neon sign, the screen, the ticket counter, or a row of chairs).
        Example: {"center_y": 0.3}
        """
        response = client.models.generate_content(
            model='gemini-2.5-flash', contents=[prompt, pil_img]
        )
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            return float(data.get("center_y", 0.5))
    except Exception as e:
        print(f"   ⚠️ Gemini Slice Analysis failed: {e}")
    return 0.5

# --- IMAGE GENERATORS ---

def create_sunburst_background(width: int, height: int) -> Image.Image:
    """Generates a radial gradient background (Sunburst)."""
    base_size = 512
    img = Image.new("RGB", (base_size, base_size), SUNBURST_OUTER)
    draw = ImageDraw.Draw(img)
    center_color = SUNBURST_CENTER
    outer_color = SUNBURST_OUTER
    max_radius = int(base_size * 0.7) 
    center = base_size // 2
    for r in range(max_radius, 0, -2):
        ratio = r / max_radius
        red = int(outer_color[0] * ratio + center_color[0] * (1 - ratio))
        green = int(outer_color[1] * ratio + center_color[1] * (1 - ratio))
        blue = int(outer_color[2] * ratio + center_color[2] * (1 - ratio))
        draw.ellipse([center - r, center - r, center + r, center + r], fill=(red, green, blue))
    return img.resize((width, height), Image.Resampling.LANCZOS)

def create_cinema_collage(cinemas: List[Tuple[str, Path]]) -> Image.Image:
    """
    Creates a 'Cinema Reel' Collage.
    - Takes 3 cinemas.
    - Enhances them (Replicate).
    - Finds best slice (Gemini).
    - Stacks them vertically.
    - Applies Glitch effect.
    """
    print(f"🎬 Creating Cinema Reel Collage with: {[c[0] for c in cinemas]}")
    
    num_slices = len(cinemas)
    slice_height = CANVAS_HEIGHT // num_slices
    canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), (10,10,10))
    
    for i, (name, path) in enumerate(cinemas):
        try:
            img = Image.open(path).convert("RGB")
            
            # 1. Enhance
            img = upscale_image_replicate(img)
            
            # 2. Analyze Crop
            center_y_ratio = ask_gemini_for_slice(img)
            
            # 3. Calculate Crop Box
            # We need an image that is CANVAS_WIDTH wide and slice_height high
            target_ratio = CANVAS_WIDTH / slice_height
            img_ratio = img.width / img.height
            
            if img_ratio > target_ratio:
                # Image is wider than strip -> Scale to height, crop width
                new_h = slice_height
                new_w = int(new_h * img_ratio)
                img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                left = (new_w - CANVAS_WIDTH) // 2
                img_strip = img_resized.crop((left, 0, left + CANVAS_WIDTH, slice_height))
            else:
                # Image is taller than strip (Common) -> Scale to width, crop height based on Gemini
                new_w = CANVAS_WIDTH
                new_h = int(new_w / img_ratio)
                img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                
                # Use Gemini's center_y
                center_px = int(new_h * center_y_ratio)
                top = center_px - (slice_height // 2)
                
                # Clamp
                if top < 0: top = 0
                if top + slice_height > new_h: top = new_h - slice_height
                
                img_strip = img_resized.crop((0, top, CANVAS_WIDTH, top + slice_height))

            # 4. Paste
            y_pos = i * slice_height
            canvas.paste(img_strip, (0, y_pos))
            
            # 5. Add Separator Line
            draw = ImageDraw.Draw(canvas)
            if i > 0:
                draw.line([(0, y_pos), (CANVAS_WIDTH, y_pos)], fill=(255, 210, 0), width=4)
                
        except Exception as e:
            print(f"Error processing {name}: {e}")
            
    # --- POST PROCESSING: THE "PROJECTION" LOOK ---
    # RGB Split (Chromatic Aberration)
    r, g, b = canvas.split()
    canvas = Image.merge("RGB", (
        ImageChops.offset(r, 4, 0),
        ImageChops.offset(g, 0, 0),
        ImageChops.offset(b, -4, 0)
    ))
    
    # Slight Noise
    noise = Image.effect_noise((CANVAS_WIDTH, CANVAS_HEIGHT), 10).convert("RGB")
    canvas = Image.blend(canvas, noise, 0.05)
    
    # Vignette
    overlay = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0,0,0,0))
    draw_ov = ImageDraw.Draw(overlay)
    draw_ov.rectangle([0,0,CANVAS_WIDTH,CANVAS_HEIGHT], fill=(0,0,0,60)) # Darken overall
    
    # Gradient Edges
    for i in range(150):
        alpha = int(255 * (1 - (i/150)))
        draw_ov.rectangle([i, i, CANVAS_WIDTH-i, CANVAS_HEIGHT-i], outline=(0,0,0,alpha))

    canvas.paste(overlay, (0,0), mask=overlay)
    return canvas

def draw_hero_slide_v1(bilingual_date: str, collage_img: Image.Image, featured_names: List[str]) -> Image.Image:
    """Draws the standard Text Overlay on the new Collage Background."""
    img = collage_img.copy()
    overlay = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0,0,0,0))
    draw_ov = ImageDraw.Draw(overlay)
    
    try:
        header_font = ImageFont.truetype(str(BOLD_FONT_PATH), 80)
        jp_title_font = ImageFont.truetype(str(BOLD_FONT_PATH), 100)
        en_subtitle_font = ImageFont.truetype(str(BOLD_FONT_PATH), 45)
        date_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 40)
        footer_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 30)
        credit_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 22) 
    except Exception:
        header_font = ImageFont.load_default()
        jp_title_font = ImageFont.load_default()
        en_subtitle_font = ImageFont.load_default()
        date_font = ImageFont.load_default()
        footer_font = ImageFont.load_default()
        credit_font = ImageFont.load_default()

    cx = CANVAS_WIDTH // 2
    cy = CANVAS_HEIGHT // 2
    
    # Box behind text to ensure readability over messy collage
    box_h = 500
    box_w = 900
    draw_ov.rectangle(
        [cx - box_w//2, cy - box_h//2, cx + box_w//2, cy + box_h//2], 
        fill=(0, 0, 0, 180)
    )
    draw_ov.rectangle(
        [cx - box_w//2, cy - box_h//2, cx + box_w//2, cy + box_h//2], 
        outline=(255, 255, 255, 100), width=3
    )

    def draw_centered_text(y, text, font, color=WHITE):
        draw_ov.text((cx, y), text, font=font, fill=color, anchor="mm")

    draw_centered_text(cy - 120, "TOKYO CINEMA INDEX", header_font)
    draw_centered_text(cy, "本日の上映館", jp_title_font)
    draw_centered_text(cy + 100, "Today's Theater Guide", en_subtitle_font)
    draw_centered_text(cy + 180, bilingual_date, date_font, (220, 220, 220))
    
    draw_centered_text(CANVAS_HEIGHT - MARGIN - 40, "→ SWIPE FOR SCHEDULES →", footer_font, (255, 210, 0)) 
    
    # List featured cinemas at bottom right
    if featured_names:
        clean_names = [n.split(' ')[0] for n in featured_names] # Shorten
        credit_text = "Featuring: " + " | ".join(clean_names)
        draw_ov.text((CANVAS_WIDTH - 20, CANVAS_HEIGHT - 15), credit_text, font=credit_font, fill=(180, 180, 180), anchor="rb")

    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

def draw_story_slide(cinema_name: str, cinema_name_en: str, listings: List[Dict[str, str | None]], bg_template: Image.Image) -> Image.Image:
    """Generates a 9:16 vertical Story slide (Kept Sunburst)."""
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
        header_font = ImageFont.load_default() # Fallbacks
        subhead_font = ImageFont.load_default()
        movie_font = ImageFont.load_default()
        en_movie_font = ImageFont.load_default()
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
        if listing["en_title"]:
            wrapped_en = textwrap.wrap(f"({listing['en_title']})", width=40)
            for line in wrapped_en:
                draw.text((center_x, y_pos), line, font=en_movie_font, fill=GRAY, anchor="mm")
                y_pos += 45
        if listing['times']:
            draw.text((center_x, y_pos), listing["times"], font=time_font, fill=GRAY, anchor="mm")
            y_pos += 80
        else:
            y_pos += 40
    draw.text((center_x, STORY_CANVAS_HEIGHT - 150), "Full Schedule Link in Bio", font=footer_font, fill=BLACK, anchor="mm")
    return img

def draw_cinema_slide(cinema_name: str, cinema_name_en: str, listings: List[Dict[str, str | None]], bg_template: Image.Image) -> Image.Image:
    """Generates standard feed slide (Kept Sunburst)."""
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

def main() -> None:
    # 1. Basic Setup
    today = today_in_tokyo().date()
    today_str = today.isoformat()
    date_jp = today.strftime("%Y年%m月%d日")
    date_en = today.strftime("%b %d, %Y")
    bilingual_date_str = f"{date_jp} / {date_en}"

    # Cleanup
    for old_file in glob.glob(str(BASE_DIR / "post_image_*.png")): os.remove(old_file) 
    for old_file in glob.glob(str(BASE_DIR / "story_image_*.png")): os.remove(old_file)

    todays_showings = load_showtimes(today_str)
    if not todays_showings: return
    
    # 2. Pre-generate Sunbursts for Slides (NOT Cover)
    feed_bg_template = create_sunburst_background(CANVAS_WIDTH, CANVAS_HEIGHT)
    story_bg_template = create_sunburst_background(CANVAS_WIDTH, STORY_CANVAS_HEIGHT)

    # 3. Group Cinemas
    grouped: Dict[str, List[Dict]] = defaultdict(list)
    for show in todays_showings:
        if show.get("cinema_name"):
            grouped[show.get("cinema_name")].append(show)

    all_candidates_raw = []
    FEED_METRICS = {'jp_line': 40, 'en_line': 30, 'time_line': 55}
    
    for cinema_name, showings in grouped.items():
        unique_titles = set(s.get('movie_title') for s in showings if s.get('movie_title'))
        
        # Check for asset availability
        has_asset = get_cinema_image_path(cinema_name) is not None

        if len(unique_titles) >= MINIMUM_FILM_THRESHOLD:
            listings = format_listings(showings)
            feed_segments = segment_listings(listings, MAX_FEED_VERTICAL_SPACE, FEED_METRICS)
            all_candidates_raw.append({
                "name": cinema_name,
                "listings": listings,
                "feed_segments": feed_segments,
                "has_asset": has_asset
            })

    # 4. Selection Logic
    recent_cinemas = get_recently_featured(OUTPUT_CAPTION_PATH)
    fresh_candidates = []
    recent_candidates = []
    for cand in all_candidates_raw:
        if cand['name'] in recent_cinemas: recent_candidates.append(cand)
        else: fresh_candidates.append(cand)
    
    random.shuffle(fresh_candidates)
    random.shuffle(recent_candidates)
    all_candidates = fresh_candidates + recent_candidates
    
    MAX_CONTENT_SLIDES = INSTAGRAM_SLIDE_LIMIT - 1 
    final_selection = []
    current_slide_count = 0
    
    for cand in all_candidates:
        needed = len(cand['feed_segments'])
        if current_slide_count + needed <= MAX_CONTENT_SLIDES:
            final_selection.append(cand)
            current_slide_count += needed

    if not final_selection: return

    # --- 5. COVER GENERATION (NEW LOGIC) ---
    print("--- Generating V1 Cover (Cinema Reel Style) ---")
    
    # Find cinemas with assets
    asset_candidates = [c['name'] for c in final_selection if c['has_asset']]
    if len(asset_candidates) < 3:
        # If not enough in selection, pick randoms from existing assets
        print("   Not enough selected cinemas have assets. Filling with random assets.")
        all_assets = list(ASSETS_DIR.glob("*.jpg"))
        random.shuffle(all_assets)
        collage_inputs = []
        
        # Add selected ones first
        for name in asset_candidates:
            p = get_cinema_image_path(name)
            if p: collage_inputs.append((name, p))
            
        # Fill rest
        for p in all_assets:
            if len(collage_inputs) >= 3: break
            name_guess = p.stem.replace('_', ' ').title()
            # Avoid dupes
            if not any(c[1] == p for c in collage_inputs):
                 collage_inputs.append((name_guess, p))
    else:
        random.shuffle(asset_candidates)
        picked = asset_candidates[:3]
        collage_inputs = [(n, get_cinema_image_path(n)) for n in picked]

    if collage_inputs:
        collage_bg = create_cinema_collage(collage_inputs)
        hero_slide = draw_hero_slide_v1(bilingual_date_str, collage_bg, [x[0] for x in collage_inputs])
        hero_slide.save(BASE_DIR / f"post_image_00.png")
        
        # Reuse for story (resize)
        hero_story_bg = collage_bg.resize((CANVAS_WIDTH, STORY_CANVAS_HEIGHT), Image.Resampling.LANCZOS)
        hero_story = draw_hero_slide_v1(bilingual_date_str, hero_story_bg, [x[0] for x in collage_inputs])
        hero_story.save(BASE_DIR / f"story_image_00.png")
    else:
        print("⚠️ No cinema assets found at all. Using Fallback Sunburst.")
        fallback_bg = create_sunburst_background(CANVAS_WIDTH, CANVAS_HEIGHT)
        hero_slide = draw_hero_slide_v1(bilingual_date_str, fallback_bg, [])
        hero_slide.save(BASE_DIR / "post_image_00.png")
        # Story Fallback
        fbs = create_sunburst_background(CANVAS_WIDTH, STORY_CANVAS_HEIGHT)
        hs = draw_hero_slide_v1(bilingual_date_str, fbs, [])
        hs.save(BASE_DIR / "story_image_00.png")

    # --- 6. SLIDE GENERATION (Sunburst) ---
    print("Generating Content Slides...")
    feed_counter = 0
    all_featured_for_caption = []
    
    for item in final_selection:
        cinema_name = item['name']
        cinema_name_en = CINEMA_ENGLISH_NAMES.get(cinema_name, "")
        listings = item['listings']
        all_featured_for_caption.append({"cinema_name": cinema_name, "listings": listings})
        feed_segments = segment_listings(listings, MAX_FEED_VERTICAL_SPACE, FEED_METRICS)
        
        for segment in feed_segments:
            feed_counter += 1
            slide_img = draw_cinema_slide(cinema_name, cinema_name_en, segment, feed_bg_template)
            slide_img.save(BASE_DIR / f"post_image_{feed_counter:02}.png")

    # Story Slides
    story_counter = 0
    STORY_METRICS = {'jp_line': 55, 'en_line': 45, 'time_line': 80} 
    for item in final_selection:
        cinema_name = item['name']
        cinema_name_en = CINEMA_ENGLISH_NAMES.get(cinema_name, "")
        listings = item['listings']
        story_segments = segment_listings(listings, MAX_STORY_VERTICAL_SPACE, STORY_METRICS)
        for segment in story_segments:
            story_counter += 1
            slide_img = draw_story_slide(cinema_name, cinema_name_en, segment, story_bg_template)
            slide_img.save(BASE_DIR / f"story_image_{story_counter:02}.png")

    # 7. Caption
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
        "\ndetails: leonelki.com/cinemas",
        f"\n#東京ミニシアター #映画 #映画館 #tokyo #{dynamic_hashtag}",
        "#tokyocinema #arthousecinema"
    ])
    OUTPUT_CAPTION_PATH.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
