"""
generate_post3.py
The "Infinite Cinemascape" Protocol (V5 - Precision Edition).

Improvements:
1. DAILY ROTATION: Selects a different 'Anchor Film' every day based on the date.
2. SMART CUTOUTS: Restored the 'Trim Whitespace' logic from V2 so images are centered.
3. PRECISE MASKING: Uses exact Alpha channels to protect posters from SDXL hallucination.
4. THEMATIC CONNECTOR: Forces SDXL to generate a vertical object (vine, wire, beam) connecting the layout.
"""

import os
import sys
import json
import random
import requests
import time
from pathlib import Path
from datetime import datetime
from io import BytesIO
from typing import Dict, List, Tuple

# --- LIBRARIES ---
try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageChops
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
        Act as a Visual Futurist for a cinema magazine.
        FILM: "{film_title}"
        SYNOPSIS: "{synopsis}"

        1. Describe a BACKGROUND atmosphere (texture, lighting).
        2. Invent a "CONNECTOR OBJECT" (vertical line like a cable, vine, beam, crack).
        
        OUTPUT JSON ONLY:
        {{
            "visual_prompt": "string (SDXL prompt, minimal, negative space)",
            "connector_object": "string (The vertical object)",
            "connector_adjective": "string"
        }}
        """
        try:
            resp = self.client.models.generate_content(
                model="gemini-2.5-flash", contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            data = json.loads(resp.text)
            if isinstance(data, list): data = data[0] if data else {}
            return data
        except:
            return {
                "visual_prompt": "Cinematic texture, dark minimalist atmosphere",
                "connector_object": "steel wire",
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
    
    def save(self, exit_x: float, anchor_title: str):
        self.state["last_exit_x"] = exit_x
        self.state["last_anchor"] = anchor_title
        STATE_FILE.write_text(json.dumps(self.state, indent=2))

# --- HELPER: ASSET PROCESSING (Restored from V2) ---
def trim_transparent_borders(img: Image.Image) -> Image.Image:
    """Crops the transparent whitespace around a cutout."""
    bbox = img.getbbox()
    if bbox:
        return img.crop(bbox)
    return img

def download_asset(tmdb_id: int, suffix: str) -> Image.Image:
    if not suffix: return None
    path = ASSETS_DIR / f"{tmdb_id}_{suffix.strip('/').replace('/','-')}"
    
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

def get_cutout(image_path: Path) -> Image.Image:
    """Removes background via Replicate and Trims."""
    print(f"✂️ Cutting out: {image_path.name}...")
    try:
        output = replicate.run(
            "lucataco/remove-bg:95fcc2a26d3899cd6c2691c900465aaeff466285a65c14638cc5f36f34befaf1",
            input={"image": open(image_path, "rb")}
        )
        cutout = Image.open(BytesIO(requests.get(output).content)).convert("RGBA")
        return trim_transparent_borders(cutout) # Crucial: Remove empty space
    except:
        print("⚠️ Cutout failed, using raw.")
        return Image.open(image_path).convert("RGBA")

# --- MAIN LOGIC ---
def main():
    print("🎬 Starting Infinite Cinemascape V5 (Daily Rotation)...")
    
    if not SHOWTIMES_PATH.exists(): return
    with open(SHOWTIMES_PATH) as f: showtimes = json.load(f)

    # 1. SELECT FILMS (Daily Rotation Logic)
    # Filter only films that have valid images
    valid_films = [f for f in showtimes if f.get('tmdb_poster_path')]
    
    if not valid_films:
        print("❌ No valid films found.")
        return

    # Use Day of Year to rotate the "Anchor"
    day_of_year = datetime.now().timetuple().tm_yday
    anchor_index = day_of_year % len(valid_films)
    
    anchor = valid_films[anchor_index]
    # Pick next 4 films as guests (wrapping around)
    guests = [valid_films[(anchor_index + i + 1) % len(valid_films)] for i in range(4)]
    
    print(f"📅 Day {day_of_year} -> Anchor Index {anchor_index}")
    print(f"🎥 Anchor: {anchor['movie_title']}")
    print(f"🎥 Guests: {[g['movie_title'] for g in guests]}")

    # 2. ART DIRECT
    director = ArtDirector(GEMINI_API_KEY)
    style = director.dream_scene(anchor['movie_title'], anchor.get('synopsis', ''))
    print(f"🎨 Theme: {style['visual_prompt']}")
    
    # 3. CANVAS SETUP (IG Portrait)
    W, H = 1080, 1350
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    mask = Image.new("L", (W, H), 255) # White = Inpaint
    mask_draw = ImageDraw.Draw(mask)
    
    # 4. DRAW THE "THEMATIC LINE" (Connector)
    grid = GridManager()
    entry_x = int(W * grid.get_entry())
    exit_x = int(W * random.uniform(0.3, 0.7)) # Keep it somewhat central
    
    # Define the Path
    points = [
        (entry_x, 0),
        (entry_x, H * 0.3),     # Straight down 30%
        (exit_x, H * 0.7),      # Angle across
        (exit_x, H)             # Straight out
    ]
    
    # Draw logic:
    # We want SDXL to generate the line, so we leave it White (Inpaint) on mask.
    # However, to help SDXL, we can draw a very faint guide on the canvas?
    # No, let's trust the mask. We ensure the line area is WHITE.
    # But wait, the whole mask is White. 
    # We need to protect the POSTERS (Black). The empty space (White) becomes the line + BG.
    
    # Let's save the line coordinates to draw a debug line if needed, 
    # but primarily we rely on the prompt "A vertical object running through..."
    print(f"🔗 Connector Path: {entry_x} -> {exit_x}")

    # 5. PLACE ANCHOR (Top Hero)
    # Prefer Backdrop for Anchor (Horizontal)
    anchor_suffix = anchor.get('tmdb_backdrop_path') or anchor.get('tmdb_poster_path')
    anchor_raw = download_asset(anchor['tmdb_id'], anchor_suffix)
    
    if anchor_raw:
        # Save temp for BG removal
        temp_path = ASSETS_DIR / "temp_anchor.png"
        anchor_raw.save(temp_path)
        anchor_cutout = get_cutout(temp_path)
        
        # Scale Anchor to be LARGE (Hero)
        # Max width 90% of canvas, Max height 40% of canvas
        max_w = W * 0.95
        max_h = H * 0.45
        
        # Calculate scale to fit within box (contain)
        scale = min(max_w / anchor_cutout.width, max_h / anchor_cutout.height)
        new_size = (int(anchor_cutout.width * scale), int(anchor_cutout.height * scale))
        anchor_cutout = anchor_cutout.resize(new_size, Image.Resampling.LANCZOS)
        
        # Position: Top Center
        x = (W - new_size[0]) // 2
        y = 100 # Slight padding from top
        
        canvas.paste(anchor_cutout, (x, y), anchor_cutout)
        
        # Mask: Protect Anchor (Black = 0)
        # We take the alpha channel, invert it (Opaque->0, Transparent->255)
        alpha = anchor_cutout.split()[3]
        protection = ImageOps.invert(alpha)
        mask.paste(protection, (x, y), alpha)

    # 6. PLACE GUESTS (Bottom Grid)
    # Grid area: Y=700 to 1300
    grid_y_start = 700
    grid_y_end = 1250
    row_h = (grid_y_end - grid_y_start) // 2
    col_w = W // 2
    
    for i, guest in enumerate(guests):
        suffix = guest.get('tmdb_poster_path')
        raw = download_asset(guest['tmdb_id'], suffix)
        
        if raw:
            # Save temp & cutout
            temp_path = ASSETS_DIR / f"temp_guest_{i}.png"
            raw.save(temp_path)
            guest_cutout = get_cutout(temp_path)
            
            # Grid Calc
            row = i // 2
            col = i % 2
            
            # Target Size: smaller than cell
            target_h = int(row_h * 0.85)
            scale = target_h / guest_cutout.height
            new_size = (int(guest_cutout.width * scale), int(guest_cutout.height * scale))
            guest_cutout = guest_cutout.resize(new_size, Image.Resampling.LANCZOS)
            
            # Center in cell
            cell_x = col * col_w
            cell_y = grid_y_start + (row * row_h)
            
            x = cell_x + (col_w - new_size[0]) // 2
            y = cell_y + (row_h - new_size[1]) // 2
            
            canvas.paste(guest_cutout, (x, y), guest_cutout)
            
            # Mask: Protect
            alpha = guest_cutout.split()[3]
            protection = ImageOps.invert(alpha)
            mask.paste(protection, (x, y), alpha)

    # 7. GENERATE BACKGROUND
    canvas.convert("RGB").save("input.png")
    mask.save("mask.png")
    
    full_prompt = (
        f"Magazine layout background. {style['visual_prompt']}. "
        f"A {style['connector_adjective']} {style['connector_object']} runs vertically through the center, "
        f"connecting the elements. Negative space, minimalist, 8k, photorealistic."
    )
    
    print("🚀 Sending to SDXL Inpainting...")
    try:
        output = replicate.run(
            "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
            input={
                "prompt": full_prompt,
                "negative_prompt": "text, watermark, ugly, distorted, cluttered, messy",
                "image": open("input.png", "rb"),
                "mask": open("mask.png", "rb"), # White = Inpaint
                "prompt_strength": 0.85, # Lowered from 0.95 to preserve composition
                "width": W,
                "height": H
            }
        )
        
        # 8. SAVE
        final_img = Image.open(BytesIO(requests.get(output[0]).content)).convert("RGB")
        filename = "post_v3_image_01.png"
        final_img.save(OUTPUT_DIR / filename)
        print(f"💾 Saved: {filename}")
        
        # Save state for next run
        grid.save(exit_x / W, anchor['movie_title'])
        
    except Exception as e:
        print(f"❌ Generation Error: {e}")

if __name__ == "__main__":
    main()
