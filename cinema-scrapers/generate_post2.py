"""
Generate Instagram-ready image carousel (V11 - Vibrant Block Color + Deep Data).

- Design: "Hyper Vibrant" solid backgrounds (Jewel Tones) based on poster colors.
- Data: Displays Bilingual Titles, Director, Year, Genres, and Logline.
- Layout: 55% Image / 45% Info Block.
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
IMAGE_AREA_HEIGHT = int(CANVAS_HEIGHT * 0.55) 
MARGIN = 60 

# --- Helpers ---

def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")

def get_bilingual_date():
    today = datetime.now()
    return today.strftime("%Y.%m.%d"), today.strftime("%a")

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
    """
    Extracts dominant color and boosts saturation/value for a 'Jewel Tone' look.
    """
    # 1. Quantize to reduce colors
    small = pil_img.resize((150, 150))
    result = small.quantize(colors=10, method=2)
    dominant_color = result.getpalette()[:3]
    
    r, g, b = dominant_color
    h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
    
    # 2. Boost Saturation and normalize Value
    new_s = 0.85 # High saturation
    new_v = 0.25 # Darker value for text contrast (Dark block background)
    
    # Special handling for desaturated images (B&W)
    if s < 0.1: 
        new_s, new_v = 0.0, 0.20 
        
    nr, ng, nb = colorsys.hsv_to_rgb(h, new_s, new_v)
    return (int(nr*255), int(ng*255), int(nb*255))

def create_3x3_grid(images: list[Image.Image]) -> Image.Image:
    canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0))
    cols, rows = 3, 3
    cell_w = CANVAS_WIDTH // cols
    cell_h = CANVAS_HEIGHT // rows
    
    pool = images.copy()
    while len(pool) < 9: pool += images
    random.shuffle(pool)
    
    for i in range(9):
        img = pool[i]
        col, row = i % 3, i // 3
        x_pos, y_pos = col * cell_w, row * cell_h
        
        # Crop Center
        img_ratio = img.width / img.height
        cell_ratio = cell_w / cell_h
        
        if img_ratio > cell_ratio:
            new_h = cell_h
            new_w = int(new_h * img_ratio)
        else:
            new_w = cell_w
            new_h = int(new_w / img_ratio)
            
        img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        cx, cy = img_resized.width // 2, img_resized.height // 2
        left, top = cx - (cell_w // 2), cy - (cell_h // 2)
        
        cell_img = img_resized.crop((left, top, left + cell_w, top + cell_h))
        
        # Dim slightly
        enhancer = ImageEnhance.Brightness(cell_img)
        cell_img = enhancer.enhance(0.8)
        
        canvas.paste(cell_img, (x_pos, y_pos))
    return canvas

def resize_hero(pil_img: Image.Image) -> Image.Image:
    """Resizes image to fill the top 55% area."""
    img_ratio = pil_img.width / pil_img.height
    target_ratio = CANVAS_WIDTH / IMAGE_AREA_HEIGHT
    
    if img_ratio > target_ratio:
        new_height = IMAGE_AREA_HEIGHT
        new_width = int(new_height * img_ratio)
    else:
        new_width = CANVAS_WIDTH
        new_height = int(new_width / img_ratio)
        
    pil_img = pil_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    left = (pil_img.width - CANVAS_WIDTH) // 2
    top = (pil_img.height - IMAGE_AREA_HEIGHT) // 2
    return pil_img.crop((left, top, left + CANVAS_WIDTH, top + IMAGE_AREA_HEIGHT))

def fit_text_to_width(draw, text, font_path, max_width, max_font_size, min_font_size=30):
    """Shrinks text until it fits within max_width."""
    size = max_font_size
    font = ImageFont.truetype(str(font_path), size)
    while size > min_font_size:
        bbox = draw.textbbox((0, 0), text, font=font)
        width = bbox[2] - bbox[0]
        if width <= max_width:
            return font, bbox[3] - bbox[1] # Return font and height
        size -= 2
        font = ImageFont.truetype(str(font_path), size)
    return font, size

def get_fonts():
    try:
        return {
            "cover_main": ImageFont.truetype(str(BOLD_FONT_PATH), 110),
            "cover_sub": ImageFont.truetype(str(BOLD_FONT_PATH), 45),
            "meta": ImageFont.truetype(str(REGULAR_FONT_PATH), 28),
            "cinema": ImageFont.truetype(str(BOLD_FONT_PATH), 30),
            "times": ImageFont.truetype(str(REGULAR_FONT_PATH), 30),
            "synopsis": ImageFont.truetype(str(REGULAR_FONT_PATH), 26),
        }
    except:
        return {k: ImageFont.load_default() for k in ["cover_main", "cover_sub", "meta", "cinema", "times", "synopsis"]}

def draw_cover_slide(images, fonts, date_str, day_str):
    bg = create_3x3_grid(images)
    draw = ImageDraw.Draw(bg)
    cx, cy = CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2
    
    box_w, box_h = 800, 550
    box_x1, box_y1 = cx - box_w // 2, cy - box_h // 2
    box_x2, box_y2 = cx + box_w // 2, cy + box_h // 2
    
    # Shadow
    draw.rectangle([(box_x1 + 15, box_y1 + 15), (box_x2 + 15, box_y2 + 15)], fill=(0, 0, 0))
    # Main Box
    draw.rectangle([(box_x1, box_y1), (box_x2, box_y2)], fill=(255, 210, 0))
    
    draw.text((cx, cy - 160), f"{date_str} {day_str}", font=fonts['cover_sub'], fill=(0,0,0), anchor="mm")
    draw.text((cx, cy + 20), "SCREENING\nTODAY IN\nTOKYO", font=fonts['cover_main'], fill=(0,0,0), align="center", anchor="mm", spacing=20)
    return bg

def draw_film_slide(film, img_obj, fonts):
    # 1. Background Color
    bg_color = get_vibrant_bg(img_obj)
    canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), bg_color)
    draw = ImageDraw.Draw(canvas)
    
    # 2. Hero Image
    hero = resize_hero(img_obj)
    canvas.paste(hero, (0,0))
    
    # 3. Content Block
    cursor_y = IMAGE_AREA_HEIGHT + 50 
    left_x = MARGIN
    content_width = CANVAS_WIDTH - (MARGIN * 2)
    
    # Accent Line
    draw.rectangle([(left_x, cursor_y + 10), (left_x + 8, cursor_y + 130)], fill=(255, 210, 0))
    text_indent = 35
    
    # --- METADATA ROW (Year | Runtime | Genre) ---
    meta_parts = []
    if film.get('year') and film['year'] != 'N/A': 
        meta_parts.append(str(film['year']))
    
    if film.get('tmdb_runtime'):
        meta_parts.append(f"{film['tmdb_runtime']} min")
    elif film.get('runtime'):
        meta_parts.append(f"{film['runtime']} min")

    if film.get('genres'): # Assuming List from scraper
        if isinstance(film['genres'], list):
            # Take top 2 genres to save space
            meta_parts.append("/".join(film['genres'][:2]))
        
    meta_text = "  |  ".join(meta_parts)
    draw.text((left_x + text_indent, cursor_y), meta_text, font=fonts['meta'], fill=(200, 200, 200))
    cursor_y += 45
    
    # --- JAPANESE TITLE (Auto-Fit) ---
    jp_title = film.get('clean_title_jp') or film.get('movie_title', 'No Title')
    jp_font, jp_height = fit_text_to_width(draw, jp_title, BOLD_FONT_PATH, content_width - text_indent, 80)
    draw.text((left_x + text_indent, cursor_y), jp_title, font=jp_font, fill=(255, 255, 255))
    cursor_y += jp_height + 20
    
    # --- ENGLISH TITLE ---
    if film.get('movie_title_en'):
        en_title = film.get('movie_title_en').upper()
        en_font, en_height = fit_text_to_width(draw, en_title, BOLD_FONT_PATH, content_width - text_indent, 40)
        draw.text((left_x + text_indent, cursor_y), en_title, font=en_font, fill=(255, 255, 255, 180))
        cursor_y += en_height + 25
    else:
        cursor_y += 10
        
    # --- DIRECTOR ---
    director = film.get('tmdb_director') or film.get('director')
    if director:
        draw.text((left_x + text_indent, cursor_y), f"Dir. {director}", font=fonts['meta'], fill=(220, 220, 220))
        cursor_y += 50
    
    # Divider
    cursor_y += 10
    draw.line([(left_x, cursor_y), (CANVAS_WIDTH - MARGIN, cursor_y)], fill=(255,255,255, 80), width=1)
    cursor_y += 30
    
    # --- LOGLINE (Optional) ---
    # Only show if we have plenty of vertical space left
    synopsis = film.get('tmdb_overview_jp')
    if synopsis and len(synopsis) > 5:
        # Check space
        remaining_h = CANVAS_HEIGHT - cursor_y - 200 # Reserve 200px for showtimes
        if remaining_h > 100:
            wrapper = textwrap.TextWrapper(width=38)
            lines = wrapper.wrap(text=synopsis)
            # Limit lines based on space
            max_lines = 3
            for line in lines[:max_lines]:
                draw.text((left_x, cursor_y), line, font=fonts['synopsis'], fill=(200, 200, 200))
                cursor_y += 38
            cursor_y += 30

    # --- SHOWTIMES ---
    sorted_cinemas = sorted(film['showings'].keys())
    for cinema in sorted_cinemas:
        if cursor_y > CANVAS_HEIGHT - 60: break
        
        times = sorted(film['showings'][cinema])
        times_str = " / ".join(times)
        
        draw.text((left_x, cursor_y), f"📍 {cinema}", font=fonts['cinema'], fill=(255, 210, 0))
        # Draw times to the right or below? Below is safer
        draw.text((left_x + 30, cursor_y + 40), times_str, font=fonts['times'], fill=(255, 255, 255))
        cursor_y += 90

    return canvas

def main():
    print("--- Starting V11 (Vibrant Block + Deep Data) ---")
    
    for f in glob.glob(str(BASE_DIR / "post_v2_*.png")): os.remove(f)
    date_str = get_today_str()
    
    if not SHOWTIMES_PATH.exists(): 
        print("No showtimes.json found.")
        return
        
    with open(SHOWTIMES_PATH, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
        
    # Filter & Group
    films_map = {}
    for item in raw_data:
        if item.get('date_text') != date_str: continue
        # Strict: Must have TMDB image to look good
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
        
        slide = draw_film_slide(film, img, fonts)
        slide.save(BASE_DIR / f"post_v2_image_{i+1:02}.png")
        
        # Caption Generation
        t_jp = film.get('clean_title_jp') or film.get('movie_title')
        caption_lines.append(f"🎬 {t_jp}")
        if film.get('movie_title_en'): 
            caption_lines.append(f"({film['movie_title_en']})")
            
        for cin, t in film['showings'].items():
            t.sort()
            caption_lines.append(f"📍 {cin}: {', '.join(t)}")
        caption_lines.append("")
        
    caption_lines.append("\nLink in Bio for Full Schedule")
    caption_lines.append("#TokyoIndieCinema #MiniTheater #MovieLog")
    
    with open(OUTPUT_CAPTION_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(caption_lines))
        
    print("Done. V11 Generated.")

if __name__ == "__main__":
    main()
