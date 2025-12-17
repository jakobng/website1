"""
Generate Instagram-ready image carousel (V62 - "A24 Style" + Spread Layout).
REPLACES V28/V61.
- Design: Minimalist typography ("Today's Film Selection"), no yellow accents.
- Layout: "Explosive" collage (images spread to edges/bleed off canvas).
- Tech: Gemini 2.5 Flash + Replicate + Pillow.
- Update: Enforces JST dates, 3-day film rotation history, and new folder structure.
- Feature: Multi-day Showtime Aggregation (Today + Next 2 Days) ON IMAGE + Captions.
"""
from __future__ import annotations

import json
import random
import textwrap
import os
import glob
import requests
import math
import colorsys
import re
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageEnhance, ImageChops

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

# --- Timezone Setup (JST Enforcement) ---
try:
    from zoneinfo import ZoneInfo
    JST = ZoneInfo("Asia/Tokyo")
except ImportError:
    # Fallback for older environments
    JST = timezone(timedelta(hours=9))

# --- Secrets ---
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
FONTS_DIR = BASE_DIR / "fonts"
OUTPUT_DIR = BASE_DIR / "ig_posts"

# Ensure output directory exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Updated Paths
SHOWTIMES_PATH = DATA_DIR / "showtimes.json"
HISTORY_PATH = DATA_DIR / "featured_history.json"
OUTPUT_CAPTION_PATH = OUTPUT_DIR / "post_v2_caption.txt"

# Updated Font Paths
BOLD_FONT_PATH = FONTS_DIR / "NotoSansJP-Bold.ttf"
REGULAR_FONT_PATH = FONTS_DIR / "NotoSansJP-Regular.ttf"

# --- RESTORED CONSTANTS ---
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350       # 4:5 Aspect Ratio (Feed)
STORY_CANVAS_HEIGHT = 1920 # 9:16 Aspect Ratio (Story)

# --- Cinema Name Mapping ---
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

# --- Helpers ---

def get_today_jst():
    """Returns the current datetime in JST."""
    return datetime.now(JST)

def get_today_str():
    """Returns YYYY-MM-DD in JST."""
    return get_today_jst().strftime("%Y-%m-%d")

def get_japanese_date_str():
    """Returns formatted date string for display (JST)."""
    d = get_today_jst()
    # Format: 2025.11.24 (Mon)
    return f"{d.year}.{d.month:02}.{d.day:02}"

