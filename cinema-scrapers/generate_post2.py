"""
Generate Instagram-ready image carousel (V10 - The "Cinematic Streamer" Edition).

Features:
- Blurred Backdrop Backgrounds (Netflix-style).
- Dynamic Font Sizing (Auto-shrink for long titles).
- Rich Metadata (Flags, Ratings, Runtimes).
- Synopsis & Tagline integration.
"""
from __future__ import annotations

import json
import random
import textwrap
import os
import glob
import requests
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"
BOLD_FONT_PATH = BASE_DIR / "NotoSansJP-Bold.ttf"
REGULAR_FONT_PATH = BASE_DIR / "NotoSansJP-Regular.ttf"
OUTPUT_CAPTION_PATH = BASE_DIR / "post_v2_caption.txt"

# Layout Dimensions
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350
MARGIN = 60 

# --- Helpers ---

def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")

def get_bilingual_date():
    today = datetime.now()
    # Returns "2023.11.22" and "Wed"
    return today.strftime("%Y.%m.%d"), today.strftime("%a")

def country_code_to_flag(code):
    """Converts 'US' to 🇺🇸."""
    if not code: return ""
    return "".join([chr(ord(c) + 127397) for c in code.upper()])

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

def create_cinematic_background(pil_img: Image.Image) -> Image.Image:
    """Creates a dark, blurred background from the movie image."""
    # Crop to portrait ratio to fill bg
    img_ratio = pil_img.width / pil_img.height
    target_ratio = CANVAS_WIDTH / CANVAS_HEIGHT
    
    if img_ratio > target_ratio:
        new_height = CANVAS_HEIGHT
        new_width = int(new_height * img_ratio)
        left = (new_width - CANVAS_WIDTH) // 2
        bg = pil_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        bg = bg.crop((left, 0, left + CANVAS_WIDTH, CANVAS_HEIGHT))
    else:
        new_width = CANVAS_WIDTH
        new_height = int(new_width / img_ratio)
        top = (new_height - CANVAS_HEIGHT) // 2
        bg = pil_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        bg = bg.crop((0, top, CANVAS_WIDTH, top + CANVAS_HEIGHT))

    # Heavy Blur
    bg = bg.filter(ImageFilter.GaussianBlur(radius=40))
    
    # Dark Overlay (Gradient)
    overlay = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0,0,0,0))
    draw = ImageDraw.Draw(overlay)
    
    # Top gradient (slight darkening)
    for y in range(400):
        alpha = int(150 * (1 - (y/400)))
        draw.line([(0,y), (CANVAS_WIDTH,y)], fill=(0,0,0,alpha))
        
    # Bottom gradient (heavy darkening for text)
    start_y = 600
    for y in range(start_y, CANVAS_HEIGHT):
        alpha = int(240 * ((y - start_y) / (CANVAS_HEIGHT - start_y)))
        draw.line([(0,y), (CANVAS_WIDTH,y)], fill=(0,0,0,alpha))
        
    # Solid dark floor
    draw.rectangle([(0, CANVAS_HEIGHT - 300), (CANVAS_WIDTH, CANVAS_HEIGHT)], fill=(10,10,10, 255))

    bg = bg.convert("RGBA")
    return Image.alpha_composite(bg, overlay).convert("RGB")

def fit_text_to_width(draw, text, font_path, max_width, max_font_size, min_font_size=30):
    """Dynamic font sizing."""
    size = max_font_size
    font = ImageFont.truetype(str(font_path), size)
    while size > min_font_size:
        bbox = draw.textbbox((0, 0), text, font=font)
        width = bbox[2] - bbox[0]
        if width <= max_width:
            return font, bbox[3] - bbox[1] # Return font and height
        size -= 2
        font = ImageFont.truetype(str(font_path), size)
    return font, size # Return min sized font

def create_hero_grid(images: list[Image.Image]) -> Image.Image:
    """Creates the 3x3 cover grid."""
    canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), (10, 10, 10))
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
        
        # Center crop
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
            
        # Darken slightly
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(0.7)
        canvas.paste(img, (x, y))
        
    return canvas

