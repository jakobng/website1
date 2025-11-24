"""
Generate Instagram-ready image carousel (V65 - "Visual Storyteller").
- Design: Punk Zine / A24 Style.
- Architecture:
  1. Gemini Selects Background vs Foreground.
  2. Python/Pillow blends 2 backgrounds.
  3. Replicate cuts out foreground stickers.
  4. Gemini "Storyteller" analyzes interactions and places stickers creatively.
"""
from __future__ import annotations

import json
import random
import textwrap
import os
import glob
import requests
import math
import colorsys
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from io import BytesIO

# --- Imports must be here ---
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageEnhance, ImageChops

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

def normalize_string(s):
    if not s: return ""
    return re.sub(r'\W+', '', str(s)).lower()

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
    # Create White Border
    border_mask = alpha.filter(ImageFilter.MaxFilter(9))
    sticker_base = Image.new("RGBA", img.size, (255, 255, 255, 0))
    sticker_base.paste((255, 255, 255, 255), (0,0), mask=border_mask)
    sticker_base.paste(img, (0,0), mask=alpha)
    
    # Create Shadow
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow_mask = border_mask.filter(ImageFilter.GaussianBlur(10))
    shadow_layer = Image.new("RGBA", img.size, (0,0,0,150))
    shadow.paste(shadow_layer, (10, 20), mask=shadow_mask)
    
    final = Image.new("RGBA", img.size, (0,0,0,0))
    final.paste(shadow, (0,0), mask=shadow)
    final.paste(sticker_base, (0,0), mask=sticker_base)
    return final

def create_blended_background(img1: Image.Image, img2: Image.Image, width, height) -> Image.Image:
    """Blends two images using a vertical gradient mask."""
    def fill_screen(img):
        ratio = img.width / img.height
        target_ratio = width / height
        if ratio > target_ratio:
            new_h = height
            new_w = int(new_h * ratio)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            left = (new_w - width) // 2
            return img.crop((left, 0, left+width, height))
        else:
            new_w = width
            new_h = int(new_w / ratio)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            top = (new_h - height) // 2
            return img.crop((0, top, width, top+height))

    bg1 = fill_screen(img1)
    bg2 = fill_screen(img2)

    # Vertical Gradient Mask (Top=Img1, Bottom=Img2)
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    for y in range(height):
        alpha = int((y / height) * 255)
        draw.line([(0, y), (width, y)], fill=alpha)
        
    blended = Image.composite(bg2, bg1, mask)
    # Darken and Blur for text legibility
    blended = blended.filter(ImageFilter.GaussianBlur(5))
    enhancer = ImageEnhance.Brightness(blended)
    blended = enhancer.enhance(0.60) 
    return blended

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
    """Call 1: Decide which images are Backgrounds vs Foreground."""
    if not GEMINI_AVAILABLE or not GEMINI_API_KEY:
        return [0, 1] 

    print("🧠 (1/2) Gemini Casting: Selecting backgrounds...")
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = """
        Analyze these 9 movie stills.
        1. Select 2 images that are best for BACKGROUNDS (scenery, wide shots, texture, less faces).
        2. The rest will be cutouts.
        Return JSON: {"background_indices": [2, 5]}
        """
        response = client.models.generate_content(
            model='gemini-2.5-flash', contents=[prompt, *images]
        )
        clean_json = re.search(r'\{.*\}', response.text, re.DOTALL)
        if clean_json:
            data = json.loads(clean_json.group(0))
            return data.get("background_indices", [0, 1])
    except Exception as e:
        print(f"⚠️ Gemini Selection failed: {e}")
    return [0, 1]

