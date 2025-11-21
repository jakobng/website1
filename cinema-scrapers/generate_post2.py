"""
Generate Instagram-ready image carousel (V2 Updated - Dynamic Color & Collage).

FEATURES:
- Cover: 3x3 Grid Collage of all featured films.
- Design: Dynamic background color extracted from the movie image (Muted Dark Tone).
- Data: Fetches Director, Genre, and Synopsis from TMDB API.
- Output: Saves as 'post_v2_image_XX.png' to maintain workflow compatibility.
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
OUTPUT_CAPTION_PATH = BASE_DIR / "post_v2_caption.txt" # Kept as v2

TMDB_API_KEY = os.environ.get("TMDB_API_KEY")

# Layout Dimensions (Instagram Portrait 4:5)
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350
IMAGE_HEIGHT = 740  # Top ~55%
# Text area is the remaining bottom ~45%

# Padding
MARGIN = 50

# --- Helpers ---

def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")

def get_bilingual_date():
    today = datetime.now()
    # Returns: "2025.11.21", "Fri"
    return today.strftime("%Y.%m.%d"), today.strftime("%a")

# --- Image Processing & Color ---

def download_image(path: str) -> Image.Image | None:
    """Downloads image from TMDB."""
    if not path: return None
    url = f"https://image.tmdb.org/t/p/w1280{path}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return Image.open(BytesIO(resp.content)).convert("RGB")
    except:
        return None
    return None

def get_dynamic_bg_color(pil_img: Image.Image) -> tuple[int, int, int]:
    """
    Extracts a dominant color from the image and converts it to 
    a dark, muted background color for the text area.
    """
    # 1. Resize to small size for fast processing
    small_img = pil_img.resize((150, 150))
    # 2. Reduce to 5 colors
    result = small_img.quantize(colors=5, method=2)
    dominant_color = result.getpalette()[:3]
    
    # 3. Convert to HSV to manipulate
    r, g, b = dominant_color
    h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
    
    # 4. Adjust: Darken (Value) and Desaturate (Saturation)
    # value=0.12 makes it very dark (readable for white text)
    # saturation=min(s, 0.5) ensures it's not neon/distracting
    new_v = 0.12
    new_s = min(s, 0.5) 
    
    nr, ng, nb = colorsys.hsv_to_rgb(h, new_s, new_v)
    return (int(nr*255), int(ng*255), int(nb*255))

def create_collage(images: list[Image.Image]) -> Image.Image:
    """Creates a 3x3 collage of images for the cover slide."""
    canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0))
    
    cell_w = CANVAS_WIDTH // 3
    cell_h = CANVAS_HEIGHT // 3
    
    # Ensure we have enough images to fill 9 slots
    display_images = images.copy()
    while len(display_images) < 9:
        display_images += images
    
    random.shuffle(display_images)
    
    for i in range(9):
        row = i // 3
        col = i % 3
        
        img = display_images[i]
        
        # Scale image to fill the cell
        img_ratio = img.width / img.height
        cell_ratio = cell_w / cell_h
        
        if img_ratio > cell_ratio:
            new_h = cell_h
            new_w = int(new_h * img_ratio)
        else:
            new_w = cell_w
            new_h = int(new_w / img_ratio)
            
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        # Center Crop
        left = (img.width - cell_w) // 2
        top = (img.height - cell_h) // 2
        img = img.crop((left, top, left + cell_w, top + cell_h))
        
        # Darken slightly so white text pops later
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(0.6) 
        
        canvas.paste(img, (col * cell_w, row * cell_h))
        
    return canvas

def resize_hero(pil_img: Image.Image) -> Image.Image:
    """Resizes image to fill the top 55% area."""
    img_ratio = pil_img.width / pil_img.height
    target_ratio = CANVAS_WIDTH / IMAGE_HEIGHT
    
    if img_ratio > target_ratio:
        new_height = IMAGE_HEIGHT
        new_width = int(new_height * img_ratio)
    else:
        new_width = CANVAS_WIDTH
        new_height = int(new_width / img_ratio)
        
    pil_img = pil_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Crop Center
    left = (pil_img.width - CANVAS_WIDTH) // 2
    top = (pil_img.height - IMAGE_HEIGHT) // 2
    return pil_img.crop((left, top, left + CANVAS_WIDTH, top + IMAGE_HEIGHT))

# --- TMDB Data Fetching ---

def fetch_tmdb_details(backdrop_path: str, movie_title: str):
    """
    Fetches extended details (Director, Genres, Synopsis) from TMDB.
    """
    if not TMDB_API_KEY: return {}
    
    # 1. Search to get ID
    search_url = "https://api.themoviedb.org/3/search/movie"
    params = {"api_key": TMDB_API_KEY, "query": movie_title, "language": "ja-JP"}
    
    try:
        resp = requests.get(search_url, params=params, timeout=5)
        results = resp.json().get('results', [])
        
        target_movie = None
        # Try to match by backdrop path to ensure it's the exact same film
        for m in results:
            if m.get('backdrop_path') == backdrop_path:
                target_movie = m
                break
        
        if not target_movie and results:
            target_movie = results[0] # Fallback to first result
            
        if not target_movie: return {}
        
        movie_id = target_movie['id']
        
        # 2. Fetch English Details (Director, Genres, EN Title)
        details_url = f"https://api.themoviedb.org/3/movie/{movie_id}"
        en_resp = requests.get(details_url, params={"api_key": TMDB_API_KEY, "language": "en-US", "append_to_response": "credits"}, timeout=5)
        en_data = en_resp.json()
        
        # 3. Fetch Japanese Details (JP Synopsis)
        jp_resp = requests.get(details_url, params={"api_key": TMDB_API_KEY, "language": "ja-JP"}, timeout=5)
        jp_data = jp_resp.json()

        # Extract Director
        director = ""
        crew = en_data.get("credits", {}).get("crew", [])
        for person in crew:
            if person['job'] == 'Director':
                director = person['name']
                break

        # Extract Genres (Top 2)
        genres = [g['name'] for g in en_data.get('genres', [])[:2]]

        return {
            "en_title": en_data.get("title"),
            "en_overview": en_data.get("overview"),
            "jp_overview": jp_data.get("overview"),
            "year": en_data.get("release_date", "")[:4],
            "genres": genres,
            "director": director,
            "runtime": en_data.get("runtime")
        }
        
    except Exception as e:
        print(f"Error fetching details for {movie_title}: {e}")
        return {}

# --- Draw Functions ---

def get_fonts():
    try:
        return {
            "cover_main": ImageFont.truetype(str(BOLD_FONT_PATH), 110),
            "cover_sub": ImageFont.truetype(str(BOLD_FONT_PATH), 50),
            "jp_title": ImageFont.truetype(str(BOLD_FONT_PATH), 55),
            "en_title": ImageFont.truetype(str(BOLD_FONT_PATH), 32),
            "meta": ImageFont.truetype(str(REGULAR_FONT_PATH), 26),
            "synopsis_jp": ImageFont.truetype(str(REGULAR_FONT_PATH), 28),
            "synopsis_en": ImageFont.truetype(str(REGULAR_FONT_PATH), 24),
            "cinema": ImageFont.truetype(str(BOLD_FONT_PATH), 30),
            "times": ImageFont.truetype(str(REGULAR_FONT_PATH), 30),
        }
    except:
        # Fallback
        return {k: ImageFont.load_default() for k in ["cover_main", "cover_sub", "jp_title", "en_title", "meta", "synopsis_jp", "synopsis_en", "cinema", "times"]}

def draw_cover_slide(images, fonts, date_str, day_str):
    """Draws Slide 0: The Collage Cover."""
    # 1. Background Collage
    bg = create_collage(images)
    
    # 2. Overlay for readability
    overlay = Image.new("RGBA", bg.size, (0,0,0,120))
    bg = bg.convert("RGBA")
    bg = Image.alpha_composite(bg, overlay)
    draw = ImageDraw.Draw(bg)
    
    cx, cy = CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2
    
    # 3. Date Box (Yellow Accent)
    draw.rectangle([(cx - 150, cy - 220), (cx + 150, cy - 160)], fill=(255, 210, 0))
    draw.text((cx, cy - 190), f"{date_str} {day_str}", font=fonts['cover_sub'], fill=(20,20,20), anchor="mm")
    
    # 4. Main Text
    draw.text((cx, cy), "SCREENING\nTODAY IN\nTOKYO", font=fonts['cover_main'], fill=(255,255,255), align="center", anchor="mm")
    
    # 5. Sub Text
    draw.text((cx, cy + 200), "本日の厳選作品", font=fonts['cover_sub'], fill=(220,220,220), anchor="mm")
    
    return bg.convert("RGB")

def draw_film_slide(film, img_obj, fonts):
    """Draws Slides 1-9: Featured Films."""
    # 1. Dynamic Background Color
    bg_color = get_dynamic_bg_color(img_obj)
    canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), bg_color)
    draw = ImageDraw.Draw(canvas)
    
    # 2. Paste Hero Image
    hero = resize_hero(img_obj)
    canvas.paste(hero, (0,0))
    
    # 3. Text Info
    cursor_y = IMAGE_HEIGHT + 50
    left_x = MARGIN
    
    # --- Yellow Accent Bar ---
    draw.rectangle([(left_x, cursor_y + 5), (left_x + 8, cursor_y + 65)], fill=(255, 210, 0))
    text_indent = 35
    
    # --- JP Title (Wrap) ---
    wrapped_jp = textwrap.wrap(film['title'], width=19)
    for line in wrapped_jp:
        draw.text((left_x + text_indent, cursor_y), line, font=fonts['jp_title'], fill=(255,255,255))
        cursor_y += 75
    
    # --- EN Title ---
    if film.get('en_title'):
        # Upper case looks cleaner
        draw.text((left_x + text_indent, cursor_y), str(film['en_title']).upper(), font=fonts['en_title'], fill=(200,200,200))
        cursor_y += 55
    
    cursor_y += 10 # Spacer
    
    # --- Metadata Line (Year | Genres | Director) ---
    meta_parts = []
    if film.get('year'): meta_parts.append(film['year'])
    if film.get('genres'): meta_parts.append(" / ".join(film['genres']))
    if film.get('director'): meta_parts.append(f"Dir: {film['director']}")
    
    if meta_parts:
        meta_text = " | ".join(meta_parts)
        draw.text((left_x, cursor_y), meta_text, font=fonts['meta'], fill=(150,150,150))
        cursor_y += 45
        
    # --- Divider ---
    draw.line([(left_x, cursor_y), (CANVAS_WIDTH - MARGIN, cursor_y)], fill=(80,80,80), width=1)
    cursor_y += 30
    
    # --- Synopses (Max 2 lines each) ---
    # JP Synopsis
    jp_txt = film.get('jp_overview') or ""
    if jp_txt:
        wrapped_syn_jp = textwrap.wrap(jp_txt, width=42)
        for line in wrapped_syn_jp[:2]:
            draw.text((left_x, cursor_y), line, font=fonts['synopsis_jp'], fill=(230,230,230))
            cursor_y += 42
            
    # EN Synopsis
    en_txt = film.get('en_overview') or ""
    if en_txt:
        cursor_y += 5
        wrapped_syn_en = textwrap.wrap(en_txt, width=55)
        for line in wrapped_syn_en[:2]:
            draw.text((left_x, cursor_y), line, font=fonts['synopsis_en'], fill=(180,180,180))
            cursor_y += 35
            
    cursor_y += 25

    # --- Showtimes ---
    for cinema, times in film['showings'].items():
        if cursor_y > CANVAS_HEIGHT - 60: break
        
        # Cinema Name (Yellow)
        draw.text((left_x, cursor_y), f"📍 {cinema}", font=fonts['cinema'], fill=(255,210,0))
        
        # Times (White) - Display below cinema name
        times_str = " / ".join(times)
        cursor_y += 40
        draw.text((left_x + 40, cursor_y), times_str, font=fonts['times'], fill=(255,255,255))
        
        cursor_y += 60

    return canvas

# --- Main Execution ---

def main():
    print("--- Starting V2 (Design Upgrade) Generation ---")
    
    # 1. Cleanup
    for f in glob.glob(str(BASE_DIR / "post_v2_*.png")): os.remove(f)
    
    date_str = get_today_str()
    
    # 2. Load Showtimes
    if not SHOWTIMES_PATH.exists():
        print("No showtimes.json found.")
        return
        
    with open(SHOWTIMES_PATH, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
        
    # 3. Group Films
    films_map = {}
    for item in raw_data:
        if item.get('date_text') != date_str: continue
        if not item.get('tmdb_backdrop_path'): continue # Filter: Must have image
        
        t = item.get('movie_title')
        if t not in films_map:
            films_map[t] = {
                'title': t,
                'backdrop': item.get('tmdb_backdrop_path'),
                'showings': defaultdict(list)
            }
        films_map[t]['showings'][item.get('cinema_name', '')].append(item.get('showtime', ''))

    all_films = list(films_map.values())
    random.shuffle(all_films)
    selected = all_films[:9] # Max 9 films
    
    if not selected:
        print("No films with images found for today.")
        return

    print(f"Selected {len(selected)} films.")
    
    # 4. Prepare Data & Images
    slide_data = []
    all_images_for_cover = [] 
    
    for film in selected:
        print(f"Fetching details for: {film['title']}")
        # Fetch extra info (Director, Genre, Synopsis)
        details = fetch_tmdb_details(film['backdrop'], film['title'])
        film.update(details)
        
        # Download Image
        img = download_image(film['backdrop'])
        if img:
            all_images_for_cover.append(img)
            slide_data.append({"film": film, "img": img})
    
    fonts = get_fonts()
    
    # 5. Generate Cover (Slide 00)
    if all_images_for_cover:
        print("Drawing Cover Collage...")
        d_str, day_str = get_bilingual_date()
        cover = draw_cover_slide(all_images_for_cover, fonts, d_str, day_str)
        cover.save(BASE_DIR / "post_v2_image_00.png")
        
    # 6. Generate Film Slides (Slide 01-09)
    caption_lines = [f"🗓️ {date_str} Tokyo Cinema Selection\n"]
    
    for i, item in enumerate(slide_data):
        film = item['film']
        img = item['img']
        
        # Sort Showtimes
        for k in film['showings']: film['showings'][k].sort()
        
        # Draw
        slide = draw_film_slide(film, img, fonts)
        slide.save(BASE_DIR / f"post_v2_image_{i+1:02}.png")
        print(f"Saved Slide {i+1}: {film['title']}")
        
        # Build Caption
        caption_lines.append(f"🎬 {film['title']}")
        if film.get('en_title'):
            caption_lines.append(f"({film['en_title']})")
        for cin, t in film['showings'].items():
            caption_lines.append(f"📍 {cin}: {', '.join(t)}")
        caption_lines.append("")
        
    # 7. Save Caption File
    caption_lines.append("\n詳細はプロフィールリンクから / Full schedule in bio")
    caption_lines.append("#東京ミニシアター #映画 #映画館 #tokyocinema #minitheater")
    
    with open(OUTPUT_CAPTION_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(caption_lines))

    print("Done. Generated V2 files with V3 design.")

if __name__ == "__main__":
    main()
