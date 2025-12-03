"""
Generate Post V4: "The Curated Scene"
- Workflow:
  1. Extract subjects from multiple films (The "Audition").
  2. Show candidates to Gemini -> Ask to pick 3 that fit together.
  3. Assemble based on Gemini's logic.
  4. Show result to Gemini -> Ask for Inpainting Prompt.
  5. Inpaint (Flux).
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
    print("⚠️ Replicate library not found.")

try:
    from google import genai
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
OUTPUT_FILENAME = "post_v4_result.png"
DEBUG_SHEET_FILENAME = "post_v4_debug_audition.png"
DEBUG_LAYOUT_FILENAME = "post_v4_debug_layout.png"

CANVAS_W, CANVAS_H = 1080, 1350

def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")

def clean_title(title):
    return re.sub(r'\[.*?\]|\(.*?\)', '', title).strip()

def load_candidates():
    """Loads today's films to audition."""
    if not SHOWTIMES_PATH.exists(): return []
    with open(SHOWTIMES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    today = get_today_str()
    print(f"📅 Auditioning films for: {today}")
    
    candidates = []
    seen = set()
    for film in data:
        if film.get('date_text') != today: continue
        # User requested Horizontal images (Backdrops)
        if not film.get('tmdb_backdrop_path'): continue
        
        t = film.get('movie_title')
        if t in seen: continue
        seen.add(t)
        candidates.append(film)
        
    random.shuffle(candidates)
    # Limit to 6 to prevent timeouts/excessive API usage during audition
    return candidates[:6]

def fetch_image(url):
    try:
        resp = requests.get(url, timeout=10)
        return Image.open(BytesIO(resp.content)).convert("RGBA")
    except:
        return None

def remove_background(pil_img):
    """Returns the cutout or None if failed."""
    if not REPLICATE_AVAILABLE or not REPLICATE_API_TOKEN: return pil_img
    
    # Resize for speed
    pil_img.thumbnail((800, 800))
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
            # Check for empty result
            if cutout.getextrema()[3][1] == 0: return None
            return cutout
    except Exception as e:
        print(f"   ❌ Rembg error: {e}")
    return None

def create_contact_sheet(cutouts):
    """Creates a numbered grid of candidates for Gemini to review."""
    count = len(cutouts)
    cols = 3
    rows = math.ceil(count / cols)
    cell_w, cell_h = 300, 300
    
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (50, 50, 50))
    draw = ImageDraw.Draw(sheet)
    
    try:
        font = ImageFont.truetype(str(BASE_DIR / "NotoSansJP-Bold.ttf"), 40)
    except:
        font = ImageFont.load_default()

    for i, item in enumerate(cutouts):
        img = item['img']
        # Fit to cell
        img.thumbnail((280, 280))
        
        c = i % cols
        r = i // cols
        x = c * cell_w + 10
        y = r * cell_h + 10
        
        sheet.paste(img, (x, y), img)
        
        # Label ID
        label = str(item['id'])
        draw.text((x+10, y+10), label, font=font, fill="yellow", stroke_width=2, stroke_fill="black")
        
    return sheet

def ask_gemini_selection(contact_sheet, candidates_info):
    """Step 1: Ask Gemini which 3 fit together."""
    print("\n🧠 --- GEMINI CASTING (Step 1) ---")
    if not GEMINI_API_KEY: return [0, 1, 2] # Fallback
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""
    You are a Film Curator. I have extracted characters/objects from {len(candidates_info)} different movies.
    See the attached image (Candidates labeled 0 to {len(candidates_info)-1}).
    
    FILM CONTEXT:
    {json.dumps(candidates_info, indent=2, ensure_ascii=False)}

    TASK:
    1. Select exactly 3 candidates that could visually belong in the SAME SCENE (e.g., similar lighting, theme, or interesting contrast).
    2. Decide a LAYOUT strategy (Triangle, Linear, Depth).
    
    RETURN JSON ONLY:
    {{
        "selected_ids": [id_a, id_b, id_c],
        "layout_concept": "The three characters are meeting in a dark alley..."
    }}
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt, contact_sheet]
        )
        text = response.text.strip()
        # Extract JSON
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            print(f"🤖 Selected: {data.get('selected_ids')}")
            print(f"🤖 Concept: {data.get('layout_concept')}")
            return data
    except Exception as e:
        print(f"⚠️ Gemini Selection Error: {e}")
        
    return {"selected_ids": [0, 1, 2], "layout_concept": "Random placement"}