def ask_gemini_to_place_stickers(bg_image: Image.Image, stickers: list[Image.Image]):
    """
    V65: 'Visual Storyteller' Mode.
    We ask Gemini to find narrative interactions between the stickers and the background.
    """
    if not GEMINI_AVAILABLE or not GEMINI_API_KEY:
        return [{
            "sticker_index": i, 
            "x": random.randint(10, 90), 
            "y": random.randint(10, 90), 
            "scale": 1.0, 
            "rotation": 0
        } for i in range(len(stickers))]

    print("🧠 (2/2) Gemini Visual Storyteller: Analyzing interactions...")
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Resize for API efficiency
        small_bg = bg_image.resize((512, 640))
        small_stickers = [s.resize((256, int(256*s.height/s.width))) for s in stickers]
        
        prompt = """
        You are a punk-art collage artist. I have 1 Background and several Cutouts (Sticker 0, Sticker 1...).
        Your job is to arrange them into a SCENE that implies a story or a joke.
        
        STEP 1: ANALYZE VISUALS
        - Look at the FACES: Are they happy? Shocked? Kissing? Looking in a specific direction?
        - Look at the BACKGROUND: Is there a cool building or object? Don't cover it.
        
        STEP 2: CREATE INTERACTIONS
        - If Sticker A is kissing, and Sticker B looks shocked, place B so they are watching A.
        - If Sticker A is pointing, place Sticker B where they are pointing.
        - If a sticker is a giant monster, make it huge (Scale 1.8) and looming in the back.
        - If a sticker is a texture/object, maybe place it as a "floor" or "hat".
        
        STEP 3: COMPOSE (0-100 Coordinate System)
        - X=0 is Left, X=100 is Right. Y=0 is Top, Y=100 is Bottom.
        - DANGER ZONE: Avoid placing faces in the center box (X=30-70, Y=30-70) where the text goes.
        - SIZE MATTERS: Use scale to create depth. 0.6 is background, 1.5 is foreground.
        - ROTATION: Use tilt (-30 to 30) to add chaos.
        
        Return JSON: 
        {
          "thought_process": "I see a couple kissing (Sticker 0) and a man yelling (Sticker 1). I will put the couple on the left and the yelling man on the right facing them.",
          "layout": [
            { "sticker_index": 0, "x": 20, "y": 80, "scale": 1.2, "rotation": 0 },
            { "sticker_index": 1, "x": 80, "y": 75, "scale": 1.1, "rotation": -10 }
          ]
        }
        """
        
        contents = [prompt, small_bg]
        contents.extend(small_stickers)
        
        response = client.models.generate_content(
            model='gemini-2.5-flash', contents=contents
        )
        
        clean_json = re.search(r'\{.*\}', response.text, re.DOTALL)
        if clean_json:
            data = json.loads(clean_json.group(0))
            if "thought_process" in data:
                print(f"🤔 Gemini Logic: {data['thought_process']}")
            return data.get("layout", [])
            
    except Exception as e:
        print(f"⚠️ Gemini Storytelling failed: {e}")
    
    return []

# --- Collage Engine ---