def format_date_for_caption(date_str: str) -> str:
    """Converts YYYY-MM-DD to MM/DD (Day)."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%m/%d (%a)")
    except:
        return date_str

def format_date_short(date_str: str, is_today: bool) -> str:
    """Short format for Image: 'Today' or 'Wed 12'"""
    if is_today: return "TODAY"
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%a %d").upper()
    except:
        return date_str

def normalize_string(s):
    if not s: return ""
    return re.sub(r'\W+', '', str(s)).lower()

def download_image(path: str) -> Image.Image | None:
    if not path: return None
    if path.startswith("http"):
        url = path
    else:
        url = f"https://image.tmdb.org/t/p/w1280{path}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            return Image.open(BytesIO(resp.content)).convert("RGB")
    except:
        return None
    return None

def get_fonts():
    try:
        return {
            "cover_main_jp": ImageFont.truetype(str(BOLD_FONT_PATH), 110),
            "cover_sub_en": ImageFont.truetype(str(REGULAR_FONT_PATH), 55),
            "cover_date": ImageFont.truetype(str(REGULAR_FONT_PATH), 40),
            "title_jp": ImageFont.truetype(str(BOLD_FONT_PATH), 60),
            "title_en": ImageFont.truetype(str(REGULAR_FONT_PATH), 32),
            "meta": ImageFont.truetype(str(REGULAR_FONT_PATH), 24),
            "cinema": ImageFont.truetype(str(BOLD_FONT_PATH), 28),
            "times": ImageFont.truetype(str(REGULAR_FONT_PATH), 24), # Slightly smaller for multi-line
            "date_label": ImageFont.truetype(str(BOLD_FONT_PATH), 20),
        }
    except:
        print("⚠️ Fonts not found, using default.")
        d = ImageFont.load_default()
        return {k: d for k in ["cover_main_jp", "cover_sub_en", "cover_date", "title_jp", "title_en", "meta", "cinema", "times", "date_label"]}

def get_faithful_colors(pil_img: Image.Image) -> tuple[tuple, tuple]:
    small = pil_img.resize((150, 150))
    result = small.quantize(colors=3, method=2)
    palette = result.getpalette()
    c1 = (palette[0], palette[1], palette[2])
    c2 = (palette[3], palette[4], palette[5])
    def adjust_for_bg(rgb_tuple, is_accent=False):
        r, g, b = rgb_tuple
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        if is_accent:
            new_v = max(v, 0.4)
            new_s = s 
        else:
            new_v = 0.22 
            new_s = min(max(s, 0.4), 0.9) 
            if s < 0.05: 
                new_s = 0.02
                new_v = 0.20
        nr, ng, nb = colorsys.hsv_to_rgb(h, new_s, new_v)
        return (int(nr*255), int(ng*255), int(nb*255))
    return adjust_for_bg(c1), adjust_for_bg(c2, is_accent=True)

def create_textured_bg(base_color, accent_color, width, height):
    img = Image.new("RGB", (width, height), base_color)
    texture = Image.new("RGBA", (width, height), (0,0,0,0))
    draw = ImageDraw.Draw(texture)
    line_color = (*accent_color, 25) 
    num_lines = int(40 * (height / 1350))
    for _ in range(num_lines):
        x1 = random.randint(-width, width * 2)
        y1 = random.randint(-height, height * 2)
        length = random.randint(300, 1500)
        angle = math.radians(45)
        x2 = x1 + length * math.cos(angle)
        y2 = y1 + length * math.sin(angle)
        w = random.randint(1, 4)
        draw.line([(x1, y1), (x2, y2)], fill=line_color, width=w)
    texture = texture.filter(ImageFilter.GaussianBlur(radius=2))
    img.paste(texture, (0,0), texture)
    return img

def apply_film_grain(img):
    width, height = img.size
    noise_data = os.urandom(width * height)
    noise_img = Image.frombytes('L', (width, height), noise_data)
    if img.mode != 'RGBA': img = img.convert('RGBA')
    noise_img = noise_img.convert('RGBA')
    return Image.blend(img, noise_img, alpha=0.05).convert("RGB")

def draw_centered_text(draw, y, text, font, fill, canvas_width=CANVAS_WIDTH):
    length = draw.textlength(text, font=font)
    x = (canvas_width - length) // 2
    draw.text((x, y), text, font=font, fill=fill)
    return y + font.size + 10 

# --- HISTORY / COOLDOWN MANAGER ---

class HistoryManager:
    def __init__(self, filepath, retention_days=3):
        self.filepath = filepath
        self.retention_days = retention_days
        self.history = self._load()

    def _load(self):
        if not self.filepath.exists():
            return {}
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}

    def is_on_cooldown(self, film_id):
        """Check if film_id was featured within the retention period."""
        today = datetime.now(JST).date()
        
        # Check explicit history
        last_seen_str = self.history.get(str(film_id))
        if last_seen_str:
            try:
                last_seen_date = datetime.strptime(last_seen_str, "%Y-%m-%d").date()
                days_diff = (today - last_seen_date).days
                if days_diff < self.retention_days:
                    return True # Still on cooldown
            except ValueError:
                pass # Bad date format, ignore
        return False

    def update(self, film_ids):
        """Update history with today's picks."""
        today_str = get_today_str()
        for fid in film_ids:
            self.history[str(fid)] = today_str
            
        self._save()

    def _save(self):
        # Prune old entries to keep file size small
        today = datetime.now(JST).date()
        clean_history = {}
        for fid, date_str in self.history.items():
            try:
                entry_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                if (today - entry_date).days < 14: # Keep 2 weeks of history just in case
                    clean_history[fid] = date_str
            except:
                pass
        
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(clean_history, f, indent=2)

