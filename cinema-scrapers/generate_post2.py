"""
Generate Instagram-ready image carousel (V26 - Subtle Texture / Faithful Colors).

- Base: V22 (Smart-Fit Layout).
- Visuals:
  1. Faithful Colors: No artificial contrast boosting. Uses real image palette.
  2. Texture Engine: Generates thin, diagonal scratches/streaks.
  3. Subtlety: Low opacity, slight blur. "Paper grain" feel.
"""
from __future__ import annotations

import json
import random
import textwrap
import os
import glob
import requests
import colorsys
import re
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter, ImageChops

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"
BOLD_FONT_PATH = BASE_DIR / "NotoSansJP-Bold.ttf"
REGULAR_FONT_PATH = BASE_DIR / "NotoSansJP-Regular.ttf"
OUTPUT_CAPTION_PATH = BASE_DIR / "post_v2_caption.txt"

# Layout Dimensions
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350
MARGIN = 80

# --- Cinema Name Mapping (JP -> EN) ---
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
    "Morc Asagaya": "Morc Asagaya",
    "TULLYWOOD": "Tollywood",
    "Tollywood": "Tollywood"
}

# --- Helpers ---

def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")

def get_bilingual_date():
    today = datetime.now()
    return today.strftime("%Y.%m.%d"), today.strftime("%A").upper()

def normalize_string(s):
    if not s: return ""
    return re.sub(r'\W+', '', str(s)).lower()

def download_image(path: str) -> Image.Image | None:
    if not path: return None
    url = f"https://image.tmdb.org/t/p/w1280{path}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return Image.open(BytesIO(resp.content)).convert("RGB")
    except:
        return None
    return None

def get_faithful_colors(pil_img: Image.Image) -> tuple[tuple, tuple]:
    """
    Extracts the two most dominant colors without artificial shifting.
    Only adjusts Brightness (Value) to ensure text readability.
    """
    small = pil_img.resize((150, 150))
    # Quantize to just 3 colors to find the absolute main vibes
    result = small.quantize(colors=3, method=2)
    palette = result.getpalette()
    
    # Base = Most dominant
    c1 = (palette[0], palette[1], palette[2])
    # Accent = Second most dominant
    c2 = (palette[3], palette[4], palette[5])
    
    def adjust_for_bg(rgb_tuple, is_accent=False):
        r, g, b = rgb_tuple
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        
        if is_accent:
            # Accent: Just needs to be visible against Base. 
            # Slight boost to brightness if it's too dark.
            new_v = max(v, 0.4)
            new_s = s # Keep saturation faithful
        else:
            # Base: Needs to support white text.
            # Darken if too bright, Brighten if pitch black.
            new_v = 0.22 # Standard "Dark Mode" grey level
            new_s = min(max(s, 0.4), 0.9) # Ensure some color remains
            
            # Special case: True B&W
            if s < 0.05: 
                new_s = 0.02
                new_v = 0.20
        
        nr, ng, nb = colorsys.hsv_to_rgb(h, new_s, new_v)
        return (int(nr*255), int(ng*255), int(nb*255))

    return adjust_for_bg(c1), adjust_for_bg(c2, is_accent=True)

def create_textured_bg(base_color, accent_color, width, height):
    """
    Creates a background with thin, subtle diagonal streaks.
    """
    img = Image.new("RGB", (width, height), base_color)
    
    # Texture Layer
    texture = Image.new("RGBA", (width, height), (0,0,0,0))
    draw = ImageDraw.Draw(texture)
    
    # Draw many thin diagonal lines
    # Low alpha for "barely there" look
    line_color = (*accent_color, 25) # Alpha 25/255 (Very transparent)
    
    num_lines = 40
    
    for _ in range(num_lines):
        # Random geometry
        x1 = random.randint(-width, width * 2)
        y1 = random.randint(-height, height * 2)
        
        length = random.randint(300, 1500)
        angle = math.radians(45) # 45 degree streaks
        
        x2 = x1 + length * math.cos(angle)
        y2 = y1 + length * math.sin(angle)
        
        # Thin width
        w = random.randint(1, 4)
        
        draw.line([(x1, y1), (x2, y2)], fill=line_color, width=w)
        
    # Slight blur to merge lines into a "texture" rather than vector art
    texture = texture.filter(ImageFilter.GaussianBlur(radius=2))
    
    # Composite
    img.paste(texture, (0,0), texture)
    return img

def apply_film_grain(img, intensity=0.08):
    width, height = img.size
    noise_data = os.urandom(width * height)
    noise_img = Image.frombytes('L', (width, height), noise_data)
    if img.mode != 'RGBA': img = img.convert('RGBA')
    noise_img = noise_img.convert('RGBA')
    return Image.blend(img, noise_img, alpha=0.05).convert("RGB")

