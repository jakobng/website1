"""
Generate Instagram-ready image carousel (V7 - Vibrant & Smart Search).

FEATURES:
- Cover: 3x3 Grid.
- Design: "Hyper Vibrant" background (Rich Jewel Tones).
- Logic Update: Adds 'clean_title_for_search' to fix missing metadata
  caused by "4K", "Remaster", or extra text in cinema titles.
"""
from __future__ import annotations

import json
import random
import textwrap
import os
import glob
import requests
import colorsys
import re  # Added for title cleaning
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

TMDB_API_KEY = os.environ.get("TMDB_API_KEY")

# Layout Dimensions (Instagram Portrait 4:5)
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

def clean_title_for_search(title: str) -> str:
    """
    Removes common 'cinema noise' from titles to improve TMDB search success.
    E.g., '落下の王国 4Kデジタルリマスター' -> '落下の王国'
    """
    # List of noise patterns (Regex)
    noise_patterns = [
        r"4K", r"２Ｋ", r"2K",
        r"デジタルリマスター", r"リマスター",
        r"完全版", r"劇場版", r"ディレクターズ・カット",
        r"版", r"上映", r"記念",
        r"（.*?）", r"\(.*?\)", # Remove text in parentheses
    ]
    
    cleaned = title
    for pattern in noise_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    
    # Remove extra spaces
    return " ".join(cleaned.split())

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

def get_vibrant_bg(pil_img: Image.Image) -> tuple[int, int, int]:
    """Extracts dominant hue and forces HYPER VIBRANCE."""
    small = pil_img.resize((150, 150))
    result = small.quantize(colors=10, method=2)
    dominant_color = result.getpalette()[:3]
    
    r, g, b = dominant_color
    h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
    
    new_s = 0.9 
    new_v = 0.3
    
    if s < 0.1: # Grayscale handling
        new_s = 0.0
        new_v = 0.25 
        
    nr, ng, nb = colorsys.hsv_to_rgb(h, new_s, new_v)
    return (int(nr*255), int(ng*255), int(nb*255))

def create_3x3_grid(images: list[Image.Image]) -> Image.Image:
    """Creates a 3x3 Grid Collage."""
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
        enhancer = ImageEnhance.Brightness(cell_img)
        cell_img = enhancer.enhance(0.9)
        
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

# --- TMDB Fetcher ---

def fetch_tmdb_details(backdrop_path: str, original_title: str):
    """Fetches metadata using a CLEANED title search."""
    if not TMDB_API_KEY: return {}
    
    # 1. Clean the title (remove "4K", "Remaster", etc.)
    search_query = clean_title_for_search(original_title)
    print(f"   > Searching TMDB for: '{search_query}' (Original: '{original_title}')")
    
    search_url = "https://api.themoviedb.org/3/search/movie"
    params = {"api_key": TMDB_API_KEY, "query": search_query, "language": "ja-JP"}
    
    try:
        resp = requests.get(search_url, params=params, timeout=5)
        results = resp.json().get('results', [])
        
        target_movie = None
        
        # A. Try to find exact backdrop match in results
        for m in results:
            if m.get('backdrop_path') == backdrop_path:
                target_movie = m
                break
        
        # B. Fallback: Just take the first result if we have one
        if not target_movie and results:
            target_movie = results[0]
            
        if not target_movie:
            print("   > No TMDB match found.")
            return {}
        
        movie_id = target_movie['id']
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
    except Exception as e:
        print(f"Error fetching details: {e}")
        return {}

# --- Draw Functions ---

def get_fonts():
    try:
        return {
            "cover_main": ImageFont.truetype(str(BOLD_FONT_PATH), 110),
            "cover_sub": ImageFont.truetype(str(BOLD_FONT_PATH), 45),
            "jp_title": ImageFont.truetype(str(BOLD_FONT_PATH), 70),
            "en_title": ImageFont.truetype(str(BOLD_FONT_PATH), 36),
            "meta": ImageFont.truetype(str(REGULAR_FONT_PATH), 28),
            "cinema": ImageFont.truetype(str(BOLD_FONT_PATH), 34),
            "times": ImageFont.truetype(str(REGULAR_FONT_PATH), 34),
        }
    except:
        return {k: ImageFont.load_default() for k in ["cover_main", "cover_sub", "jp_title", "en_title", "meta", "cinema", "times"]}

