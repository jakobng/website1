"""
Generate Instagram-ready image carousel (V5 - API Enhanced).

FEATURES:
1. Cover Slide Mashup:
   - Level 1 (Default): Local Python "Vertical Strip" Collage.
   - Level 2 (+Cloudinary): Uploads collage & applies "Oil Paint" or "Vibrant" filters.
   - Level 3 (+Stability AI): Sends collage to AI to "re-imagine" as a painted poster.

2. Film Slides:
   - Uses "Vibrant Dark" color extraction for backgrounds.
   - Clean layout (No synopsis, big bold titles).
"""
from __future__ import annotations

import json
import random
import textwrap
import os
import glob
import requests
import colorsys
import io
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, ImageEnhance

# --- 3rd Party Imports (Optional) ---
try:
    import cloudinary
    import cloudinary.uploader
    import cloudinary.api
except ImportError:
    cloudinary = None

try:
    from stability_sdk import client
    import stability_sdk.interfaces.gooseai.generation.generation_pb2 as generation
except ImportError:
    client = None

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"
BOLD_FONT_PATH = BASE_DIR / "NotoSansJP-Bold.ttf"
REGULAR_FONT_PATH = BASE_DIR / "NotoSansJP-Regular.ttf"
OUTPUT_CAPTION_PATH = BASE_DIR / "post_v2_caption.txt"

# API KEYS
TMDB_API_KEY = os.environ.get("TMDB_API_KEY")
CLOUDINARY_URL = os.environ.get("CLOUDINARY_URL") # Format: cloudinary://api_key:api_secret@cloud_name
STABILITY_KEY = os.environ.get("STABILITY_KEY")

# Layout Dimensions
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350
IMAGE_AREA_HEIGHT = 780 
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

# --- Image Processing (Local) ---

def get_vibrant_bg_color(pil_img: Image.Image) -> tuple[int, int, int]:
    """Extracts a vibrant dominant color."""
    small = pil_img.resize((150, 150))
    result = small.quantize(colors=10, method=2)
    dominant_color = result.getpalette()[:3]
    
    r, g, b = dominant_color
    h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
    
    # Force high saturation and dark value for contrast
    new_s = 0.85 
    new_v = 0.18 
    if s < 0.1: # If greyscale, keep it greyscale
        new_s = 0.0
        new_v = 0.15
        
    nr, ng, nb = colorsys.hsv_to_rgb(h, new_s, new_v)
    return (int(nr*255), int(ng*255), int(nb*255))