def get_fonts():
    try:
        return {
            "cover_main": ImageFont.truetype(str(BOLD_FONT_PATH), 120),
            "cover_sub": ImageFont.truetype(str(REGULAR_FONT_PATH), 30),
            "title_jp": ImageFont.truetype(str(BOLD_FONT_PATH), 60),
            "title_en": ImageFont.truetype(str(REGULAR_FONT_PATH), 32),
            "meta": ImageFont.truetype(str(REGULAR_FONT_PATH), 24),
            "logline": ImageFont.truetype(str(REGULAR_FONT_PATH), 26),
            "cinema": ImageFont.truetype(str(BOLD_FONT_PATH), 28),
            "times": ImageFont.truetype(str(REGULAR_FONT_PATH), 28),
        }
    except:
        return {k: ImageFont.load_default() for k in ["cover_main", "cover_sub", "title_jp", "title_en", "meta", "logline", "cinema", "times"]}

def draw_centered_text(draw, y, text, font, fill):
    length = draw.textlength(text, font=font)
    x = (CANVAS_WIDTH - length) // 2
    draw.text((x, y), text, font=font, fill=fill)
    return y + font.size + 10 

def draw_cover_slide(images, fonts, date_str, day_str):
    c1, c2 = get_faithful_colors(images[0])
    bg = create_textured_bg(c1, c2, CANVAS_WIDTH, CANVAS_HEIGHT)
    bg = apply_film_grain(bg)
    draw = ImageDraw.Draw(bg)
    
    cx, cy = CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2
    draw.text((cx, cy - 80), "TOKYO", font=fonts['cover_main'], fill=(255,255,255), anchor="mm")
    draw.text((cx, cy + 40), "CINEMA", font=fonts['cover_main'], fill=(255,255,255), anchor="mm")
    draw.text((cx, cy + 160), f"{date_str} • {day_str}", font=fonts['cover_sub'], fill=(220,220,220), anchor="mm")
    return bg

