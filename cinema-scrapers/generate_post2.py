"""
Generate Instagram-ready image carousel (V66 - "Gravity & Anchors").
- Design: Punk Zine / Structured Chaos.
- Logic:
  1. Uses ALL 9 images (1 BG + 8 Cutouts).
  2. Detects "Flat Edges" (cut-off bodies) via Gemini.
  3. ANCHORS flat edges to the canvas bounds (Bottom/Left/Right).
  4. Floats "complete" stickers in the empty space.
"""
from __future__ import annotations

import json
import random
import textwrap
import os
import glob
import requests
import math
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from io import BytesIO

# --- Imports ---
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageEnhance

# --- API Setup ---
try:
    import replicate
    REPLICATE_AVAILABLE = True
except ImportError:
    print("⚠️ Replicate library not found. Run: pip install replicate")
    REPLICATE_AVAILABLE = False

try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    print("⚠️ Google GenAI library not found. Run: pip install google-genai")
    GEMINI_AVAILABLE = False

# --- Secrets ---
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"
BOLD_FONT_PATH = BASE_DIR / "NotoSansJP-Bold.ttf"
REGULAR_FONT_PATH = BASE_DIR / "NotoSansJP-Regular.ttf"
OUTPUT_CAPTION_PATH = BASE_DIR / "post_v2_caption.txt"

CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350       # 4:5 Feed
STORY_CANVAS_HEIGHT = 1920 # 9:16 Story

# --- Helpers ---

def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")

def get_japanese_date_str():
    d = datetime.now()
    return f"{d.year}.{d.month:02}.{d.day:02}"

def download_image(path: str) -> Image.Image | None:
    if not path: return None
    url = path if path.startswith("http") else f"https://image.tmdb.org/t/p/w1280{path}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            return Image.open(BytesIO(resp.content)).convert("RGB")
    except:
        return None
    return None

def get_fonts():
    try:
        return {
            "cover_main_jp": ImageFont.truetype(str(BOLD_FONT_PATH), 110),
            "cover_sub_en": ImageFont.truetype(str(REGULAR_FONT_PATH), 55),
            "cover_date": ImageFont.truetype(str(REGULAR_FONT_PATH), 40),
            "title_jp": ImageFont.truetype(str(BOLD_FONT_PATH), 60),
            "title_en": ImageFont.truetype(str(REGULAR_FONT_PATH), 32),
            "meta": ImageFont.truetype(str(REGULAR_FONT_PATH), 24),
            "cinema": ImageFont.truetype(str(BOLD_FONT_PATH), 28),
            "times": ImageFont.truetype(str(REGULAR_FONT_PATH), 28),
        }
    except:
        print("⚠️ Fonts not found, using default.")
        d = ImageFont.load_default()
        return {k: d for k in ["cover_main_jp", "cover_sub_en", "cover_date", "title_jp", "title_en", "meta", "cinema", "times"]}

# --- Visual FX Helpers ---

def apply_film_grain(img):
    width, height = img.size
    noise_data = os.urandom(width * height)
    noise_img = Image.frombytes('L', (width, height), noise_data)
    if img.mode != 'RGBA': img = img.convert('RGBA')
    noise_img = noise_img.convert('RGBA')
    return Image.blend(img, noise_img, alpha=0.07).convert("RGB")

def create_sticker_style(img: Image.Image) -> Image.Image:
    """Adds white border + drop shadow to a cutout."""
    img = img.convert("RGBA")
    alpha = img.split()[3]
    # White Border
    border_mask = alpha.filter(ImageFilter.MaxFilter(9))
    sticker_base = Image.new("RGBA", img.size, (255, 255, 255, 0))
    sticker_base.paste((255, 255, 255, 255), (0,0), mask=border_mask)
    sticker_base.paste(img, (0,0), mask=alpha)
    
    # Shadow
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow_mask = border_mask.filter(ImageFilter.GaussianBlur(10))
    shadow_layer = Image.new("RGBA", img.size, (0,0,0,150))
    shadow.paste(shadow_layer, (10, 20), mask=shadow_mask)
    
    final = Image.new("RGBA", img.size, (0,0,0,0))
    final.paste(shadow, (0,0), mask=shadow)
    final.paste(sticker_base, (0,0), mask=sticker_base)
    return final

def create_single_bg(img: Image.Image, width, height) -> Image.Image:
    """Creates a simple, darkened, blurred background from 1 image."""
    ratio = img.width / img.height
    target_ratio = width / height
    if ratio > target_ratio:
        new_h = height
        new_w = int(new_h * ratio)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - width) // 2
        img = img.crop((left, 0, left+width, height))
    else:
        new_w = width
        new_h = int(new_w / ratio)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        top = (new_h - height) // 2
        img = img.crop((0, top, width, top+height))
        
    img = img.filter(ImageFilter.GaussianBlur(8)) # Heavy blur
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(0.5) # Darken to 50%
    return img

