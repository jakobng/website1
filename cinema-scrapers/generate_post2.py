"""
Generate Instagram-ready image carousel (V15 - Swiss Poster + Metadata).

- Design: Asymmetrical "Print" Layout.
- Typography: Massive Left-Aligned Titles.
- Metadata: Integrated as a typographic row (Year / Genre / Runtime).
- Visual: Floating Image with Hard Shadow on Vibrant Background.
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

from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter, ImageOps

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"
BOLD_FONT_PATH = BASE_DIR / "NotoSansJP-Bold.ttf"
REGULAR_FONT_PATH = BASE_DIR / "NotoSansJP-Regular.ttf"
OUTPUT_CAPTION_PATH = BASE_DIR / "post_v2_caption.txt"

# Layout Dimensions
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350
MARGIN = 70 

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
    
    # Logic: Dark and Rich (Good for White Text)
    new_s = 0.80 
    new_v = 0.20 
    
    if s < 0.1: # Grayscale images get a slate grey
        new_s, new_v = 0.1, 0.15
        
    nr, ng, nb = colorsys.hsv_to_rgb(h, new_s, new_v)
    return (int(nr*255), int(ng*255), int(nb*255))

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
            
        # Desaturate significantly
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(0.0) # Black and White cover
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(0.4) # Dark
        
        canvas.paste(img, (x, y))
    return canvas

def add_drop_shadow(img, offset=(15, 15), background_color=(0,0,0,0), shadow_color=(0,0,0,180), border_width=0):
    """Adds a hard shadow to an image (Paper cutout effect)."""
    width, height = img.size
    total_width = width + abs(offset[0])
    total_height = height + abs(offset[1])
    
    back = Image.new("RGBA", (total_width, total_height), background_color)
    
    # Draw Shadow
    shadow = Image.new("RGBA", (width, height), shadow_color)
    shadow_left = max(offset[0], 0)
    shadow_top = max(offset[1], 0)
    back.paste(shadow, (shadow_left, shadow_top), shadow)
    
    # Paste Image
    img_left = min(offset[0], 0) * -1
    img_top = min(offset[1], 0) * -1
    back.paste(img, (img_left, img_top))
    
    return back

def fit_text_to_width(draw, text, font_path, max_width, max_font_size, min_font_size=40):
    size = max_font_size
    font = ImageFont.truetype(str(font_path), size)
    while size > min_font_size:
        bbox = draw.textbbox((0, 0), text, font=font)
        width = bbox[2] - bbox[0]
        if width <= max_width:
            return font, bbox[3] - bbox[1] 
        size -= 5
        font = ImageFont.truetype(str(font_path), size)
    return font, size

def get_fonts():
    try:
        return {
            "cover_main": ImageFont.truetype(str(BOLD_FONT_PATH), 130),
            "cover_sub": ImageFont.truetype(str(REGULAR_FONT_PATH), 40),
            "title_jp": ImageFont.truetype(str(BOLD_FONT_PATH), 100),
            "title_en": ImageFont.truetype(str(REGULAR_FONT_PATH), 45),
            "meta_bold": ImageFont.truetype(str(BOLD_FONT_PATH), 32), # For Metadata
            "cinema_bold": ImageFont.truetype(str(BOLD_FONT_PATH), 34),
            "times_reg": ImageFont.truetype(str(REGULAR_FONT_PATH), 34),
            "desc": ImageFont.truetype(str(REGULAR_FONT_PATH), 30),
        }
    except:
        return {k: ImageFont.load_default() for k in ["cover_main", "cover_sub", "title_jp", "title_en", "meta_bold", "cinema_bold", "times_reg", "desc"]}

def draw_cover_slide(images, fonts, date_str, day_str):
    bg = create_3x3_grid(images)
    draw = ImageDraw.Draw(bg)
    
    # Massive Typography in Center
    cx, cy = CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2
    
    # "TOKYO"
    draw.text((cx, cy - 120), "TOKYO", font=fonts['cover_main'], fill=(255,255,255), anchor="mm")
    # "CINEMA"
    draw.text((cx, cy + 20), "CINEMA", font=fonts['cover_main'], fill=(255,255,255), anchor="mm")
    
    # Date Pill
    draw.rectangle([(cx - 200, cy + 120), (cx + 200, cy + 180)], fill=(255, 210, 0))
    draw.text((cx, cy + 150), f"{date_str}", font=fonts['cover_sub'], fill=(0,0,0), anchor="mm")
    
    return bg

def draw_poster_slide(film, img_obj, fonts):
    # 1. Background
    bg_color = get_vibrant_bg(img_obj)
    canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), bg_color)
    draw = ImageDraw.Draw(canvas)
    
    # 2. The Image (Floating Card Style)
    target_w = CANVAS_WIDTH - (MARGIN * 2)
    target_h = int(target_w * 0.65) # Landscape aspect ratio
    
    img_ratio = img_obj.width / img_obj.height
    crop_ratio = target_w / target_h
    
    if img_ratio > crop_ratio:
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
    
    # Add Hard Shadow
    img_with_shadow = add_drop_shadow(img_final, offset=(20, 20), shadow_color=(0,0,0,100))
    canvas.paste(img_with_shadow, (MARGIN, 150), img_with_shadow)
    
    cursor_y = 150 + target_h + 60
    
    # 3. Typography (Left Aligned, No Icons)
    
    # Japanese Title (Huge)
    jp_title = film.get('clean_title_jp') or film.get('movie_title', '')
    jp_font, jp_h = fit_text_to_width(draw, jp_title, BOLD_FONT_PATH, CANVAS_WIDTH - (MARGIN*2), 110)
    draw.text((MARGIN, cursor_y), jp_title, font=jp_font, fill=(255, 255, 255))
    cursor_y += jp_h + 20
    
    # English Title (Small, Regular)
    if film.get('movie_title_en'):
        en_title = film.get('movie_title_en').upper()
        # Wrap if super long
        if len(en_title) > 40: en_title = en_title[:40] + "..."
        draw.text((MARGIN, cursor_y), en_title, font=fonts['title_en'], fill=(255, 255, 255, 180))
        cursor_y += 70
    else:
        cursor_y += 20

    # --- NEW: METADATA LINE (Typography Only) ---
    # Format: 2024 / 112 MIN / DRAMA
    meta_parts = []
    if film.get('year'): 
        meta_parts.append(str(film['year']))
    if film.get('tmdb_runtime'): 
        meta_parts.append(f"{film['tmdb_runtime']} MIN")
    
    # Add Genre if available
    if film.get('genres') and isinstance(film['genres'], list) and len(film['genres']) > 0:
         meta_parts.append(film['genres'][0].upper())

    meta_str = "  /  ".join(meta_parts)
    
    if meta_str:
        # Use Bold font to make it stand out from English title but same size
        draw.text((MARGIN, cursor_y), meta_str, font=fonts['meta_bold'], fill=(255, 210, 0)) # Yellow accent for data? Or keep white?
        # Let's keep it white for "No Yellow" rule, or maybe a subtle grey?
        # User said "No Yellow" in V13, but standard text color is better.
        draw.text((MARGIN, cursor_y), meta_str, font=fonts['meta_bold'], fill=(220, 220, 220)) 
        cursor_y += 60

    # Director (Text only)
    director = film.get('tmdb_director') or film.get('director')
    if director:
        draw.text((MARGIN, cursor_y), f"DIRECTED BY {director.upper()}", font=fonts['title_en'], fill=(255, 255, 255, 150))
        cursor_y += 60
        
    cursor_y += 30
    
    # 4. Showtimes (Grid Layout)
    sorted_cinemas = sorted(film['showings'].keys())
    for cinema in sorted_cinemas:
        if cursor_y > CANVAS_HEIGHT - 50: break
        
        times = sorted(film['showings'][cinema])
        times_str = "  ".join(times) 
        
        # Cinema Name (Bold White)
        draw.text((MARGIN, cursor_y), cinema, font=fonts['cinema_bold'], fill=(255, 255, 255))
        
        # Times on next line
        cursor_y += 45
        draw.text((MARGIN, cursor_y), times_str, font=fonts['times_reg'], fill=(200, 200, 200))
        
        cursor_y += 80 # Gap

    return canvas

def main():
    print("--- Starting V15 (Swiss Poster + Metadata) ---")
    
    for f in glob.glob(str(BASE_DIR / "post_v2_*.png")): os.remove(f)
    date_str = get_today_str()
    
    if not SHOWTIMES_PATH.exists(): 
        print("No showtimes.json found.")
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
        
    print("Done. V15 Generated.")

if __name__ == "__main__":
    main()
