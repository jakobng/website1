"""
Generate Post V3 (Prototype): "The Dream Weaver"
- Concept: Collage of cinema stills with AI-inpainted surroundings.
- Constraint: Selected films must be from "Today's Carousel" list.
- Context: Passes film titles/synopses to Gemini for grounded prompting.
"""

import os
import json
import random
import requests
import re
from pathlib import Path
from io import BytesIO
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageOps

# --- API Setup ---
try:
    import replicate
except ImportError:
    print("⚠️ Replicate library not found. Run: pip install replicate")

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("⚠️ Google GenAI library not found. Run: pip install google-genai")

# --- Secrets ---
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"
TMDB_BASE_URL = "https://image.tmdb.org/t/p/original"
OUTPUT_FILENAME = "post_v3_test.png"

# Canvas Settings (Instagram Portrait)
CANVAS_W, CANVAS_H = 1080, 1350

def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")

def load_showtimes_for_today():
    """
    Loads showtimes and filters for TODAY's films only.
    Returns the top 9 films (simulating the carousel selection).
    """
    if not SHOWTIMES_PATH.exists():
        print("❌ showtimes.json not found.")
        return []
    
    with open(SHOWTIMES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    today_str = get_today_str()
    print(f"📅 Filtering for date: {today_str}")

    # 1. Filter by Date & Valid Images
    valid_films = []
    seen_titles = set()
    
    for film in data:
        # Check date (assuming 'date_text' format is YYYY-MM-DD)
        if film.get('date_text') != today_str:
            continue
            
        # Check for images
        if not (film.get('tmdb_backdrop_path') or film.get('tmdb_poster_path')):
            continue
            
        # Deduplicate by title
        title = film.get('movie_title')
        if title in seen_titles:
            continue
            
        seen_titles.add(title)
        valid_films.append(film)

    # 2. Randomize and Select Carousel Candidates (Top 9)
    # Note: In production, this logic must match generate_post2.py exactly
    # to ensure the cover matches the slides.
    random.shuffle(valid_films)
    carousel_films = valid_films[:9]
    
    print(f"✅ Found {len(carousel_films)} films for today's carousel.")
    return carousel_films

def fetch_image(url):
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return Image.open(BytesIO(resp.content)).convert("RGBA")
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return None

def create_random_cutout(img):
    """Crops a random interesting section of the image."""
    w, h = img.size
    
    # Crop 50-80% of original
    crop_w = int(w * random.uniform(0.5, 0.8))
    crop_h = int(h * random.uniform(0.5, 0.8))
    
    left = random.randint(0, w - crop_w)
    top = random.randint(0, h - crop_h)
    
    crop = img.crop((left, top, left + crop_w, top + crop_h))
    
    # Resize to canvas scale (~500px wide)
    target_w = random.randint(400, 700)
    ratio = target_w / crop_w
    target_h = int(crop_h * ratio)
    crop = crop.resize((target_w, target_h), Image.Resampling.LANCZOS)
    
    return crop

def build_collage(films):
    """
    Places cutouts on a transparent canvas.
    Returns: (composite_rgb, mask, film_context_string)
    """
    # Create base canvas (Transparent)
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    context_lines = []

    # Gather images
    placed_count = 0
    for film in films:
        if placed_count >= 3: break 
        
        path = film.get("tmdb_backdrop_path") or film.get("tmdb_poster_path")
        if not path: continue
        
        full_url = TMDB_BASE_URL + path
        print(f"🎨 Fetching image for: {film.get('movie_title')}")
        src_img = fetch_image(full_url)
        
        if src_img:
            # Add to context string for Gemini
            title = film.get('movie_title', 'Unknown Film')
            synopsis = film.get('tmdb_overview', 'No synopsis available.')
            # Truncate synopsis to keep prompt manageable
            synopsis = (synopsis[:150] + '..') if len(synopsis) > 150 else synopsis
            context_lines.append(f"- Film: '{title}'. Context: {synopsis}")

            cutout = create_random_cutout(src_img)
            
            # Random rotation/pos
            angle = random.uniform(-10, 10)
            cutout = cutout.rotate(angle, expand=True, resample=Image.BICUBIC)
            
            x = random.randint(-50, CANVAS_W - cutout.width + 50)
            y = random.randint(-50, CANVAS_H - cutout.height + 50)
            
            canvas.paste(cutout, (x, y), cutout)
            placed_count += 1
            
    if placed_count == 0:
        print("❌ No images could be placed.")
        return None, None, None

    # Create Mask (Replicate Flux Fill: White = Fill, Black = Keep)
    alpha = canvas.split()[3]
    # Invert alpha: Transparent (0) -> White (255) [Fill this], Opaque -> Black [Keep this]
    mask = ImageOps.invert(alpha)
    
    # Create RGB Base (Grey background for valid parts, to help the AI see context)
    flat_canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), (128, 128, 128))
    flat_canvas.paste(canvas, (0, 0), canvas)
    
    context_str = "\n".join(context_lines)
    return flat_canvas, mask, context_str

