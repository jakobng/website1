"""
Generate Instagram-ready image carousel (V18 - A24 Minimalist).

- Base: V16 (Textured Backgrounds).
- Layout: Centered "Gallery" Frame.
- Typography: Small, Uppercase, Centered, Minimal.
- Vibe: A24, MUBI, High-End Indie.
"""
from __future__ import annotations

import json
import random
import textwrap
import os
import glob
import requests
import colorsys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, ImageEnhance

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"
BOLD_FONT_PATH = BASE_DIR / "NotoSansJP-Bold.ttf"
REGULAR_FONT_PATH = BASE_DIR / "NotoSansJP-Regular.ttf"
OUTPUT_CAPTION_PATH = BASE_DIR / "post_v2_caption.txt"

# Layout Dimensions
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350
MARGIN = 80 # Generous margins for minimalism

# --- Helpers ---

def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")

def get_bilingual_date():
    today = datetime.now()
    return today.strftime("%Y.%m.%d"), today.strftime("%A").upper()

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

def get_vibrant_bg(pil_img: Image.Image) -> tuple[int, int, int]:
    """Extracts a deep, rich dominant color."""
    small = pil_img.resize((150, 150))
    result = small.quantize(colors=5, method=2)
    dominant_color = result.getpalette()[:3]
    
    r, g, b = dominant_color
    h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
    
    # A24 Style: Deep, Muted, Moody
    new_s = 0.60 # Less saturated than before
    new_v = 0.20 # Very Dark
    
    if s < 0.1: 
        new_s, new_v = 0.0, 0.15
        
    nr, ng, nb = colorsys.hsv_to_rgb(h, new_s, new_v)
    return (int(nr*255), int(ng*255), int(nb*255))

def apply_film_grain(img, intensity=0.08):
    """Adds subtle film grain."""
    width, height = img.size
    noise_data = os.urandom(width * height)
    noise_img = Image.frombytes('L', (width, height), noise_data)
    
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    noise_img = noise_img.convert('RGBA')
    
    # Blend very subtly
    return Image.blend(img, noise_img, alpha=0.04).convert("RGB")

def create_3x3_grid(images: list[Image.Image]) -> Image.Image:
    canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), (15, 15, 15))
    cols, rows = 3, 3
    cell_w = CANVAS_WIDTH // cols
    cell_h = CANVAS_HEIGHT // rows
    
    pool = images.copy()
    while len(pool) < 9: pool += images
    random.shuffle(pool)
    
    for i in range(9):
        img = pool[i]
        col, row = i % 3, i // 3
        x, y = col * cell_w, row * cell_h
        
        img_ratio = img.width / img.height
        cell_ratio = cell_w / cell_h
        
        if img_ratio > cell_ratio:
            nh = cell_h
            nw = int(nh * img_ratio)
            img = img.resize((nw, nh), Image.Resampling.LANCZOS)
            left = (nw - cell_w) // 2
            img = img.crop((left, 0, left + cell_w, nh))
        else:
            nw = cell_w
            nh = int(nw / img_ratio)
            img = img.resize((nw, nh), Image.Resampling.LANCZOS)
            top = (nh - cell_h) // 2
            img = img.crop((0, top, nw, top + cell_h))
            
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(0.0) 
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(0.3)
        
        canvas.paste(img, (x, y))
    return canvas

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
    """Helper to center text horizontally."""
    length = draw.textlength(text, font=font)
    x = (CANVAS_WIDTH - length) // 2
    draw.text((x, y), text, font=font, fill=fill)
    return y + font.size + 10 # Return next Y position

def draw_cover_slide(images, fonts, date_str, day_str):
    bg = create_3x3_grid(images)
    bg = apply_film_grain(bg)
    draw = ImageDraw.Draw(bg)
    
    cx, cy = CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2
    
    # Minimalist Cover
    draw.text((cx, cy - 80), "TOKYO", font=fonts['cover_main'], fill=(255,255,255), anchor="mm")
    draw.text((cx, cy + 40), "CINEMA", font=fonts['cover_main'], fill=(255,255,255), anchor="mm")
    
    # Small elegant date
    draw.text((cx, cy + 160), f"{date_str} • {day_str}", font=fonts['cover_sub'], fill=(200,200,200), anchor="mm")
    
    return bg

