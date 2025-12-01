"""
generate_post3.py
The "Infinite Cinemascape" Protocol (V4 - 1 Anchor + 4 Guests + AI Connector).

Changes:
1. No Text Header (Pure Art).
2. Layout: 1 Anchor (Top) + 4 Guests (Bottom Grid).
3. Thematic Line: Uses masking to force AI to generate a specific object (vine, wire, beam) along a path.
"""

import os
import sys
import json
import random
import requests
from pathlib import Path
from datetime import datetime
from io import BytesIO
from typing import Dict, List, Tuple

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

# Create dirs
ASSETS_DIR.mkdir(exist_ok=True)

# --- CLASS 1: THE ART DIRECTOR ---
class ArtDirector:
    def __init__(self, api_key: str):
        if not api_key: raise ValueError("⚠️ GEMINI_API_KEY missing!")
        self.client = genai.Client(api_key=api_key)

    def dream_scene(self, film_title: str, synopsis: str) -> Dict:
        print(f"🧠 Art Director reading: {film_title}...")
        prompt = f"""
        Act as a Visual Futurist.
        FILM: "{film_title}"
        SYNOPSIS: "{synopsis}"

        1. Describe a BACKGROUND atmosphere for this film (texture, lighting).
        2. Invent a "CONNECTOR OBJECT" that is long and vertical (e.g., a rusty chain, a fiber optic cable, a vine, a beam of light, a crack in reality).
        
        OUTPUT JSON ONLY:
        {{
            "visual_prompt": "string (SDXL prompt for background)",
            "connector_object": "string (The vertical object to generate)",
            "connector_adjective": "string (Adjective for the object, e.g. 'glowing', 'rusty')"
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

# --- CLASS 2: GRID MEMORY ---
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
    
    def save(self, exit_x: float):
        self.state["last_exit_x"] = exit_x
        STATE_FILE.write_text(json.dumps(self.state))

# --- HELPERS ---
def download_asset(tmdb_id: int, suffix: str) -> Image.Image:
    if not suffix: return None
    path = ASSETS_DIR / f"{tmdb_id}_{suffix.strip('/').replace('/','-')}" # Sanitize filename
    
    if not path.exists():
        url = f"https://image.tmdb.org/t/p/w780{suffix}"
        print(f"⬇️ Downloading: {url}")
        try:
            resp = requests.get(url)
            resp.raise_for_status()
            with open(path, 'wb') as f: f.write(resp.content)
        except: return None
            
    try: return Image.open(path).convert("RGBA")
    except: return None

def remove_bg_api(image_path: Path) -> Image.Image:
    print(f"✂️ Removing Background: {image_path.name}...")
    try:
        output = replicate.run(
            "lucataco/remove-bg:95fcc2a26d3899cd6c2691c900465aaeff466285a65c14638cc5f36f34befaf1",
            input={"image": open(image_path, "rb")}
        )
        return Image.open(BytesIO(requests.get(output).content)).convert("RGBA")
    except:
        print("⚠️ BG Removal failed, using raw.")
        return Image.open(image_path).convert("RGBA")

# --- MAIN LOGIC ---
def main():
    print("🎬 Starting Infinite Cinemascape V4 (1+4 Layout)...")
    
    if not SHOWTIMES_PATH.exists(): return
    with open(SHOWTIMES_PATH) as f: showtimes = json.load(f)

    # 1. SELECT FILMS (1 Anchor + 4 Guests)
    valid_films = [f for f in showtimes if f.get('tmdb_poster_path')]
    if len(valid_films) < 5:
        print(f"⚠️ Only found {len(valid_films)} valid films. Using what we have.")
    
    anchor = valid_films[0]
    guests = valid_films[1:5] # Up to 4 guests
    
    print(f"🎥 Anchor: {anchor['movie_title']}")
    print(f"🎥 Guests: {len(guests)}")

    # 2. ART DIRECT
    director = ArtDirector(GEMINI_API_KEY)
    style = director.dream_scene(anchor['movie_title'], anchor.get('synopsis', ''))
    print(f"🎨 Connector: {style['connector_adjective']} {style['connector_object']}")
    
    # 3. CANVAS SETUP
    W, H = 864, 1080
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    mask = Image.new("L", (W, H), 255) # White = Inpaint, Black = Keep
    mask_draw = ImageDraw.Draw(mask)
    
    # 4. THEMATIC CONNECTOR LINE
    grid = GridManager()
    entry_x = int(W * grid.get_entry())
    exit_x = int(W * random.uniform(0.2, 0.8))
    
    # Line Points (Simple Curve via multi-segment line)
    # We want the line to be "White" on the mask so SDXL regenerates it.
    # We leave the canvas transparent so SDXL fills it.
    points = [
        (entry_x, 0),
        (entry_x, H * 0.2), # Go straight down a bit
        (exit_x, H * 0.8),  # Angle across
        (exit_x, H)         # Straight out
    ]
    
    # Draw THICK line on MASK (White = "Inpaint this area please")
    # Note: Previously we protected (Black) the line. Now we WANT to generate it (White).
    # But wait! The mask is initialized to White (255).
    # We will Paste images as Black (0).
    # So the background is White (Inpaint).
    # To force a SPECIFIC object on the line, we just rely on the prompt + the fact it's empty space.
    # Actually, to ensure the line is distinct from the background, we might want to guide it?
    # No, simplest is: Just let the background generation handle it via prompt:
    # "A {connector} running vertically..."
    
    print(f"🔗 Line Path: {entry_x} -> {exit_x}")

    # 5. PLACE ANCHOR (Top Half)
    # Prefer Backdrop
    anchor_suffix = anchor.get('tmdb_backdrop_path') or anchor.get('tmdb_poster_path')
    anchor_img = download_asset(anchor['tmdb_id'], anchor_suffix)
    
    if anchor_img:
        temp = ASSETS_DIR / "temp_anchor.png"
        anchor_img.save(temp)
        anchor_cutout = remove_bg_api(temp)
        
        # Scale: ~85% Width
        scale = (W * 0.85) / anchor_cutout.width
        new_size = (int(anchor_cutout.width * scale), int(anchor_cutout.height * scale))
        anchor_cutout = anchor_cutout.resize(new_size, Image.Resampling.LANCZOS)
        
        # Pos: Top Center
        x = (W - new_size[0]) // 2
        y = 50
        
        canvas.paste(anchor_cutout, (x, y), anchor_cutout)
        # Mask: Protect this area (Black)
        mask.paste(ImageOps.invert(anchor_cutout.split()[3]), (x, y), anchor_cutout.split()[3])

    # 6. PLACE GUESTS (Bottom Half - 2x2 Grid)
    # Available area starts around y=500
    grid_start_y = 550
    grid_h = H - grid_start_y - 50
    cell_w = W // 2
    cell_h = grid_h // 2
    
    for i, guest in enumerate(guests):
        suffix = guest.get('tmdb_poster_path')
        img = download_asset(guest['tmdb_id'], suffix)
        if img:
            # Grid Position
            row = i // 2
            col = i % 2
            center_x = (col * cell_w) + (cell_w // 2)
            center_y = grid_start_y + (row * cell_h) + (cell_h // 2)
            
            # Scale: Fit within cell (padded)
            # Max width 200px?
            scale = 180 / img.width
            new_size = (int(img.width * scale), int(img.height * scale))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            x = center_x - (new_size[0] // 2)
            y = center_y - (new_size[1] // 2)
            
            canvas.paste(img, (x, y), img)
            # Mask: Protect
            mask.paste(ImageOps.invert(img.split()[3]), (x, y), img.split()[3])

    # 7. GENERATE
    canvas.convert("RGB").save("input.png")
    mask.save("mask.png")
    
    # Prompt Engineering
    # We explicitly ask for the Connector Line in the prompt
    full_prompt = (
        f"{style['visual_prompt']}. "
        f"A {style['connector_adjective']} {style['connector_object']} runs vertically through the center of the image "
        f"connecting the top to the bottom. "
        f"Photorealistic, 8k, highly detailed."
    )
    
    print("🚀 Sending to SDXL...")
    try:
        output = replicate.run(
            "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
            input={
                "prompt": full_prompt,
                "negative_prompt": "text, watermark, ugly, distorted, low quality",
                "image": open("input.png", "rb"),
                "mask": open("mask.png", "rb"), # White areas = Generate
                "prompt_strength": 0.95,
                "width": W,
                "height": H
            }
        )
        
        # 8. SAVE
        final_img = Image.open(BytesIO(requests.get(output[0]).content)).convert("RGB")
        filename = "post_v3_image_01.png"
        final_img.save(OUTPUT_DIR / filename)
        print(f"💾 Saved: {filename}")
        
        grid.save(exit_x / W)
        
    except Exception as e:
        print(f"❌ Generation Error: {e}")

if __name__ == "__main__":
    main()
