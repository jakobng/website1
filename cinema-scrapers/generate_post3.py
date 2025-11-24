"""
Generate Instagram-ready image carousel (V60 - Stable & Fixed).

- Fix: Removed dependency on deleted 'get_bilingual_date' function.
- Logic: "Smart Collage" (Gemini 2.5 + Replicate) + Spaced Layout.
- Text: Large Japanese Date format for both Main and Fallback covers.
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
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from io import BytesIO

# Essential Imports
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

REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"
BOLD_FONT_PATH = BASE_DIR / "NotoSansJP-Bold.ttf"
REGULAR_FONT_PATH = BASE_DIR / "NotoSansJP-Regular.ttf"
OUTPUT_CAPTION_PATH = BASE_DIR / "post_v3_caption.txt"

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

def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")

def get_japanese_date_str():
    """Returns date in format: 2025年11月24日 (月)"""
    d = datetime.now()
    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    wd = weekdays[d.weekday()]
    return f"{d.year}年{d.month}月{d.day}日 ({wd})"

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
            "cover_main": ImageFont.truetype(str(BOLD_FONT_PATH), 90),
            "cover_sub": ImageFont.truetype(str(BOLD_FONT_PATH), 45),
            "title_jp": ImageFont.truetype(str(BOLD_FONT_PATH), 60),
            "title_en": ImageFont.truetype(str(REGULAR_FONT_PATH), 32),
            "meta": ImageFont.truetype(str(REGULAR_FONT_PATH), 24),
            "cinema": ImageFont.truetype(str(BOLD_FONT_PATH), 28),
            "times": ImageFont.truetype(str(REGULAR_FONT_PATH), 28),
            "date_jp": ImageFont.truetype(str(BOLD_FONT_PATH), 55),
        }
    except:
        d = ImageFont.load_default()
        return {k: d for k in ["cover_main", "cover_sub", "title_jp", "title_en", "meta", "cinema", "times", "date_jp"]}

# --- V60 Logic ---

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
    except:
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
    
    # Spacing Logic: Anchor Zones + Jitter
    zones = [
        (int(width * 0.15), int(height * 0.2)), # TL
        (int(width * 0.65), int(height * 0.2)), # TR
        (int(width * 0.15), int(height * 0.6)), # BL
        (int(width * 0.65), int(height * 0.6)), # BR
        (int(width * 0.40), int(height * 0.35)) # Center-High
    ]
    random.shuffle(zones)
    
    for i, sticker in enumerate(stickers):
        scale = random.uniform(0.40, 0.70)
        ratio = sticker.width / sticker.height
        new_w = int(width * scale)
        new_h = int(new_w / ratio)
        
        # Reduced Height Cap for spacing
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
            
        jitter_x = random.randint(-100, 100)
        jitter_y = random.randint(-100, 100)
        
        x = anchor_x + jitter_x
        y = anchor_y + jitter_y
        
        x = max(-50, min(x, width - s_rotated.width + 50))
        y = max(50, min(y, height - s_rotated.height - 50))
        
        canvas.paste(s_rotated, (x, y), s_rotated)

    noise_data = os.urandom(width * height)
    noise = Image.frombytes('L', (width, height), noise_data)
    canvas = Image.blend(canvas, noise.convert("RGB"), alpha=0.06)
    
    return canvas

def draw_final_cover(composite, fonts, is_story=False):
    """Draws Title and Date (Japanese Only)"""
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
    s_off = 5 
    
    # 1. Main Title
    title_text = "TODAY'S SCREENINGS"
    draw.text((cx + s_off, cy - 80 + offset + s_off), title_text, font=fonts['cover_main'], fill=(0,0,0), anchor="mm")
    draw.text((cx, cy - 80 + offset), title_text, font=fonts['cover_main'], fill=(255,255,255), anchor="mm")
    
    # 2. Subtitle
    jp_text = "今日の上映作品"
    draw.text((cx + s_off, cy + 20 + offset + s_off), jp_text, font=fonts['cover_sub'], fill=(0,0,0), anchor="mm")
    draw.text((cx, cy + 20 + offset), jp_text, font=fonts['cover_sub'], fill=(255, 235, 59), anchor="mm") 
    
    # 3. Date
    jp_date_text = get_japanese_date_str()
    draw.text((cx + 3, cy + 140 + offset + 3), jp_date_text, font=fonts['date_jp'], fill=(0,0,0), anchor="mm")
    draw.text((cx, cy + 140 + offset), jp_date_text, font=fonts['date_jp'], fill=(255,255,255), anchor="mm")
    
    return bg

def draw_fallback_cover(images, fonts, is_story=False):
    """Fallback text only cover"""
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
    
    draw.text((cx, cy - 80 + offset), "TODAY'S SCREENINGS", font=fonts['cover_main'], fill=(255,255,255), anchor="mm")
    draw.text((cx, cy + 20 + offset), "今日の上映作品", font=fonts['cover_sub'], fill=(255, 235, 59), anchor="mm")
    
    jp_date_text = get_japanese_date_str()
    draw.text((cx, cy + 140 + offset), jp_date_text, font=fonts['date_jp'], fill=(255,255,255), anchor="mm")
    
    return bg

# --- Main Execution ---

def main():
    print("--- Starting V60 (Fixed Date Bug) ---")
    
    for f in glob.glob(str(BASE_DIR / "post_v3_*.png")): os.remove(f)
    for f in glob.glob(str(BASE_DIR / "story_v3_*.png")): os.remove(f)

    date_str = get_today_str()
    if not SHOWTIMES_PATH.exists(): 
        print("Showtimes file missing.")
        return
        
    with open(SHOWTIMES_PATH, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
        
    films_map = {}
    for item in raw_data:
        if item.get('date_text') != date_str: continue
        if not item.get('tmdb_backdrop_path'): continue
        key = item.get('tmdb_id') or item.get('movie_title')
        if key not in films_map:
            films_map[key] = item
            films_map[key]['showings'] = defaultdict(list)
        films_map[key]['showings'][item.get('cinema_name', '')].append(item.get('showtime', ''))

    all_films = list(films_map.values())
    random.shuffle(all_films)
    selected = all_films[:9]
    
    if not selected:
        print("No films found.")
        return

    print(f"Selected {len(selected)} films.")
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

    collage = create_chaotic_collage(cover_images)
    
    if collage:
        print("✅ Collage Assembled!")
        cover_feed = draw_final_cover(collage, fonts, is_story=False)
        cover_story = draw_final_cover(collage, fonts, is_story=True)
        cover_feed.save(BASE_DIR / "post_v3_image_00.png")
        cover_story.save(BASE_DIR / "story_v3_image_00.png")
    else:
        print("⚠️ Collage Failed. Using Fallback.")
        fb_feed = draw_fallback_cover(cover_images, fonts, is_story=False)
        fb_feed.save(BASE_DIR / "post_v3_image_00.png")
        fb_story = draw_fallback_cover(cover_images, fonts, is_story=True)
        fb_story.save(BASE_DIR / "story_v3_image_00.png")

    caption_lines = [f"🗓️ {date_str} Tokyo Cinema Daily\n"]
    
    for i, item in enumerate(slide_data):
        film = item['film']
        img = item['img']
        slide_feed = draw_poster_slide(film, img, fonts, is_story=False)
        slide_feed.save(BASE_DIR / f"post_v3_image_{i+1:02}.png")
        slide_story = draw_poster_slide(film, img, fonts, is_story=True)
        slide_story.save(BASE_DIR / f"story_v3_image_{i+1:02}.png")
        
        t_jp = film.get('clean_title_jp') or film.get('movie_title')
        caption_lines.append(f"{t_jp}") 
        if film.get('movie_title_en'): caption_lines.append(f"{film['movie_title_en']}")
        for cin, t in film['showings'].items():
            t.sort()
            caption_lines.append(f"{cin}: {', '.join(t)}")
        caption_lines.append("")
        
    caption_lines.append("\nLink in Bio for Full Schedule")
    caption_lines.append("#TokyoIndieCinema #MiniTheater #MovieLog")
    
    with open(OUTPUT_CAPTION_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(caption_lines))
        
    print("Done. V60 Generated.")

if __name__ == "__main__":
    main()
