"""
Generate Post V16: "The Hybrid Pro"
- Step 1: Replicate (remove-bg) for precise character cutouts.
- Step 2: Gemini 3 Pro (Nano Banana) for scene composition and native text rendering.
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
    from google.genai import types
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

OUTPUT_FILENAME = "post_v3_test.png"
CANVAS_W, CANVAS_H = 1080, 1350

def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")

def get_formatted_date():
    return datetime.now().strftime("%b %d, %Y").upper()

def clean_title(title):
    return re.sub(r'\[.*?\]|\(.*?\)', '', title).strip()

def load_candidates():
    if not SHOWTIMES_PATH.exists(): return []
    with open(SHOWTIMES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    today = get_today_str()
    print(f"📅 Auditioning films for: {today}")
    
    candidates = []
    seen = set()
    for film in data:
        if film.get('date_text') != today: continue
        path = film.get('tmdb_backdrop_path') or film.get('tmdb_poster_path')
        if not path: continue
        t = film.get('movie_title')
        if t in seen: continue
        seen.add(t)
        candidates.append({"film": film, "path": path})
        
    random.shuffle(candidates)
    return candidates[:9]

def fetch_image(url):
    try:
        resp = requests.get(url, timeout=10)
        return Image.open(BytesIO(resp.content)).convert("RGBA")
    except:
        return None

def remove_background(pil_img):
    """
    Uses Replicate to create a high-quality cutout.
    """
    if not REPLICATE_AVAILABLE or not REPLICATE_API_TOKEN: 
        print("⚠️ Replicate unavailable, skipping cutout.")
        return pil_img
    
    # Save temp file
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
            
            # Simple check for empty image
            if cutout.getextrema()[3][1] == 0: 
                return None
            return cutout
    except Exception as e:
        print(f"   ❌ Rembg error: {e}")
    return None

def create_contact_sheet(cutouts):
    count = len(cutouts)
    if count == 0: return None
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
        thumb = img.copy()
        thumb.thumbnail((280, 280))
        c = i % cols
        r = i // cols
        x = c * cell_w + 10
        y = r * cell_h + 10
        sheet.paste(thumb, (x, y), thumb)
        draw.text((x+10, y+10), str(item['id']), font=font, fill="#FDB813", stroke_width=2, stroke_fill="black")
    return sheet

def ask_gemini_selection(contact_sheet, candidates_info):
    print("\n🧠 --- GEMINI CASTING (Model: 2.5-flash) ---")
    if not GEMINI_API_KEY: return {"selected_ids": [0, 1, 2], "concept": "Fallback"}
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    simple_ctx = [{"id": c['id'], "title": c['title']} for c in candidates_info]

    prompt = f"""
    You are a Film Curator.
    Context: {json.dumps(simple_ctx, indent=2, ensure_ascii=False)}
    TASK: Select exactly 3 candidates.
    CRITICAL: Choose clear subjects. Ignore debris.
    Return JSON: {{ "selected_ids": [0, 1, 2], "concept": "Shared mood..." }}
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt, contact_sheet]
        )
        text = response.text.strip()
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
    except Exception as e:
        print(f"⚠️ Gemini Selection Error: {e}")
    return {"selected_ids": [0, 1, 2], "concept": "Cinematic Collage"}