def remove_background(pil_img: Image.Image) -> Image.Image | None:
    if not REPLICATE_AVAILABLE or not REPLICATE_API_TOKEN:
        return None
    try:
        temp_path = BASE_DIR / "temp_rembg_in.png"
        pil_img.save(temp_path, format="PNG")
        output = replicate.run(
            "lucataco/remove-bg:95fcc2a26d3899cd6c2691c900465aaeff466285a65c14638cc5f36f34befaf1",
            input={"image": open(temp_path, "rb")}
        )
        if temp_path.exists(): os.remove(temp_path)
        if output:
            resp = requests.get(str(output))
            if resp.status_code == 200:
                return Image.open(BytesIO(resp.content)).convert("RGBA")
    except Exception as e:
        print(f"Replicate Error: {e}")
    return None

# --- AI Logic ---

def ask_gemini_for_selection(images: list[Image.Image]):
    """Call 1: Pick 1 Background."""
    if not GEMINI_AVAILABLE or not GEMINI_API_KEY:
        return 0
    print("🧠 (1/2) Gemini Selection...")
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = "Select ONE image index that is best for a blurred background (texture/landscape). Return JSON: {'bg_index': 0}"
        response = client.models.generate_content(model='gemini-2.5-flash', contents=[prompt, *images])
        clean_json = re.search(r'\{.*\}', response.text, re.DOTALL)
        if clean_json:
            data = json.loads(clean_json.group(0))
            return data.get("bg_index", 0)
    except:
        pass
    return 0

def ask_gemini_to_anchor_stickers(stickers: list[Image.Image]):
    """
    Call 2: The Anchor Manager.
    Analyzes stickers for flat edges (cut-offs).
    """
    if not GEMINI_AVAILABLE or not GEMINI_API_KEY:
        # Fallback: Anchor 50% to bottom, float rest
        return [{"sticker_index": i, "anchor": "bottom" if i%2==0 else "float", "scale_boost": 1.0} for i in range(len(stickers))]

    print("🧠 (2/2) Gemini Anchor Manager...")
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        # Resize inputs to save tokens
        small_stickers = [s.resize((256, int(256*s.height/s.width))) for s in stickers]
        
        prompt = """
        Analyze these transparent stickers. Look at their EDGES.
        
        1. ANCHOR CHECK:
           - If the person is cut off at the WAIST or KNEES (flat line at bottom) -> "bottom"
           - If the image is cut off at the LEFT side -> "left"
           - If the image is cut off at the RIGHT side -> "right"
           - If the person/ object is cut off at the TOP (flat line at top) - > "top"
           - If the person/object is complete (head and shoulders floating) -> "float"
        
        2. IMPORTANCE:
           - If it looks like a main character face -> scale_boost: 1.3
           - If it is small/background -> scale_boost: 0.8
        
        Return JSON: 
        {
          "layout": [
            { "sticker_index": 0, "anchor": "bottom", "scale_boost": 1.2 },
            { "sticker_index": 1, "anchor": "float", "scale_boost": 0.9 }
          ]
        }
        """
        response = client.models.generate_content(model='gemini-2.5-flash', contents=[prompt, *small_stickers])
        clean_json = re.search(r'\{.*\}', response.text, re.DOTALL)
        if clean_json:
            data = json.loads(clean_json.group(0))
            return data.get("layout", [])
    except Exception as e:
        print(f"⚠️ Gemini Anchor failed: {e}")
    
    return []

# --- Collage Engine ---

