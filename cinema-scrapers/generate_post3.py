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

# Output matches the V2 workflow expectations
OUTPUT_CAPTION_PATH = BASE_DIR / "post_v2_caption.txt"

CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350       # 4:5 Aspect Ratio (Feed)
STORY_CANVAS_HEIGHT = 1920 # 9:16 Aspect Ratio (Story)

# --- Cinema Name Mapping ---
CINEMA_ENGLISH_NAMES = {
    "Bunkamura ル・シネマ 渋谷宮下": "Bunkamura Le Cinéma",
    "K's Cinema (ケイズシネマ)": "K's Cinema",
    "シネマート新宿": "Cinemart Shinjuku",
    "新宿シネマカリテ": "Shinjuku Cinema Qualite",
    "新宿武蔵野館": "Shinjuku Musashino-kan",
    "テアトル新宿": "Theatre Shinjuku",
    "早稲田松竹": "Waseda Shochiku",
    "YEBISU GARDEN CINEMA": "Yebisu Garden Cinema",
    "シアター・イメージフォーラム": "Theatre Image Forum",
    "ユーロスペース": "Eurospace",
    "ヒューマントラストシネマ渋谷": "Human Trust Cinema Shibuya",
    "Stranger (ストレンジャー)": "Stranger",
    "新文芸坐": "Shin-Bungeiza",
    "目黒シネマ": "Meguro Cinema",
    "ポレポレ東中野": "Pole Pole Higashi-Nakano",
    "K2 Cinema": "K2 Cinema",
    "ヒューマントラストシネマ有楽町": "Human Trust Cinema Yurakucho",
    "ラピュタ阿佐ヶ谷": "Laputa Asagaya",
    "下高井戸シネマ": "Shimotakaido Cinema",
    "国立映画アーカイブ": "National Film Archive of Japan",
    "池袋シネマ・ロサ": "Ikebukuro Cinema Rosa",
    "シネスイッチ銀座": "Cine Switch Ginza",
    "シネマブルースタジオ": "Cinema Blue Studio",
    "CINEMA Chupki TABATA": "Cinema Chupki Tabata",
    "シネクイント": "Cine Quinto Shibuya",
    "アップリンク吉祥寺": "Uplink Kichijoji",
    "Morc阿佐ヶ谷": "Morc Asagaya",
    "Tollywood": "Tollywood"
}

# --- Helpers ---

def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")

def get_japanese_date_str():
    d = datetime.now()
    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    wd = weekdays[d.weekday()]
    # Format: 2025.11.24 (Mon) - Cleaner, more modern look
    return f"{d.year}.{d.month:02}.{d.day:02}"

def normalize_string(s):
    if not s:
        return ""
    return re.sub(r'\W+', '', str(s)).lower()

def download_image(path: str) -> Image.Image | None:
    if not path:
        return None
    if path.startswith("http"):
        url = path
    else:
        url = f"https://image.tmdb.org/t/p/w1280{path}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            return Image.open(BytesIO(resp.content)).convert("RGB")
    except Exception:
        return None
    return None

def get_fonts():
    try:
        return {
            # NEW: Massive Japanese Title (Bold, 110px)
            "cover_main_jp": ImageFont.truetype(str(BOLD_FONT_PATH), 110),
            # NEW: Medium English Subtitle (Regular, 55px)
            "cover_sub_en": ImageFont.truetype(str(REGULAR_FONT_PATH), 55),
            # Date
            "cover_date": ImageFont.truetype(str(REGULAR_FONT_PATH), 40),
            
            # Slide fonts (Keep these the same)
            "title_jp": ImageFont.truetype(str(BOLD_FONT_PATH), 60),
            "title_en": ImageFont.truetype(str(REGULAR_FONT_PATH), 32),
            "meta": ImageFont.truetype(str(REGULAR_FONT_PATH), 24),
            "cinema": ImageFont.truetype(str(BOLD_FONT_PATH), 28),
            "times": ImageFont.truetype(str(REGULAR_FONT_PATH), 28),
        }
    except Exception:
        print("⚠️ Fonts not found, using default.")
        d = ImageFont.load_default()
        # Ensure all keys exist to prevent crashes
        return {k: d for k in ["cover_main_jp", "cover_sub_en", "cover_date", "title_jp", "title_en", "meta", "cinema", "times"]}

