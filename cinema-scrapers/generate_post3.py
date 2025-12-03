"""
Generate Post V3 (Prototype): "The Dream Weaver"
- Concept: Collage of cinema stills with AI-inpainted surroundings.
- Update: Uses 'rembg' for true cutouts and saves debug layouts.
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

# Canvas Settings (Instagram Portrait)
CANVAS_W, CANVAS_H = 1080, 1350

def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")

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
        if not (film.get('tmdb_backdrop_path') or film.get('tmdb_poster_path')): continue
        
        title = film.get('movie_title')
        if title in seen_titles: continue
        
        seen_titles.add(title)
        valid_films.append(film)

    random.shuffle(valid_films)
    carousel_films = valid_films[:9]
    return carousel_films

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
        print("   ⚠️ No API Token. Skipping cutout.")
        return pil_img

    # Resize to speed up processing (we don't need 4k for a cutout)
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
            return Image.open(BytesIO(resp.content)).convert("RGBA")
    except Exception as e:
        print(f"   ❌ Cutout failed: {e}")
        return pil_img # Fallback to original square
    
    return pil_img

def build_collage(films):
    """
    Places cutouts on a transparent canvas.
    Returns: (composite_rgb, mask, film_context_string)
    """
    # Create base canvas (Transparent)
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    context_lines = []

    placed_count = 0
    for film in films:
        if placed_count >= 3: break 
        
        path = film.get("tmdb_backdrop_path") or film.get("tmdb_poster_path")
        if not path: continue
        
        full_url = TMDB_BASE_URL + path
        print(f"🎨 Processing: {film.get('movie_title')}")
        src_img = fetch_image(full_url)
        
        if src_img:
            # 1. Create Cutout
            cutout = remove_background(src_img)
            
            # 2. Add Context
            title = film.get('movie_title', 'Unknown Film')
            synopsis = film.get('tmdb_overview', 'No synopsis available.')
            synopsis = (synopsis[:150] + '..') if len(synopsis) > 150 else synopsis
            context_lines.append(f"- Film: '{title}'. Context: {synopsis}")

            # 3. Resize & Rotate
            # Random scale relative to canvas
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
        print("❌ No images could be placed.")
        return None, None, None

    # Create Mask (White = Fill, Black = Keep)
    alpha = canvas.split()[3]
    mask = ImageOps.invert(alpha)
    
    # Create RGB Base (Grey background for valid parts)
    # The grey background helps the model understand "this is empty space" vs "this is a black object"
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
    You are an Art Director. I have placed cutout characters from 3 films on a grey canvas.
    
    Film Context:
    {film_context}

    Task:
    Write a prompt for an AI Image Generator (Flux) to FILL the grey empty space.
    The goal is to create a seamless, surreal poster where these characters exist in a unified world.
    
    Guidelines:
    1. Do NOT describe the characters (they are already there).
    2. Describe the ATMOSPHERE, TEXTURE, and LIGHTING that connects them.
    3. Use keywords like: "thick fog," "neon rain," "crumpled paper texture," "double exposure," "cinematic grain."
    4. Return ONLY the prompt string.
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
                "prompt": prompt + ", masterpiece, high quality, 4k, seamless integration",
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
    
    carousel_films = load_showtimes_for_today()
    if not carousel_films:
        print("No films found for today.")
        return

    cover_selection = random.sample(carousel_films, min(3, len(carousel_films)))
    
    # Build Layout
    collage_base, mask, film_context = build_collage(cover_selection)
    if not collage_base: return
    
    # SAVE DEBUG IMAGE
    debug_path = BASE_DIR / DEBUG_FILENAME
    collage_base.save(debug_path)
    print(f"🐛 Saved debug layout to: {debug_path}")

    # Gemini
    prompt = ask_gemini_for_prompt(collage_base, film_context)
    
    # Inpaint
    final_art = run_inpainting(collage_base, mask, prompt)
    
    # Finish
    final_post = add_typography(final_art)
    out_path = BASE_DIR / OUTPUT_FILENAME
    final_post.save(out_path)
    print(f"✅ Saved V3 test to: {out_path}")

if __name__ == "__main__":
    main()