# --- COLLAGE LOGIC ---

def ask_gemini_for_layout(images: list[Image.Image]):
    if not GEMINI_AVAILABLE or not GEMINI_API_KEY:
        print("⚠️ Gemini not configured. Falling back.")
        return 0, [1, 2, 3, 4] 

    print("🧠 Consulting Gemini 2.5 Flash...")
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = """
        You are an art director making a movie collage poster.
        1. Select ONE image to be the BACKGROUND (negative space/texture).
        2. Select 4 to 5 images to be FOREGROUND CUTOUTS (clear humans).
        Return JSON: {"background_index": 0, "foreground_indices": [1, 3, 4, 6]}
        """
        response = client.models.generate_content(
            model='gemini-2.5-flash', contents=[prompt, *images]
        )
        clean_json = re.search(r'\{.*\}', response.text, re.DOTALL)
        if clean_json:
            data = json.loads(clean_json.group(0))
            return data.get("background_index", 0), data.get("foreground_indices", [1,2,3])
    except Exception as e:
        print(f"⚠️ Gemini Analysis failed: {e}")
    return 0, [1, 2, 3, 4]

def remove_background(pil_img: Image.Image) -> Image.Image | None:
    print("✂️ Cutting out sticker...")
    if not REPLICATE_AVAILABLE or not REPLICATE_API_TOKEN:
        print("⚠️ Replicate not configured.")
        return None
        
    try:
        temp_path = BASE_DIR / "temp_rembg_in.png"
        pil_img.save(temp_path, format="PNG")
        output = replicate.run(
            "lucataco/remove-bg:95fcc2a26d3899cd6c2691c900465aaeff466285a65c14638cc5f36f34befaf1",
            input={"image": open(temp_path, "rb")}
        )
        if temp_path.exists(): os.remove(temp_path)
        if output:
            resp = requests.get(str(output))
            if resp.status_code == 200:
                return Image.open(BytesIO(resp.content)).convert("RGBA")
    except Exception as e:
        print(f"Replicate Error: {e}")
        return None
    return None

