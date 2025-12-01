"""
generate_post3.py
The "Infinite Cinemascape" Protocol (V7 - Primed Canvas & Maximalist Layout).

Key Changes:
1. PRIMED CANVAS: Fills background with rough noise/color so SDXL doesn't see "black void".
2. GUIDED CONNECTOR: Draws a physical line on the input to guide the AI's geometry.
3. MAXIMALIST: Increased image scale and density. Overlap is encouraged.
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

        1. Describe a BACKGROUND texture (e.g. concrete, neon mist, crumpled paper).
        2. Pick a "BASE COLOR" (Hex code) for the mood.
        3. Invent a "CONNECTOR OBJECT" (vertical line: rusty chain, neon cable, vine, beam, crack).
        
        OUTPUT JSON ONLY:
        {{
            "visual_prompt": "string (SDXL prompt for background texture)",
            "base_color_hex": "string (e.g. #FF0055)",
            "connector_object": "string (The vertical object name)",
            "connector_adjective": "string (Adjective)"
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
    """Creates a base layer so SDXL doesn't hallucinate from black void."""
    # Create solid color
    try:
        color = ImageOps.colorize(Image.new("L", (w, h), 128), "black", hex_color)
    except:
        color = Image.new("RGB", (w, h), hex_color)
        
    # Add Noise
    noise = Image.effect_noise((w, h), 20).convert("RGB")
    blend = Image.blend(color.convert("RGB"), noise, 0.2)
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

# --- MAIN ---
def main():
    print("🎬 Starting Cinemascape V7 (Primed Canvas)...")
    
    if not SHOWTIMES_PATH.exists(): return
    with open(SHOWTIMES_PATH) as f: showtimes = json.load(f)

    # 1. FILMS
    valid_films = [f for f in showtimes if f.get('tmdb_backdrop_path') or f.get('tmdb_poster_path')]
    if not valid_films: return

    # Rotation
    day_of_year = datetime.now().timetuple().tm_yday
    anchor_index = day_of_year % len(valid_films)
    anchor = valid_films[anchor_index]
    guests = [valid_films[(anchor_index + i + 1) % len(valid_films)] for i in range(4)]
    
    print(f"📅 Anchor: {anchor['movie_title']}")

    # 2. ART DIRECTION
    director = ArtDirector(GEMINI_API_KEY)
    style = director.dream_scene(anchor['movie_title'], anchor.get('synopsis', ''))
    print(f"🎨 Mood: {style['base_color_hex']} | {style['visual_prompt']}")

    # 3. PRIMED CANVAS
    W, H = 1080, 1352
    # Instead of black, use a noisy colored base
    canvas = generate_noise_layer(W, H, style.get('base_color_hex', '#222222'))
    mask = Image.new("L", (W, H), 255) # White = Inpaint
    
    # 4. DRAW CONNECTOR GUIDE (On Canvas + Mask)
    grid = GridManager()
    entry_x = int(W * grid.get_entry())
    exit_x = int(W * random.uniform(0.3, 0.7))
    
    print(f"🔗 Line: {entry_x} -> {exit_x}")
    
    draw_guide = ImageDraw.Draw(canvas)
    
    # We draw a BRIGHT line on the canvas. SDXL will see this and transform it.
    # Using Cyan or Magenta usually triggers "glowing" effects well, or White.
    guide_color = (255, 255, 255, 128) 
    line_width = 15
    
    points = [
        (entry_x, 0),
        (entry_x, H * 0.2),
        (exit_x, H * 0.8),
        (exit_x, H)
    ]
    draw_guide.line(points, fill=guide_color, width=line_width)
    
    # Note: We keep the mask WHITE here. We want SDXL to redraw the line area.
    # By providing the guide pixels, we are doing "img2img" for the background.

    # 5. PLACE ANCHOR (Large)
    sfx = anchor.get('tmdb_backdrop_path') or anchor.get('tmdb_poster_path')
    hero = get_cutout(anchor['tmdb_id'], sfx)
    
    if hero:
        # Scale: 95% Width (Bleed)
        scale = (W * 0.95) / hero.width
        new_size = (int(hero.width * scale), int(hero.height * scale))
        hero = hero.resize(new_size, Image.Resampling.LANCZOS)
        x = (W - new_size[0]) // 2
        y = 50
        canvas.paste(hero, (x, y), hero)
        
        # Mask: Protect Hero (Black)
        mask.paste(ImageOps.invert(hero.split()[3]), (x, y), hero.split()[3])

    # 6. PLACE GUESTS (Maximalist Scatter)
    start_y = 550
    end_y = 1250
    step = (end_y - start_y) // len(guests)
    
    for i, g in enumerate(guests):
        sfx = g.get('tmdb_backdrop_path') or g.get('tmdb_poster_path')
        img = get_cutout(g['tmdb_id'], sfx)
        
        if img:
            # Scale: 60-70% Width (Overlap encouraged)
            scale_pct = random.uniform(0.6, 0.7)
            scale = (W * scale_pct) / img.width
            new_size = (int(img.width * scale), int(img.height * scale))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Rotate
            img = img.rotate(random.uniform(-8, 8), expand=True, resample=Image.Resampling.BICUBIC)
            
            # Position
            is_left = i % 2 == 0
            if is_left:
                x = int(random.uniform(-50, W//2 - 100))
            else:
                x = int(random.uniform(W//2 - 100, W - new_size[0] + 50))
                
            y = start_y + (i * step) + random.randint(-50, 50)
            
            canvas.paste(img, (x, y), img)
            # Mask: Protect
            mask.paste(ImageOps.invert(img.split()[3]), (x, y), img.split()[3])

    # 7. GENERATE
    canvas.convert("RGB").save("input.png")
    mask.save("mask.png")
    
    prompt = (
        f"A rich, dense magazine collage. {style['visual_prompt']}. "
        f"A {style['connector_adjective']} {style['connector_object']} transforming from the white line, "
        f"running vertically through the composition. "
        f"Maximalist, filling the space, high texture, 8k."
    )
    
    print("🚀 Sending to SDXL...")
    try:
        output = replicate.run(
            "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
            input={
                "prompt": prompt,
                "negative_prompt": "black background, empty space, minimalist, boring, text, watermark",
                "image": open("input.png", "rb"),
                "mask": open("mask.png", "rb"),
                "prompt_strength": 0.9, 
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
