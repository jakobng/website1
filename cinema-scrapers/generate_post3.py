"""
generate_post3.py
The "Infinite Cinemascape" Protocol (V9 - Blended & Dynamic).

Fixes:
1. BLENDING: Feathers edges of cutouts so SDXL integrates them with lighting/shadows.
2. DEPTH: Adds drop shadows to input to guide SDXL's ambient occlusion.
3. VARIETY: Removes fixed seeds. Every run is unique.
4. LAYOUT: 1 Large Anchor + 2 Small Guests (Total 3).
"""

import os
import sys
import json
import random
import requests
import math
import time
from pathlib import Path
from datetime import datetime
from io import BytesIO

# --- LIBRARIES ---
try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
except ImportError:
    print("❌ PIL (Pillow) not found. Run: pip install Pillow")
    sys.exit(1)

try:
    import replicate
except ImportError:
    print("❌ Replicate not found. Run: pip install replicate")
    sys.exit(1)

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("❌ Google GenAI not found. Run: pip install google-genai")
    sys.exit(1)

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "cinema_assets"
OUTPUT_DIR = BASE_DIR
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"
STATE_FILE = BASE_DIR / "cinemascape_state.json"

# Secrets
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

ASSETS_DIR.mkdir(exist_ok=True)

# --- CLASS 1: THE ART DIRECTOR ---
class ArtDirector:
    def __init__(self, api_key: str):
        if not api_key: raise ValueError("⚠️ GEMINI_API_KEY missing!")
        self.client = genai.Client(api_key=api_key)

    def dream_scene(self, film_title: str, synopsis: str) -> dict:
        print(f"🧠 Art Director reading: {film_title}...")
        prompt = f"""
        Act as a Visual Futurist.
        FILM: "{film_title}"
        SYNOPSIS: "{synopsis}"

        1. Describe a BACKGROUND atmosphere (texture, lighting, mood).
        2. Pick a "BASE COLOR" (Hex code).
        3. Invent a "CONNECTOR OBJECT" (vertical line: rusty chain, neon cable, vine, beam, crack).
        
        OUTPUT JSON ONLY:
        {{
            "visual_prompt": "string (SDXL prompt)",
            "base_color_hex": "string (e.g. #FF0055)",
            "connector_object": "string",
            "connector_adjective": "string"
        }}
        """
        try:
            resp = self.client.models.generate_content(
                model="gemini-2.0-flash", contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            data = json.loads(resp.text)
            if isinstance(data, list): data = data[0] if data else {}
            return data
        except:
            return {
                "visual_prompt": "Gritty urban texture, concrete and shadows",
                "base_color_hex": "#333333",
                "connector_object": "steel cable",
                "connector_adjective": "heavy"
            }

# --- CLASS 2: CONTINUITY ---
class GridManager:
    def __init__(self):
        self.state = self._load()
    
    def _load(self):
        if STATE_FILE.exists():
            try: return json.loads(STATE_FILE.read_text())
            except: pass
        return {"last_exit_x": 0.5} 
    
    def get_entry(self) -> float:
        return self.state.get("last_exit_x", 0.5)
    
    def save(self, exit_x: float, anchor_title: str):
        self.state["last_exit_x"] = exit_x
        self.state["last_anchor"] = anchor_title
        STATE_FILE.write_text(json.dumps(self.state, indent=2))

# --- HELPERS ---
def generate_noise_layer(w, h, hex_color) -> Image.Image:
    try:
        color = ImageOps.colorize(Image.new("L", (w, h), 128), "black", hex_color)
    except:
        color = Image.new("RGB", (w, h), hex_color)
    noise = Image.effect_noise((w, h), 20).convert("RGB")
    blend = Image.blend(color.convert("RGB"), noise, 0.15)
    return blend.convert("RGBA")

def trim_transparent_borders(img: Image.Image) -> Image.Image:
    bbox = img.getbbox()
    if bbox: return img.crop(bbox)
    return img

def get_cutout(tmdb_id: int, suffix: str) -> Image.Image:
    if not suffix: return None
    filename = f"{tmdb_id}_{suffix.strip('/').replace('/','-')}.png"
    local_path = ASSETS_DIR / filename
    
    if local_path.exists():
        return Image.open(local_path).convert("RGBA")
    
    url = f"https://image.tmdb.org/t/p/w780{suffix}"
    print(f"⬇️ Downloading: {url}")
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        raw = Image.open(BytesIO(resp.content)).convert("RGBA")
        
        # Remove BG
        print(f"✂️ Cutting out {tmdb_id}...")
        temp_input = ASSETS_DIR / "temp_input.png"
        raw.save(temp_input)
        output = replicate.run(
            "lucataco/remove-bg:95fcc2a26d3899cd6c2691c900465aaeff466285a65c14638cc5f36f34befaf1",
            input={"image": open(temp_input, "rb")}
        )
        cutout = Image.open(BytesIO(requests.get(output).content)).convert("RGBA")
        cutout = trim_transparent_borders(cutout)
        cutout.save(local_path)
        return cutout
    except:
        return None

def apply_soft_mask(canvas: Image.Image, mask: Image.Image, img: Image.Image, x: int, y: int):
    """
    Pastes the image onto canvas with a shadow.
    Updates the mask with a FEATHERED edge to allow blending.
    """
    # 1. Draw Shadow on Canvas (Input)
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    # Extract alpha for shadow shape
    alpha = img.split()[3]
    shadow.paste((0,0,0,150), (0,0), mask=alpha)
    shadow = shadow.filter(ImageFilter.GaussianBlur(15))
    
    # Paste shadow slightly offset
    canvas.paste(shadow, (x + 10, y + 15), shadow)
    
    # 2. Paste Image on Canvas
    canvas.paste(img, (x, y), img)
    
    # 3. Create Feathered Protection Mask
    # Invert alpha: Black = Protect, White = Paint.
    # We want the core to be Black (Protected), but edges to be Grey (Blended).
    protection = ImageOps.invert(alpha)
    
    # Erode the protection slightly (pull back mask) so edges get painted over?
    # Or Blur it? Blurring makes edges grey.
    # Grey = 50% generation. This blends the cutout into the BG.
    protection = protection.filter(ImageFilter.GaussianBlur(5))
    
    # Paste into main mask
    mask.paste(protection, (x, y), alpha)

# --- MAIN ---
def main():
    print("🎬 Starting Cinemascape V9 (Blended & Dynamic)...")
    
    # FORCE RANDOMNESS (Fixes 'same every time')
    random.seed(time.time())

    if not SHOWTIMES_PATH.exists(): return
    with open(SHOWTIMES_PATH) as f: raw_data = json.load(f)

    # 1. DEDUPLICATE & SELECT
    unique_movies = {}
    for item in raw_data:
        title = item['movie_title']
        if title not in unique_movies:
            unique_movies[title] = item
        else:
            if not unique_movies[title].get('tmdb_backdrop_path') and item.get('tmdb_backdrop_path'):
                unique_movies[title] = item
    
    valid_films = list(unique_movies.values())
    valid_films = [f for f in valid_films if f.get('tmdb_backdrop_path') or f.get('tmdb_poster_path')]
    
    if not valid_films: return

    # Pick Anchor (Random or Rotated, let's allow Random now for variety)
    anchor = random.choice(valid_films)
    
    # Pick 2 Guests (Different from Anchor)
    others = [f for f in valid_films if f['movie_title'] != anchor['movie_title']]
    guests = random.sample(others, min(2, len(others)))
    
    print(f"📅 Anchor: {anchor['movie_title']}")
    print(f"🎥 Guests: {[g['movie_title'] for g in guests]}")

    # 2. ART DIRECT
    director = ArtDirector(GEMINI_API_KEY)
    style = director.dream_scene(anchor['movie_title'], anchor.get('synopsis', ''))
    print(f"🎨 Mood: {style['visual_prompt']}")

    # 3. PRIMED CANVAS
    W, H = 1080, 1352
    canvas = generate_noise_layer(W, H, style.get('base_color_hex', '#222222'))
    mask = Image.new("L", (W, H), 255) # White = Inpaint
    
    # 4. DRAW CONNECTOR GUIDE (Thick & Neon)
    grid = GridManager()
    entry_x = int(W * grid.get_entry())
    exit_x = int(W * random.uniform(0.3, 0.7))
    print(f"🔗 Line: {entry_x} -> {exit_x}")
    
    draw_guide = ImageDraw.Draw(canvas)
    # Neon Green/Cyan to cut through noise
    guide_color = (0, 255, 255, 200) 
    points = [(entry_x, 0), (entry_x, H * 0.2), (exit_x, H * 0.8), (exit_x, H)]
    draw_guide.line(points, fill=guide_color, width=25)

    # 5. PLACE ANCHOR (Large, Top)
    sfx = anchor.get('tmdb_backdrop_path') or anchor.get('tmdb_poster_path')
    hero = get_cutout(anchor['tmdb_id'], sfx)
    
    if hero:
        # Scale: 95% Width
        scale = (W * 0.95) / hero.width
        new_size = (int(hero.width * scale), int(hero.height * scale))
        hero = hero.resize(new_size, Image.Resampling.LANCZOS)
        
        x = (W - new_size[0]) // 2
        y = 60
        
        apply_soft_mask(canvas, mask, hero, x, y)

    # 6. PLACE GUESTS (2 Floating Below)
    start_y = 550
    end_y = 1200
    
    for i, g in enumerate(guests):
        sfx = g.get('tmdb_backdrop_path') or g.get('tmdb_poster_path')
        img = get_cutout(g['tmdb_id'], sfx)
        
        if img:
            # Scale: 60-80% Width (Varied)
            scale_pct = random.uniform(0.6, 0.8)
            scale = (W * scale_pct) / img.width
            new_size = (int(img.width * scale), int(img.height * scale))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Rotation (Organic)
            rot = random.uniform(-10, 10)
            img = img.rotate(rot, expand=True, resample=Image.Resampling.BICUBIC)
            
            # Position: Staggered
            y = int(start_y + (i * (end_y - start_y)/2) + random.randint(-50, 50))
            
            # Align relative to the Line
            # Interpolate line X
            line_x = entry_x + (exit_x - entry_x) * (y/H)
            
            if i % 2 == 0:
                x = int(line_x - new_size[0] + 50) # Left
            else:
                x = int(line_x - 50) # Right
                
            # Clamp
            x = max(-50, min(W - new_size[0] + 50, x))
            
            apply_soft_mask(canvas, mask, img, x, y)

    # 7. GENERATE
    canvas.convert("RGB").save("input.png")
    mask.save("mask.png")
    
    prompt = (
        f"Artistic magazine collage. {style['visual_prompt']}. "
        f"A {style['connector_adjective']} {style['connector_object']} glowing and connecting the images vertically. "
        f"The lighting wraps around the paper cutouts. High contrast, 8k."
    )
    
    print("🚀 Sending to SDXL...")
    try:
        output = replicate.run(
            "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
            input={
                "prompt": prompt,
                "negative_prompt": "text, watermark, ugly, distorted, sticker outlines, white borders",
                "image": open("input.png", "rb"),
                "mask": open("mask.png", "rb"),
                "prompt_strength": 0.85, 
                "width": W,
                "height": H
            }
        )
        
        url = output[0]
        final = Image.open(BytesIO(requests.get(url).content)).convert("RGB")
        final.save(OUTPUT_DIR / "post_v3_image_01.png")
        print("💾 Saved.")
        
        grid.save(exit_x / W, anchor['movie_title'])
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