def get_faithful_colors(pil_img: Image.Image) -> tuple[tuple, tuple]:
    small = pil_img.resize((150, 150))
    result = small.quantize(colors=3, method=2)
    palette = result.getpalette()
    c1 = (palette[0], palette[1], palette[2])
    c2 = (palette[3], palette[4], palette[5])
    def adjust_for_bg(rgb_tuple, is_accent=False):
        r, g, b = rgb_tuple
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        if is_accent:
            new_v = max(v, 0.4)
            new_s = s 
        else:
            new_v = 0.22 
            new_s = min(max(s, 0.4), 0.9) 
            if s < 0.05: 
                new_s = 0.02
                new_v = 0.20
        nr, ng, nb = colorsys.hsv_to_rgb(h, new_s, new_v)
        return (int(nr*255), int(ng*255), int(nb*255))
    return adjust_for_bg(c1), adjust_for_bg(c2, is_accent=True)

def create_textured_bg(base_color, accent_color, width, height):
    img = Image.new("RGB", (width, height), base_color)
    texture = Image.new("RGBA", (width, height), (0,0,0,0))
    draw = ImageDraw.Draw(texture)
    line_color = (*accent_color, 25) 
    num_lines = int(40 * (height / 1350))
    for _ in range(num_lines):
        x1 = random.randint(-width, width * 2)
        y1 = random.randint(-height, height * 2)
        length = random.randint(300, 1500)
        angle = math.radians(45)
        x2 = x1 + length * math.cos(angle)
        y2 = y1 + length * math.sin(angle)
        w = random.randint(1, 4)
        draw.line([(x1, y1), (x2, y2)], fill=line_color, width=w)
    texture = texture.filter(ImageFilter.GaussianBlur(radius=2))
    img.paste(texture, (0,0), texture)
    return img

def apply_film_grain(img):
    width, height = img.size
    noise_data = os.urandom(width * height)
    noise_img = Image.frombytes('L', (width, height), noise_data)
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    noise_img = noise_img.convert('RGBA')
    return Image.blend(img, noise_img, alpha=0.05).convert("RGB")

def draw_centered_text(draw, y, text, font, fill, canvas_width=CANVAS_WIDTH):
    length = draw.textlength(text, font=font)
    x = (canvas_width - length) // 2
    draw.text((x, y), text, font=font, fill=fill)
    return y + font.size + 10 

# --- COLLAGE / AI LAYOUT HELPERS FROM V2 (KEPT FOR FALLBACK) ---

def ask_gemini_for_layout(images: list[Image.Image]):
    if not GEMINI_AVAILABLE or not GEMINI_API_KEY:
        print("⚠️ Gemini not configured. Falling back.")
        return 0, [1, 2, 3, 4] 

    print("🧠 Consulting Gemini 2.5 Flash...")
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = """
        You are an art director making a movie collage poster.
        1. Select ONE image to be the BACKGROUND (negative space/texture).
        2. Select 4 to 5 images to be FOREGROUND CUTOUTS (clear humans).
        Return JSON: {"background_index": 0, "foreground_indices": [1, 3, 4, 6]}
        """
        response = client.models.generate_content(
            model='gemini-2.5-flash', contents=[prompt, *images]
        )
        clean_json = re.search(r'\{.*\}', response.text, re.DOTALL)
        if clean_json:
            data = json.loads(clean_json.group(0))
            return data.get("background_index", 0), data.get("foreground_indices", [1,2,3])
    except Exception as e:
        print(f"⚠️ Gemini Analysis failed: {e}")
    return 0, [1, 2, 3, 4]

def remove_background(pil_img: Image.Image) -> Image.Image | None:
    print("✂️ Cutting out sticker...")
    if not REPLICATE_AVAILABLE or not REPLICATE_API_TOKEN:
        print("⚠️ Replicate not configured.")
        return None
        
    try:
        temp_path = BASE_DIR / "temp_rembg_in.png"
        pil_img.save(temp_path, format="PNG")
        output = replicate.run(
            "lucataco/remove-bg:95fcc2a26d3899cd6c2691c900465aaeff466285a65c14638cc5f36f34befaf1",
            input={"image": open(temp_path, "rb")}
        )
        if temp_path.exists():
            os.remove(temp_path)
        if output:
            resp = requests.get(str(output))
            if resp.status_code == 200:
                return Image.open(BytesIO(resp.content)).convert("RGBA")
    except Exception as e:
        print(f"Replicate Error: {e}")
        return None
    return None

