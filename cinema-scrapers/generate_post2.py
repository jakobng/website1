"""
Generate Instagram-ready image carousel (V4 - Vibrant).
- Cover: Vertical Strip Mashup (5 films).
- Film Slides: Rich, Vibrant Backgrounds matched to image.
- Content: Titles + Metadata + Schedule (No Synopsis).
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

from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"
BOLD_FONT_PATH = BASE_DIR / "NotoSansJP-Bold.ttf"
REGULAR_FONT_PATH = BASE_DIR / "NotoSansJP-Regular.ttf"
OUTPUT_CAPTION_PATH = BASE_DIR / "post_v2_caption.txt"

TMDB_API_KEY = os.environ.get("TMDB_API_KEY")

# Layout Dimensions
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350
IMAGE_AREA_HEIGHT = 780 # Top 58%
TEXT_AREA_HEIGHT = CANVAS_HEIGHT - IMAGE_AREA_HEIGHT
MARGIN = 60 

# --- Helpers ---

def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")

def get_bilingual_date():
    today = datetime.now()
    return today.strftime("%Y.%m.%d"), today.strftime("%a")

# --- Image Processing & Color ---

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

def get_vibrant_bg_color(pil_img: Image.Image) -> tuple[int, int, int]:
    """
    Extracts the dominant hue but forces a rich, deep saturation/value
    to ensure the background is colorful but dark enough for white text.
    """
    # 1. Resize and Quantize to find dominant color
    small = pil_img.resize((150, 150))
    result = small.quantize(colors=10, method=2)
    dominant_color = result.getpalette()[:3]
    
    r, g, b = dominant_color
    h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
    
    # 2. Force "Vibrant Dark"
    # We ignore the original brightness/saturation to avoid gray/muddy colors.
    # We keep the Hue (H), but force high Saturation (S) and low-ish Value (V).
    
    new_s = 0.8  # High saturation for color richness
    new_v = 0.15 # Dark enough for white text to pop (0.0 is black, 1.0 is bright)
    
    # Special case: If the image is nearly black/white (very low saturation), keep it gray
    if s < 0.1:
        new_s = 0.0
        new_v = 0.15
        
    nr, ng, nb = colorsys.hsv_to_rgb(h, new_s, new_v)
    return (int(nr*255), int(ng*255), int(nb*255))

def create_strip_collage(images: list[Image.Image]) -> Image.Image:
    """Creates a vertical strip mashup of images."""
    canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0))
    
    # We will use 5 strips
    num_strips = 5
    strip_width = CANVAS_WIDTH // num_strips
    
    # Ensure we have enough images by cycling
    pool = images.copy()
    while len(pool) < num_strips:
        pool += images
    random.shuffle(pool)
    
    for i in range(num_strips):
        img = pool[i]
        
        # Resize height to match canvas, maintaining aspect ratio
        img_ratio = img.width / img.height
        target_h = CANVAS_HEIGHT
        target_w = int(target_h * img_ratio)
        
        img_resized = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        
        # Crop the center vertical strip from the resized image
        center_x = img_resized.width // 2
        crop_left = center_x - (strip_width // 2)
        crop_right = crop_left + strip_width
        
        strip = img_resized.crop((crop_left, 0, crop_right, CANVAS_HEIGHT))
        
        # Paste into canvas
        x_pos = i * strip_width
        canvas.paste(strip, (x_pos, 0))
        
    return canvas

def resize_hero(pil_img: Image.Image) -> Image.Image:
    """Resizes image to fill the top area."""
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

# --- TMDB Fetcher ---

def fetch_tmdb_details(backdrop_path: str, movie_title: str):
    """Fetches metadata (Director, Genres, Year)."""
    if not TMDB_API_KEY: return {}
    
    search_url = "https://api.themoviedb.org/3/search/movie"
    params = {"api_key": TMDB_API_KEY, "query": movie_title, "language": "ja-JP"}
    
    try:
        resp = requests.get(search_url, params=params, timeout=5)
        results = resp.json().get('results', [])
        
        target_movie = None
        for m in results:
            if m.get('backdrop_path') == backdrop_path:
                target_movie = m
                break
        if not target_movie and results: target_movie = results[0]
        if not target_movie: return {}
        
        movie_id = target_movie['id']
        
        # Fetch Credits for Director
        details_url = f"https://api.themoviedb.org/3/movie/{movie_id}"
        en_resp = requests.get(details_url, params={"api_key": TMDB_API_KEY, "language": "en-US", "append_to_response": "credits"}, timeout=5)
        en_data = en_resp.json()
        
        director = ""
        for person in en_data.get("credits", {}).get("crew", []):
            if person['job'] == 'Director':
                director = person['name']
                break

        genres = [g['name'] for g in en_data.get('genres', [])[:2]]

        return {
            "en_title": en_data.get("title"),
            "year": en_data.get("release_date", "")[:4],
            "genres": genres,
            "director": director,
            "runtime": en_data.get("runtime")
        }
    except:
        return {}

# --- Draw Functions ---

def get_fonts():
    try:
        return {
            "cover_main": ImageFont.truetype(str(BOLD_FONT_PATH), 110),
            "cover_sub": ImageFont.truetype(str(BOLD_FONT_PATH), 45),
            "jp_title": ImageFont.truetype(str(BOLD_FONT_PATH), 60),
            "en_title": ImageFont.truetype(str(BOLD_FONT_PATH), 35),
            "meta": ImageFont.truetype(str(REGULAR_FONT_PATH), 28),
            "cinema": ImageFont.truetype(str(BOLD_FONT_PATH), 32),
            "times": ImageFont.truetype(str(REGULAR_FONT_PATH), 32),
        }
    except:
        return {k: ImageFont.load_default() for k in ["cover_main", "cover_sub", "jp_title", "en_title", "meta", "cinema", "times"]}

def draw_cover_slide(images, fonts, date_str, day_str):
    # 1. Vertical Strip Collage
    bg = create_strip_collage(images)
    
    draw = ImageDraw.Draw(bg)
    cx, cy = CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2
    
    # 2. Main Text Box (Yellow)
    box_width = 800
    box_height = 600
    box_x1 = cx - box_width // 2
    box_y1 = cy - box_height // 2
    box_x2 = cx + box_width // 2
    box_y2 = cy + box_height // 2
    
    # Draw Shadow
    draw.rectangle([(box_x1 + 20, box_y1 + 20), (box_x2 + 20, box_y2 + 20)], fill=(0,0,0))
    # Draw Box
    draw.rectangle([(box_x1, box_y1), (box_x2, box_y2)], fill=(255, 210, 0)) # Brand Yellow
    
    # 3. Text
    # Date
    draw.text((cx, cy - 200), f"{date_str} {day_str}", font=fonts['cover_sub'], fill=(0,0,0), anchor="mm")
    
    # "SCREENING TODAY"
    draw.text((cx, cy), "SCREENING\nTODAY IN\nTOKYO", font=fonts['cover_main'], fill=(0,0,0), align="center", anchor="mm")
    
    # Sub
    draw.text((cx, cy + 200), "本日の厳選作品", font=fonts['cover_sub'], fill=(0,0,0), anchor="mm")
    
    return bg

def draw_film_slide(film, img_obj, fonts):
    # 1. Dynamic Background Color
    bg_color = get_vibrant_bg_color(img_obj)
    canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), bg_color)
    draw = ImageDraw.Draw(canvas)
    
    # 2. Paste Hero Image
    hero = resize_hero(img_obj)
    canvas.paste(hero, (0,0))
    
    # 3. Info Area
    cursor_y = IMAGE_AREA_HEIGHT + 50
    left_x = MARGIN
    
    # Yellow Accent Bar
    draw.rectangle([(left_x, cursor_y + 5), (left_x + 8, cursor_y + 65)], fill=(255, 210, 0))
    text_indent = 35
    
    # JP Title
    wrapped_jp = textwrap.wrap(film['title'], width=18)
    for line in wrapped_jp:
        draw.text((left_x + text_indent, cursor_y), line, font=fonts['jp_title'], fill=(255,255,255))
        cursor_y += 80
    
    # EN Title (Uppercase)
    if film.get('en_title'):
        draw.text((left_x + text_indent, cursor_y), str(film['en_title']).upper(), font=fonts['en_title'], fill=(200,200,200))
        cursor_y += 50
        
    cursor_y += 20
    
    # Metadata (Year | Genre | Dir)
    meta_parts = []
    if film.get('year'): meta_parts.append(film['year'])
    if film.get('genres'): meta_parts.append(", ".join(film['genres']))
    if film.get('runtime'): meta_parts.append(f"{film['runtime']}min")
    
    if meta_parts:
        draw.text((left_x, cursor_y), " | ".join(meta_parts), font=fonts['meta'], fill=(180,180,180))
        cursor_y += 40
        
    if film.get('director'):
        draw.text((left_x, cursor_y), f"Dir: {film['director']}", font=fonts['meta'], fill=(180,180,180))
        cursor_y += 40
        
    # Divider
    cursor_y += 15
    draw.line([(left_x, cursor_y), (CANVAS_WIDTH - MARGIN, cursor_y)], fill=(255,255,255, 100), width=1)
    cursor_y += 35
    
    # Showtimes
    for cinema, times in film['showings'].items():
        if cursor_y > CANVAS_HEIGHT - 60: break
        
        draw.text((left_x, cursor_y), f"📍 {cinema}", font=fonts['cinema'], fill=(255,210,0))
        
        times_str = " / ".join(times)
        draw.text((left_x, cursor_y + 45), times_str, font=fonts['times'], fill=(255,255,255))
        
        cursor_y += 100

    return canvas

# --- Main ---

def main():
    print("--- Starting V4 (Vibrant) Generation ---")
    for f in glob.glob(str(BASE_DIR / "post_v2_*.png")): os.remove(f)
    
    date_str = get_today_str()
    if not SHOWTIMES_PATH.exists(): return
        
    with open(SHOWTIMES_PATH, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
        
    films_map = {}
    for item in raw_data:
        if item.get('date_text') != date_str: continue
        if not item.get('tmdb_backdrop_path'): continue
        
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
    selected = all_films[:9]
    
    if not selected:
        print("No films found.")
        return

    print(f"Selected {len(selected)} films.")
    
    fonts = get_fonts()
    slide_data = []
    all_images = []
    
    for film in selected:
        print(f"Processing: {film['title']}")
        details = fetch_tmdb_details(film['backdrop'], film['title'])
        film.update(details)
        
        img = download_image(film['backdrop'])
        if img:
            all_images.append(img)
            slide_data.append({"film": film, "img": img})
            
    # Cover Slide
    if all_images:
        d_str, day_str = get_bilingual_date()
        cover = draw_cover_slide(all_images, fonts, d_str, day_str)
        cover.save(BASE_DIR / "post_v2_image_00.png")
        
    # Film Slides
    caption_lines = [f"🗓️ {date_str} Tokyo Cinema Selection\n"]
    
    for i, item in enumerate(slide_data):
        film = item['film']
        img = item['img']
        
        # Sort times
        for k in film['showings']: film['showings'][k].sort()
        
        slide = draw_film_slide(film, img, fonts)
        slide.save(BASE_DIR / f"post_v2_image_{i+1:02}.png")
        
        caption_lines.append(f"🎬 {film['title']}")
        for cin, t in film['showings'].items():
            caption_lines.append(f"📍 {cin}: {', '.join(t)}")
        caption_lines.append("")
        
    caption_lines.append("\n#東京ミニシアター #映画 #tokyocinema")
    with open(OUTPUT_CAPTION_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(caption_lines))
        
    print("Done.")

if __name__ == "__main__":
    main()
