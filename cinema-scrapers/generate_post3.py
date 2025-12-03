"""
Generate Post V10.1: "Pure Python & AI Text"
- Logic:
  - No Numpy dependency (Easy install).
  - Selection: Relies on Gemini "Strict Mode" to ignore garbage cutouts.
  - Text: Asks Flux (via Gemini Prompt) to render typography in-scene.
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

# Filenames
OUTPUT_FILENAME = "post_v3_test.png"
DEBUG_AUDITION_FILENAME = "post_v3_debug_audition.png"
DEBUG_LAYOUT_FILENAME = "post_v3_debug_layout.png"

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
        
        path = film.get('tmdb_backdrop_path')
        if not path: path = film.get('tmdb_poster_path')
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
    Sends full resolution image to Replicate.
    No pixel analysis—we trust Gemini to reject bad results later.
    """
    if not REPLICATE_AVAILABLE or not REPLICATE_API_TOKEN: return pil_img
    
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
            
            # Basic sanity check: is it fully transparent?
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
    print("\n🧠 --- GEMINI CASTING (Strict Mode) ---")
    if not GEMINI_API_KEY: return {"selected_ids": [0, 1, 2], "concept": "Fallback"}
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    simple_ctx = [{"id": c['id'], "title": c['title'], "genres": c['genre']} for c in candidates_info]

    prompt = f"""
    You are a Film Curator. 
    Context: {json.dumps(simple_ctx, indent=2, ensure_ascii=False)}
    
    Look at the contact sheet (labeled 0, 1, 2...).
    
    TASK: Select exactly 3 candidates.
    CRITICAL:
    1. Only choose candidates where the subject is CLEAR and VISIBLE.
    2. Do NOT choose empty boxes or tiny debris.
    3. If a box looks empty, IGNORE IT.
    
    Return JSON: {{ "selected_ids": [0, 1, 2], "concept": "A brief description..." }}
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=[prompt, contact_sheet]
        )
        text = response.text.strip()
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
    except Exception as e:
        print(f"⚠️ Gemini Selection Error: {e}")
        
    return {"selected_ids": [0, 1, 2], "concept": "Cinematic Collage"}

def ask_gemini_prompt(layout_image, concept_text, date_str):
    print("\n🎨 --- GEMINI TRANSLATION (AI Typography) ---")
    if not GEMINI_API_KEY: return "cinematic collage"
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    preview = layout_image.resize((512, 640))
    
    prompt = f"""
    You are an AI Prompt Engineer for Flux.
    
    Goal: Create a cohesive movie poster from the attached layout.
    Concept: "{concept_text}"
    Required Text: "TOKYO CINEMA" and "{date_str}"
    
    Instructions for Flux:
    1. UNIFY the characters with a strong environment (lighting, fog, texture).
    2. INTEGRATE THE TEXT ("TOKYO CINEMA") into the scene naturally.
       (e.g., Neon sign, graffiti, projected light, cinematic title card style).
    3. Make the text LEGIBLE but STYLISH.
    4. Do not describe the characters (they are locked).

    Return ONLY the prompt string.
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=[prompt, preview]
        )
        return response.text.strip().replace("Prompt:", "").replace('"', '').strip()
    except:
        return f"cinematic high quality collage, text 'TOKYO CINEMA {date_str}'"

def build_layout(selected_items):
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0,0,0,0))
    cols = [0, 1, 2]
    random.shuffle(cols)
    rows = [0, 1, 2]
    random.shuffle(rows)
    
    for i, item in enumerate(selected_items):
        if i >= 3: break
        img = item['img']
        target_w = random.randint(550, 800)
        ratio = target_w / img.width
        target_h = int(img.height * ratio)
        if target_h > CANVAS_H * 0.6: 
            target_h = int(CANVAS_H * 0.6)
            target_w = int(target_h / ratio)
            
        img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        
        col = cols[i]
        if col == 0:   center_x = CANVAS_W * 0.2
        elif col == 1: center_x = CANVAS_W * 0.5
        else:          center_x = CANVAS_W * 0.8
        
        x = int(center_x - (img.width / 2))
        x += random.randint(-50, 50)
        
        row = rows[i]
        padding = 200 # Space for text
        
        if row == 0:   # Top
            min_y, max_y = padding, int(CANVAS_H * 0.33)
        elif row == 1: # Mid
            min_y, max_y = int(CANVAS_H * 0.33), int(CANVAS_H * 0.66)
        else:          # Bot
            min_y, max_y = int(CANVAS_H * 0.66), CANVAS_H - padding - img.height
            
        max_y = max(min_y, max_y)
        y = random.randint(min_y, max_y)
        
        canvas.paste(img, (x, y), img)
        print(f"   Placed Item {item['id']} at ({x}, {y}) [Col:{col}, Row:{row}]")
        
    alpha = canvas.split()[3]
    mask = ImageOps.invert(alpha)
    flat = Image.new("RGB", (CANVAS_W, CANVAS_H), (128, 128, 128))
    flat.paste(canvas, (0,0), canvas)
    
    return flat, mask

def main():
    print("🚀 Starting V10.1 (No Numpy)...")
    
    candidates = load_candidates()
    processed_roster = []
    
    print("✂️  Auditioning...")
    for i, item in enumerate(candidates):
        if len(processed_roster) >= 6: break 
        url = TMDB_BASE_URL + item['path']
        print(f"   Processing {i+1}: {clean_title(item['film']['movie_title'])}...")
        
        src = fetch_image(url)
        if src:
            cutout = remove_background(src)
            if cutout:
                processed_roster.append({
                    "id": len(processed_roster), 
                    "title": clean_title(item['film']['movie_title']),
                    "genre": ", ".join(item['film'].get('genres', [])),
                    "img": cutout
                })
                
    if len(processed_roster) < 3:
        print("❌ Not enough cutouts.")
        return

    sheet = create_contact_sheet(processed_roster)
    if sheet: sheet.save(BASE_DIR / DEBUG_AUDITION_FILENAME)
    
    selection = ask_gemini_selection(sheet, processed_roster)
    ids = selection.get('selected_ids', [])[:3]
    final_cast = [c for c in processed_roster if c['id'] in ids]
    if len(final_cast) < 3: final_cast = processed_roster[:3]

    layout, mask = build_layout(final_cast)
    layout.save(BASE_DIR / DEBUG_LAYOUT_FILENAME)
    print(f"📐 Layout Saved: {DEBUG_LAYOUT_FILENAME}")
    
    date_str = get_formatted_date()
    viz_prompt = ask_gemini_prompt(layout, selection.get('concept', 'Collage'), date_str)
    
    print("🎨 Inpainting with AI Text...")
    if REPLICATE_AVAILABLE and REPLICATE_API_TOKEN:
        layout.save(BASE_DIR / "temp_src.png")
        mask.save(BASE_DIR / "temp_mask.png")
        try:
            output = replicate.run(
                "black-forest-labs/flux-fill-dev",
                input={
                    "image": open(BASE_DIR / "temp_src.png", "rb"),
                    "mask": open(BASE_DIR / "temp_mask.png", "rb"),
                    "prompt": viz_prompt + ", legible text, high quality, 4k",
                    "guidance": 40,
                    "output_format": "png"
                }
            )
            if output:
                res = requests.get(str(output) if not isinstance(output, list) else output[0])
                final = Image.open(BytesIO(res.content))
                final.save(BASE_DIR / OUTPUT_FILENAME)
                print(f"✅ Success! Saved to {BASE_DIR / OUTPUT_FILENAME}")
        except Exception as e:
            print(f"❌ Replicate Error: {e}")

if __name__ == "__main__":
    main()
