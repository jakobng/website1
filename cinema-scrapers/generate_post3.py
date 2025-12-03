"""
Generate Post V4: "The Curator"
- Fixes V3.2 crash by using anchor-based positioning (no invalid random ranges).
- Implements "Audition" workflow: Extract -> Curate -> Assemble -> Paint.
"""

import os
import json
import random
import requests
import re
import math
from pathlib import Path
from io import BytesIO
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageOps

# --- API Setup ---
try:
    import replicate
    REPLICATE_AVAILABLE = True
except ImportError:
    REPLICATE_AVAILABLE = False
    print("⚠️ Replicate library not found. Run: pip install replicate")

try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ Google GenAI library not found. Run: pip install google-genai")

# --- Secrets ---
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"
TMDB_BASE_URL = "https://image.tmdb.org/t/p/original"

# Output files
OUTPUT_FILENAME = "post_v4_result.png"
DEBUG_AUDITION_FILENAME = "post_v4_debug_audition.png" # The "Contact Sheet"
DEBUG_LAYOUT_FILENAME = "post_v4_debug_layout.png"     # The assembled collage before painting

CANVAS_W, CANVAS_H = 1080, 1350

def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")

def clean_title(title):
    return re.sub(r'\[.*?\]|\(.*?\)', '', title).strip()

def load_candidates():
    """Loads today's films to audition."""
    if not SHOWTIMES_PATH.exists(): 
        print("❌ showtimes.json not found.")
        return []
        
    with open(SHOWTIMES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    today = get_today_str()
    print(f"📅 Auditioning films for: {today}")
    
    candidates = []
    seen = set()
    for film in data:
        if film.get('date_text') != today: continue
        
        # User requested Horizontal images (Backdrops)
        # We fallback to poster if backdrop is missing, to ensure we get enough candidates
        path = film.get('tmdb_backdrop_path')
        img_type = "backdrop"
        
        if not path:
            path = film.get('tmdb_poster_path')
            img_type = "poster"

        if not path: continue
        
        t = film.get('movie_title')
        if t in seen: continue
        seen.add(t)
        
        candidates.append({
            "film": film,
            "path": path,
            "type": img_type
        })
        
    random.shuffle(candidates)
    # Audition top 9 (Process stops once we get enough successful cuts)
    return candidates[:9]

def fetch_image(url):
    try:
        resp = requests.get(url, timeout=10)
        return Image.open(BytesIO(resp.content)).convert("RGBA")
    except:
        return None

def remove_background(pil_img):
    """Returns the cutout or None if failed."""
    if not REPLICATE_AVAILABLE or not REPLICATE_API_TOKEN: return pil_img
    
    # Resize for speed and better focus
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
            
            # Validation: Check if image is empty (fully transparent)
            extrema = cutout.getextrema() # ((min, max), (min, max), ...)
            if extrema[3][1] == 0: 
                print("   ⚠️ Result was empty (transparent). Skipping.")
                return None
            return cutout
    except Exception as e:
        print(f"   ❌ Rembg error: {e}")
    return None

def create_contact_sheet(cutouts):
    """Creates a numbered grid of candidates for Gemini to review."""
    count = len(cutouts)
    if count == 0: return None
    
    cols = 3
    rows = math.ceil(count / cols)
    cell_w, cell_h = 300, 300
    
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (50, 50, 50))
    draw = ImageDraw.Draw(sheet)
    
    try:
        font_path = BASE_DIR / "NotoSansJP-Bold.ttf"
        font = ImageFont.truetype(str(font_path), 40)
    except:
        font = ImageFont.load_default()

    for i, item in enumerate(cutouts):
        img = item['img']
        # Thumbnail for contact sheet (copy so we don't affect original)
        thumb = img.copy()
        thumb.thumbnail((280, 280))
        
        c = i % cols
        r = i // cols
        x = c * cell_w + 10
        y = r * cell_h + 10
        
        sheet.paste(thumb, (x, y), thumb)
        
        # Label ID
        label = str(item['id'])
        # Yellow Text with Black Stroke
        draw.text((x+10, y+10), label, font=font, fill="#FDB813", stroke_width=2, stroke_fill="black")
        
    return sheet