def create_sticker_style(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    alpha = img.split()[3]
    border_mask = alpha.filter(ImageFilter.MaxFilter(9))
    sticker_base = Image.new("RGBA", img.size, (255, 255, 255, 0))
    sticker_base.paste((255, 255, 255, 255), (0,0), mask=border_mask)
    sticker_base.paste(img, (0,0), mask=alpha)
    
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow_mask = border_mask.filter(ImageFilter.GaussianBlur(10))
    shadow_layer = Image.new("RGBA", img.size, (0,0,0,150))
    shadow.paste(shadow_layer, (10, 20), mask=shadow_mask)
    
    final = Image.new("RGBA", img.size, (0,0,0,0))
    final.paste(shadow, (0,0), mask=shadow)
    final.paste(sticker_base, (0,0), mask=sticker_base)
    return final

def create_chaotic_collage(images: list[Image.Image], width=896, height=1152) -> Image.Image:
    """
    Original V2 collage (background image + sticker cutouts).
    Kept here as a fallback in case inpainting fails.
    """
    canvas = Image.new("RGB", (width, height), (10,10,10))
    if not images:
        return canvas

    bg_idx, fg_idxs = ask_gemini_for_layout(images)
    if bg_idx >= len(images):
        bg_idx = 0
    fg_idxs = [i for i in fg_idxs if i < len(images) and i != bg_idx]
    
    # Background
    bg_img = images[bg_idx]
    bg_ratio = bg_img.width / bg_img.height
    target_ratio = width / height
    if bg_ratio > target_ratio:
        new_h = height
        new_w = int(new_h * bg_ratio)
        bg_img = bg_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - width) // 2
        bg_img = bg_img.crop((left, 0, left+width, height))
    else:
        new_w = width
        new_h = int(new_w / bg_ratio)
        bg_img = bg_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        top = (new_h - height) // 2
        bg_img = bg_img.crop((0, top, width, top+height))
    
    # Darken background slightly to make white text pop
    bg_img = ImageEnhance.Brightness(bg_img).enhance(0.7)
    bg_img = bg_img.filter(ImageFilter.GaussianBlur(3)) 
    canvas.paste(bg_img, (0,0))
    
    # Process Stickers
    stickers = []
    print(f"🧩 Processing {len(fg_idxs)} stickers...")
    for idx in fg_idxs:
        raw = images[idx]
        cutout = remove_background(raw)
        if cutout:
            bbox = cutout.getbbox()
            if bbox:
                cutout = cutout.crop(bbox)
                sticker = create_sticker_style(cutout)
                stickers.append(sticker)
    
    random.shuffle(stickers) 
    
    # --- UPDATED LAYOUT LOGIC (Spread Out) ---
    # We push the anchor zones much closer to the edges
    # TL, TR, BL, BR, Center
    zones = [
        (int(width * 0.10), int(height * 0.15)), # Top Left (closer to edge)
        (int(width * 0.90), int(height * 0.15)), # Top Right (closer to edge)
        (int(width * 0.10), int(height * 0.75)), # Bottom Left
        (int(width * 0.90), int(height * 0.75)), # Bottom Right
        (int(width * 0.50), int(height * 0.50))  # Center
    ]
    random.shuffle(zones)
    
    for i, sticker in enumerate(stickers):
        scale = random.uniform(0.40, 0.70)
        ratio = sticker.width / sticker.height
        new_w = int(width * scale)
        new_h = int(new_w / ratio)
        
        # Cap height just in case
        if new_h > int(height * 0.60): 
            new_h = int(height * 0.60)
            new_w = int(new_h * ratio)
            
        s_resized = sticker.resize((new_w, new_h), Image.Resampling.LANCZOS)
        angle = random.randint(-15, 15)
        s_rotated = s_resized.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
        
        if i < len(zones):
            anchor_x, anchor_y = zones[i]
        else:
            anchor_x = random.randint(100, width-300)
            anchor_y = random.randint(100, height-400)
            
        # Increased Jitter for chaos
        jitter_x = random.randint(-200, 200)
        jitter_y = random.randint(-150, 150)
        x = anchor_x + jitter_x
        y = anchor_y + jitter_y
        
        # --- RELAXED BOUNDARIES (Bleed Allowed) ---
        # Allow stickers to go off the edge by ~20% of their width
        # This prevents the "Squashed Center" effect
        min_x = int(-s_rotated.width * 0.2)
        max_x = width - int(s_rotated.width * 0.8)
        min_y = int(-s_rotated.height * 0.2)
        max_y = height - int(s_rotated.height * 0.8)

        # Apply clamp with the new relaxed limits
        x = max(min_x, min(x, max_x))
        y = max(min_y, min(y, max_y))
        
        canvas.paste(s_rotated, (x, y), s_rotated)

    noise_data = os.urandom(width * height)
    noise = Image.frombytes('L', (width, height), noise_data)
    canvas = Image.blend(canvas, noise.convert("RGB"), alpha=0.06)
    return canvas