def create_sticker_style(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    alpha = img.split()[3]
    border_mask = alpha.filter(ImageFilter.MaxFilter(9))
    sticker_base = Image.new("RGBA", img.size, (255, 255, 255, 0))
    sticker_base.paste((255, 255, 255, 255), (0,0), mask=border_mask)
    sticker_base.paste(img, (0,0), mask=alpha)
    
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow_mask = border_mask.filter(ImageFilter.GaussianBlur(10))
    shadow_layer = Image.new("RGBA", img.size, (0,0,0,150))
    shadow.paste(shadow_layer, (10, 20), mask=shadow_mask)
    
    final = Image.new("RGBA", img.size, (0,0,0,0))
    final.paste(shadow, (0,0), mask=shadow)
    final.paste(sticker_base, (0,0), mask=sticker_base)
    return final

def create_chaotic_collage(images: list[Image.Image], width=896, height=1152) -> Image.Image:
    canvas = Image.new("RGB", (width, height), (10,10,10))
    if not images: return canvas

    bg_idx, fg_idxs = ask_gemini_for_layout(images)
    if bg_idx >= len(images): bg_idx = 0
    fg_idxs = [i for i in fg_idxs if i < len(images) and i != bg_idx]
    
    # Background
    bg_img = images[bg_idx]
    bg_ratio = bg_img.width / bg_img.height
    target_ratio = width / height
    if bg_ratio > target_ratio:
        new_h = height
        new_w = int(new_h * bg_ratio)
        bg_img = bg_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - width) // 2
        bg_img = bg_img.crop((left, 0, left+width, height))
    else:
        new_w = width
        new_h = int(new_w / bg_ratio)
        bg_img = bg_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        top = (new_h - height) // 2
        bg_img = bg_img.crop((0, top, width, top+height))
    
    # Darken background slightly to make white text pop
    bg_img = ImageEnhance.Brightness(bg_img).enhance(0.7)
    bg_img = bg_img.filter(ImageFilter.GaussianBlur(3)) 
    canvas.paste(bg_img, (0,0))
    
    # Process Stickers
    stickers = []
    print(f"🧩 Processing {len(fg_idxs)} stickers...")
    for idx in fg_idxs:
        raw = images[idx]
        cutout = remove_background(raw)
        if cutout:
            bbox = cutout.getbbox()
            if bbox:
                cutout = cutout.crop(bbox)
                sticker = create_sticker_style(cutout)
                stickers.append(sticker)
    
    random.shuffle(stickers) 
    
    zones = [
        (int(width * 0.10), int(height * 0.15)), 
        (int(width * 0.90), int(height * 0.15)), 
        (int(width * 0.10), int(height * 0.75)), 
        (int(width * 0.90), int(height * 0.75)), 
        (int(width * 0.50), int(height * 0.50)) 
    ]
    random.shuffle(zones)
    
    for i, sticker in enumerate(stickers):
        scale = random.uniform(0.40, 0.70)
        ratio = sticker.width / sticker.height
        new_w = int(width * scale)
        new_h = int(new_w / ratio)
        
        if new_h > int(height * 0.60): 
            new_h = int(height * 0.60)
            new_w = int(new_h * ratio)
            
        s_resized = sticker.resize((new_w, new_h), Image.Resampling.LANCZOS)
        angle = random.randint(-15, 15)
        s_rotated = s_resized.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
        
        if i < len(zones):
            anchor_x, anchor_y = zones[i]
        else:
            anchor_x = random.randint(100, width-300)
            anchor_y = random.randint(100, height-400)
            
        jitter_x = random.randint(-200, 200)
        jitter_y = random.randint(-150, 150)
        x = anchor_x + jitter_x
        y = anchor_y + jitter_y
        
        min_x = int(-s_rotated.width * 0.2)
        max_x = width - int(s_rotated.width * 0.8)
        min_y = int(-s_rotated.height * 0.2)
        max_y = height - int(s_rotated.height * 0.8)

        x = max(min_x, min(x, max_x))
        y = max(min_y, min(y, max_y))
        
        canvas.paste(s_rotated, (x, y), s_rotated)

    noise_data = os.urandom(width * height)
    noise = Image.frombytes('L', (width, height), noise_data)
    canvas = Image.blend(canvas, noise.convert("RGB"), alpha=0.06)
    return canvas

def draw_final_cover(composite, fonts, is_story=False):
    width = CANVAS_WIDTH
    height = STORY_CANVAS_HEIGHT if is_story else CANVAS_HEIGHT
    bg = composite.copy()
    bg_ratio = bg.width / bg.height
    target_ratio = width / height
    
    if bg_ratio > target_ratio:
        new_h = height
        new_w = int(new_h * bg_ratio)
        bg = bg.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - width) // 2
        bg = bg.crop((left, 0, left+width, height))
    else:
        new_w = width
        new_h = int(new_w / bg_ratio)
        bg = bg.resize((new_w, new_h), Image.Resampling.LANCZOS)
        top = (new_h - height) // 2
        bg = bg.crop((0, top, width, top+height))
        
    draw = ImageDraw.Draw(bg)
    cx, cy = width // 2, height // 2
    offset = -80 if is_story else 0
    
    jp_text = "今日の上映作品"
    draw.text((cx + 4, cy - 80 + offset + 4), jp_text, font=fonts['cover_main_jp'], fill=(0,0,0), anchor="mm")
    draw.text((cx, cy - 80 + offset), jp_text, font=fonts['cover_main_jp'], fill=(255,255,255), anchor="mm")

    en_text = "Today's Film Selection"
    draw.text((cx + 2, cy + 30 + offset + 2), en_text, font=fonts['cover_sub_en'], fill=(0,0,0), anchor="mm")
    draw.text((cx, cy + 30 + offset), en_text, font=fonts['cover_sub_en'], fill=(230,230,230), anchor="mm")

    date_text = get_japanese_date_str()
    draw.text((cx + 2, cy + 110 + offset + 2), date_text, font=fonts['cover_date'], fill=(0,0,0), anchor="mm")
    draw.text((cx, cy + 110 + offset), date_text, font=fonts['cover_date'], fill=(180,180,180), anchor="mm")

    return bg