def create_strip_collage(images: list[Image.Image]) -> Image.Image:
    """Creates the base vertical strip mashup locally."""
    canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0))
    num_strips = 5
    strip_width = CANVAS_WIDTH // num_strips
    
    pool = images.copy()
    while len(pool) < num_strips:
        pool += images
    random.shuffle(pool)
    
    for i in range(num_strips):
        img = pool[i]
        img_ratio = img.width / img.height
        target_h = CANVAS_HEIGHT
        target_w = int(target_h * img_ratio)
        
        img_resized = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        
        center_x = img_resized.width // 2
        crop_left = center_x - (strip_width // 2)
        crop_right = crop_left + strip_width
        
        strip = img_resized.crop((crop_left, 0, crop_right, CANVAS_HEIGHT))
        
        if i % 2 != 0: # Darken alternate strips for style
            enhancer = ImageEnhance.Brightness(strip)
            strip = enhancer.enhance(0.8)

        canvas.paste(strip, (i * strip_width, 0))
        
    return canvas

# --- API Enhancers ---

def enhance_with_cloudinary(pil_img: Image.Image) -> Image.Image:
    """Uploads to Cloudinary and applies an artistic filter."""
    if not cloudinary:
        print("⚠️ Cloudinary module not found. Skipping.")
        return pil_img
        
    print("✨ Uploading to Cloudinary for enhancement...")
    try:
        # 1. Convert PIL to Byte Stream
        img_byte_arr = io.BytesIO()
        pil_img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        # 2. Upload
        upload_resp = cloudinary.uploader.upload(img_byte_arr)
        public_id = upload_resp['public_id']
        
        # 3. Construct URL with Transformations
        # e_art:incognito gives a cool "movie poster" blended look
        # e_improve: auto-corrects color/contrast
        url, options = cloudinary.utils.cloudinary_url(
            public_id,
            transformation=[
                {'effect': "art:incognito"}, 
                {'effect': "improve"},
                {'quality': "auto"}
            ]
        )
        
        # 4. Download Result
        print(f"   Downloading enhanced image from: {url}")
        resp = requests.get(url)
        return Image.open(BytesIO(resp.content)).convert("RGB")
        
    except Exception as e:
        print(f"⚠️ Cloudinary Error: {e}")
        return pil_img

def enhance_with_stability(pil_img: Image.Image) -> Image.Image:
    """Sends image to Stability AI to 're-imagine' it."""
    if not client or not STABILITY_KEY:
        print("⚠️ Stability SDK/Key not found. Skipping.")
        return pil_img

    print("🎨 Sending to Stability AI for reimagining...")
    try:
        # Initialize API
        stability_api = client.StabilityInference(
            key=STABILITY_KEY,
            verbose=True,
            engine="stable-diffusion-xl-1024-v1-0", 
        )

        # Config
        answers = stability_api.generate(
            prompt="cinematic movie poster collage, unified artistic style, vibrant lighting, 8k resolution, masterpiece",
            init_image=pil_img,
            start_schedule=0.65, # 0.65 means "Keep 65% of original structure, change 35%"
            steps=30,
            cfg_scale=8.0,
            width=1024, # Resize closer to SDXL native
            height=1344,
            sampler=generation.SAMPLER_K_DPMPP_2M
        )

        for resp in answers:
            for artifact in resp.artifacts:
                if artifact.finish_reason == generation.FILTER:
                    print("⚠️ Stability Safety Filter triggered.")
                if artifact.type == generation.ARTIFACT_IMAGE:
                    img = Image.open(io.BytesIO(artifact.binary))
                    return img.resize((CANVAS_WIDTH, CANVAS_HEIGHT)) # Resize back to canvas
        
    except Exception as e:
        print(f"⚠️ Stability AI Error: {e}")
        
    return pil_img


# --- Drawing ---

def get_fonts():
    try:
        return {
            "cover_main": ImageFont.truetype(str(BOLD_FONT_PATH), 110),
            "cover_sub": ImageFont.truetype(str(BOLD_FONT_PATH), 45),
            "jp_title": ImageFont.truetype(str(BOLD_FONT_PATH), 65),
            "en_title": ImageFont.truetype(str(BOLD_FONT_PATH), 38),
            "meta": ImageFont.truetype(str(REGULAR_FONT_PATH), 28),
            "cinema": ImageFont.truetype(str(BOLD_FONT_PATH), 34),
            "times": ImageFont.truetype(str(REGULAR_FONT_PATH), 34),
        }
    except:
        return {k: ImageFont.load_default() for k in ["cover_main", "cover_sub", "jp_title", "en_title", "meta", "cinema", "times"]}

def draw_cover_slide(images, fonts, date_str, day_str):
    # 1. Base Collage (Local)
    bg = create_strip_collage(images)
    
    # 2. ENHANCE! (Check for Keys)
    if STABILITY_KEY:
        bg = enhance_with_stability(bg)
    elif CLOUDINARY_URL:
        bg = enhance_with_cloudinary(bg)
    else:
        print("ℹ️ No API keys found. Using local mashup.")

    draw = ImageDraw.Draw(bg)
    cx, cy = CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2
    
    # 3. Central Sticker Box
    box_w, box_h = 800, 600
    box_x1, box_y1 = cx - box_w // 2, cy - box_h // 2
    box_x2, box_y2 = cx + box_w // 2, cy + box_h // 2
    
    draw.rectangle([(box_x1 + 20, box_y1 + 20), (box_x2 + 20, box_y2 + 20)], fill=(0, 0, 0)) # Shadow
    draw.rectangle([(box_x1, box_y1), (box_x2, box_y2)], fill=(255, 210, 0)) # Box
    
    draw.text((cx, cy - 200), f"{date_str} {day_str}", font=fonts['cover_sub'], fill=(0,0,0), anchor="mm")
    draw.text((cx, cy), "SCREENING\nTODAY IN\nTOKYO", font=fonts['cover_main'], fill=(0,0,0), align="center", anchor="mm", spacing=20)
    draw.text((cx, cy + 200), "本日の厳選作品", font=fonts['cover_sub'], fill=(0,0,0), anchor="mm")
    
    return bg

def draw_film_slide(film, img_obj, fonts):
    # (Same vibrant logic as V4)
    bg_color = get_vibrant_bg_color(img_obj)
    canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), bg_color)
    draw = ImageDraw.Draw(canvas)
    
    # Hero Image
    hero_aspect = CANVAS_WIDTH / IMAGE_AREA_HEIGHT
    img_aspect = img_obj.width / img_obj.height
    if img_aspect > hero_aspect:
        new_h = IMAGE_AREA_HEIGHT
        new_w = int(new_h * img_aspect)
        hero = img_obj.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (hero.width - CANVAS_WIDTH) // 2
        hero = hero.crop((left, 0, left + CANVAS_WIDTH, IMAGE_AREA_HEIGHT))
    else:
        new_w = CANVAS_WIDTH
        new_h = int(new_w / img_aspect)
        hero = img_obj.resize((new_w, new_h), Image.Resampling.LANCZOS)
        top = (hero.height - IMAGE_AREA_HEIGHT) // 2
        hero = hero.crop((0, top, CANVAS_WIDTH, top + IMAGE_AREA_HEIGHT))
        
    canvas.paste(hero, (0,0))
    
    # Info
    cursor_y = IMAGE_AREA_HEIGHT + 50
    left_x = MARGIN
    
    draw.rectangle([(left_x, cursor_y + 8), (left_x + 10, cursor_y + 75)], fill=(255, 210, 0))
    text_indent = 40
    
    wrapped_jp = textwrap.wrap(film['title'], width=16)
    for line in wrapped_jp:
        draw.text((left_x + text_indent, cursor_y), line, font=fonts['jp_title'], fill=(255,255,255))
        cursor_y += 85
    
    if film.get('en_title'):
        draw.text((left_x + text_indent, cursor_y), str(film['en_title']).upper(), font=fonts['en_title'], fill=(255,255,255, 180))
        cursor_y += 60
        
    cursor_y += 20
    meta_parts = []
    if film.get('year'): meta_parts.append(film['year'])
    if film.get('genres'): meta_parts.append("・".join(film['genres']))
    if film.get('runtime'): meta_parts.append(f"{film['runtime']}min")
    
    if meta_parts:
        draw.text((left_x, cursor_y), " | ".join(meta_parts), font=fonts['meta'], fill=(220,220,220))
        cursor_y += 40
        
    if film.get('director'):
        draw.text((left_x, cursor_y), f"Dir: {film['director']}", font=fonts['meta'], fill=(220,220,220))
        cursor_y += 40
        
    cursor_y += 10
    draw.line([(left_x, cursor_y), (CANVAS_WIDTH - MARGIN, cursor_y)], fill=(255,255,255, 80), width=1)
    cursor_y += 30
    
    for cinema, times in film['showings'].items():
        if cursor_y > CANVAS_HEIGHT - 60: break
        draw.text((left_x, cursor_y), f"📍 {cinema}", font=fonts['cinema'], fill=(255, 210, 0))
        times_str = " / ".join(times)
        draw.text((left_x, cursor_y + 45), times_str, font=fonts['times'], fill=(255,255,255))
        cursor_y += 110

    return canvas

# --- TMDB Fetcher (Same as V4) ---
def fetch_tmdb_details(backdrop_path: str, movie_title: str):
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
    except: return {}

# --- Main ---

def main():
    print("--- Starting V5 Generation (API Enhanced) ---")
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
        for k in film['showings']: film['showings'][k].sort()
        slide = draw_film_slide(film, img, fonts)
        slide.save(BASE_DIR / f"post_v2_image_{i+1:02}.png")
        
        caption_lines.append(f"🎬 {film['title']}")
        if film.get('en_title'):
            caption_lines.append(f"({film['en_title']})")
        for cin, t in film['showings'].items():
            caption_lines.append(f"📍 {cin}: {', '.join(t)}")
        caption_lines.append("")
        
    caption_lines.append("\n詳細はプロフィールリンクから / Full schedule in bio")
    caption_lines.append("#東京ミニシアター #映画 #映画館 #tokyocinema #minitheater")
    
    with open(OUTPUT_CAPTION_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(caption_lines))
        
    print("Done. V5 Generated.")

if __name__ == "__main__":
    main()
