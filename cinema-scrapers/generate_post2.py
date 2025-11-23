"""
Generate Instagram-ready image carousel (V25 - High Contrast / True Light Leaks).

- Base: V24 (Light Leak Atmospheric).
- Improvements:
  1. Color Separation: Maximizes Hue Distance between Base and Accent.
  2. Contrast Force: Accents are forced Bright/Luminous.
  3. Monochrome Fallback: Artificially shifts hue if image is too single-colored.
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

def get_dual_colors(pil_img: Image.Image) -> tuple[tuple, tuple]:
    """
    Extracts a Dark Base and a High-Contrast Bright Accent.
    """
    small = pil_img.resize((150, 150))
    result = small.quantize(colors=10, method=2)
    palette = result.getpalette()
    
    candidates = []
    for i in range(0, min(30, len(palette)), 3):
        r, g, b = palette[i], palette[i+1], palette[i+2]
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        candidates.append({'r':r, 'g':g, 'b':b, 'h':h, 's':s, 'v':v})

    # 1. Find BASE Color (Rich, Deep, Saturated)
    base_color = None
    max_base_score = -1
    for c in candidates:
        # Preference: High Saturation, Mid-Dark Value (not black)
        score = c['s'] * 2.5 + c['v']
        if c['v'] < 0.15: score -= 2.0 
        if score > max_base_score:
            max_base_score = score
            base_color = c
    if not base_color: base_color = candidates[0]

    # 2. Find ACCENT Color (Maximum Distance)
    accent_color = None
    max_dist = -1
    
    for c in candidates:
        # Hue Distance (0.0 - 0.5)
        h_dist = abs(c['h'] - base_color['h'])
        if h_dist > 0.5: h_dist = 1.0 - h_dist
        
        # We prioritize Hue Difference above all
        # Then Brightness (Accent should be brighter)
        score = (h_dist * 5.0) + (c['v'] * 2.0) + c['s']
        
        if score > max_dist:
            max_dist = score
            accent_color = c
            
    # Check if the "best" accent is actually different enough?
    # If hue distance is very low (< 0.05), it's a monochrome image.
    h_dist_final = abs(accent_color['h'] - base_color['h'])
    if h_dist_final > 0.5: h_dist_final = 1.0 - h_dist_final
    
    # --- Adjust Base (Mid-Dark for text) ---
    bh, bs, bv = base_color['h'], base_color['s'], base_color['v']
    n_bv = 0.25 # Standard background darkness
    n_bs = min(max(bs, 0.5), 0.95) # Keep saturation high
    
    rb, gb, bb = colorsys.hsv_to_rgb(bh, n_bs, n_bv)
    final_base = (int(rb*255), int(gb*255), int(bb*255))

    # --- Adjust Accent (Bright & Glowing) ---
    ah, as_, av = accent_color['h'], accent_color['s'], accent_color['v']
    
    # MONOCHROME FIX: If hues are too close, shift accent hue artificially
    if h_dist_final < 0.1 and n_bs > 0.1: # Only if base has some color
        # Shift hue by 30 degrees (0.08)
        ah = (ah + 0.08) % 1.0
        
    # Force high brightness for light leak effect
    n_av = 0.95 
    # Slightly lower saturation so it looks like "light"
    n_as = min(as_, 0.6) 
    
    ra, ga, ba = colorsys.hsv_to_rgb(ah, n_as, n_av)
    final_accent = (int(ra*255), int(ga*255), int(ba*255))

    return final_base, final_accent

def create_light_leaks(base_color, accent_color, width, height):
    """
    Creates a background with glowing 'Light Leaks' using Screen Blend.
    """
    # 1. Base Layer
    base = Image.new("RGB", (width, height), base_color)
    
    # 2. Light Leak Layer (Black background for Screen blend)
    leak_layer = Image.new("RGB", (width, height), "black")
    draw = ImageDraw.Draw(leak_layer)
    
    # Draw 2 large soft beams
    for _ in range(2):
        x = random.randint(-width//2, width + width//2)
        y = random.randint(-height//2, height + height//2)
        r_x = random.randint(500, 1000)
        r_y = random.randint(500, 1000)
        bbox = [x - r_x, y - r_y, x + r_x, y + r_y]
        draw.ellipse(bbox, fill=accent_color)
        
    # 3. Blur
    leak_layer = leak_layer.filter(ImageFilter.GaussianBlur(radius=90))
    
    # 4. Composite using Screen (Adds light)
    final_bg = ImageChops.screen(base, leak_layer)
    
    return final_bg

def apply_film_grain(img, intensity=0.08):
    width, height = img.size
    noise_data = os.urandom(width * height)
    noise_img = Image.frombytes('L', (width, height), noise_data)
    if img.mode != 'RGBA': img = img.convert('RGBA')
    noise_img = noise_img.convert('RGBA')
    return Image.blend(img, noise_img, alpha=0.06).convert("RGB")

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
    # Use first image for color theme
    c1, c2 = get_dual_colors(images[0])
    bg = create_light_leaks(c1, c2, CANVAS_WIDTH, CANVAS_HEIGHT)
    bg = apply_film_grain(bg)
    draw = ImageDraw.Draw(bg)
    
    cx, cy = CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2
    
    draw.text((cx, cy - 80), "TOKYO", font=fonts['cover_main'], fill=(255,255,255), anchor="mm")
    draw.text((cx, cy + 40), "CINEMA", font=fonts['cover_main'], fill=(255,255,255), anchor="mm")
    draw.text((cx, cy + 160), f"{date_str} • {day_str}", font=fonts['cover_sub'], fill=(200,200,200), anchor="mm")
    
    return bg

def draw_poster_slide(film, img_obj, fonts):
    # 1. Background with Light Leaks
    c_base, c_accent = get_dual_colors(img_obj)
    bg = create_light_leaks(c_base, c_accent, CANVAS_WIDTH, CANVAS_HEIGHT)
    canvas = apply_film_grain(bg)
    draw = ImageDraw.Draw(canvas)
    
    # 2. Layout Logic
    synopsis = film.get('tmdb_overview_jp', '')
    has_synopsis = len(synopsis) > 10
    
    target_w = 900 
    if has_synopsis:
        img_y = 120
        target_h = 550
    else:
        img_y = 180
        target_h = 600
        
    # Resize Image
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
    
    img_x = (CANVAS_WIDTH - target_w) // 2
    canvas.paste(img_final, (img_x, img_y))
    
    cursor_y = img_y + target_h + 70
    
    # 3. Typography
    
    # Metadata
    meta_parts = []
    if film.get('year'): meta_parts.append(str(film['year']))
    if film.get('tmdb_runtime'): meta_parts.append(f"{film['tmdb_runtime']}m")
    if film.get('genres'): meta_parts.append(film['genres'][0].upper())
    
    meta_str = "  •  ".join(meta_parts)
    cursor_y = draw_centered_text(draw, cursor_y, meta_str, fonts['meta'], (200, 200, 200))
    cursor_y += 15

    # Japanese Title
    jp_title = film.get('clean_title_jp') or film.get('movie_title', '')
    en_title = film.get('movie_title_en')
    
    if normalize_string(jp_title) == normalize_string(en_title):
        en_title = None
        
    if len(jp_title) > 15:
        wrapper = textwrap.TextWrapper(width=15)
        lines = wrapper.wrap(jp_title)
        for line in lines:
            cursor_y = draw_centered_text(draw, cursor_y, line, fonts['title_jp'], (255, 255, 255))
    else:
        cursor_y = draw_centered_text(draw, cursor_y, jp_title, fonts['title_jp'], (255, 255, 255))
    
    cursor_y += 10

    # English Title
    if en_title:
        cursor_y = draw_centered_text(draw, cursor_y, en_title.upper(), fonts['title_en'], (200, 200, 200))
    
    # Director
    director = film.get('tmdb_director') or film.get('director')
    if director:
        cursor_y += 15
        draw_centered_text(draw, cursor_y, f"Dir. {director}", fonts['meta'], (150, 150, 150))
        cursor_y += 30

    # 4. Logline
    if has_synopsis:
        cursor_y += 20
        available_h = (CANVAS_HEIGHT - 200) - cursor_y 
        if available_h > 80:
            wrapper = textwrap.TextWrapper(width=40)
            lines = wrapper.wrap(synopsis)
            for line in lines[:3]: 
                cursor_y = draw_centered_text(draw, cursor_y, line, fonts['logline'], (180, 180, 180))
    
    # 5. Showtimes (Smart-Fit V2)
    sorted_cinemas = sorted(film['showings'].keys())
    num_cinemas = len(sorted_cinemas)
    
    available_space = CANVAS_HEIGHT - cursor_y - 50
    std_font_size = 28
    std_gap = 50
    
    block_unit = (std_font_size * 1.2 * 2) + std_gap 
    total_needed = num_cinemas * block_unit
    
    scale = 1.0
    if total_needed > available_space:
        scale = available_space / total_needed
        scale = max(scale, 0.45) 
        
    final_font_size = int(std_font_size * scale)
    # Aggressive gap reduction
    gap_scale = scale if scale > 0.8 else scale * 0.6
    final_gap = int(std_gap * gap_scale)
    
    try:
        dyn_font_cin = ImageFont.truetype(str(BOLD_FONT_PATH), final_font_size)
        dyn_font_time = ImageFont.truetype(str(REGULAR_FONT_PATH), final_font_size)
    except:
        dyn_font_cin = ImageFont.load_default()
        dyn_font_time = ImageFont.load_default()
        
    unit_height = (final_font_size * 1.2) + (final_font_size * 1.2) + final_gap
    final_block_height = num_cinemas * unit_height
    
    if available_space > final_block_height:
        start_y = cursor_y + (available_space - final_block_height) // 2
    else:
        start_y = cursor_y + 20 
        
    for cinema in sorted_cinemas:
        times = sorted(film['showings'][cinema])
        times_str = " ".join(times)
        cinema_en = CINEMA_ENGLISH_NAMES.get(cinema, cinema)
        
        len_c = draw.textlength(cinema_en, font=dyn_font_cin)
        x_c = (CANVAS_WIDTH - len_c) // 2
        draw.text((x_c, start_y), cinema_en, font=dyn_font_cin, fill=(255, 255, 255))
        
        y_time = start_y + final_font_size + 5 
        len_t = draw.textlength(times_str, font=dyn_font_time)
        x_t = (CANVAS_WIDTH - len_t) // 2
        draw.text((x_t, y_time), times_str, font=dyn_font_time, fill=(200, 200, 200))
        
        start_y += unit_height

    return canvas

def main():
    print("--- Starting V25 (High Contrast / True Light Leaks) ---")
    
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
        
    print("Done. V25 Generated.")

if __name__ == "__main__":
    main()