# --- NEW: INPAINTING LOGIC PORTED FROM V1 ---

def inpaint_gaps(layout_img: Image.Image, mask_img: Image.Image) -> Image.Image:
    """
    Uses Stability AI Inpaint to fill the WHITE gaps in the collage with a simple prompt.
    Black areas in the mask are preserved.
    """
    if not REPLICATE_AVAILABLE or not REPLICATE_API_TOKEN:
        print("   ⚠️ Replicate not available. Skipping Inpaint.")
        return layout_img

    print("   🎨 Inpainting gaps with 'Cinema Still'...")
    try:
        temp_img_path = BASE_DIR / "temp_inpaint_img.png"
        temp_mask_path = BASE_DIR / "temp_inpaint_mask.png"
        
        layout_img.save(temp_img_path, format="PNG")
        mask_img.save(temp_mask_path, format="PNG")
        
        output = replicate.run(
            "stability-ai/stable-diffusion-inpainting:c28b92a7ecd66eee4aefcd8a94eb9e7f6c3805d5f06038165407fb5cb355ba67",
            input={
                "image": open(temp_img_path, "rb"),
                "mask": open(temp_mask_path, "rb"),
                "prompt": "Cinema Still",
                "negative_prompt": "",
                "num_inference_steps": 30,
                "guidance_scale": 7.5,
                "strength": 0.85
            }
        )
        
        if temp_img_path.exists():
            os.remove(temp_img_path)
        if temp_mask_path.exists():
            os.remove(temp_mask_path)
        
        if output:
            url = output[0] if isinstance(output, list) else output
            resp = requests.get(url)
            if resp.status_code == 200:
                img = Image.open(BytesIO(resp.content)).convert("RGB")
                return img.resize(layout_img.size, Image.Resampling.LANCZOS)
    except Exception as e:
        print(f"   ⚠️ Inpainting failed: {e}. Using raw layout.")
    return layout_img