def draw_cover_slide(images, date_str, day_str):
    bg = create_hero_grid(images)
    draw = ImageDraw.Draw(bg)
    cx, cy = CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2
    
    # Stylish box
    box_w, box_h = 850, 500
    draw.rectangle([(cx - box_w//2, cy - box_h//2), (cx + box_w//2, cy + box_h//2)], fill=(0, 0, 0))
    
    # Double border effect
    border = 6
    draw.rectangle([(cx - box_w//2 + 20, cy - box_h//2 + 20), (cx + box_w//2 - 20, cy + box_h//2 - 20)], outline=(255, 255, 255), width=border)

    try:
        font_main = ImageFont.truetype(str(BOLD_FONT_PATH), 120)
        font_sub = ImageFont.truetype(str(BOLD_FONT_PATH), 50)
    except:
        font_main = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    draw.text((cx, cy - 80), "TOKYO", font=font_main, fill=(255, 255, 255), anchor="mm")
    draw.text((cx, cy + 40), "CINEMA GUIDE", font=font_sub, fill=(200, 200, 200), anchor="mm")
    draw.text((cx, cy + 140), f"{date_str} [{day_str}]", font=font_sub, fill=(255, 210, 0), anchor="mm")
    
    return bg

def draw_film_slide(film, img_obj):
    # 1. Generate Background
    canvas = create_cinematic_background(img_obj)
    draw = ImageDraw.Draw(canvas)
    
    # 2. Place Hero Image (Unblurred)
    # Place it at top, occupying ~50%
    hero_h = int(CANVAS_HEIGHT * 0.45)
    
    img_ratio = img_obj.width / img_obj.height
    target_ratio = CANVAS_WIDTH / hero_h
    
    if img_ratio > target_ratio:
        nw = int(hero_h * img_ratio)
        hero = img_obj.resize((nw, hero_h), Image.Resampling.LANCZOS)
        left = (nw - CANVAS_WIDTH) // 2
        hero = hero.crop((left, 0, left+CANVAS_WIDTH, hero_h))
    else:
        # If image is too tall/square, fit width and crop height
        nw = CANVAS_WIDTH
        nh = int(nw / img_ratio)
        hero = img_obj.resize((nw, nh), Image.Resampling.LANCZOS)
        hero = hero.crop((0, 0, CANVAS_WIDTH, hero_h))
        
    canvas.paste(hero, (0, 60)) # Slight top margin
    
    # 3. Text Block
    cursor_y = hero_h + 100
    content_w = CANVAS_WIDTH - (MARGIN * 2)
    
    # --- A. TITLES ---
    # Japanese Title (Dynamic Sizing)
    jp_title = film.get('clean_title_jp') or film.get('movie_title') or ""
    jp_font, jp_h = fit_text_to_width(draw, jp_title, BOLD_FONT_PATH, content_w, 90)
    draw.text((MARGIN, cursor_y), jp_title, font=jp_font, fill=(255, 255, 255))
    cursor_y += jp_h + 20
    
    # English Title
    en_title = film.get('movie_title_en')
    if en_title:
        en_font, en_h = fit_text_to_width(draw, en_title.upper(), BOLD_FONT_PATH, content_w, 45)
        draw.text((MARGIN, cursor_y), en_title.upper(), font=en_font, fill=(200, 200, 200))
        cursor_y += en_h + 40
    else:
        cursor_y += 20

    # --- B. METADATA ROW ---
    meta_items = []
    
    # Year
    if film.get('year'): meta_items.append(str(film['year']))
    
    # Runtime
    if film.get('tmdb_runtime'):
        meta_items.append(f"{film['tmdb_runtime']}m")
    elif film.get('runtime'):
        meta_items.append(f"{film['runtime']}")

    # Rating
    if film.get('vote_average') and float(film['vote_average']) > 0:
        score = float(film['vote_average'])
        meta_items.append(f"★ {score:.1f}")
        
    # Country Flags
    if film.get('production_countries'):
        flags = [country_code_to_flag(c) for c in film['production_countries'][:2]]
        meta_items.append(" ".join(flags))
        
    meta_text = "   |   ".join(meta_items)
    try:
        meta_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 32)
    except: meta_font = ImageFont.load_default()
    
    draw.text((MARGIN, cursor_y), meta_text, font=meta_font, fill=(255, 210, 0))
    cursor_y += 60
    
    # Divider
    draw.line([(MARGIN, cursor_y), (CANVAS_WIDTH - MARGIN, cursor_y)], fill=(80, 80, 80), width=2)
    cursor_y += 40
    
    # --- C. SYNOPSIS OR TAGLINE ---
    # Prefer Tagline for punchiness, else synopsis
    text_content = film.get('tmdb_tagline_jp') or film.get('tmdb_overview_jp')
    
    if text_content:
        try:
            desc_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 34)
        except: desc_font = ImageFont.load_default()
        
        # Limit to 3 lines max
        wrapped = textwrap.wrap(text_content, width=38)
        for line in wrapped[:3]:
            draw.text((MARGIN, cursor_y), line, font=desc_font, fill=(220, 220, 220))
            cursor_y += 50
        cursor_y += 30

    # --- D. SHOWTIMES ---
    # Group by cinema
    try:
        cinema_font = ImageFont.truetype(str(BOLD_FONT_PATH), 32)
        time_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 32)
    except:
        cinema_font = ImageFont.load_default()
        time_font = ImageFont.load_default()
        
    # Sort cinemas alphabetically or by priority? Alphabetical for now
    sorted_cinemas = sorted(film['showings'].keys())
    
    # Limit to remaining space
    max_y = CANVAS_HEIGHT - 80
    
    for cinema in sorted_cinemas:
        if cursor_y > max_y: break
        
        times = sorted(film['showings'][cinema])
        times_str = " / ".join(times)
        
        # Draw Cinema Name
        draw.text((MARGIN, cursor_y), f"📍 {cinema}", font=cinema_font, fill=(255, 255, 255))
        
        # Draw Times on same line if fits, or next line
        # Let's put times on next line for cleanliness
        cursor_y += 45
        draw.text((MARGIN + 40, cursor_y), times_str, font=time_font, fill=(180, 180, 180))
        cursor_y += 70 # Gap between cinemas

    return canvas

def main():
    print("--- Starting V10 (Cinematic Streamer Design) ---")
    
    # Clean old
    for f in glob.glob(str(BASE_DIR / "post_v2_*.png")): os.remove(f)
    
    date_str = get_today_str()
    if not SHOWTIMES_PATH.exists(): return
        
    with open(SHOWTIMES_PATH, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
        
    # Filter & Group
    films_map = {}
    for item in raw_data:
        if item.get('date_text') != date_str: continue
        # Strict: Must have TMDB image
        if not item.get('tmdb_backdrop_path'): continue
        
        key = item.get('tmdb_id') or item.get('movie_title')
        
        if key not in films_map:
            films_map[key] = item
            films_map[key]['showings'] = defaultdict(list)
            
        films_map[key]['showings'][item.get('cinema_name', '')].append(item.get('showtime', ''))

    all_films = list(films_map.values())
    
    # Shuffle but maybe prioritize ones with high ratings?
    # Let's just shuffle for variety
    random.shuffle(all_films)
    selected = all_films[:9] # Max 9 slides + 1 cover
    
    if not selected:
        print("No films found for today.")
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
        
        # Caption Building
        t_jp = film.get('clean_title_jp') or film.get('movie_title')
        line = f"🎬 {t_jp}"
        
        # Add Flag to caption too
        if film.get('production_countries'):
            flags = [country_code_to_flag(c) for c in film['production_countries'][:1]]
            line += " " + " ".join(flags)
            
        caption_lines.append(line)
        
        if film.get('movie_title_en'): 
            caption_lines.append(f"({film['movie_title_en']})")
            
        # Condensed times for caption
        for cin, t_list in film['showings'].items():
            t_list.sort()
            caption_lines.append(f"📍 {cin}: {', '.join(t_list)}")
        caption_lines.append("")
        
    caption_lines.append("\nDetails & Tickets via Link in Bio")
    caption_lines.append("#TokyoIndieCinema #MiniTheater #MovieLog")
    
    with open(OUTPUT_CAPTION_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(caption_lines))
        
    print("Done. V10 Generated.")

if __name__ == "__main__":
    main()