def draw_fallback_cover(images, fonts, is_story=False):
    width = CANVAS_WIDTH
    height = STORY_CANVAS_HEIGHT if is_story else CANVAS_HEIGHT
    if images:
        bg = images[0].resize((width, int(width * images[0].height / images[0].width)))
        if bg.height < height: bg = bg.resize((int(height * bg.width / bg.height), height))
        left = (bg.width - width) // 2
        top = (bg.height - height) // 2
        bg = bg.crop((left, top, left + width, top + height))
    else:
        bg = Image.new("RGB", (width, height), (20,20,20))
    
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 160))
    bg.paste(overlay, (0, 0), overlay)
    draw = ImageDraw.Draw(bg)
    cx, cy = width // 2, height // 2
    offset = -80 if is_story else 0
    
    draw.text((cx, cy + offset), "Today's Film Selection", font=fonts['cover_main_jp'], fill=(255,255,255), anchor="mm")
    draw.text((cx, cy + 100 + offset), get_japanese_date_str(), font=fonts['cover_date'], fill=(200,200,200), anchor="mm")
    return bg

def draw_poster_slide(film, img_obj, fonts, is_story=False, primary_date=None):
    width = CANVAS_WIDTH
    height = STORY_CANVAS_HEIGHT if is_story else CANVAS_HEIGHT
    c_base, c_accent = get_faithful_colors(img_obj)
    bg = create_textured_bg(c_base, c_accent, width, height)
    canvas = apply_film_grain(bg)
    draw = ImageDraw.Draw(canvas)
    
    if is_story:
        target_w, target_h = 950, 850
        img_y = 180
    else:
        target_w, target_h = 900, 640
        img_y = 140
        
    # Draw Image
    img_ratio = img_obj.width / img_obj.height
    if img_ratio > (target_w / target_h):
        new_h = target_h
        new_w = int(new_h * img_ratio)
        img_resized = img_obj.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - target_w) // 2
        img_final = img_resized.crop((left, 0, left+target_w, target_h))
    else:
        new_w = target_w
        new_h = int(new_w / img_ratio)
        img_resized = img_obj.resize((new_w, new_h), Image.Resampling.LANCZOS)
        top = (new_h - target_h) // 2
        img_final = img_resized.crop((0, top, target_w, top+target_h))
    
    canvas.paste(img_final, ((width - target_w) // 2, img_y))
    cursor_y = img_y + target_h + (70 if is_story else 50)
    
    # Metadata
    meta_parts = []
    if film.get('year'): meta_parts.append(str(film['year']))
    if film.get('tmdb_runtime'): meta_parts.append(f"{film['tmdb_runtime']}m")
    if film.get('genres'): meta_parts.append(film['genres'][0].upper())
    meta_str = "  •  ".join(meta_parts)
    cursor_y = draw_centered_text(draw, cursor_y, meta_str, fonts['meta'], (200, 200, 200), width)
    cursor_y += 10

    # Titles (Dynamic Shrink)
    jp_title = film.get('clean_title_jp') or film.get('movie_title', '')
    en_title = film.get('movie_title_en')
    if normalize_string(jp_title) == normalize_string(en_title): en_title = None
    
    # Logic: If title is huge, use smaller font
    use_small_title = len(jp_title) > 10
    t_font = fonts['title_sm'] if use_small_title and 'title_sm' in fonts else fonts['title_jp']
    
    if len(jp_title) > 18:
        wrapper = textwrap.TextWrapper(width=18)
        lines = wrapper.wrap(jp_title)
        for line in lines:
            cursor_y = draw_centered_text(draw, cursor_y, line, t_font, (255, 255, 255), width)
    else:
        cursor_y = draw_centered_text(draw, cursor_y, jp_title, t_font, (255, 255, 255), width)
    cursor_y += 5

    if en_title:
        cursor_y = draw_centered_text(draw, cursor_y, en_title.upper(), fonts['title_en'], (200, 200, 200), width)
    
    director = film.get('tmdb_director') or film.get('director')
    if director:
        cursor_y += 10
        draw_centered_text(draw, cursor_y, f"Dir. {director}", fonts['meta'], (150, 150, 150), width)
        cursor_y += 20
    
    # --- Showtimes Logic (1 vs 2 Columns) ---
    schedule_map = defaultdict(lambda: defaultdict(list))
    if not primary_date: primary_date = get_today_str()
    all_dates = sorted(film['multi_day_showings'].keys())
    for d_key in all_dates:
        for cin_name, times in film['multi_day_showings'][d_key].items():
            schedule_map[cin_name][d_key] = sorted(times)
            
    sorted_cinemas = sorted(schedule_map.keys())
    
    # Estimate total lines needed
    total_lines = 0
    for cin in sorted_cinemas:
        total_lines += 1.2 # Header
        total_lines += len(schedule_map[cin]) # Lines
        total_lines += 0.5 # Gap
        
    available_space = height - cursor_y - (100 if is_story else 40)
    base_line_h = 32 if is_story else 28
    
    # Threshold for 2-column mode: If content > available height
    needs_split = (total_lines * base_line_h) > available_space
    
    if needs_split:
        # --- TWO COLUMN MODE ---
        col_w = (width - 100) // 2
        col1_x = 50
        col2_x = 50 + col_w + 20
        
        # Compact fonts
        compact_size = 24
        try:
            f_cin = ImageFont.truetype(str(BOLD_FONT_PATH), compact_size + 2)
            f_time = ImageFont.truetype(str(REGULAR_FONT_PATH), compact_size)
        except:
             f_cin = fonts['cinema']
             f_time = fonts['times']
        
        curr_x, curr_y = col1_x, cursor_y + 10
        
        for i, cin in enumerate(sorted_cinemas):
            # Move to col 2 if past half or out of space
            remaining = height - curr_y - 50
            if i > 0 and curr_x == col1_x and (i >= len(sorted_cinemas)/2 or remaining < 200):
                curr_x = col2_x
                curr_y = cursor_y + 10
                
            # Draw Cinema
            draw.text((curr_x, curr_y), cin, font=f_cin, fill=(255,255,255))
            curr_y += 35
            
            for d_key in sorted(schedule_map[cin].keys()):
                times_str = ", ".join(schedule_map[cin][d_key])
                is_today = (d_key == primary_date)
                date_label = format_date_short(d_key, is_today)
                
                # Draw Date Label (accent if today)
                lbl_color = (255, 200, 100) if is_today else (180, 180, 180)
                draw.text((curr_x, curr_y), date_label, font=f_time, fill=lbl_color)
                
                # Draw Time
                lbl_w = draw.textlength(date_label, font=f_time)
                draw.text((curr_x + lbl_w + 10, curr_y), times_str, font=f_time, fill=(230,230,230))
                curr_y += 30
            
            curr_y += 15 # Gap
            
    else:
        # --- STANDARD CENTERED MODE ---
        scale = 1.0
        est_h = total_lines * base_line_h
        if est_h > available_space:
            scale = max(available_space / est_h, 0.8) # Limit shrinkage
            
        final_size = int(base_line_h * scale)
        try:
            f_cin = ImageFont.truetype(str(BOLD_FONT_PATH), final_size)
            f_time = ImageFont.truetype(str(REGULAR_FONT_PATH), final_size)
        except:
            f_cin = fonts['cinema']
            f_time = fonts['times']
        
        start_y = cursor_y + 10
        for cin in sorted_cinemas:
            cin_en = CINEMA_ENGLISH_NAMES.get(cin, cin)
            len_c = draw.textlength(cin_en, font=f_cin)
            draw.text(((width - len_c)//2, start_y), cin_en, font=f_cin, fill=(255,255,255))
            start_y += (final_size * 1.2)
            
            for d_key in sorted(schedule_map[cin].keys()):
                times_str = ", ".join(schedule_map[cin][d_key])
                is_today = (d_key == primary_date)
                date_label = format_date_short(d_key, is_today)
                full_line = f"{date_label}   {times_str}"
                
                len_line = draw.textlength(full_line, font=f_time)
                x_line = (width - len_line) // 2
                
                lbl_color = (255, 200, 100) if is_today else (180, 180, 180)
                draw.text((x_line, start_y), date_label, font=f_time, fill=lbl_color)
                
                lbl_w = draw.textlength(date_label, font=f_time)
                draw.text((x_line + lbl_w + 15, start_y), times_str, font=f_time, fill=(230,230,230))
                start_y += (final_size * 1.1)
                
            start_y += (final_size * 0.6)

    return canvas

def main():
    print("--- Starting V2 (Punk Zine Style - A24 Edit) ---")
    
    # 🧹 TARGETED CLEANUP (V2 Only)
    # Only delete V2 files so we don't touch V1 cinemas
    print("🧹 Cleaning old V2 images...")
    if OUTPUT_DIR.exists():
        # Delete only post_v2_*.png and story_v2_*.png
        for f in OUTPUT_DIR.glob("post_v2_*.png"):
            try: os.remove(f)
            except: pass
        for f in OUTPUT_DIR.glob("story_v2_*.png"):
            try: os.remove(f)
            except: pass

    # 1. FIX: Get JST Date Range (Today + 2 Days)
    # We use the fixed 'get_today_jst()' helper here to ensure it's Tokyo time
    today_dt = get_today_jst().date()
    
    date_strs = [
        today_dt.strftime("%Y-%m-%d"),
        (today_dt + timedelta(days=1)).strftime("%Y-%m-%d"),
        (today_dt + timedelta(days=2)).strftime("%Y-%m-%d")
    ]
    primary_date = date_strs[0]
    print(f"📅 Target Dates (JST): {date_strs}")
    
    if not SHOWTIMES_PATH.exists(): 
        print(f"Showtimes file missing at: {SHOWTIMES_PATH}")
        return
        
    with open(SHOWTIMES_PATH, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    
    history_manager = HistoryManager(HISTORY_PATH)
    
    # 2. First Pass: Identify Candidates screenings TODAY
    # A film must screen TODAY to be eligible.
    candidates_today = set()
    for item in raw_data:
        if item.get('date_text') == primary_date:
            if not item.get('tmdb_backdrop_path'): continue
            fid = item.get('tmdb_id')
            if not fid: fid = normalize_string(item.get('movie_title'))
            candidates_today.add(fid)

    # 3. Second Pass: Aggregate Showtimes for Candidates across 3 days
    films_map = {}
    
    for item in raw_data:
        d_text = item.get('date_text')
        if d_text not in date_strs: continue
        
        fid = item.get('tmdb_id')
        if not fid: fid = normalize_string(item.get('movie_title'))
        
        # Only process if this film is a valid candidate (screens today)
        if fid not in candidates_today: continue
        
        if history_manager.is_on_cooldown(fid): continue
        
        if fid not in films_map:
            films_map[fid] = item
            films_map[fid]['showings'] = defaultdict(list) # TODAY ONLY (Legacy, kept for ref)
            films_map[fid]['multi_day_showings'] = defaultdict(lambda: defaultdict(list)) # 3-DAY (Primary)
            films_map[fid]['unique_id'] = fid
        
        cinema = item.get('cinema_name', '')
        time_str = item.get('showtime', '')
        
        # Add to multi-day structure
        films_map[fid]['multi_day_showings'][d_text][cinema].append(time_str)
        
        # Add to 'showings' ONLY if it is today
        if d_text == primary_date:
            films_map[fid]['showings'][cinema].append(time_str)

    all_films = list(films_map.values())
    
    if len(all_films) < 5:
        print("⚠️ Warning: Low film count after cooldown filter.")
        
    random.shuffle(all_films)
    selected = all_films[:9]
    
    if not selected:
        print("No films found for this date (or all filtered).")
        return

    print(f"Selected {len(selected)} films.")
    
    selected_ids = [f['unique_id'] for f in selected]
    history_manager.update(selected_ids)
    print("💾 History updated.")
    
    fonts = get_fonts()
    slide_data = []
    cover_images = []
    
    for film in selected:
        print(f"Processing: {film.get('clean_title_jp') or film.get('movie_title')}")
        img = download_image(film.get('tmdb_backdrop_path'))
        if img:
            slide_data.append({"film": film, "img": img})
            cover_images.append(img)
            
    if not slide_data: return

    # --- COLLAGE GENERATION ---
    collage = create_chaotic_collage(cover_images)
    
    if collage:
        print("✅ Collage Assembled!")
        cover_feed = draw_final_cover(collage, fonts, is_story=False)
        cover_feed.save(OUTPUT_DIR / "post_v2_image_00.png")
        
        cover_story = draw_final_cover(collage, fonts, is_story=True)
        cover_story.save(OUTPUT_DIR / "story_v2_image_00.png")
    else:
        print("⚠️ Collage Failed. Using Fallback.")
        fb_feed = draw_fallback_cover(cover_images, fonts, is_story=False)
        fb_feed.save(OUTPUT_DIR / "post_v2_image_00.png")
        
        fb_story = draw_fallback_cover(cover_images, fonts, is_story=True)
        fb_story.save(OUTPUT_DIR / "story_v2_image_00.png")

    # --- SLIDE & CAPTION GENERATION ---
    caption_lines = [f"🗓️ {primary_date} Tokyo Cinema Daily\n"]
    
    for i, item in enumerate(slide_data):
        film = item['film']
        img = item['img']
        
        # Pass primary_date to draw function for highlighting 'TODAY'
        slide_feed = draw_poster_slide(film, img, fonts, is_story=False, primary_date=primary_date)
        slide_feed.save(OUTPUT_DIR / f"post_v2_image_{i+1:02}.png")
        
        slide_story = draw_poster_slide(film, img, fonts, is_story=True, primary_date=primary_date)
        slide_story.save(OUTPUT_DIR / f"story_v2_image_{i+1:02}.png")
        
        # Caption Generation (Uses Multi-Day Data)
        t_jp = film.get('clean_title_jp') or film.get('movie_title')
        caption_lines.append(f"🎬 {t_jp}") 
        if film.get('movie_title_en'): caption_lines.append(f"({film['movie_title_en']})")
        
        sorted_dates = sorted(film['multi_day_showings'].keys())
        for d_key in sorted_dates:
            pretty_date = format_date_for_caption(d_key)
            if d_key == primary_date:
                caption_lines.append(f"\n🔻 {pretty_date} (Today)")
            else:
                caption_lines.append(f"\n🗓️ {pretty_date}")
                
            daily_shows = film['multi_day_showings'][d_key]
            for cin, t_list in daily_shows.items():
                t_list.sort()
                caption_lines.append(f"📍 {cin}: {', '.join(t_list)}")
                
        caption_lines.append("\n" + "-"*15 + "\n")
        
    caption_lines.append("Link in Bio for Full Schedule / 詳細はリンクへ")
    caption_lines.append("#TokyoIndieCinema #MiniTheater #MovieLog")
    
    with open(OUTPUT_CAPTION_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(caption_lines))
        
    print("Done. V2 Generated (Punk Style) with Multi-Day On-Image Schedules.")

if __name__ == "__main__":
    main()