def create_chaotic_collage(images: list[Image.Image], width=1080, height=1350) -> Image.Image:
    if not images: return Image.new("RGB", (width, height), (20,20,20))

    # 1. Select BG
    bg_idx = ask_gemini_for_selection(images)
    bg_img = images[bg_idx]
    
    # The rest are cutouts (Max 8 to keep it sane, but using "all available" logic)
    fg_raw = [img for i, img in enumerate(images) if i != bg_idx]
    
    # 2. Build Background
    base_canvas = create_single_bg(bg_img, width, height)
    
    # 3. Cutouts (Process ALL)
    print(f"✂️ Cutting out {len(fg_raw)} stickers...")
    stickers = []
    for raw in fg_raw:
        cutout = remove_background(raw)
        if cutout:
            stickers.append(create_sticker_style(cutout))

    if not stickers: return apply_film_grain(base_canvas)

    # 4. AI Analysis
    layout_plan = ask_gemini_to_anchor_stickers(stickers)
    if not layout_plan:
        layout_plan = [{"sticker_index": i, "anchor": "bottom", "scale_boost": 1.0} for i in range(len(stickers))]

    # 5. Assembly (Gravity System)
    print("🏗️ Assembling Scene (Gravity Mode)...")
    
    # We want to draw "floaters" first (behind), then "anchors" (front)?
    # Actually, anchors usually cover the bottom, so they should be front.
    # Let's sort: Floaters first, then Anchors.
    
    def get_sort_key(item):
        a = item.get("anchor", "float")
        return 0 if a == "float" else 1
    
    layout_plan.sort(key=get_sort_key)
    
    occupied_zones = [] # Track roughly where we put things to avoid total overlap

    for instruction in layout_plan:
        idx = instruction.get("sticker_index")
        if idx is None or idx >= len(stickers): continue
        sticker = stickers[idx]
        
        anchor = instruction.get("anchor", "float")
        boost = float(instruction.get("scale_boost", 1.0))
        
        # Base Scale (Bigger than before)
        # We want them to take up ~45% of width by default
        base_w = width * 0.45
        target_w = int(base_w * boost)
        
        ratio = sticker.height / sticker.width
        target_h = int(target_w * ratio)
        s_placed = sticker.resize((target_w, target_h), Image.Resampling.LANCZOS)
        
        # Position Logic
        x, y = 0, 0
        
        if anchor == "bottom":
            # Place at bottom, random X
            y = height - s_placed.height + 20 # +20 to hide the jagged edge
            x = random.randint(-50, width - s_placed.width + 50)

        elif anchor == "top":
            # Place at top, random X
            y = -20 
            x = random.randint(-50, width - s_placed.width + 50)
            
        elif anchor == "left":
            x = -20
            y = random.randint(height//2, height - s_placed.height)
            
        elif anchor == "right":
            x = width - s_placed.width + 20
            y = random.randint(height//2, height - s_placed.height)
            
        else: # FLOAT
            # Avoid the "Text Box" (Center 30-70%)
            # We define safe zones: Top Band, or just random scatter
            s_placed = s_placed.rotate(random.randint(-15, 15), expand=True)
            
            # Try to find a spot
            attempts = 0
            while attempts < 5:
                # Weighted towards top half
                test_x = random.randint(50, width - s_placed.width - 50)
                test_y = random.randint(50, int(height * 0.6))
                
                # Check Center Collision (Simple Box)
                center_box = (width*0.3, height*0.3, width*0.7, height*0.7)
                sticker_center_x = test_x + s_placed.width//2
                sticker_center_y = test_y + s_placed.height//2
                
                if not (center_box[0] < sticker_center_x < center_box[2] and 
                        center_box[1] < sticker_center_y < center_box[3]):
                    x, y = test_x, test_y
                    break
                attempts += 1
            
            if attempts == 5: # Force it somewhere top corners
                x = random.choice([50, width - s_placed.width - 50])
                y = random.randint(50, 300)

        # Paste
        base_canvas.paste(s_placed, (x, y), s_placed)

    return apply_film_grain(base_canvas)

# --- Text & Final Output ---

def draw_final_cover(composite, fonts, is_story=False):
    width = CANVAS_WIDTH
    height = STORY_CANVAS_HEIGHT if is_story else CANVAS_HEIGHT
    bg = composite.copy()
    
    # Fill Crop
    bg_ratio = bg.width / bg.height
    target_ratio = width / height
    if bg_ratio > target_ratio:
        new_h = height
        new_w = int(new_h * bg_ratio)
        bg = bg.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - width) // 2
        bg = bg.crop((left, 0, left+width, height))
    else:
        new_w = width
        new_h = int(new_w / bg_ratio)
        bg = bg.resize((new_w, new_h), Image.Resampling.LANCZOS)
        top = (new_h - height) // 2
        bg = bg.crop((0, top, width, top+height))
        
    draw = ImageDraw.Draw(bg)
    cx, cy = width // 2, height // 2
    offset = -80 if is_story else 0
    
    # Shadows for text
    def draw_shadowed(text, font, y_pos, main_col=(255,255,255)):
        draw.text((cx + 3, y_pos + 3), text, font=font, fill=(0,0,0), anchor="mm")
        draw.text((cx, y_pos), text, font=font, fill=main_col, anchor="mm")

    draw_shadowed("今日の上映作品", fonts['cover_main_jp'], cy - 80 + offset)
    draw_shadowed("Today's Film Selection", fonts['cover_sub_en'], cy + 30 + offset, (230,230,230))
    draw_shadowed(get_japanese_date_str(), fonts['cover_date'], cy + 110 + offset, (180,180,180))

    return bg

def draw_centered_text(draw, y, text, font, fill, canvas_width):
    length = draw.textlength(text, font=font)
    x = (canvas_width - length) // 2
    draw.text((x, y), text, font=font, fill=fill)
    return y + font.size + 10

def draw_poster_slide(film, img_obj, fonts, is_story=False):
    width = CANVAS_WIDTH
    height = STORY_CANVAS_HEIGHT if is_story else CANVAS_HEIGHT
    bg = Image.new("RGB", (width, height), (15,15,15))
    bg = apply_film_grain(bg)
    draw = ImageDraw.Draw(bg)
    
    target_w = 950 if is_story else 900
    target_h = 850 if is_story else 640
    img_y = 180 if is_story else 140
    
    # Fit Image
    img_ratio = img_obj.width / img_obj.height
    if img_ratio > (target_w / target_h):
        new_h = target_h
        new_w = int(new_h * img_ratio)
        img_resized = img_obj.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - target_w) // 2
        img_final = img_resized.crop((left, 0, left+target_w, target_h))
    else:
        new_w = target_w
        new_h = int(new_w / img_ratio)
        img_resized = img_obj.resize((new_w, new_h), Image.Resampling.LANCZOS)
        top = (new_h - target_h) // 2
        img_final = img_resized.crop((0, top, target_w, top+target_h))
        
    bg.paste(img_final, ((width - target_w)//2, img_y))
    
    cursor = img_y + target_h + 50
    t_jp = film.get('clean_title_jp') or film.get('movie_title', '')
    cursor = draw_centered_text(draw, cursor, t_jp, fonts['title_jp'], (255,255,255), width)
    
    cursor += 20
    for cin in film.get('showings', {}):
        times = " ".join(sorted(film['showings'][cin]))
        draw_centered_text(draw, cursor, f"{cin}: {times}", fonts['times'], (200,200,200), width)
        cursor += 40
        
    return bg

# --- Main ---

def main():
    print("--- Starting V66 (Gravity & Anchors) ---")
    
    for f in glob.glob(str(BASE_DIR / "post_v2_*.png")): os.remove(f)
    for f in glob.glob(str(BASE_DIR / "story_v2_*.png")): os.remove(f)

    date_str = get_today_str()
    if not SHOWTIMES_PATH.exists(): 
        print("Showtimes file missing.")
        return
        
    with open(SHOWTIMES_PATH, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
        
    films_map = {}
    for item in raw_data:
        if item.get('date_text') != date_str: continue
        if not item.get('tmdb_backdrop_path'): continue
        key = item.get('tmdb_id') or item.get('movie_title')
        if key not in films_map:
            films_map[key] = item
            films_map[key]['showings'] = defaultdict(list)
        films_map[key]['showings'][item.get('cinema_name', '')].append(item.get('showtime', ''))

    all_films = list(films_map.values())
    random.shuffle(all_films)
    selected = all_films[:9]
    
    if not selected:
        print("No films found.")
        return

    print(f"Selected {len(selected)} films.")
    fonts = get_fonts()
    slide_data = []
    cover_images = []
    
    for film in selected:
        img = download_image(film.get('tmdb_backdrop_path'))
        if img:
            slide_data.append({"film": film, "img": img})
            cover_images.append(img)
            
    if not slide_data: return

    # --- COVER ---
    collage = create_chaotic_collage(cover_images)
    
    if collage:
        draw_final_cover(collage, fonts, is_story=False).save(BASE_DIR / "post_v2_image_00.png")
        draw_final_cover(collage, fonts, is_story=True).save(BASE_DIR / "story_v2_image_00.png")
    else:
        Image.new("RGB",(CANVAS_WIDTH,CANVAS_HEIGHT),(50,50,50)).save(BASE_DIR / "post_v2_image_00.png")

    # --- SLIDES ---
    caption_lines = [f"🗓️ {date_str} Tokyo Cinema Daily\n"]
    for i, item in enumerate(slide_data):
        slide_feed = draw_poster_slide(item['film'], item['img'], fonts, is_story=False)
        slide_feed.save(BASE_DIR / f"post_v2_image_{i+1:02}.png")
        slide_story = draw_poster_slide(item['film'], item['img'], fonts, is_story=True)
        slide_story.save(BASE_DIR / f"story_v2_image_{i+1:02}.png")
        caption_lines.append(f"{item['film'].get('movie_title')}")

    caption_lines.append("\n#TokyoIndieCinema")
    with open(OUTPUT_CAPTION_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(caption_lines))
        
    print("✅ V66 Complete.")

if __name__ == "__main__":
    main()
