"""
Generate Post V3 (Prototype): "The Dream Weaver"
- Concept: Collage of cinema stills with AI-inpainted surroundings.
- Update: Prioritizes POSTERS for better cutouts. Cleans titles.
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
DEBUG_FILENAME = "post_v3_debug_layout.png"

CANVAS_W, CANVAS_H = 1080, 1350

def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")

def clean_title(title):
    # Removes [1201], (Sub), etc.
    return re.sub(r'\[.*?\]|\(.*?\)', '', title).strip()

def load_showtimes_for_today():
    if not SHOWTIMES_PATH.exists():
        print("❌ showtimes.json not found.")
        return []
    
    with open(SHOWTIMES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    today_str = get_today_str()
    print(f"📅 Filtering for date: {today_str}")

    valid_films = []
    seen_titles = set()
    
    for film in data:
        if film.get('date_text') != today_str: continue
        # Must have at least one image
        if not (film.get('tmdb_backdrop_path') or film.get('tmdb_poster_path')): continue
        
        title = film.get('movie_title')
        if title in seen_titles: continue
        
        seen_titles.add(title)
        valid_films.append(film)

    random.shuffle(valid_films)
    # Pick Top 9
    return valid_films[:9]

def fetch_image(url):
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return Image.open(BytesIO(resp.content)).convert("RGBA")
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return None

def remove_background(pil_img):
    """
    Uses Replicate to remove background, creating a true 'cutout'.
    """
    print("   ✂️ Removing background (Replicate)...")
    if not REPLICATE_API_TOKEN:
        return pil_img

    # Downscale slightly for speed/reliability
    pil_img.thumbnail((1024, 1024)) 
    
    temp_path = BASE_DIR / "temp_rembg_in.png"
    pil_img.save(temp_path, format="PNG")
    
    try:
        output = replicate.run(
            "lucataco/remove-bg:95fcc2a26d3899cd6c2691c900465aaeff466285a65c14638cc5f36f34befaf1",
            input={"image": open(temp_path, "rb")}
        )
        if output:
            resp = requests.get(str(output))
            cutout = Image.open(BytesIO(resp.content)).convert("RGBA")
            # Validation: Did it actually cut anything?
            # If the alpha channel is fully opaque (255), rembg likely failed to find a subject.
            extrema = cutout.getextrema()
            alpha_extrema = extrema[3] # (min, max) of alpha
            if alpha_extrema[0] == 255:
                print("   ⚠️ Warning: result is fully opaque (Rectangular).")
            return cutout
    except Exception as e:
        print(f"   ❌ Cutout failed: {e}")
    
    return pil_img 

def build_collage(films):
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    context_lines = []
    placed_count = 0

    for film in films:
        if placed_count >= 3: break 
        
        # KEY CHANGE: Prioritize Poster for Cutouts (Better subjects)
        path = film.get("tmdb_poster_path") or film.get("tmdb_backdrop_path")
        if not path: continue
        
        full_url = TMDB_BASE_URL + path
        raw_title = film.get('movie_title', 'Unknown')
        clean_t = clean_title(raw_title)
        
        print(f"🎨 Processing: {clean_t}")
        src_img = fetch_image(full_url)
        
        if src_img:
            # 1. Create Cutout
            cutout = remove_background(src_img)
            
            # 2. Add Context (Use Clean Title if synopsis missing)
            synopsis = film.get('tmdb_overview', '')
            if not synopsis or synopsis == "No synopsis available.":
                synopsis = f"A film titled '{clean_t}'."
            
            # Truncate
            synopsis = (synopsis[:150] + '..') if len(synopsis) > 150 else synopsis
            context_lines.append(f"- Film: {clean_t} | Context: {synopsis}")

            # 3. Resize & Rotate
            target_w = random.randint(500, 800) 
            ratio = target_w / cutout.width
            target_h = int(cutout.height * ratio)
            cutout = cutout.resize((target_w, target_h), Image.Resampling.LANCZOS)
            
            angle = random.uniform(-15, 15)
            cutout = cutout.rotate(angle, expand=True, resample=Image.BICUBIC)
            
            # 4. Position
            x = random.randint(-100, CANVAS_W - cutout.width + 100)
            y = random.randint(-100, CANVAS_H - cutout.height + 100)
            
            canvas.paste(cutout, (x, y), cutout)
            placed_count += 1
            
    if placed_count == 0:
        return None, None, None

    # Mask: White = Empty Space (Fill), Black = Sticker (Keep)
    alpha = canvas.split()[3]
    mask = ImageOps.invert(alpha)
    
    # Base: Grey helps the AI understand neutrality
    flat_canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), (128, 128, 128))
    flat_canvas.paste(canvas, (0, 0), canvas)
    
    context_str = "\n".join(context_lines)
    return flat_canvas, mask, context_str

def ask_gemini_for_prompt(collage_image, film_context):
    print("\n✨ --- GEMINI BRIEFING ---")
    print(f"Context Sent:\n{film_context}")
    
    if not GEMINI_API_KEY:
        print("❌ No GEMINI_API_KEY found.")
        return "surreal cinematic collage, atmospheric lighting"

    client = genai.Client(api_key=GEMINI_API_KEY)
    preview = collage_image.resize((512, 640))
    
    prompt = f"""
    You are an Art Director. I have placed 3 film characters on a canvas.
    
    Film Data:
    {film_context}

    Task:
    Write a 1-sentence prompt for an AI Image Generator (Flux) to FILL the empty grey space.
    The goal is a cohesive, high-art poster. 
    
    Guidelines:
    1. Do NOT describe the characters (they are locked).
    2. Describe the SURROUNDINGS: smoke, neon lights, abstract paint strokes, torn paper, floral decay, city bokeh.
    3. Make it surreal and textured.
    4. Return ONLY the prompt.
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt, preview]
        )
        suggestion = response.text.strip()
        suggestion = re.sub(r'^Prompt:\s*', '', suggestion, flags=re.IGNORECASE).strip('"')
        print(f"🤖 Gemini's Prompt: '{suggestion}'")
        print("---------------------------\n")
        return suggestion
    except Exception as e:
        print(f"⚠️ Gemini Error: {e}")
        return "cinematic atmosphere, high detail, 8k"