def draw_cover_slide(images, fonts, date_str, day_str):
    bg = create_3x3_grid(images)
    draw = ImageDraw.Draw(bg)
    cx, cy = CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2
    
    box_w, box_h = 800, 550
    box_x1, box_y1 = cx - box_w // 2, cy - box_h // 2
    box_x2, box_y2 = cx + box_w // 2, cy + box_h // 2
    
    draw.rectangle([(box_x1 + 15, box_y1 + 15), (box_x2 + 15, box_y2 + 15)], fill=(0, 0, 0))
    draw.rectangle([(box_x1, box_y1), (box_x2, box_y2)], fill=(255, 210, 0))
    
    draw.text((cx, cy - 160), f"{date_str} {day_str}", font=fonts['cover_sub'], fill=(0,0,0), anchor="mm")
    draw.text((cx, cy + 20), "SCREENING\nTODAY IN\nTOKYO", font=fonts['cover_main'], fill=(0,0,0), align="center", anchor="mm", spacing=20)
    return bg

def draw_film_slide(film, img_obj, fonts):
    bg_color = get_vibrant_bg(img_obj)
    canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), bg_color)
    draw = ImageDraw.Draw(canvas)
    
    hero = resize_hero(img_obj)
    canvas.paste(hero, (0,0))
    
    cursor_y = IMAGE_AREA_HEIGHT + 50 
    left_x = MARGIN
    
    draw.rectangle([(left_x, cursor_y + 10), (left_x + 8, cursor_y + 80)], fill=(255, 210, 0))
    text_indent = 35
    
    wrapped_jp = textwrap.wrap(film['title'], width=15)
    for line in wrapped_jp:
        draw.text((left_x + text_indent, cursor_y), line, font=fonts['jp_title'], fill=(255,255,255))
        cursor_y += 90
    
    if film.get('en_title'):
        draw.text((left_x + text_indent, cursor_y), str(film['en_title']).upper(), font=fonts['en_title'], fill=(255,255,255, 180))
        cursor_y += 60
        
    cursor_y += 20
    
    meta_parts = []
    if film.get('year'): meta_parts.append(film['year'])
    if film.get('genres'): meta_parts.append("・".join(film['genres']))
    if film.get('runtime'): meta_parts.append(f"{film['runtime']}min")
    
    if meta_parts:
        draw.text((left_x, cursor_y), " | ".join(meta_parts), font=fonts['meta'], fill=(255,255,255))
        cursor_y += 40
        
    if film.get('director'):
        draw.text((left_x, cursor_y), f"Dir: {film['director']}", font=fonts['meta'], fill=(255,255,255))
        cursor_y += 40
        
    cursor_y += 15
    draw.line([(left_x, cursor_y), (CANVAS_WIDTH - MARGIN, cursor_y)], fill=(255,255,255, 100), width=1)
    cursor_y += 35
    
    for cinema, times in film['showings'].items():
        if cursor_y > CANVAS_HEIGHT - 60: break
        draw.text((left_x, cursor_y), f"📍 {cinema}", font=fonts['cinema'], fill=(255, 210, 0))
        times_str = " / ".join(times)
        draw.text((left_x, cursor_y + 45), times_str, font=fonts['times'], fill=(255,255,255))
        cursor_y += 110

    return canvas

# --- Main ---

def main():
    print("--- Starting V7 Generation (Vibrant + Smart Search) ---")
    
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
    
    if not selected: return

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
            
    if all_images:
        d_str, day_str = get_bilingual_date()
        cover = draw_cover_slide(all_images, fonts, d_str, day_str)
        cover.save(BASE_DIR / "post_v2_image_00.png")
        
    caption_lines = [f"🗓️ {date_str} Tokyo Cinema Selection\n"]
    
    for i, item in enumerate(slide_data):
        film = item['film']
        img = item['img']
        for k in film['showings']: film['showings'][k].sort()
        
        slide = draw_film_slide(film, img, fonts)
        slide.save(BASE_DIR / f"post_v2_image_{i+1:02}.png")
        
        caption_lines.append(f"🎬 {film['title']}")
        if film.get('en_title'): caption_lines.append(f"({film['en_title']})")
        for cin, t in film['showings'].items():
            caption_lines.append(f"📍 {cin}: {', '.join(t)}")
        caption_lines.append("")
        
    caption_lines.append("\n詳細はプロフィールリンクから / Full schedule in bio")
    caption_lines.append("#東京ミニシアター #映画 #映画館")
    
    with open(OUTPUT_CAPTION_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(caption_lines))
        
    print("Done. V7 Generated.")

if __name__ == "__main__":
    main()
