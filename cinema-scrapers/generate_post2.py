"""
Generate Instagram-ready image carousel (V12 - Pixel Art Zine Edition).

- Design: 2-Color Pixel Noise Background (derived from poster).
- Typography: High-Contrast White with Black Stroke (Sticker style).
- Vibe: Retro, Indie, Lo-Fi.
- No Yellow.
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

# FONT LOGIC: Try to find a custom pixel font, fallback to Noto
CUSTOM_FONT_PATH = BASE_DIR / "custom_font.ttf" 
BOLD_FONT_PATH = BASE_DIR / "NotoSansJP-Bold.ttf"
REGULAR_FONT_PATH = BASE_DIR / "NotoSansJP-Regular.ttf"

OUTPUT_CAPTION_PATH = BASE_DIR / "post_v2_caption.txt"

# Layout Dimensions
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350
IMAGE_AREA_HEIGHT = int(CANVAS_HEIGHT * 0.50) 
MARGIN = 50

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

def extract_two_dominant_colors(pil_img: Image.Image) -> tuple[tuple, tuple]:
    """
    Finds the two most distinct dominant colors.
    """
    # Resize to speed up processing
    small = pil_img.resize((100, 100))
    # Quantize to 5 colors to find groups
    result = small.quantize(colors=5, method=2)
    palette = result.getpalette()
    
    # Get top 2 colors
    c1 = (palette[0], palette[1], palette[2])
    c2 = (palette[3], palette[4], palette[5])
    
    # Helper to boost saturation/brightness if too dull
    def boost_color(c):
        r, g, b = c
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        # Force high saturation and brightness for "Pixel Art" pop
        new_s = max(s, 0.6)
        new_v = max(v, 0.4)
        nr, ng, nb = colorsys.hsv_to_rgb(h, new_s, new_v)
        return (int(nr*255), int(ng*255), int(nb*255))

    return boost_color(c1), boost_color(c2)

def create_pixel_noise_bg(c1, c2, width, height, pixel_size=25):
    """
    Generates a 2-color random pixel noise pattern.
    """
    # Calculate grid size
    grid_w = width // pixel_size + 1
    grid_h = height // pixel_size + 1
    
    # Create tiny image
    small_canvas = Image.new("RGB", (grid_w, grid_h))
    pixels = small_canvas.load()
    
    for y in range(grid_h):
        for x in range(grid_w):
            # 50/50 Chance
            if random.random() > 0.5:
                pixels[x, y] = c1
            else:
                pixels[x, y] = c2
                
    # Resize up with NEAREST neighbor to keep hard pixel edges
    big_canvas = small_canvas.resize((width, height), Image.Resampling.NEAREST)
    return big_canvas

def draw_text_with_stroke(draw, pos, text, font, text_color=(255,255,255), stroke_color=(0,0,0), stroke_width=4, anchor=None):
    """Draws text with a thick hard outline."""
    x, y = pos
    draw.text((x, y), text, font=font, fill=text_color, stroke_width=stroke_width, stroke_fill=stroke_color, anchor=anchor)

def fit_text_to_width(draw, text, font_obj, max_width):
    """Recursively shrinks font size."""
    # We need to load the font path again to resize it
    # This function assumes font_obj has a 'path' attribute or we pass path
    # For simplicity, let's just use a simplified loop here
    return font_obj # Placeholder if we don't resize, but we should

def load_dynamic_font(path, size):
    try:
        return ImageFont.truetype(str(path), size)
    except:
        return ImageFont.load_default()

def draw_cover_slide(images, date_str, day_str):
    # Use first image for colors
    c1, c2 = extract_two_dominant_colors(images[0])
    bg = create_pixel_noise_bg(c1, c2, CANVAS_WIDTH, CANVAS_HEIGHT, pixel_size=40)
    
    # Darken center
    overlay = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0,0,0,0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle([(100, 300), (CANVAS_WIDTH-100, CANVAS_HEIGHT-300)], fill=(0,0,0, 200))
    bg.paste(overlay, (0,0), overlay)
    
    draw = ImageDraw.Draw(bg)
    
    title_font = load_dynamic_font(BOLD_FONT_PATH, 140)
    sub_font = load_dynamic_font(BOLD_FONT_PATH, 60)
    
    cx, cy = CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2
    
    draw_text_with_stroke(draw, (cx, cy - 100), "TOKYO", title_font, stroke_width=8, anchor="mm")
    draw_text_with_stroke(draw, (cx, cy + 20), "CINEMA", title_font, stroke_width=8, anchor="mm")
    
    draw_text_with_stroke(draw, (cx, cy + 180), f"{date_str} [{day_str}]", sub_font, text_color=(200, 200, 200), stroke_width=4, anchor="mm")
    
    return bg

def draw_film_slide(film, img_obj):
    # 1. Generate Pixel BG
    c1, c2 = extract_two_dominant_colors(img_obj)
    canvas = create_pixel_noise_bg(c1, c2, CANVAS_WIDTH, CANVAS_HEIGHT, pixel_size=20)
    draw = ImageDraw.Draw(canvas)
    
    # 2. Place Hero Image with Hard Border
    hero_h = int(CANVAS_HEIGHT * 0.50)
    
    # Resize Logic
    img_ratio = img_obj.width / img_obj.height
    target_ratio = CANVAS_WIDTH / hero_h
    
    if img_ratio > target_ratio:
        nw = int(hero_h * img_ratio)
        hero = img_obj.resize((nw, hero_h), Image.Resampling.LANCZOS)
        left = (nw - CANVAS_WIDTH) // 2
        hero = hero.crop((left, 0, left+CANVAS_WIDTH, hero_h))
    else:
        nw = CANVAS_WIDTH
        nh = int(nw / img_ratio)
        hero = img_obj.resize((nw, nh), Image.Resampling.LANCZOS)
        hero = hero.crop((0, 0, CANVAS_WIDTH, hero_h))
        
    # Add border to hero
    hero_w_border = ImageOps.expand(hero, border=10, fill='black')
    canvas.paste(hero_w_border, (-10, 50)) # Slight negative margin to bleed edges
    
    # 3. Text Layout
    cursor_y = hero_h + 80
    left_x = MARGIN
    
    # Determine Font (Custom or Noto)
    main_font_path = CUSTOM_FONT_PATH if CUSTOM_FONT_PATH.exists() else BOLD_FONT_PATH
    
    # --- INFO PILL (Year | Runtime) ---
    meta_text = ""
    if film.get('year'): meta_text += f"{film['year']}"
    if film.get('tmdb_runtime'): meta_text += f"  //  {film['tmdb_runtime']} MIN"
    
    meta_font = load_dynamic_font(REGULAR_FONT_PATH, 30)
    # Draw simple black box for meta
    draw.rectangle([(left_x, cursor_y), (left_x + 300, cursor_y + 40)], fill="black")
    draw.text((left_x + 10, cursor_y + 2), meta_text, font=meta_font, fill="white")
    
    cursor_y += 60
    
    # --- JAPANESE TITLE ---
    jp_title = film.get('clean_title_jp') or film.get('movie_title')
    jp_font = load_dynamic_font(main_font_path, 80)
    
    # Wrap title if too long
    wrapped_jp = textwrap.wrap(jp_title, width=12)
    for line in wrapped_jp:
        draw_text_with_stroke(draw, (left_x, cursor_y), line, jp_font, stroke_width=6)
        cursor_y += 90
        
    # --- ENGLISH TITLE ---
    if film.get('movie_title_en'):
        en_title = film.get('movie_title_en').upper()
        en_font = load_dynamic_font(main_font_path, 40)
        draw_text_with_stroke(draw, (left_x, cursor_y), en_title, en_font, text_color=(220,220,220), stroke_width=4)
        cursor_y += 50
        
    cursor_y += 20
    
    # --- DIRECTOR ---
    director = film.get('tmdb_director') or film.get('director')
    if director:
        dir_font = load_dynamic_font(REGULAR_FONT_PATH, 30)
        draw_text_with_stroke(draw, (left_x, cursor_y), f"DIR: {director}", dir_font, stroke_width=3)
        cursor_y += 50
        
    cursor_y += 20
    draw.line([(left_x, cursor_y), (CANVAS_WIDTH-MARGIN, cursor_y)], fill="black", width=5)
    cursor_y += 30
    
    # --- SHOWTIMES (Black Box Style) ---
    time_font = load_dynamic_font(BOLD_FONT_PATH, 32)
    
    sorted_cinemas = sorted(film['showings'].keys())
    for cinema in sorted_cinemas:
        if cursor_y > CANVAS_HEIGHT - 60: break
        
        times = sorted(film['showings'][cinema])
        times_str = " ".join(times)
        
        # Cinema Name
        draw_text_with_stroke(draw, (left_x, cursor_y), f"▼ {cinema}", time_font, stroke_width=4)
        cursor_y += 45
        
        # Times (in a simple text style)
        draw_text_with_stroke(draw, (left_x + 20, cursor_y), times_str, time_font, text_color=(200,200,200), stroke_width=3)
        cursor_y += 70

    return canvas

def main():
    print("--- Starting V12 (Pixel Art Zine) ---")
    
    for f in glob.glob(str(BASE_DIR / "post_v2_*.png")): os.remove(f)
    date_str = get_today_str()
    
    if not SHOWTIMES_PATH.exists(): return
        
    with open(SHOWTIMES_PATH, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
        
    # Filter & Group
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
    
    slide_data = []
    all_images = []
    
    for film in selected:
        print(f"Processing: {film.get('clean_title_jp')}")
        img = download_image(film.get('tmdb_backdrop_path'))
        if img:
            all_images.append(img)
            slide_data.append({"film": film, "img": img})
            
    if all_images:
        d_str, day_str = get_bilingual_date()
        cover = draw_cover_slide(all_images, d_str, day_str)
        cover.save(BASE_DIR / "post_v2_image_00.png")
        
    caption_lines = [f"🗓️ {date_str} Tokyo Cinema Selection\n"]
    
    for i, item in enumerate(slide_data):
        film = item['film']
        img = item['img']
        slide = draw_film_slide(film, img)
        slide.save(BASE_DIR / f"post_v2_image_{i+1:02}.png")
        
        # Caption
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
        
    print("Done. V12 Generated.")

if __name__ == "__main__":
    main()