def build_layout(selected_items):
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0,0,0,0))
    cols = [0, 1, 2]
    random.shuffle(cols)
    rows = [0, 1, 2]
    random.shuffle(rows)
    
    for i, item in enumerate(selected_items):
        if i >= 3: break
        img = item['img']
        
        target_w = random.randint(600, 850)
        ratio = target_w / img.width
        target_h = int(img.height * ratio)
        if target_h > CANVAS_H * 0.55:
            target_h = int(CANVAS_H * 0.55)
            target_w = int(target_h / ratio)
            
        img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        
        col = cols[i]
        if col == 0: center_x = CANVAS_W * 0.2
        elif col == 1: center_x = CANVAS_W * 0.5
        else: center_x = CANVAS_W * 0.8
        x = int(center_x - (img.width / 2)) + random.randint(-50, 50)
        
        row = rows[i]
        if row == 0: min_y, max_y = 200, int(CANVAS_H * 0.33)
        elif row == 1: min_y, max_y = int(CANVAS_H * 0.33), int(CANVAS_H * 0.66)
        else: min_y, max_y = int(CANVAS_H * 0.66), CANVAS_H - 200 - img.height
        y = random.randint(min_y, max(min_y, max_y))
        
        canvas.paste(img, (x, y), img)
        print(f"   Placed Item {item['id']} at ({x}, {y})")
        
    flat = Image.new("RGB", (CANVAS_W, CANVAS_H), (128, 128, 128))
    flat.paste(canvas, (0,0), canvas)
    return flat

def generate_with_nano_banana(layout_image, concept_text, date_str):
    print("\n🍌 --- GENERATING WITH GEMINI 3 PRO (Nano Banana) ---")
    if not GEMINI_API_KEY: return None
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""
    Transform this collage layout into a coherent, interesting image.
    
    CONCEPT: {concept_text}
    
    INSTRUCTIONS:
    1. STYLE: Create a unified artistic style (e.g. painted, cinematic lighting, mixed media) that blends the characters into the background, and makes a coherent scene (i.e. shows the characters from different cutouts interacting with eachother)
    2. BACKGROUND: Fill the grey space with a detailed environment, texture and lighting that matches the concept.
    3. CHARACTERS: Keep the characters in their current positions, but blend their lighting so they belong in the scene.
    4. TEXT: Render the text "TOKYO CINEMA" and "{date_str}" into the artwork. 
       - The text should be legible, stylish, and part of the composition (in any style that fits the concept).
    
    Output a high-quality, photorealistic or artistic image.
    """
    
    print(f"📤 Sending to gemini-3-pro-image-preview...")

    try:
        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=[prompt, layout_image],
            config=types.GenerateContentConfig(
                response_modalities=['IMAGE'],
                image_config=types.ImageConfig(
                    aspect_ratio="4:5",
                    image_size="2K"
                )
            )
        )
        
        for part in response.parts:
            if part.inline_data:
                print("   ✅ Image received!")
                return Image.open(BytesIO(part.inline_data.data))
            elif hasattr(part, 'as_image'):
                 return part.as_image()

    except Exception as e:
        print(f"❌ Gemini Generation Error: {e}")
        return None

def main():
    print("🚀 Starting V16 (Hybrid Pro)...")
    
    candidates = load_candidates()
    processed_roster = []
    
    print("✂️  Auditioning...")
    for i, item in enumerate(candidates):
        if len(processed_roster) >= 6: break 
        url = TMDB_BASE_URL + item['path']
        src = fetch_image(url)
        if src:
            # Use Replicate for the cutout
            cutout = remove_background(src)
            if cutout:
                processed_roster.append({
                    "id": len(processed_roster), 
                    "title": clean_title(item['film']['movie_title']),
                    "img": cutout
                })
                print(f"   ✅ {item['film']['movie_title']}")

    if len(processed_roster) < 3:
        print("❌ Not enough cutouts.")
        return

    sheet = create_contact_sheet(processed_roster)
    selection = ask_gemini_selection(sheet, processed_roster)
    ids = selection.get('selected_ids', [])[:3]
    final_cast = [c for c in processed_roster if c['id'] in ids]
    if len(final_cast) < 3: final_cast = processed_roster[:3]

    layout = build_layout(final_cast)
    
    date_str = get_formatted_date()
    final_art = generate_with_nano_banana(layout, selection.get('concept', 'Collage'), date_str)
    
    if final_art:
        final_art.save(BASE_DIR / OUTPUT_FILENAME)
        print(f"✅ Success! Saved to {BASE_DIR / OUTPUT_FILENAME}")

if __name__ == "__main__":
    main()
