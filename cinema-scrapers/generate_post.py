"""
Generate Instagram-ready image (Single Hero Only).

VERSION: SINGLE HERO TEST
- Hero Design: Fetches a high-res movie backdrop from TMDB.
- Logic: Stops immediately after generating the first slide.
"""
from __future__ import annotations

import json
import math
import random
import re
import os
import requests
import glob
import time
import colorsys
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Tuple
from PIL import Image, ImageDraw, ImageFont

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"
BOLD_FONT_PATH = BASE_DIR / "NotoSansJP-Bold.ttf"
REGULAR_FONT_PATH = BASE_DIR / "NotoSansJP-Regular.ttf"
OUTPUT_CAPTION_PATH = BASE_DIR / "post_caption.txt"
TMDB_API_KEY = os.environ.get("TMDB_API_KEY")

CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350
MARGIN = 60 

# --- Utility Functions ---
def load_showtimes() -> List[Dict]:
    try:
        with SHOWTIMES_PATH.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return []

def generate_fallback_burst() -> Image.Image:
    """Generates a Solar Burst gradient fallback."""
    img = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    center_x, center_y = CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2
    max_radius = int(math.sqrt((CANVAS_WIDTH/2)**2 + (CANVAS_HEIGHT/2)**2))
    
    for r in range(max_radius, 0, -2):
        t = r / max_radius
        t_adj = t ** 0.6
        draw.ellipse([center_x - r, center_y - r, center_x + r, center_y + r], fill=(int(255*t_adj), int(200*t_adj), int(100)))
    return img

def fetch_tmdb_backdrop(movie_title: str) -> Tuple[Image.Image, str] | None:
    if not TMDB_API_KEY: return None
    try:
        search_url = f"https://api.themoviedb.org/3/search/movie"
        params = {"api_key": TMDB_API_KEY, "query": movie_title, "language": "ja-JP"}
        time.sleep(0.1)
        response = requests.get(search_url, params=params)
        data = response.json()
        if not data.get("results"): return None
        
        movie = next((res for res in data["results"] if res.get("backdrop_path")), None)
        if not movie: return None
            
        image_url = f"https://image.tmdb.org/t/p/w1280{movie['backdrop_path']}"
        print(f"   [TMDB] Found: {movie.get('title')} -> {image_url}")
        
        img = Image.open(BytesIO(requests.get(image_url).content)).convert("RGB")
        
        # Crop to Portrait
        target_ratio = CANVAS_WIDTH / CANVAS_HEIGHT
        if (img.width / img.height) > target_ratio:
            new_width = int(img.height * target_ratio)
            img = img.crop(((img.width - new_width) // 2, 0, (img.width - new_width) // 2 + new_width, img.height))
        else:
            new_height = int(img.width / target_ratio)
            img = img.crop((0, (img.height - new_height) // 2, img.width, (img.height - new_height) // 2 + new_height))
            
        return img.resize((CANVAS_WIDTH, CANVAS_HEIGHT), Image.Resampling.LANCZOS), movie.get('title')
    except Exception as e:
        print(f"TMDB Error: {e}")
        return None

def draw_hero_slide(todays_titles: List[str]) -> Image.Image:
    # 1. Try to find an image
    random.shuffle(todays_titles)
    bg_image, credit_title = generate_fallback_burst(), ""
    
    for title in todays_titles:
        res = fetch_tmdb_backdrop(title)
        if res:
            bg_image, credit_title = res
            break

    # 2. Draw Overlay
    overlay = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0,0,0,0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle([0, 0, CANVAS_WIDTH, CANVAS_HEIGHT], fill=(0, 0, 0, 80)) # Dim
    
    # Text
    try:
        title_font = ImageFont.truetype(str(BOLD_FONT_PATH), 110)
        date_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 40)
    except:
        title_font = ImageFont.load_default()
        date_font = ImageFont.load_default()

    today = datetime.now()
    date_str = f"{today.strftime('%Y年%m月%d日')} / {today.strftime('%b %d, %Y')}"

    draw.text((CANVAS_WIDTH//2, CANVAS_HEIGHT//2 - 50), "TOKYO\nMINI THEATER", font=title_font, fill=(255,255,255), anchor="mm", align="center")
    draw.text((CANVAS_WIDTH//2, CANVAS_HEIGHT//2 + 100), date_str, font=date_font, fill=(220,220,220), anchor="mm")
    
    if credit_title:
        draw.text((CANVAS_WIDTH - 20, CANVAS_HEIGHT - 20), f"Image: {credit_title}", font=date_font, fill=(150,150,150), anchor="rb", font_size=24)

    return Image.alpha_composite(bg_image.convert("RGBA"), overlay).convert("RGB")

def main():
    # Clear old images
    for f in glob.glob(str(BASE_DIR / "post_image_*.png")): os.remove(f)

    showings = load_showtimes()
    titles = list(set(s.get('movie_title') for s in showings if s.get('movie_title')))
    
    # Generate ONLY the hero slide
    hero = draw_hero_slide(titles)
    hero.save(BASE_DIR / "post_image_00.png")
    print("✅ Saved post_image_00.png (Single Hero Slide)")

    # Simple Caption
    caption = f"🗓️ {datetime.now().strftime('%Y-%m-%d')}\nTokyo Cinema Listings.\n\nLink in bio for full schedule.\n\n#tokyocinema #minitheater"
    OUTPUT_CAPTION_PATH.write_text(caption, encoding="utf-8")

if __name__ == "__main__":
    main()