def create_inpainted_tmdb_collage(images: list[Image.Image], width: int = CANVAS_WIDTH, height: int = CANVAS_HEIGHT) -> Image.Image | None:
    """
    New V3 hero:
    - Take TMDB stills
    - Cut out subjects (replicate remove-bg)
    - Place them on a WHITE canvas in a chaotic layout
    - Inpaint WHITE gaps using Stable Diffusion Inpainting with prompt 'Cinema Still'
    - Paste original cutouts back with a soft drop shadow
    """
    if not images:
        return None

    # Prepare base canvases
    layout_rgba = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    layout_rgb = Image.new("RGB", (width, height), (255, 255, 255))
    mask = Image.new("L", (width, height), 255)  # WHITE = paint, BLACK = keep

    # Limit to 5 sources; repeat if needed
    imgs_to_process = [img for img in images if img is not None]
    if not imgs_to_process:
        return None
    imgs_to_process = imgs_to_process[:5]
    if len(imgs_to_process) < 5:
        imgs_to_process = (imgs_to_process * 3)[:5]
    random.shuffle(imgs_to_process)

    anchors = [
        (int(width * 0.30), int(height * 0.22)),
        (int(width * 0.72), int(height * 0.26)),
        (int(width * 0.50), int(height * 0.52)),
        (int(width * 0.30), int(height * 0.78)),
        (int(width * 0.76), int(height * 0.76)),
    ]

    used = 0
    for i, raw in enumerate(imgs_to_process):
        try:
            cutout = remove_background(raw)
            if cutout is None:
                continue
            cutout = cutout.convert("RGBA")
            bbox = cutout.getbbox()
            if not bbox:
                continue
            cutout = cutout.crop(bbox)

            # Scale similarly to V1
            scale_variance = random.uniform(0.7, 1.2)
            max_dim = int(550 * scale_variance)
            cutout.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

            # Anchor + jitter
            cx, cy = anchors[min(i, len(anchors) - 1)]
            cx += random.randint(-100, 100)
            cy += random.randint(-100, 100)
            x = cx - (cutout.width // 2)
            y = cy - (cutout.height // 2)

            # Paste cutout onto transparent + white layout
            layout_rgba.paste(cutout, (x, y), mask=cutout)
            layout_rgb.paste(cutout, (x, y), mask=cutout)

            alpha = cutout.split()[3]
            mask.paste(0, (x, y), mask=alpha)  # BLACK where we KEEP the cutouts
            used += 1
        except Exception as e:
            print(f"   ⚠️ Error placing cutout: {e}")
            continue

    if used == 0:
        print("   ⚠️ No cutouts created; falling back.")
        return None

    # Slight dilation so we do not overwrite edges
    mask = mask.filter(ImageFilter.MaxFilter(11))

    # Inpaint the white gaps
    inpainted_bg = inpaint_gaps(layout_rgb, mask)

    # Composite: soft shadow + original crisp cutouts
    if inpainted_bg.mode != "RGBA":
        inpainted_bg = inpainted_bg.convert("RGBA")
    final_composite = inpainted_bg.copy()

    # Shadow from the global alpha of the collage
    alpha_layout = layout_rgba.split()[3]
    shadow_layer = Image.new("RGBA", final_composite.size, (0, 0, 0, 0))
    shadow_layer.paste((0, 0, 0, 80), (10, 10), mask=alpha_layout)
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(15))

    final_composite.paste(shadow_layer, (0, 0), mask=shadow_layer)
    final_composite.paste(layout_rgba, (0, 0), mask=layout_rgba)

    return final_composite.convert("RGB")

# --- COVER RENDERING ---

def draw_final_cover(composite, fonts, is_story=False):
    width = CANVAS_WIDTH
    height = STORY_CANVAS_HEIGHT if is_story else CANVAS_HEIGHT
    bg = composite.copy()
    bg_ratio = bg.width / bg.height
    target_ratio = width / height
    
    # Crop/Resize logic
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
    
    # 1. Main Title: Japanese (Big & Bold)
    jp_text = "今日の上映作品"
    draw.text((cx + 4, cy - 80 + offset + 4), jp_text, font=fonts['cover_main_jp'], fill=(0,0,0), anchor="mm")
    draw.text((cx, cy - 80 + offset), jp_text, font=fonts['cover_main_jp'], fill=(255,255,255), anchor="mm")

    # 2. Subtitle: English (Medium Size)
    en_text = "Today's Film Selection"
    draw.text((cx + 2, cy + 30 + offset + 2), en_text, font=fonts['cover_sub_en'], fill=(0,0,0), anchor="mm")
    draw.text((cx, cy + 30 + offset), en_text, font=fonts['cover_sub_en'], fill=(230,230,230), anchor="mm")

    # 3. Date (Small, at bottom)
    date_text = get_japanese_date_str()
    draw.text((cx + 2, cy + 110 + offset + 2), date_text, font=fonts['cover_date'], fill=(0,0,0), anchor="mm")
    draw.text((cx, cy + 110 + offset), date_text, font=fonts['cover_date'], fill=(180,180,180), anchor="mm")

    return bg

def draw_fallback_cover(images, fonts, is_story=False):
    width = CANVAS_WIDTH
    height = STORY_CANVAS_HEIGHT if is_story else CANVAS_HEIGHT
    if images:
        bg = images[0].resize((width, int(width * images[0].height / images[0].width)))
        if bg.height < height:
            bg = bg.resize((int(height * bg.width / bg.height), height))
        left = (bg.width - width) // 2
        top = (bg.height - height) // 2
        bg = bg.crop((left, top, left + width, top + height))
    else:
        bg = Image.new("RGB", (width, height), (20,20,20))
    
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 160))
    bg.paste(overlay, (0, 0), overlay)
    draw = ImageDraw.Draw(bg)
    cx, cy = width // 2, height // 2
    offset = -80 if is_story else 0
    
    draw.text((cx, cy + offset), "Today's Film Selection", font=fonts['cover_main_jp'], fill=(255,255,255), anchor="mm")
    draw.text((cx, cy + 100 + offset), get_japanese_date_str(), font=fonts['cover_date'], fill=(200,200,200), anchor="mm")
    return bg