def draw_poster_slide(film, img_obj, fonts):
    # 1. Textured Background
    c_base, c_accent = get_faithful_colors(img_obj)
    bg = create_textured_bg(c_base, c_accent, CANVAS_WIDTH, CANVAS_HEIGHT)
    canvas = apply_film_grain(bg)
    draw = ImageDraw.Draw(canvas)
    
    # 2. Layout Logic
    # --- MODIFIED: Use Taglines instead of Synopsis ---
    tagline_jp = film.get('tmdb_tagline_jp', '')
    tagline_en = film.get('tmdb_tagline_en', '')
    has_tagline = bool(tagline_jp or tagline_en)
    
    target_w = 900
    # If we have text to show, make the image slightly smaller to make room
    if has_tagline:
        img_y = 120
        target_h = 550
    else:
        img_y = 180
        target_h = 600
        
    # Resize Image (Standard "Contain/Crop" logic)
    img_ratio = img_obj.width / img_obj.height
    if img_ratio > (target_w / target_h):
        # Image is wider than target
        new_h = target_h
        new_w = int(new_h * img_ratio)
        img_resized = img_obj.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - target_w) // 2
        img_cropped = img_resized.crop((left, 0, left + target_w, target_h))
    else:
        # Image is taller/narrower than target
        new_w = target_w
        new_h = int(new_w / img_ratio)
        img_resized = img_obj.resize((new_w, new_h), Image.LANCZOS)
        top = (new_h - target_h) // 2
        img_cropped = img_resized.crop((0, top, target_w, top + target_h))
        
    # Draw Shadow and Image
    shadow = Image.new("RGB", (target_w + 20, target_h + 20), (0,0,0))
    canvas.paste(shadow, ((CANVAS_WIDTH - target_w)//2 + 10, img_y + 10))
    canvas.paste(img_cropped, ((CANVAS_WIDTH - target_w)//2, img_y))
    
    cursor_y = img_y + target_h + 40
    
    # 3. Title Info
    title_jp = film.get('clean_title_jp') or film.get('movie_title')
    title_en = film.get('movie_title_en')
    
    # Main Title (JP)
    cursor_y = draw_centered_text(draw, cursor_y, title_jp, fonts['cover_main'], (255, 255, 255))
    
    # Sub Title (EN)
    if title_en:
        cursor_y = draw_centered_text(draw, cursor_y, title_en, fonts['cover_sub'], (200, 200, 200))
         
    cursor_y += 20
    
    # 4. Draw Taglines (Modified Section)
    # Calculate available space for text
    available_h = CANVAS_HEIGHT - cursor_y - 350 # Leave space for showtimes at bottom
    
    if has_tagline and available_h > 50:
        # Draw Japanese Tagline
        if tagline_jp:
            wrapper_jp = textwrap.TextWrapper(width=30) # Wrap at 30 chars for JP
            lines = wrapper_jp.wrap(tagline_jp)
            for line in lines:
                # Use 'logline' font (usually smaller/lighter than title)
                cursor_y = draw_centered_text(draw, cursor_y, line, fonts['logline'], (220, 220, 220))
            cursor_y += 10 # Gap between JP and EN
            
        # Draw English Tagline
        if tagline_en:
            wrapper_en = textwrap.TextWrapper(width=50) # Wider wrap for English
            lines = wrapper_en.wrap(tagline_en)
            for line in lines:
                # Use same font, maybe slightly darker color for contrast
                cursor_y = draw_centered_text(draw, cursor_y, line, fonts['logline'], (180, 180, 180))

    # 5. Showtimes (Smart-Fit V2)
    # (This part remains mostly the same, ensuring it fits in remaining space)
    sorted_cinemas = sorted(film['showings'].keys())
    num_cinemas = len(sorted_cinemas)
    
    # Calculate space remaining for showtimes
    available_space = CANVAS_HEIGHT - cursor_y - 50
    std_font_size = 28
    std_gap = 50
    block_unit = (std_font_size * 1.2 * 2) + std_gap
    
    total_needed = num_cinemas * block_unit
    scale = 1.0
    
    if total_needed > available_space:
        scale = available_space / total_needed
        scale = max(scale, 0.45) # Don't shrink too much
        
    final_font_size = int(std_font_size * scale)
    gap_scale = scale if scale > 0.8 else scale * 0.6
    final_gap = int(std_gap * gap_scale)
    
    try:
        dyn_font_cin = ImageFont.truetype(str(BOLD_FONT_PATH), final_font_size)
        dyn_font_time = ImageFont.truetype(str(REGULAR_FONT_PATH), final_font_size)
    except:
        dyn_font_cin = fonts['cover_sub']
        dyn_font_time = fonts['cover_sub']

    for cinema in sorted_cinemas:
        times = film['showings'][cinema]
        times.sort()
        
        # Cinema Name
        display_name = CINEMA_ENGLISH_NAMES.get(cinema, cinema)
        draw_centered_text(draw, cursor_y, display_name, dyn_font_cin, (255, 215, 0))
        cursor_y += final_font_size * 1.4
        
        # Times
        time_str = " / ".join(times)
        draw_centered_text(draw, cursor_y, time_str, dyn_font_time, (255, 255, 255))
        cursor_y += final_font_size * 1.4 + final_gap

    return canvas

def main():
    print("--- Starting V26 (Subtle Texture) ---")
    
    for f in glob.glob(str(BASE_DIR / "post_v2_*.png")): os.remove(f)
    date_str = get_today_str()
    
    if not SHOWTIMES_PATH.exists(): return
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
    all_images = []
    
    for film in selected:
        print(f"Processing: {film.get('clean_title_jp') or film.get('movie_title')}")
        img = download_image(film.get('tmdb_backdrop_path'))
        if img:
            all_images.append(img)
            slide_data.append({"film": film, "img": img})
            
    if all_images:
        d_str, day_str = get_bilingual_date()
        cover = draw_cover_slide(all_images, fonts, d_str, day_str)
        cover.save(BASE_DIR / "post_v2_image_00.png")
        
    caption_lines = [f"🗓️ {date_str} Tokyo Cinema Selection\n"]
    
    for i, item in enumerate(slide_data):
        film = item['film']
        img = item['img']
        slide = draw_poster_slide(film, img, fonts)
        slide.save(BASE_DIR / f"post_v2_image_{i+1:02}.png")
        
        t_jp = film.get('clean_title_jp') or film.get('movie_title')
        caption_lines.append(f"{t_jp}") 
        if film.get('movie_title_en'): 
            caption_lines.append(f"{film['movie_title_en']}")
            
        for cin, t in film['showings'].items():
            t.sort()
            caption_lines.append(f"{cin}: {', '.join(t)}")
        caption_lines.append("")
        
    caption_lines.append("\nLink in Bio for Full Schedule")
    caption_lines.append("#TokyoIndieCinema #MiniTheater #MovieLog")
    
    with open(OUTPUT_CAPTION_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(caption_lines))
        
    print("Done. V26 Generated.")

if __name__ == "__main__":
    main()
