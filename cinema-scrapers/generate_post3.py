"""
Generate Post V3.2: "The Coherent Dream"
- Visuals: Uses AI Background Removal (rembg) on ALL images to get clean subjects.
- Logic: Places subjects on canvas, then asks Gemini to "unify" them.
- Prompting: deeply descriptive, asking for interaction and cohesive lighting.
"""

import os
import json
import random
import requests
import re
from pathlib import Path
from io import BytesIO
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

# --- API Setup ---
try:
    import replicate
    REPLICATE_AVAILABLE = True
except ImportError:
    REPLICATE_AVAILABLE = False
    print("⚠️ Replicate library not found.")

try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ Google GenAI library not found.")

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
        if not (film.get('tmdb_backdrop_path') or film.get('tmdb_poster_path')): continue
        
        title = film.get('movie_title')
        if title in seen_titles: continue
        
        seen_titles.add(title)
        valid_films.append(film)

    random.shuffle(valid_films)
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
    Uses Replicate to remove background.
    """
    print("   ✂️  Extracting subject (Replicate)...")
    if not REPLICATE_AVAILABLE or not REPLICATE_API_TOKEN:
        return pil_img

    # Resize to speed up API and ensure focus
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
            
            # Check if it failed (returned empty or full block)
            extrema = cutout.getextrema()
            alpha_extrema = extrema[3]
            if alpha_extrema[1] == 0: 
                print("   ⚠️ Warning: Subject extraction returned empty image.")
                return pil_img # Fallback to original
                
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
        
        # Try poster first for clearer subjects, then backdrop
        path = film.get("tmdb_poster_path") or film.get("tmdb_backdrop_path")
        if not path: continue
        
        full_url = TMDB_BASE_URL + path
        clean_t = clean_title(film.get('movie_title', 'Unknown'))
        
        print(f"🎨 Processing: {clean_t}")
        src_img = fetch_image(full_url)
        
        if src_img:
            # 1. Extract Subject
            cutout = remove_background(src_img)
            
            # 2. Context
            genres = film.get('genres', [])
            genre_str = ", ".join(genres) if genres else "General Cinema"
            synopsis = film.get('tmdb_overview', 'No synopsis.')[:100]
            context_lines.append(f"- Subject from '{clean_t}' ({genre_str}): {synopsis}")

            # 3. Resize & Position
            # We want them large enough to interact
            target_w = random.randint(550, 850)
            ratio = target_w / cutout.width
            target_h = int(cutout.height * ratio)
            cutout = cutout.resize((target_w, target_h), Image.Resampling.LANCZOS)
            
            # Subtle rotation
            angle = random.uniform(-5, 5)
            cutout = cutout.rotate(angle, expand=True, resample=Image.BICUBIC)
            
            # Scatter but keep somewhat central
            x = random.randint(-50, CANVAS_W - cutout.width + 50)
            y = random.randint(100, CANVAS_H - cutout.height - 100)
            
            canvas.paste(cutout, (x, y), cutout)
            placed_count += 1
            
    if placed_count == 0:
        return None, None, None

    # Create Mask
    alpha = canvas.split()[3]
    mask = ImageOps.invert(alpha) # White = Fill
    
    # Grey Base
    flat_canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), (128, 128, 128))
    flat_canvas.paste(canvas, (0, 0), canvas)
    
    context_str = "\n".join(context_lines)
    return flat_canvas, mask, context_str

def ask_gemini_for_prompt(collage_image, film_context):
    print("\n✨ --- GEMINI DIRECTOR MODE ---")
    print(f"Context Sent:\n{film_context}")
    
    if not GEMINI_API_KEY:
        return "surreal cinematic collage, atmospheric lighting"

    client = genai.Client(api_key=GEMINI_API_KEY)
    preview = collage_image.resize((512, 640))
    
    prompt = f"""
    You are an avant-garde Film Director. 
    I have given you a visual collage containing {film_context.count('Subject')} extracted characters from different movies (Context below).
    They are floating in grey space.
    
    FILM CONTEXT:
    {film_context}

    YOUR MISSION:
    Write a prompt for an AI Image Generator (Flux) that turns this collage into ONE COHERENT SCENE.
    
    INSTRUCTIONS:
    1. ANALYZE THE IMAGE: Look at where the characters are standing.
    2. CREATE A SCENARIO: Why are they together? (e.g. "Meeting in a foggy subway station," "Lost in a overgrown brutalist garden," "Standing in a neon-lit cyber bazaar").
    3. INTEGRATION: Describe the lighting and atmosphere so it wraps around them.
    4. FILL THE GAPS: Explicitly describe objects or textures to fill the grey space between them.
    
    OUTPUT FORMAT:
    Return ONLY the prompt string. Use vivid, visual keywords.
    Example: "A cinematic shot of three characters standing in a flooded cathedral, volumetric god rays, floating dust particles, water reflections connecting the figures, hyper-realistic 8k."
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt, preview]
        )
        suggestion = response.text.strip()
        suggestion = re.sub(r'^Prompt:\s*', '', suggestion, flags=re.IGNORECASE).strip('"')
        print(f"🤖 Gemini's Direction: '{suggestion}'")
        return suggestion
    except Exception as e:
        print(f"⚠️ Gemini Error: {e}")
        return "cinematic atmosphere, high detail, collage style"

def run_inpainting(image, mask, prompt):
    print("🎨 Painting with Flux Fill (Replicate)...")
    if not REPLICATE_AVAILABLE or not REPLICATE_API_TOKEN: return image

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
                "prompt": prompt + ", seamless blend, cinematic lighting, 8k, masterpiece",
                "guidance": 30, # High adherence to prompt
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
    print("🚀 Starting Generate Post V3.2 (Coherent Interaction)...")
    films = load_showtimes_for_today()
    if not films:
        print("No films found.")
        return

    selection = random.sample(films, min(3, len(films)))
    
    collage, mask, ctx = build_collage(selection)
    if not collage: return
    
    # Save Debug
    collage.save(BASE_DIR / DEBUG_FILENAME)
    print(f"🐛 Saved debug layout to: {BASE_DIR / DEBUG_FILENAME}")

    prompt = ask_gemini_for_prompt(collage, ctx)
    final = run_inpainting(collage, mask, prompt)
    
    final = add_typography(final)
    final.save(BASE_DIR / OUTPUT_FILENAME)
    print(f"✅ Saved V3 test to: {BASE_DIR / OUTPUT_FILENAME}")

if __name__ == "__main__":
    main()
