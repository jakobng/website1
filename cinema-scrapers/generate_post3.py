"""
generate_post3.py
The "Infinite Cinemascape" Protocol (V3.1 - Collage Edition).

Features:
1. Multi-Film Collage: 1 Anchor Film (Backdrop) + 2 Guest Films (Posters).
2. Hard-Coded Grid Line: Draws a physical line connecting days.
3. SDXL Inpainting: Fills the gaps between the collage elements.
4. Fallback Logic: Never fails if a specific image is missing.
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
FONT_PATH = BASE_DIR / "NotoSansJP-Bold.ttf"

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
        Act as an Art Director for a cinema magazine.
        FILM: "{film_title}"
        SYNOPSIS: "{synopsis}"

        Define a background style that connects this film to a "Tokyo Indie Cinema" aesthetic.
        
        OUTPUT JSON ONLY:
        {{
            "visual_prompt": "string (SDXL prompt: texture, lighting, mood)",
            "line_color": "string (Hex code for a graphic line, e.g. #FF0055)",
            "mood": "string (Single word)"
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
            return {"visual_prompt": "Cinematic texture, dark atmosphere", "line_color": "#FFFFFF"}

# --- CLASS 2: GRID MEMORY ---
class GridManager:
    def __init__(self):
        self.state = self._load()
    
    def _load(self):
        if STATE_FILE.exists():
            try: return json.loads(STATE_FILE.read_text())
            except: pass
        return {"last_exit_x": 0.5} # Start middle
    
    def get_entry(self) -> float:
        return self.state.get("last_exit_x", 0.5)
    
    def save(self, exit_x: float):
        self.state["last_exit_x"] = exit_x
        STATE_FILE.write_text(json.dumps(self.state))

# --- HELPERS ---
def download_asset(tmdb_id: int, suffix: str) -> Image.Image:
    """Downloads and returns a PIL Image. Handles Backdrops or Posters."""
    if not suffix: return None
    path = ASSETS_DIR / f"{tmdb_id}_{suffix.strip('/')}"
    
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
    """Calls Replicate to remove background."""
    print("✂️ Removing Background...")
    try:
        output = replicate.run(
            "lucataco/remove-bg:95fcc2a26d3899cd6c2691c900465aaeff466285a65c14638cc5f36f34befaf1",
            input={"image": open(image_path, "rb")}
        )
        return Image.open(BytesIO(requests.get(output).content)).convert("RGBA")
    except:
        print("⚠️ BG Removal failed, using raw image.")
        return Image.open(image_path).convert("RGBA")

# --- MAIN LOGIC ---
def main():
    print("🎬 Starting Infinite Cinemascape V3.1 (Collage)...")
    
    if not SHOWTIMES_PATH.exists(): return
    with open(SHOWTIMES_PATH) as f: showtimes = json.load(f)

    # 1. SELECT FILMS (Collage Logic)
    # Filter valid films (must have images)
    valid_films = [f for f in showtimes if f.get('tmdb_poster_path') or f.get('tmdb_backdrop_path')]
    if not valid_films:
        print("❌ No valid films found.")
        return

    anchor = valid_films[0]
    guests = valid_films[1:3] if len(valid_films) > 1 else []
    
    print(f"🎥 Anchor: {anchor['movie_title']}")
    print(f"🎥 Guests: {[g['movie_title'] for g in guests]}")

    # 2. ART DIRECT
    director = ArtDirector(GEMINI_API_KEY)
    style = director.dream_scene(anchor['movie_title'], anchor.get('synopsis', ''))
    
    # 3. CANVAS SETUP (SDXL Portrait 4:5 friendly)
    # Using 864x1080 which is close to 4:5 and divisible by 8 for SDXL
    W, H = 864, 1080
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    mask = Image.new("L", (W, H), 255) # White = Inpaint
    mask_draw = ImageDraw.Draw(mask)
    
    # 4. DRAW GRID LINE (The "Thread")
    grid = GridManager()
    entry_x = int(W * grid.get_entry())
    exit_x = int(W * random.uniform(0.2, 0.8))
    
    # Draw line on Canvas AND Mask (Black = Keep)
    line_draw = ImageDraw.Draw(canvas)
    line_color = style.get('line_color', '#FFFFFF')
    
    # Simple Bezier-ish or straight line
    line_points = [(entry_x, 0), (entry_x, H//3), (exit_x, 2*H//3), (exit_x, H)]
    line_draw.line(line_points, fill=line_color, width=8)
    mask_draw.line(line_points, fill=0, width=8) # Protect line
    
    print(f"🔗 Line Drawn: {entry_x} -> {exit_x}")

    # 5. PLACE ANCHOR (Top, Large)
    # Prefer Backdrop, fallback to Poster
    anchor_suffix = anchor.get('tmdb_backdrop_path') or anchor.get('tmdb_poster_path')
    anchor_img = download_asset(anchor['tmdb_id'], anchor_suffix)
    
    if anchor_img:
        # Save temp for BG removal
        temp_path = ASSETS_DIR / "temp_anchor.png"
        anchor_img.save(temp_path)
        anchor_cutout = remove_bg_api(temp_path)
        
        # Scale to 90% width
        scale = (W * 0.9) / anchor_cutout.width
        new_size = (int(anchor_cutout.width * scale), int(anchor_cutout.height * scale))
        anchor_cutout = anchor_cutout.resize(new_size, Image.Resampling.LANCZOS)
        
        # Position: Top 3rd
        x = (W - new_size[0]) // 2
        y = 150
        
        canvas.paste(anchor_cutout, (x, y), anchor_cutout)
        # Protect in mask
        mask.paste(ImageOps.invert(anchor_cutout.split()[3]), (x, y), anchor_cutout.split()[3])

    # 6. PLACE GUESTS (Bottom, Smaller)
    for i, guest in enumerate(guests):
        suffix = guest.get('tmdb_poster_path')
        img = download_asset(guest['tmdb_id'], suffix)
        if img:
            # Scale to 40% width
            scale = (W * 0.4) / img.width
            new_size = (int(img.width * scale), int(img.height * scale))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Position: Bottom Left / Right
            x = 50 if i == 0 else (W - new_size[0] - 50)
            y = H - new_size[1] - 150
            
            canvas.paste(img, (x, y), img)
            # Protect in mask
            mask.paste(ImageOps.invert(img.split()[3]), (x, y), img.split()[3])

    # 7. GENERATE BACKGROUND
    canvas.convert("RGB").save("input.png")
    mask.save("mask.png")
    
    print("🚀 Sending to SDXL Inpainting...")
    try:
        output = replicate.run(
            "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
            input={
                "prompt": f"Magazine cover background, {style['visual_prompt']}, photorealistic, 8k",
                "negative_prompt": "text, watermark, ugly, distorted",
                "image": open("input.png", "rb"),
                "mask": open("mask.png", "rb"),
                "prompt_strength": 0.95,
                "width": W,
                "height": H
            }
        )
        
        # Download
        final_img = Image.open(BytesIO(requests.get(output[0]).content)).convert("RGBA")
        
        # 8. TYPOGRAPHY OVERLAY
        draw = ImageDraw.Draw(final_img)
        try:
            font_header = ImageFont.truetype(str(FONT_PATH), 80)
            font_sub = ImageFont.truetype(str(FONT_PATH), 30)
        except:
            font_header = ImageFont.load_default()
            font_sub = ImageFont.load_default()
            
        # Header
        draw.text((40, 40), "TOKYO INDIE", font=font_header, fill="white", stroke_width=4, stroke_fill="black")
        draw.text((40, 130), "CINEMA DAILY", font=font_header, fill="white", stroke_width=4, stroke_fill="black")
        
        # Date
        date_str = datetime.now().strftime("%Y.%m.%d")
        draw.text((W - 200, 60), date_str, font=font_sub, fill="white", stroke_width=2, stroke_fill="black")

        # Save
        filename = "post_v3_image_01.png"
        final_img.save(OUTPUT_DIR / filename)
        print(f"💾 Saved: {filename}")
        
        # Save State
        grid.save(exit_x / W) # Save percent
        
    except Exception as e:
        print(f"❌ Generation Error: {e}")

if __name__ == "__main__":
    main()