def ask_gemini_prompt(layout_image, concept_text):
    """Step 2: Ask Gemini to light the scene."""
    print("\n🎨 --- GEMINI DIRECTION (Step 2) ---")
    if not GEMINI_API_KEY: return "cinematic collage"
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    preview = layout_image.resize((512, 640))
    
    prompt = f"""
    You are a VFX Artist. I have assembled a collage based on this concept:
    "{concept_text}"
    
    The layout is attached. The grey area is empty space.
    
    TASK:
    Write a prompt for 'Flux Fill' (AI Inpainting) to unify these stickers into a MASTERPIECE.
    - Describe the connecting environment (fog, water, neon city, desert).
    - Describe the lighting that hits ALL characters consistently.
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
        return "cinematic high quality collage"

def build_layout(selected_items):
    """Places the 3 selected items on the canvas."""
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0,0,0,0))
    
    # Simple logic: Main character center, others supporting
    # (Future: Parse 'layout_concept' to adjust positions)
    
    positions = [
        (CANVAS_W//2, CANVAS_H - 200), # Center Low (Main)
        (250, CANVAS_H - 400),        # Left Mid
        (CANVAS_W - 250, CANVAS_H - 400) # Right Mid
    ]
    
    # Shuffle positions so it's not always 0=Center
    random.shuffle(positions)
    
    for i, item in enumerate(selected_items):
        if i >= 3: break
        img = item['img']
        
        # Resize logic (randomize slightly)
        target_w = random.randint(500, 750)
        ratio = target_w / img.width
        target_h = int(img.height * ratio)
        img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        
        # Center anchor
        x_anchor, y_anchor = positions[i]
        x = x_anchor - (img.width // 2)
        y = y_anchor - img.height # Anchor is bottom
        
        # Jitter
        x += random.randint(-50, 50)
        y += random.randint(-50, 50)
        
        canvas.paste(img, (x, y), img)
        
    # Mask & Grey Base
    alpha = canvas.split()[3]
    mask = ImageOps.invert(alpha)
    flat = Image.new("RGB", (CANVAS_W, CANVAS_H), (128, 128, 128))
    flat.paste(canvas, (0,0), canvas)
    
    return flat, mask

def main():
    print("🚀 Starting V4 (Audition & Curate)...")
    
    # 1. Audition (Extract subjects)
    raw_candidates = load_candidates()
    processed_candidates = []
    
    print("✂️  Running Auditions (Removing Backgrounds)...")
    for i, film in enumerate(raw_candidates):
        url = TMDB_BASE_URL + film.get('tmdb_backdrop_path')
        print(f"   Processing {i}: {clean_title(film['movie_title'])}")
        
        src = fetch_image(url)
        if src:
            cutout = remove_background(src)
            if cutout:
                processed_candidates.append({
                    "id": i,
                    "title": clean_title(film['movie_title']),
                    "genre": ", ".join(film.get('genres', [])),
                    "img": cutout
                })
                
    if len(processed_candidates) < 3:
        print("❌ Not enough successful cutouts (Need 3).")
        return

    # 2. Create Contact Sheet & Ask Gemini
    sheet = create_contact_sheet(processed_candidates)
    sheet.save(BASE_DIR / DEBUG_SHEET_FILENAME)
    
    # Prepare metadata for Gemini (exclude image objects)
    meta_for_ai = [{k: v for k, v in p.items() if k != 'img'} for p in processed_candidates]
    
    selection_data = ask_gemini_selection(sheet, meta_for_ai)
    selected_ids = selection_data.get('selected_ids', [])[:3]
    concept = selection_data.get('layout_concept', 'Collage')
    
    # Filter list
    final_roster = [c for c in processed_candidates if c['id'] in selected_ids]
    
    # 3. Build Layout
    layout, mask = build_layout(final_roster)
    layout.save(BASE_DIR / DEBUG_LAYOUT_FILENAME)
    
    # 4. Ask Gemini for Visuals
    viz_prompt = ask_gemini_prompt(layout, concept)
    
    # 5. Inpaint
    print("🎨 Inpainting...")
    if REPLICATE_AVAILABLE:
        layout.save(BASE_DIR / "temp_src.png")
        mask.save(BASE_DIR / "temp_mask.png")
        try:
            output = replicate.run(
                "black-forest-labs/flux-fill-dev",
                input={
                    "image": open(BASE_DIR / "temp_src.png", "rb"),
                    "mask": open(BASE_DIR / "temp_mask.png", "rb"),
                    "prompt": viz_prompt + ", high quality, 4k",
                    "output_format": "png"
                }
            )
            if output:
                res = requests.get(str(output) if not isinstance(output, list) else output[0])
                final = Image.open(BytesIO(res.content))
                
                # Typography
                try:
                    draw = ImageDraw.Draw(final)
                    font = ImageFont.truetype(str(BASE_DIR / "NotoSansJP-Bold.ttf"), 80)
                    draw.text((50, 50), "TOKYO CINEMA", font=font, fill="white", stroke_width=3, stroke_fill="black")
                except: pass
                
                final.save(BASE_DIR / OUTPUT_FILENAME)
                print("✅ Success.")
        except Exception as e:
            print(f"Replicate Error: {e}")

if __name__ == "__main__":
    main()
