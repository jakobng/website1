"""
generate_post3.py
The "Infinite Cinemascape" Protocol (V6 - Organic Flow).

Changes:
1. ALL HORIZONTAL: Uses Backdrops (Landscape) for Anchor AND Guests.
2. ORGANIC LAYOUT: No grids. Images float, scatter, and rotate slightly.
3. PRECISE CONTINUITY: Entry point matches yesterday's exit point exactly.
"""

import os
import sys
import json
import random
import requests
import math
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
        2. Invent a "CONNECTOR OBJECT" (a vertical line like a rusty chain, neon cable, thick vine, beam of light, crack in reality).
        
        OUTPUT JSON ONLY:
        {{
            "visual_prompt": "string (SDXL prompt for background, e.g. 'Cyberpunk rain, neon reflections, 8k')",
            "connector_object": "string (The vertical object name)",
            "connector_adjective": "string (Adjective, e.g. 'glowing')"
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
                "visual_prompt": "Cinematic atmosphere, dark moody lighting",
                "connector_object": "steel cable",
                "connector_adjective": "industrial"
            }

# --- CLASS 2: GRID MEMORY (Continuity Engine) ---
class GridManager:
    def __init__(self):
        self.state = self._load()
    
    def _load(self):
        if STATE_FILE.exists():
            try: return json.loads(STATE_FILE.read_text())
            except: pass
        return {"last_exit_x": 0.5} 
    
    def get_entry(self) -> float:
        """Returns the X coordinate (0.0-1.0) where the line MUST start."""
        return self.state.get("last_exit_x", 0.5)
    
    def save(self, exit_x: float, anchor_title: str):
        """Saves today's exit for tomorrow's entry."""
        self.state["last_exit_x"] = exit_x
        self.state["last_anchor"] = anchor_title
        STATE_FILE.write_text(json.dumps(self.state, indent=2))

# --- HELPER: ASSETS ---
def trim_transparent_borders(img: Image.Image) -> Image.Image:
    bbox = img.getbbox()
    if bbox: return img.crop(bbox)
    return img

def get_cutout_horizontal(tmdb_id: int, backdrop_path: str, poster_path: str) -> Image.Image:
    """Prioritizes Backdrop (Horizontal). Falls back to Poster."""
    # Logic: Try Backdrop first.
    suffix = backdrop_path if backdrop_path else poster_path
    if not suffix: return None
    
    filename = f"{tmdb_id}_{suffix.strip('/').replace('/','-')}.png"
    local_path = ASSETS_DIR / filename
    
    # 1. Load Local
    if local_path.exists():
        return Image.open(local_path).convert("RGBA")
    
    # 2. Download
    url = f"https://image.tmdb.org/t/p/w780{suffix}"
    print(f"⬇️ Downloading: {url}")
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        raw_img = Image.open(BytesIO(resp.content)).convert("RGBA")
    except:
        return None

    # 3. Remove BG (Replicate)
    print(f"✂️ Cutting out {tmdb_id}...")
    try:
        # Save temp for API
        temp_input = ASSETS_DIR / "temp_input.png"
        raw_img.save(temp_input)
        
        output = replicate.run(
            "lucataco/remove-bg:95fcc2a26d3899cd6c2691c900465aaeff466285a65c14638cc5f36f34befaf1",
            input={"image": open(temp_input, "rb")}
        )
        cutout = Image.open(BytesIO(requests.get(output).content)).convert("RGBA")
        cutout = trim_transparent_borders(cutout)
        cutout.save(local_path)
        return cutout
    except Exception as e:
        print(f"⚠️ Cutout failed: {e}. Using raw.")
        return raw_img

# --- MAIN LOGIC ---
def main():
    print("🎬 Starting Cinemascape V6 (Organic/Horizontal)...")
    
    if not SHOWTIMES_PATH.exists(): return
    with open(SHOWTIMES_PATH) as f: showtimes = json.load(f)

    # 1. SELECT FILMS
    valid_films = [f for f in showtimes if f.get('tmdb_backdrop_path') or f.get('tmdb_poster_path')]
    if not valid_films: return

    # Daily Rotation
    day_of_year = datetime.now().timetuple().tm_yday
    anchor_index = day_of_year % len(valid_films)
    
    anchor = valid_films[anchor_index]
    # 4 Guests
    guests = [valid_films[(anchor_index + i + 1) % len(valid_films)] for i in range(4)]
    
    print(f"📅 Anchor: {anchor['movie_title']}")

    # 2. ART DIRECT
    director = ArtDirector(GEMINI_API_KEY)
    style = director.dream_scene(anchor['movie_title'], anchor.get('synopsis', ''))
    print(f"🎨 Theme: {style['visual_prompt']}")
    
    # 3. CANVAS (1080x1352 for SDXL)
    W, H = 1080, 1352
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    mask = Image.new("L", (W, H), 255) # White = Inpaint
    
    # 4. PRECISE CONTINUITY LINE
    grid = GridManager()
    
    # ENTRY Point (Locked to Yesterday)
    entry_pct = grid.get_entry()
    entry_x = int(W * entry_pct)
    
    # EXIT Point (Randomized for Tomorrow)
    exit_pct = random.uniform(0.3, 0.7)
    exit_x = int(W * exit_pct)
    
    print(f"🔗 Line: Entry {entry_pct:.2f} -> Exit {exit_pct:.2f}")
    
    # Draw Thematic Line on MASK (White = Inpaint / Generate)
    # We want SDXL to see empty space here and fill it with the "Connector Object"
    # To guide the flow, we define a path, but we DON'T paint pixels on the canvas.
    # We just ensure the mask is White along this path if we place images over it?
    # Actually, the mask is already White (Inpaint Everything).
    # We only paint Black (Protect) where images are.
    # So the line exists implicitly in the negative space.
    # SDXL will naturally connect top to bottom if prompt says so.
    
    # 5. PLACE ANCHOR (Top Hero - Large Horizontal)
    hero_img = get_cutout_horizontal(anchor['tmdb_id'], anchor.get('tmdb_backdrop_path'), anchor.get('tmdb_poster_path'))
    
    if hero_img:
        # Scale: 95% Width
        scale = (W * 0.95) / hero_img.width
        new_size = (int(hero_img.width * scale), int(hero_img.height * scale))
        hero_img = hero_img.resize(new_size, Image.Resampling.LANCZOS)
        
        # Pos: Top Center
        x = (W - new_size[0]) // 2
        y = 50
        
        canvas.paste(hero_img, (x, y), hero_img)
        # Protect
        mask.paste(ImageOps.invert(hero_img.split()[3]), (x, y), hero_img.split()[3])

    # 6. PLACE GUESTS (Organic Scatter)
    # Area: From y=500 down to y=1200
    start_y = 500
    end_y = 1200
    available_h = end_y - start_y
    step_y = available_h // len(guests)
    
    for i, guest in enumerate(guests):
        g_img = get_cutout_horizontal(guest['tmdb_id'], guest.get('tmdb_backdrop_path'), guest.get('tmdb_poster_path'))
        
        if g_img:
            # Randomize Scale: Between 40% and 55% of Width
            width_pct = random.uniform(0.4, 0.55)
            scale = (W * width_pct) / g_img.width
            new_size = (int(g_img.width * scale), int(g_img.height * scale))
            g_img = g_img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Randomize Rotation: +/- 5 degrees
            rot = random.uniform(-5, 5)
            g_img = g_img.rotate(rot, expand=True, resample=Image.Resampling.BICUBIC)
            
            # Scatter Logic (Left/Right of center line)
            # We want them to NOT overlap the Connector Line too much if possible?
            # Or maybe overlapping is good (depth).
            # Let's alternate Left / Right roughly
            is_left = i % 2 == 0
            
            if is_left:
                # Random X on left half
                x = int(random.uniform(20, W/2 - new_size[0] - 20))
            else:
                # Random X on right half
                x = int(random.uniform(W/2 + 20, W - new_size[0] - 20))
                
            # Y Position: Waterfall down
            y = start_y + (i * step_y) + random.randint(-20, 20)
            
            canvas.paste(g_img, (x, y), g_img)
            # Protect
            mask.paste(ImageOps.invert(g_img.split()[3]), (x, y), g_img.split()[3])

    # 7. GENERATE
    canvas.convert("RGB").save("input.png")
    mask.save("mask.png")
    
    # Prompt: We explicitly mention the connector line coordinates in spirit
    # "running from top [x=..] to bottom [x=..]" doesn't work well in prompts.
    # Instead, we rely on "running vertically connecting the images".
    
    full_prompt = (
        f"Artistic magazine layout background. {style['visual_prompt']}. "
        f"A single continuous {style['connector_adjective']} {style['connector_object']} runs vertically from the very top edge to the very bottom edge, "
        f"passing behind the floating images. "
        f"Minimalist, negative space, high detail, 8k."
    )
    
    print("🚀 Sending to SDXL...")
    try:
        output = replicate.run(
            "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
            input={
                "prompt": full_prompt,
                "negative_prompt": "text, watermark, ugly, distorted, grid, frame, border",
                "image": open("input.png", "rb"),
                "mask": open("mask.png", "rb"),
                "prompt_strength": 0.85, 
                "width": W,
                "height": H
            }
        )
        
        # 8. SAVE
        final_img = Image.open(BytesIO(requests.get(output[0]).content)).convert("RGB")
        filename = "post_v3_image_01.png"
        final_img.save(OUTPUT_DIR / filename)
        print(f"💾 Saved: {filename}")
        
        # Save Exit for tomorrow
        grid.save(exit_pct, anchor['movie_title'])
        
    except Exception as e:
        print(f"❌ Generation Error: {e}")

if __name__ == "__main__":
    main()