def draw_poster_slide(film, img_obj, fonts):
    # 1. Background with Grain
    bg_color = get_vibrant_bg(img_obj)
    base = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), bg_color)
    canvas = apply_film_grain(base)
    draw = ImageDraw.Draw(canvas)
    
    # 2. The Image (Centered, Frameless, Smaller)
    # A24 style usually leaves ample breathing room
    target_w = 900 
    target_h = 600
    
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
    
    # Paste Image (Vertically centered in top half)
    img_y = 180
    img_x = (CANVAS_WIDTH - target_w) // 2
    canvas.paste(img_final, (img_x, img_y))
    
    cursor_y = img_y + target_h + 80
    
    # 3. Typography (Strictly Centered)
    
    # Metadata (Year • Runtime • Country) - Top of text block
    meta_parts = []
    if film.get('year'): meta_parts.append(str(film['year']))
    if film.get('tmdb_runtime'): meta_parts.append(f"{film['tmdb_runtime']}m")
    if film.get('genres'): meta_parts.append(film['genres'][0].upper())
    
    meta_str = "  •  ".join(meta_parts)
    cursor_y = draw_centered_text(draw, cursor_y, meta_str, fonts['meta'], (200, 200, 200))
    cursor_y += 20

    # Japanese Title
    jp_title = film.get('clean_title_jp') or film.get('movie_title', '')
    # Wrap if too long
    if len(jp_title) > 15:
        # Manual centering for wrapped text
        wrapper = textwrap.TextWrapper(width=15)
        lines = wrapper.wrap(jp_title)
        for line in lines:
            cursor_y = draw_centered_text(draw, cursor_y, line, fonts['title_jp'], (255, 255, 255))
    else:
        cursor_y = draw_centered_text(draw, cursor_y, jp_title, fonts['title_jp'], (255, 255, 255))
    
    cursor_y += 10

    # English Title (Uppercase, Small)
    if film.get('movie_title_en'):
        en_title = film.get('movie_title_en').upper()
        cursor_y = draw_centered_text(draw, cursor_y, en_title, fonts['title_en'], (200, 200, 200))
    
    # Director
    director = film.get('tmdb_director') or film.get('director')
    if director:
        cursor_y += 15
        draw_centered_text(draw, cursor_y, f"Dir. {director}", fonts['meta'], (150, 150, 150))
        cursor_y += 40

    # 4. Logline (Subtle)
    synopsis = film.get('tmdb_overview_jp')
    if synopsis and len(synopsis) > 10:
        cursor_y += 30
        # Check space
        if (CANVAS_HEIGHT - cursor_y) > 200:
            wrapper = textwrap.TextWrapper(width=40)
            lines = wrapper.wrap(synopsis)
            for line in lines[:2]: # Max 2 lines for minimalism
                cursor_y = draw_centered_text(draw, cursor_y, line, fonts['logline'], (180, 180, 180))
    
    # 5. Showtimes (Fixed at bottom)
    bottom_y = CANVAS_HEIGHT - 100
    
    sorted_cinemas = sorted(film['showings'].keys())
    # If multiple cinemas, stack upwards
    for cinema in reversed(sorted_cinemas):
        times = sorted(film['showings'][cinema])
        times_str = " ".join(times)
        
        # Draw upwards from bottom
        full_str = f"{cinema}   {times_str}"
        
        length = draw.textlength(full_str, font=fonts['cinema'])
        x = (CANVAS_WIDTH - length) // 2
        draw.text((x, bottom_y), full_str, font=fonts['cinema'], fill=(255, 255, 255))
        
        bottom_y -= 50

    return canvas

def main():
    print("--- Starting V18 (A24 Minimalist) ---")
    
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
        
    print("Done. V18 Generated.")

if __name__ == "__main__":
    main()