def ask_gemini_selection(contact_sheet, candidates_info):
    """Step 1: Ask Gemini which 3 fit together."""
    print("\n🧠 --- GEMINI CASTING (Step 1) ---")
    if not GEMINI_API_KEY: return {"selected_ids": [0, 1, 2], "concept": "Fallback"}
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # Simplify context for API
    simple_ctx = []
    for c in candidates_info:
        simple_ctx.append({
            "id": c['id'],
            "title": c['title'],
            "genre": c['genre'],
            "synopsis": c['synopsis']
        })

    prompt = f"""
    You are a Film Curator. I have extracted characters from different movies (labeled 0-{len(candidates_info)-1} in the image).
    
    CONTEXT:
    {json.dumps(simple_ctx, indent=2, ensure_ascii=False)}

    TASK:
    1. Select exactly 3 candidates that form a compelling narrative trio.
    2. Imagine a scene they are starring in (e.g. "A heist planning meeting," "Lost in a cyberpunk city," "Waiting for a train").
    
    OUTPUT JSON:
    {{
        "selected_ids": [0, 1, 2],
        "concept": "The three characters are standing in..."
    }}
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt, contact_sheet]
        )
        text = response.text.strip()
        # Extract JSON block
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            print(f"🤖 Selected: {data.get('selected_ids')}")
            print(f"🤖 Concept: {data.get('concept')}")
            return data
    except Exception as e:
        print(f"⚠️ Gemini Selection Error: {e}")
        
    return {"selected_ids": [0, 1, 2], "concept": "Cinematic Collage"}

def ask_gemini_prompt(layout_image, concept_text):
    """Step 2: Ask Gemini to light the scene."""
    print("\n🎨 --- GEMINI DIRECTION (Step 2) ---")
    if not GEMINI_API_KEY: return "cinematic collage"
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    preview = layout_image.resize((512, 640))
    
    prompt = f"""
    You are a VFX Artist. I have placed 3 extracted characters on a grey canvas.
    
    CONCEPT:
    "{concept_text}"
    
    TASK:
    Write a descriptive prompt for 'Flux Fill' (AI Inpainting) to turn this into a finished masterpiece.
    - Describe the ENVIRONMENT that connects them (fog, water, neon lights, ruins).
    - Describe the LIGHTING (volumetric, cinematic, shadowy).
    - Do NOT describe the characters (they are locked).
    - Return ONLY the prompt string.
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt, preview]
        )
        p = response.text.strip().replace("Prompt:", "").replace('"', '').strip()
        print(f"🤖 Visual Prompt: {p}")
        return p
    except:
        return "cinematic high quality collage, atmospheric lighting"