# --- POSTER SLIDES (UNCHANGED FROM V2) ---

def draw_poster_slide(film, img_obj, fonts, is_story=False):
    width = CANVAS_WIDTH
    height = STORY_CANVAS_HEIGHT if is_story else CANVAS_HEIGHT
    c_base, c_accent = get_faithful_colors(img_obj)
    bg = create_textured_bg(c_base, c_accent, width, height)
    canvas = apply_film_grain(bg)
    draw = ImageDraw.Draw(canvas)
    
    if is_story:
        target_w = 950
        target_h = 850
        img_y = 180
    else:
        target_w = 900
        target_h = 640
        img_y = 140
        
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
    
    img_x = (width - target_w) // 2
    canvas.paste(img_final, (img_x, img_y))
    cursor_y = img_y + target_h + (70 if is_story else 60)
    
    meta_parts = []
    if film.get('year'):
        meta_parts.append(str(film['year']))
    if film.get('tmdb_runtime'):
        meta_parts.append(f"{film['tmdb_runtime']}m")
    if film.get('genres'):
        meta_parts.append(film['genres'][0].upper())
    meta_str = "  •  ".join(meta_parts)
    cursor_y = draw_centered_text(draw, cursor_y, meta_str, fonts['meta'], (200, 200, 200), width)
    cursor_y += 15

    jp_title = film.get('clean_title_jp') or film.get('movie_title', '')
    en_title = film.get('movie_title_en')
    if normalize_string(jp_title) == normalize_string(en_title):
        en_title = None
        
    if len(jp_title) > 15:
        wrapper = textwrap.TextWrapper(width=15)
        lines = wrapper.wrap(jp_title)
        for line in lines:
            cursor_y = draw_centered_text(draw, cursor_y, line, fonts['title_jp'], (255, 255, 255), width)
    else:
        cursor_y = draw_centered_text(draw, cursor_y, jp_title, fonts['title_jp'], (255, 255, 255), width)
    cursor_y += 10

    if en_title:
        cursor_y = draw_centered_text(draw, cursor_y, en_title.upper(), fonts['title_en'], (200, 200, 200), width)
    
    director = film.get('tmdb_director') or film.get('director')
    if director:
        cursor_y += 15
        draw_centered_text(draw, cursor_y, f"Dir. {director}", fonts['meta'], (150, 150, 150), width)
        cursor_y += 20
        
    sorted_cinemas = sorted(film['showings'].keys())
    num_cinemas = len(sorted_cinemas)
    available_space = height - cursor_y - (150 if is_story else 50)
    std_font_size = 32 if is_story else 28
    std_gap = 60 if is_story else 50
    block_unit = (std_font_size * 1.2 * 2) + std_gap 
    total_needed = num_cinemas * block_unit
    
    scale = 1.0
    if total_needed > available_space:
        scale = available_space / total_needed
        scale = max(scale, 0.45) 
    final_font_size = int(std_font_size * scale)
    gap_scale = scale if scale > 0.8 else scale * 0.6
    final_gap = int(std_gap * gap_scale)
    
    try:
        dyn_font_cin = ImageFont.truetype(str(BOLD_FONT_PATH), final_font_size)
        dyn_font_time = ImageFont.truetype(str(REGULAR_FONT_PATH), final_font_size)
    except Exception:
        dyn_font_cin = ImageFont.load_default()
        dyn_font_time = ImageFont.load_default()
        
    unit_height = (final_font_size * 1.2) + (final_font_size * 1.2) + final_gap
    final_block_height = num_cinemas * unit_height
    if available_space > final_block_height:
        start_y = cursor_y + (available_space - final_block_height) // 2
    else:
        start_y = cursor_y + 20 
        
    for cinema in sorted_cinemas:
        times = sorted(film['showings'][cinema])
        times_str = " ".join(times)
        cinema_en = CINEMA_ENGLISH_NAMES.get(cinema, cinema)
        len_c = draw.textlength(cinema_en, font=dyn_font_cin)
        x_c = (width - len_c) // 2
        draw.text((x_c, start_y), cinema_en, font=dyn_font_cin, fill=(255, 255, 255))
        y_time = start_y + final_font_size + 5 
        len_t = draw.textlength(times_str, font=dyn_font_time)
        x_t = (width - len_t) // 2
        draw.text((x_t, y_time), times_str, font=dyn_font_time, fill=(200, 200, 200))
        start_y += unit_height

    return canvas