def create_chaotic_collage(images: list[Image.Image], width=1080, height=1350) -> Image.Image:
    if not images: return Image.new("RGB", (width, height), (20,20,20))

    # 1. Selection
    bg_idxs = ask_gemini_for_selection(images)
    if len(bg_idxs) < 2: 
        bg_idxs = [0, 0] if not bg_idxs else [bg_idxs[0], bg_idxs[0]]

    fg_raw = [img for i, img in enumerate(images) if i not in bg_idxs]
    bg_raw = [images[i] for i in bg_idxs]

    # 2. Background Construction
    print("🎨 Building Dual-Layer Background...")
    base_canvas = create_blended_background(bg_raw[0], bg_raw[1], width, height)
    
    # Cap stickers to 5 to avoid clutter/cost
    fg_raw = fg_raw[:5]
    
    # 3. Sticker Creation (Replicate)
    print(f"✂️ Cutting out {len(fg_raw)} stickers...")
    stickers = []
    for raw in fg_raw:
        cutout = remove_background(raw)
        if cutout:
            s_final = create_sticker_style(cutout)
            stickers.append(s_final)

    if not stickers: return apply_film_grain(base_canvas)

    # 4. AI Placement
    layout_plan = ask_gemini_to_place_stickers(base_canvas, stickers)
    
    # Fallback if Gemini returned empty layout but we have stickers
    if not layout_plan:
         layout_plan = [{"sticker_index": i, "x": (i*20)%100, "y": (i*20)%100, "scale": 0.8, "rotation": 0} for i in range(len(stickers))]

    # 5. Assembly (Free Canvas Mode)
    print("🏗️ Assembling Scene (Free Mode)...")
    
    for instruction in layout_plan:
        idx = instruction.get("sticker_index")
        
        if idx is None or idx >= len(stickers): continue
        sticker = stickers[idx]
        
        # Parse Gemini's Vision
        g_x = instruction.get("x", 50)
        g_y = instruction.get("y", 50)
        g_scale = instruction.get("scale", 1.0)
        g_rot = instruction.get("rotation", 0)
        
        # --- 1. Scale ---
        base_w = width * 0.40 
        target_w = int(base_w * float(g_scale))
        target_w = max(100, min(target_w, width * 1.2)) # Sanity cap
        
        ratio = sticker.height / sticker.width
        target_h = int(target_w * ratio)
        s_resized = sticker.resize((target_w, target_h), Image.Resampling.LANCZOS)
        
        # --- 2. Rotate ---
        s_placed = s_resized.rotate(g_rot, resample=Image.Resampling.BICUBIC, expand=True)
        
        # --- 3. Position ---
        center_x = int(width * (g_x / 100))
        center_y = int(height * (g_y / 100))
        
        paste_x = center_x - (s_placed.width // 2)
        paste_y = center_y - (s_placed.height // 2)
        
        base_canvas.paste(s_placed, (paste_x, paste_y), s_placed)

    return apply_film_grain(base_canvas)

# --- Drawing Text ---

def draw_final_cover(composite, fonts, is_story=False):
    width = CANVAS_WIDTH
    height = STORY_CANVAS_HEIGHT if is_story else CANVAS_HEIGHT
    bg = composite.copy()
    
    # Resize BG to fit canvas
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
    
    # Typography
    jp_text = "今日の上映作品"
    draw.text((cx + 4, cy - 80 + offset + 4), jp_text, font=fonts['cover_main_jp'], fill=(0,0,0), anchor="mm")
    draw.text((cx, cy - 80 + offset), jp_text, font=fonts['cover_main_jp'], fill=(255,255,255), anchor="mm")

    en_text = "Today's Film Selection"
    draw.text((cx + 2, cy + 30 + offset + 2), en_text, font=fonts['cover_sub_en'], fill=(0,0,0), anchor="mm")
    draw.text((cx, cy + 30 + offset), en_text, font=fonts['cover_sub_en'], fill=(230,230,230), anchor="mm")

    date_text = get_japanese_date_str()
    draw.text((cx + 2, cy + 110 + offset + 2), date_text, font=fonts['cover_date'], fill=(0,0,0), anchor="mm")
    draw.text((cx, cy + 110 + offset), date_text, font=fonts['cover_date'], fill=(180,180,180), anchor="mm")

    return bg

# --- Slide Logic (Standard) ---

def draw_centered_text(draw, y, text, font, fill, canvas_width):
    length = draw.textlength(text, font=font)
    x = (canvas_width - length) // 2
    draw.text((x, y), text, font=font, fill=fill)
    return y + font.size + 10

def draw_poster_slide(film, img_obj, fonts, is_story=False):
    width = CANVAS_WIDTH
    height = STORY_CANVAS_HEIGHT if is_story else CANVAS_HEIGHT
    bg = Image.new("RGB", (width, height), (15,15,15)) # Dark minimalist
    bg = apply_film_grain(bg)
    draw = ImageDraw.Draw(bg)
    
    target_w = 950 if is_story else 900
    target_h = 850 if is_story else 640
    img_y = 180 if is_story else 140
    
    # Resize Main Image
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
    
    # Text
    cursor = img_y + target_h + 50
    t_jp = film.get('clean_title_jp') or film.get('movie_title', '')
    cursor = draw_centered_text(draw, cursor, t_jp, fonts['title_jp'], (255,255,255), width)
    
    # Cinemas
    cursor += 20
    for cin in film.get('showings', {}):
        times = " ".join(sorted(film['showings'][cin]))
        draw_centered_text(draw, cursor, f"{cin}: {times}", fonts['times'], (200,200,200), width)
        cursor += 40
        
    return bg

# --- Main ---

CINEMA_ENGLISH_NAMES = {} # Omitted for brevity

def main():
    print("--- Starting V65 Generation (Visual Storyteller) ---")
    
    # Cleanup
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

    # --- COVER GENERATION ---
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
        caption_lines.append(f"{item['film'].get('movie_title')} - {', '.join(item['film']['showings'].keys())}")

    caption_lines.append("\n#TokyoIndieCinema")
    with open(OUTPUT_CAPTION_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(caption_lines))
        
    print("✅ V65 Complete.")

if __name__ == "__main__":
    main()