def ask_gemini_for_prompt(collage_image, film_context):
    """
    Shows the collage + film context to Gemini.
    """
    print("✨ Asking Gemini to direct the artwork...")
    
    if not GEMINI_API_KEY:
        print("❌ No GEMINI_API_KEY found. Using fallback.")
        return "surreal cinematic collage, atmospheric lighting, 8k"

    client = genai.Client(api_key=GEMINI_API_KEY)
    
    preview = collage_image.resize((512, 640))
    
    prompt = f"""
    You are an Art Director for a cinema magazine. 
    I have placed fragments of 3 movie stills on a canvas. The grey area is empty space.
    
    Here is the context of the films used:
    {film_context}

    Your task:
    Write a single sentence image generation prompt to FILL the empty space (grey area).
    The fill should be a cohesive, surreal, or atmospheric texture that connects these specific films.
    Do NOT describe the characters in the fragments (they are already there).
    Describe the BACKGROUND texture/environment (e.g., "neon-lit rain on asphalt," "crumpled vintage paper and ink," "dreamy bokeh and film grain," "gritty concrete wall with shadows").
    Match the mood of the film descriptions above.
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt, preview]
        )
        suggestion = response.text.strip()
        # Clean up if Gemini adds "Prompt: " prefix
        suggestion = re.sub(r'^Prompt:\s*', '', suggestion, flags=re.IGNORECASE).strip('"')
        print(f"🤖 Gemini's Vision: '{suggestion}'")
        return suggestion
    except Exception as e:
        print(f"⚠️ Gemini Error: {e}")
        return "cinematic atmosphere, high detail, 8k, photorealistic texture"

def run_inpainting(image, mask, prompt):
    print("🎨 Painting with Flux Fill (Replicate)...")
    
    if not REPLICATE_API_TOKEN:
        print("❌ No REPLICATE_API_TOKEN found.")
        return image

    img_path = BASE_DIR / "temp_src.png"
    mask_path = BASE_DIR / "temp_mask.png"
    image.save(img_path)
    mask.save(mask_path)
    
    try:
        output = replicate.run(
            "black-forest-labs/flux-fill-dev",
            input={
                "image": open(img_path, "rb"),
                "mask": open(mask_path, "rb"), # White = Fill
                "prompt": prompt + ", high quality, photorealistic, 4k, seamless blend",
                "guidance": 30,
                "output_format": "png"
            }
        )
        
        if output:
            result_url = str(output) if not isinstance(output, list) else output[0]
            print(f"⬇️ Downloading result...")
            res = requests.get(result_url)
            return Image.open(BytesIO(res.content))
            
    except Exception as e:
        print(f"❌ Replicate Error: {e}")
    
    return image

def add_typography(img):
    draw = ImageDraw.Draw(img)
    
    # Load Fonts
    try:
        font_path = BASE_DIR / "NotoSansJP-Bold.ttf"
        font = ImageFont.truetype(str(font_path), 80)
        small_font = ImageFont.truetype(str(font_path), 40)
    except:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Title
    text = "TOKYO CINEMA"
    draw.text((55, 55), text, font=font, fill="black")
    draw.text((50, 50), text, font=font, fill="white")
    
    # Date
    today = datetime.now().strftime("%Y.%m.%d")
    draw.text((55, 155), today, font=small_font, fill="black")
    draw.text((50, 150), today, font=small_font, fill="#FDB813")

    return img

def main():
    print("🚀 Starting Generate Post V3 (Contextual Collage)...")
    
    # 1. Get the Carousel List (Top 9)
    carousel_films = load_showtimes_for_today()
    if not carousel_films:
        print("No films found for today.")
        return

    # 2. Pick 3 "Cover Stars" from the Carousel List
    cover_selection = random.sample(carousel_films, min(3, len(carousel_films)))
    
    # 3. Build Collage & Context
    print("✂️ Assembling Cutouts...")
    collage_base, mask, film_context = build_collage(cover_selection)
    if not collage_base: return
    
    # 4. Gemini "Art Director" Step
    prompt = ask_gemini_for_prompt(collage_base, film_context)
    
    # 5. Replicate "Painter" Step
    final_art = run_inpainting(collage_base, mask, prompt)
    
    # 6. Typography & Save
    final_post = add_typography(final_art)
    out_path = BASE_DIR / OUTPUT_FILENAME
    final_post.save(out_path)
    print(f"✅ Saved V3 test to: {out_path}")

if __name__ == "__main__":
    main()