def build_layout(selected_items):
    """Places the 3 selected items on the canvas."""
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0,0,0,0))
    
    # Safe Anchors (Preventing the V3 crash)
    # We define fixed "center points" for the characters
    anchors = [
        (CANVAS_W//2, CANVAS_H - 100),   # Center Bottom (Main)
        (300, CANVAS_H - 300),           # Left Mid
        (CANVAS_W - 300, CANVAS_H - 300) # Right Mid
    ]
    random.shuffle(anchors)
    
    for i, item in enumerate(selected_items):
        if i >= 3: break
        img = item['img']
        
        # Resize logic
        target_w = random.randint(600, 850)
        ratio = target_w / img.width
        target_h = int(img.height * ratio)
        
        # Safety Check: Limit max height to prevent overflow
        if target_h > 1000:
            target_h = 1000
            target_w = int(target_h / ratio)

        img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        
        # Anchor logic: x is center, y is bottom
        ax, ay = anchors[i]
        
        x = ax - (img.width // 2)
        y = ay - img.height 
        
        # Add random jitter
        x += random.randint(-50, 50)
        y += random.randint(-50, 50)
        
        # Clamp to canvas
        x = max(-200, min(x, CANVAS_W - 200))
        y = max(100, min(y, CANVAS_H - 200)) # Ensure it's not off-screen
        
        canvas.paste(img, (x, y), img)
        
    # Mask & Grey Base
    alpha = canvas.split()[3]
    mask = ImageOps.invert(alpha)
    flat = Image.new("RGB", (CANVAS_W, CANVAS_H), (128, 128, 128))
    flat.paste(canvas, (0,0), canvas)
    
    return flat, mask

def add_typography(img):
    draw = ImageDraw.Draw(img)
    try:
        font_path = BASE_DIR / "NotoSansJP-Bold.ttf"
        font = ImageFont.truetype(str(font_path), 120)
        small_font = ImageFont.truetype(str(font_path), 40)
    except:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Simple, Bold Title
    text = "TOKYO CINEMA"
    draw.text((60, 60), text, font=font, fill="white", stroke_width=4, stroke_fill="black")
    
    today = datetime.now().strftime("%Y.%m.%d")
    draw.text((65, 180), today, font=small_font, fill="#FDB813", stroke_width=2, stroke_fill="black")
    
    return img

def main():
    print("🚀 Starting V4 (The Curator)...")
    
    # 1. Audition
    candidates = load_candidates()
    processed_roster = []
    
    print("✂️  Running Auditions...")
    for i, item in enumerate(candidates):
        if len(processed_roster) >= 6: break # Stop if we have enough
        
        film = item['film']
        url = TMDB_BASE_URL + item['path']
        print(f"   Auditioning {i+1}: {clean_title(film['movie_title'])}...")
        
        src = fetch_image(url)
        if src:
            cutout = remove_background(src)
            if cutout:
                processed_roster.append({
                    "id": len(processed_roster), # re-index 0 to N
                    "title": clean_title(film['movie_title']),
                    "genre": ", ".join(film.get('genres', [])),
                    "synopsis": film.get('tmdb_overview', '')[:100],
                    "img": cutout
                })
                
    if len(processed_roster) < 3:
        print("❌ Not enough successful cutouts (Need 3).")
        return

    # 2. Contact Sheet
    sheet = create_contact_sheet(processed_roster)
    if sheet:
        sheet.save(BASE_DIR / DEBUG_AUDITION_FILENAME)
        print(f"📸 Contact sheet saved: {DEBUG_AUDITION_FILENAME}")
    
    # 3. Gemini Casting
    selection_data = ask_gemini_selection(sheet, processed_roster)
    selected_ids = selection_data.get('selected_ids', [])[:3]
    concept = selection_data.get('concept', 'Collage')
    
    # Filter list
    final_cast = [c for c in processed_roster if c['id'] in selected_ids]
    if len(final_cast) < 3:
        print("⚠️ Gemini selection invalid, picking top 3.")
        final_cast = processed_roster[:3]

    # 4. Build Layout
    layout, mask = build_layout(final_cast)
    layout.save(BASE_DIR / DEBUG_LAYOUT_FILENAME)
    print(f"📐 Layout saved: {DEBUG_LAYOUT_FILENAME}")
    
    # 5. Gemini Direction
    viz_prompt = ask_gemini_prompt(layout, concept)
    
    # 6. Inpaint
    print("🎨 Inpainting...")
    if REPLICATE_AVAILABLE and REPLICATE_API_TOKEN:
        layout.save(BASE_DIR / "temp_src.png")
        mask.save(BASE_DIR / "temp_mask.png")
        try:
            output = replicate.run(
                "black-forest-labs/flux-fill-dev",
                input={
                    "image": open(BASE_DIR / "temp_src.png", "rb"),
                    "mask": open(BASE_DIR / "temp_mask.png", "rb"),
                    "prompt": viz_prompt + ", masterpiece, high quality, 4k",
                    "guidance": 30,
                    "output_format": "png"
                }
            )
            if output:
                res = requests.get(str(output) if not isinstance(output, list) else output[0])
                final = Image.open(BytesIO(res.content))
                final = add_typography(final)
                final.save(BASE_DIR / OUTPUT_FILENAME)
                print(f"✅ Success! Saved to {OUTPUT_FILENAME}")
        except Exception as e:
            print(f"❌ Replicate Error: {e}")
    else:
        print("⚠️ Replicate skipped (No Token/Lib).")

if __name__ == "__main__":
    main()
