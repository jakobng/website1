"""
generate_post3.py
The "Infinite Cinemascape" Protocol (V11 - Final Zine Edition).

Features:
1. ORGANIC LAYOUT: 1 Hero + 2 Guests floating on a Bezier Curve.
2. CONNECTIVE TISSUE: AI transforms a drawn curve into a thematic object (vine, wire, etc).
3. ZINE TYPOGRAPHY: Adds raw, typewriter-style showtime data to the artwork.
4. ANALOG FINISH: Film grain and contrast grading.
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
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageEnhance
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
FONT_PATH = BASE_DIR / "NotoSansJP-Regular.ttf" # Ensure you have a font!

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

# --- HELPERS: MATH & FX ---
def bernstein_poly(i, n, t):
    return math.comb(n, i) * (t**(n-i)) * ((1 - t)**i)

def bezier_curve(points, n_steps=100):
    n_points = len(points)
    xPoints = [p[0] for p in points]
    yPoints = [p[1] for p in points]
    t = [i/n_steps for i in range(n_steps+1)]
    curve_points = []
    for t_val in t:
        x = 0
        y = 0
        for i in range(n_points):
            b = bernstein_poly(i, n_points-1, t_val)
            x += xPoints[i] * b
            y += yPoints[i] * b
        curve_points.append((int(x), int(y)))
    return curve_points

def add_film_grain(img: Image.Image, intensity=0.15) -> Image.Image:
    w, h = img.size
    noise = Image.effect_noise((w, h), 20).convert("RGB")
    return Image.blend(img, noise, intensity)

def generate_noise_layer(w, h, hex_color) -> Image.Image:
    try:
        color = ImageOps.colorize(Image.new("L", (w, h), 128), "black", hex_color)
    except:
        color = Image.new("RGB", (w, h), hex_color)
    noise = Image.effect_noise((w, h), 30).convert("RGB")
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
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        raw = Image.open(BytesIO(resp.content)).convert("RGBA")
        
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
    # Shadow
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    alpha = img.split()[3]
    shadow.paste((0,0,0,160), (0,0), mask=alpha)
    shadow = shadow.filter(ImageFilter.GaussianBlur(25))
    canvas.paste(shadow, (x + 15, y + 25), shadow)
    
    # Image
    canvas.paste(img, (x, y), img)
    
    # Feathered Mask
    protection = ImageOps.invert(alpha)
    protection = protection.filter(ImageFilter.GaussianBlur(8))
    mask.paste(protection, (x, y), alpha)

def draw_typography(img: Image.Image, anchor_film: dict, guest_films: list) -> Image.Image:
    """Adds the Zine-style text overlay."""
    draw = ImageDraw.Draw(img)
    W, H = img.size
    
    try:
        font_header = ImageFont.truetype(str(FONT_PATH), 24)
        font_bold = ImageFont.truetype(str(FONT_PATH), 32)
    except:
        font_header = ImageFont.load_default()
        font_bold = ImageFont.load_default()

    # Footer Box (Semi-transparent black)
    footer_h = 250
    footer_shape = Image.new("RGBA", (W, footer_h), (0, 0, 0, 200))
    img.paste(footer_shape, (0, H - footer_h), footer_shape)
    
    # Text Drawing
    margin = 50
    y_text = H - footer_h + 40
    
    # Date
    date_str = datetime.now().strftime("%Y.%m.%d").replace(".", " / ")
    draw.text((margin, y_text), f"TOKYO INDIE CINEMA  —  {date_str}", font=font_header, fill="cyan")
    y_text += 50
    
    # Anchor Title
    anchor_title = anchor_film.get('movie_title', 'Unknown')
    draw.text((margin, y_text), f"★ {anchor_title}", font=font_bold, fill="white")
    y_text += 45
    
    # Guest Titles
    for g in guest_films:
        t = g.get('movie_title', '')
        draw.text((margin, y_text), f"• {t}", font=font_header, fill="lightgrey")
        y_text += 35
        
    return img

# --- MAIN ---
def main():
    print("🎬 Starting Cinemascape V11 (Final Zine)...")
    random.seed(time.time())

    if not SHOWTIMES_PATH.exists(): return
    with open(SHOWTIMES_PATH) as f: raw_data = json.load(f)

    # 1. SELECT MOVIES
    unique_movies = {}
    for item in raw_data:
        title = item['movie_title']
        if title not in unique_movies:
            unique_movies[title] = item
        else:
            if not unique_movies[title].get('tmdb_backdrop_path') and item.get('tmdb_backdrop_path'):
                unique_movies[title] = item
    
    valid = list(unique_movies.values())
    valid = [f for f in valid if f.get('tmdb_backdrop_path') or f.get('tmdb_poster_path')]
    if not valid: return

    anchor = random.choice(valid)
    others = [f for f in valid if f['movie_title'] != anchor['movie_title']]
    guests = random.sample(others, min(2, len(others)))
    
    print(f"📅 Anchor: {anchor['movie_title']}")

    # 2. ART DIRECT
    director = ArtDirector(GEMINI_API_KEY)
    style = director.dream_scene(anchor['movie_title'], anchor.get('synopsis', ''))
    print(f"🎨 Theme: {style['visual_prompt']}")

    # 3. CANVAS
    W, H = 1080, 1352
    canvas = generate_noise_layer(W, H, style.get('base_color_hex', '#222222'))
    mask = Image.new("L", (W, H), 255)
    
    # 4. CONNECTOR (Bezier)
    grid = GridManager()
    entry_x = int(W * grid.get_entry())
    exit_x = int(W * random.uniform(0.3, 0.7))
    print(f"🔗 Line: {entry_x} -> {exit_x}")
    
    ctrl1_x = entry_x + random.randint(-200, 200)
    ctrl1_y = H * 0.33
    ctrl2_x = exit_x + random.randint(-200, 200)
    ctrl2_y = H * 0.66
    curve_points = bezier_curve([(entry_x, 0), (ctrl1_x, ctrl1_y), (ctrl2_x, ctrl2_y), (exit_x, H)], n_steps=60)
    
    draw_guide = ImageDraw.Draw(canvas)
    guide_color = (0, 255, 255, 180) # Cyan
    draw_guide.line(curve_points, fill=guide_color, width=25)

    # 5. PLACE ANCHOR
    sfx = anchor.get('tmdb_backdrop_path') or anchor.get('tmdb_poster_path')
    hero = get_cutout(anchor['tmdb_id'], sfx)
    if hero:
        scale = (W * 0.95) / hero.width
        new_size = (int(hero.width * scale), int(hero.height * scale))
        hero = hero.resize(new_size, Image.Resampling.LANCZOS)
        x = (W - new_size[0]) // 2
        y = 80
        apply_soft_mask(canvas, mask, hero, x, y)

    # 6. PLACE GUESTS
    for i, g in enumerate(guests):
        sfx = g.get('tmdb_backdrop_path') or g.get('tmdb_poster_path')
        img = get_cutout(g['tmdb_id'], sfx)
        if img:
            scale_pct = random.uniform(0.6, 0.75)
            scale = (W * scale_pct) / img.width
            new_size = (int(img.width * scale), int(img.height * scale))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            img = img.rotate(random.uniform(-8, 8), expand=True, resample=Image.Resampling.BICUBIC)
            
            # Position on Curve
            t = 0.6 if i == 0 else 0.85
            pt = curve_points[int(t * len(curve_points))]
            offset = 100 if i % 2 == 0 else -100
            x = pt[0] + offset - (new_size[0] // 2)
            y = pt[1] - (new_size[1] // 2)
            x = max(-50, min(W - new_size[0] + 50, x))
            
            apply_soft_mask(canvas, mask, img, x, y)

    # 7. GENERATE
    canvas.convert("RGB").save("input.png")
    mask.save("mask.png")
    
    prompt = (
        f"Artistic magazine collage. {style['visual_prompt']}. "
        f"A {style['connector_adjective']} {style['connector_object']} flowing organically from top to bottom. "
        f"High texture, film grain, mixed media, 8k."
    )
    
    print("🚀 Sending to SDXL...")
    try:
        output = replicate.run(
            "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
            input={
                "prompt": prompt,
                "negative_prompt": "text, watermark, ugly, digital render",
                "image": open("input.png", "rb"),
                "mask": open("mask.png", "rb"),
                "prompt_strength": 0.75, # LOWER STRENGTH = BETTER LINE ADHERENCE
                "width": W,
                "height": H
            }
        )
        
        url = output[0]
        final = Image.open(BytesIO(requests.get(url).content)).convert("RGB")
        
        # 8. FINISH (Grain + Text)
        final = add_film_grain(final, 0.12)
        final = ImageEnhance.Contrast(final).enhance(1.1)
        final = draw_typography(final, anchor, guests) # Add Text
        
        final.save(OUTPUT_DIR / "post_v3_image_01.png")
        print("💾 Saved.")
        
        grid.save(exit_x / W, anchor['movie_title'])
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