# --- MAIN ---

def main():
    print("--- Starting V3 (TMDB Cutout Collage + Inpainting Hero) ---")
    
    # Clean up ANY possible output files (reuse V2 naming to keep workflow stable)
    for f in glob.glob(str(BASE_DIR / "post_v2_*.png")):
        os.remove(f)
    for f in glob.glob(str(BASE_DIR / "story_v2_*.png")):
        os.remove(f)

    date_str = get_today_str()
    if not SHOWTIMES_PATH.exists(): 
        print("Showtimes file missing.")
        return
        
    with open(SHOWTIMES_PATH, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
        
    films_map = {}
    for item in raw_data:
        if item.get('date_text') != date_str:
            continue
        if not item.get('tmdb_backdrop_path'):
            continue
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
        print(f"Processing: {film.get('clean_title_jp') or film.get('movie_title')}")
        img = download_image(film.get('tmdb_backdrop_path'))
        if img:
            slide_data.append({"film": film, "img": img})
            cover_images.append(img)
            
    if not slide_data:
        print("No images downloaded; aborting.")
        return

    # --- HERO COLLAGE WITH INPAINTING ---
    collage = create_inpainted_tmdb_collage(cover_images)

    if collage:
        print("✅ Inpainted collage assembled!")
        # FEED COVER
        cover_feed = draw_final_cover(collage, fonts, is_story=False)
        cover_feed.save(BASE_DIR / "post_v2_image_00.png")
        
        # STORY COVER
        cover_story = draw_final_cover(collage, fonts, is_story=True)
        cover_story.save(BASE_DIR / "story_v2_image_00.png")
    else:
        print("⚠️ Inpainted collage failed. Falling back to V2 chaotic collage.")
        fallback_collage = create_chaotic_collage(cover_images, width=CANVAS_WIDTH, height=CANVAS_HEIGHT)
        if fallback_collage:
            cover_feed = draw_final_cover(fallback_collage, fonts, is_story=False)
            cover_feed.save(BASE_DIR / "post_v2_image_00.png")
            cover_story = draw_final_cover(fallback_collage, fonts, is_story=True)
            cover_story.save(BASE_DIR / "story_v2_image_00.png")
        else:
            print("⚠️ Collage failed entirely. Using simple fallback cover.")
            fb_feed = draw_fallback_cover(cover_images, fonts, is_story=False)
            fb_feed.save(BASE_DIR / "post_v2_image_00.png")
            fb_story = draw_fallback_cover(cover_images, fonts, is_story=True)
            fb_story.save(BASE_DIR / "story_v2_image_00.png")

    # --- SLIDE GENERATION (UNCHANGED FROM V2) ---
    caption_lines = [f"🗓️ {date_str} Tokyo Cinema Daily\n"]
    
    for i, item in enumerate(slide_data):
        film = item['film']
        img = item['img']
        
        # Feed Slide
        slide_feed = draw_poster_slide(film, img, fonts, is_story=False)
        slide_feed.save(BASE_DIR / f"post_v2_image_{i+1:02}.png")
        
        # Story Slide
        slide_story = draw_poster_slide(film, img, fonts, is_story=True)
        slide_story.save(BASE_DIR / f"story_v2_image_{i+1:02}.png")
        
        t_jp = film.get('clean_title_jp') or film.get('movie_title')
        caption_lines.append(f"{t_jp}") 
        if film.get('movie_title_en'):
            caption_lines.append(f"{film['movie_title_en']}")
        for cin, t in film['showings'].items():
            t.sort()
            caption_lines.append(f"{cin}: {', '.join(t)}")
        caption_lines.append("")
        
    caption_lines.append("\nLink in Bio for Full Schedule")
    caption_lines.append("#TokyoIndieCinema #MiniTheater #MovieLog")
    
    with open(OUTPUT_CAPTION_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(caption_lines))
        
    print("Done. V3 Generated (Inpainted Hero).")

if __name__ == "__main__":
    main()
