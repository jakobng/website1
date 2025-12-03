"""
Generate Post V9: "Quality Control"
- Logic:
  - Pre-Filter: Discards cutouts that are too small or mostly empty (debris).
  - Gemini Prompt: Updated to prioritize LEGIBILITY and RECOGNIZABILITY.
  - Layout: 3x3 Spread (No clumping).
"""

import os
import json
import random
import requests
import re
import math
import numpy as np
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
    V2 Logic: Send full resolution image to Replicate.
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
            
            # --- QUALITY CHECK ---
            # Calculate how much of the image is non-transparent
            # If it's mostly empty (tiny debris), reject it.
            alpha = np.array(cutout.resize((100, 100)).getchannel('A'))
            fill_ratio = np.count_nonzero(alpha) / alpha.size
            
            if fill_ratio < 0.05: # Less than 5% pixels = Garbage
                print(f"   ⚠️ Rejecting debris (Fill: {fill_ratio:.2f})")
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
    
    Look at the contact sheet. Each image is labeled with an ID (0, 1, 2...).
    
    TASK: Select exactly 3 candidates.
    
    STRICT SELECTION CRITERIA:
    1. **LEGIBILITY IS KEY**: Only choose images with CLEAR, RECOGNIZABLE subjects (Faces, People, Distinct Objects).
    2. **REJECT GARBAGE**: Do NOT choose blurry blobs, tiny distant figures, or unidentifiable debris.
    3. **COMPOSITION**: Choose 3 that look like they could belong in the same scene.
    
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

def ask_gemini_prompt(layout_image, concept_text):
    print("\n🎨 --- GEMINI TRANSLATION ---")
    if not GEMINI_API_KEY: return "cinematic collage"
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    preview = layout_image.resize((512, 640))
    
    prompt = f"""
    You are an AI Prompt Engineer for Flux.
    Concept: "{concept_text}"
    Input: A layout of 3 cutouts on grey.
    Task: Write a prompt to FILL the grey space. 
    Rules: 
    1. Do NOT describe the characters.
    2. Describe lighting, texture, and environment that UNIFIES them.
    3. Use art keywords (e.g. "Mixed media," "Surrealism," "Cinematic lighting," "Ethereal fog").
    Return ONLY the prompt string.
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=[prompt, preview]
        )
        return response.text.strip().replace("Prompt:", "").replace('"', '').strip()
    except:
        return "cinematic high quality collage"

def build_layout(selected_items):
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0,0,0,0))
    
    # 3x3 Grid Shuffle Logic
    cols = [0, 1, 2]
    random.shuffle(cols)
    rows = [0, 1, 2]
    random.shuffle(rows)
    
    for i, item in enumerate(selected_items):
        if i >= 3: break
        img = item['img']
        
        # 1. Resize
        target_w = random.randint(550, 800)
        ratio = target_w / img.width
        target_h = int(img.height * ratio)
        if target_h > CANVAS_H * 0.6: 
            target_h = int(CANVAS_H * 0.6)
            target_w = int(target_h / ratio)
            
        img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        
        # 2. Position X (Column-based)
        col = cols[i]
        if col == 0:   center_x = CANVAS_W * 0.2
        elif col == 1: center_x = CANVAS_W * 0.5
        else:          center_x = CANVAS_W * 0.8
        
        x = int(center_x - (img.width / 2))
        x += random.randint(-50, 50)
        
        # 3. Position Y (Row-based)
        row = rows[i]
        padding = 150
        
        if row == 0:   # Top
            min_y, max_y = padding, int(CANVAS_H * 0.33)
        elif row == 1: # Mid
            min_y, max_y = int(CANVAS_H * 0.33), int(CANVAS_H * 0.66)
        else:          # Bot
            min_y, max_y = int(CANVAS_H * 0.66), CANVAS_H - padding - img.height
            
        max_y = max(min_y, max_y)
        y = random.randint(min_y, max_y)
        
        # 4. Paste
        canvas.paste(img, (x, y), img)
        print(f"   Placed Item {item['id']} at ({x}, {y}) [Col:{col}, Row:{row}]")
        
    alpha = canvas.split()[3]
    mask = ImageOps.invert(alpha)
    flat = Image.new("RGB", (CANVAS_W, CANVAS_H), (128, 128, 128))
    flat.paste(canvas, (0,0), canvas)
    
    return flat, mask

def add_typography(img):
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(str(BASE_DIR / "NotoSansJP-Bold.ttf"), 120)
        small = ImageFont.truetype(str(BASE_DIR / "NotoSansJP-Bold.ttf"), 40)
    except:
        font = ImageFont.load_default()
        small = ImageFont.load_default()

    draw.text((60, 60), "TOKYO CINEMA", font=font, fill="white", stroke_width=4, stroke_fill="black")
    today = datetime.now().strftime("%Y.%m.%d")
    draw.text((65, 180), today, font=small, fill="#FDB813", stroke_width=2, stroke_fill="black")
    return img

def main():
    print("🚀 Starting V9 (Quality Control)...")
    
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
    
    viz_prompt = ask_gemini_prompt(layout, selection.get('concept', 'Collage'))
    
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
                print(f"✅ Success! Saved to {BASE_DIR / OUTPUT_FILENAME}")
        except Exception as e:
            print(f"❌ Replicate Error: {e}")

if __name__ == "__main__":
    main()
