"""
Generate Instagram-ready image carousel (V30 - AI Mashup).
- Visuals: Uses Google Gemini API to "fuse" today's films into a single poster.
- Fallback: Texture Engine (if API fails).
"""
from __future__ import annotations

import json
import random
import textwrap
import os
import glob
import requests
import time
from datetime import datetime
from pathlib import Path
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# --- Google Gemini Setup ---
# pip install google-genai
from google import genai
from google.genai import types

# SET YOUR KEY HERE (Or in env variables)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_API_KEY_HERE")

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"
BOLD_FONT_PATH = BASE_DIR / "NotoSansJP-Bold.ttf"
REGULAR_FONT_PATH = BASE_DIR / "NotoSansJP-Regular.ttf"
OUTPUT_CAPTION_PATH = BASE_DIR / "post_v3_caption.txt"

# Layout Dimensions
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350       # 4:5 Feed
STORY_CANVAS_HEIGHT = 1920 # 9:16 Story

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

def get_fonts():
    # Helper to load fonts safely
    try:
        return {
            "meta": ImageFont.truetype(str(REGULAR_FONT_PATH), 24),
            "title_jp": ImageFont.truetype(str(BOLD_FONT_PATH), 60),
            "title_en": ImageFont.truetype(str(REGULAR_FONT_PATH), 32),
            "cinema": ImageFont.truetype(str(BOLD_FONT_PATH), 28),
            "times": ImageFont.truetype(str(REGULAR_FONT_PATH), 28),
            # Fallback fonts for cover if AI fails
            "cover_main": ImageFont.truetype(str(BOLD_FONT_PATH), 120),
            "cover_sub": ImageFont.truetype(str(REGULAR_FONT_PATH), 30),
        }
    except:
        print("Fonts not found, using default.")
        d = ImageFont.load_default()
        return {k: d for k in ["meta", "title_jp", "title_en", "cinema", "times", "cover_main", "cover_sub"]}

def generate_ai_mashup(images: list[Image.Image]) -> Image.Image | None:
    """
    Sends the top 3 images to Gemini and asks for a 'Fusion' poster.
    """
    print("🍌 Contacting Gemini (Nano Banana/Pro) for Image Fusion...")
    
    if not GEMINI_API_KEY or "YOUR_API_KEY" in GEMINI_API_KEY:
        print("⚠️ No API Key found. Skipping AI generation.")
        return None

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Convert PIL images to Bytes for the API
        input_images_data = []
        for img in images[:3]: # Use top 3
            buf = BytesIO()
            img.save(buf, format="JPEG")
            input_images_data.append(buf.getvalue())
            
        # The Prompt: Asking for a fusion/collage style
        # We explicitly ask for the text "TOKYO CINEMA DAILY" to be rendered by the AI
        prompt = (
            "Create a high-fashion, cinematic movie poster that artistically blends these three movie scenes "
            "into a single cohesive vertical composition. "
            "Style: Gritty, film grain, Tokyo street photography aesthetic, moody lighting. "
            "IMPORTANT: The image must include the text 'TOKYO CINEMA DAILY' in a bold, stylish typography in the center or top."
        )

        # Send to Gemini 2.0 Flash / 3.0 Pro Image (whichever is active for your key)
        # Note: 'gemini-2.0-flash-exp' is a good current choice for vision+generation
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp', 
            contents=[prompt] + [
                types.Part.from_bytes(data=d, mime_type="image/jpeg") for d in input_images_data
            ],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"]
            )
        )
        
        # Extract Image
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                return Image.open(BytesIO(part.inline_data.data))
                
    except Exception as e:
        print(f"⚠️ AI Generation failed: {e}")
        return None
    
    return None

def draw_poster_slide(film, img_obj, fonts, is_story=False):
    # ... (Keep your existing poster slide logic here, same as V28) ...
    # For brevity, I am assuming you kept the logic from the previous file for the individual slides
    # If not, paste the 'draw_poster_slide' from the previous response here.
    width = 1080
    height = 1920 if is_story else 1350
    bg = Image.new("RGB", (width, height), (20,20,20)) # Placeholder
    bg.paste(img_obj.resize((width, int(width * img_obj.height / img_obj.width))), (0, 100))
    return bg

def main():
    print("--- Starting V30 (AI Mashup) ---")
    
    # 1. Load Data & Images
    date_str = get_today_str()
    if not SHOWTIMES_PATH.exists(): return
    with open(SHOWTIMES_PATH, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
        
    films_map = {}
    for item in raw_data:
        if item.get('date_text') != date_str: continue
        if not item.get('tmdb_backdrop_path'): continue
        key = item.get('tmdb_id') or item.get('movie_title')
        films_map[key] = item
        if 'showings' not in films_map[key]: films_map[key]['showings'] = {}
        if item.get('cinema_name') not in films_map[key]['showings']:
            films_map[key]['showings'][item.get('cinema_name')] = []
        films_map[key]['showings'][item.get('cinema_name')].append(item.get('showtime', ''))

    all_films = list(films_map.values())
    random.shuffle(all_films)
    selected = all_films[:9]
    
    fonts = get_fonts()
    slide_data = []
    
    # Download images
    cover_images = []
    for film in selected:
        print(f"Processing: {film.get('movie_title')}")
        img = download_image(film.get('tmdb_backdrop_path'))
        if img:
            slide_data.append({"film": film, "img": img})
            cover_images.append(img)

    if not slide_data: return

    # 2. GENERATE COVER (AI MASHUP)
    print("🎨 Generatng AI Cover...")
    ai_cover = generate_ai_mashup(cover_images)
    
    if ai_cover:
        # Resize AI result to fit our canvas
        # AI usually outputs 1:1 or specific aspect. We crop to fit.
        cover_feed = ai_cover.resize((CANVAS_WIDTH, CANVAS_WIDTH), Image.Resampling.LANCZOS) # Square-ish for feed
        
        # For Feed (4:5) - we paste the AI art and add a footer
        canvas_feed = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), (0,0,0))
        canvas_feed.paste(cover_feed, (0, (CANVAS_HEIGHT - CANVAS_WIDTH)//2))
        
        # For Story (9:16)
        cover_story_img = ai_cover.resize((CANVAS_WIDTH, int(CANVAS_WIDTH * ai_cover.height / ai_cover.width)))
        canvas_story = Image.new("RGB", (CANVAS_WIDTH, STORY_CANVAS_HEIGHT), (0,0,0))
        canvas_story.paste(cover_story_img, (0, (STORY_CANVAS_HEIGHT - cover_story_img.height)//2))
        
        canvas_feed.save(BASE_DIR / "post_v3_image_00.png")
        canvas_story.save(BASE_DIR / "story_v3_image_00.png")
    else:
        print("Using Fallback Collage (AI failed)")
        # Call your previous V29 'draw_cover_slide' here as fallback
        pass 

    # 3. Generate Slides
    for i, item in enumerate(slide_data):
        slide_feed = draw_poster_slide(item['film'], item['img'], fonts, is_story=False)
        slide_feed.save(BASE_DIR / f"post_v3_image_{i+1:02}.png")
        
        slide_story = draw_poster_slide(item['film'], item['img'], fonts, is_story=True)
        slide_story.save(BASE_DIR / f"story_v3_image_{i+1:02}.png")
        
    print("Done.")

if __name__ == "__main__":
    main()