def run_inpainting(image, mask, prompt):
    print("🎨 Painting with Flux Fill (Replicate)...")
    if not REPLICATE_API_TOKEN: return image

    img_path = BASE_DIR / "temp_src.png"
    mask_path = BASE_DIR / "temp_mask.png"
    image.save(img_path)
    mask.save(mask_path)
    
    try:
        output = replicate.run(
            "black-forest-labs/flux-fill-dev",
            input={
                "image": open(img_path, "rb"),
                "mask": open(mask_path, "rb"),
                "prompt": prompt + ", masterpiece, high quality, 4k, seamless",
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
    try:
        font_path = BASE_DIR / "NotoSansJP-Bold.ttf"
        font = ImageFont.truetype(str(font_path), 80)
        small_font = ImageFont.truetype(str(font_path), 40)
    except:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    text = "TOKYO CINEMA"
    draw.text((55, 55), text, font=font, fill="black")
    draw.text((50, 50), text, font=font, fill="white")
    
    today = datetime.now().strftime("%Y.%m.%d")
    draw.text((55, 155), today, font=small_font, fill="black")
    draw.text((50, 150), today, font=small_font, fill="#FDB813")
    return img

def main():
    print("🚀 Starting Generate Post V3 (Sticker + Inpaint)...")
    
    films = load_showtimes_for_today()
    if not films:
        print("No films found.")
        return

    # Pick 3
    selection = random.sample(films, min(3, len(films)))
    
    # Layout
    collage, mask, ctx = build_collage(selection)
    if not collage: return
    
    # SAVE DEBUG
    collage.save(BASE_DIR / DEBUG_FILENAME)
    print(f"🐛 Saved debug layout to: {BASE_DIR / DEBUG_FILENAME}")

    # Gen
    prompt = ask_gemini_for_prompt(collage, ctx)
    final = run_inpainting(collage, mask, prompt)
    
    # Save
    final = add_typography(final)
    final.save(BASE_DIR / OUTPUT_FILENAME)
    print(f"✅ Saved V3 test to: {BASE_DIR / OUTPUT_FILENAME}")

if __name__ == "__main__":
    main()
