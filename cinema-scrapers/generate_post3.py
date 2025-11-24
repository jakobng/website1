"""
Generate Instagram-ready image carousel (V48 - Flux Analog/Grit).

- Layout: Python creates a "Soft Vertical Stack" of images with gradient overlaps.
- AI: Flux.1 Dev (via Replicate).
- Update V48: 
  - Reduced Strength to 0.55 to prevent "cartoony" faces.
  - Added 'Pre-Grain' to input to force texture retention.
  - Changed prompt to '35mm film scan / raw' style.
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

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageEnhance

# --- API Setup ---
try:
    import replicate
    REPLICATE_AVAILABLE = True
except ImportError:
    print("⚠️ Replicate library not found. Run: pip install replicate")
    REPLICATE_AVAILABLE = False

REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"
BOLD_FONT_PATH = BASE_DIR / "NotoSansJP-Bold.ttf"
REGULAR_FONT_PATH = BASE_DIR / "NotoSansJP-Regular.ttf"
OUTPUT_CAPTION_PATH = BASE_DIR / "post_v3_caption.txt"

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

def get_bilingual_date():
    today = datetime.now()
    return today.strftime("%Y.%m.%d"), today.strftime("%A").upper()

def normalize_string(s):
    if not s: return ""
    return re.sub(r'\W+', '', str(s)).lower()

def download_image(path: str) -> Image.Image | None:
    if not path: return None
    url = f"https://image.tmdb.org/t/p/w1280{path}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return Image.open(BytesIO(resp.content)).convert("RGB")
    except:
        return None
    return None

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
    if img.mode != 'RGBA': img = img.convert('RGBA')
    noise_img = noise_img.convert('RGBA')
    return Image.blend(img, noise_img, alpha=0.05).convert("RGB")

def get_fonts():
    try:
        return {
            "cover_main": ImageFont.truetype(str(BOLD_FONT_PATH), 120),
            "cover_sub": ImageFont.truetype(str(REGULAR_FONT_PATH), 30),
            "title_jp": ImageFont.truetype(str(BOLD_FONT_PATH), 60),
            "title_en": ImageFont.truetype(str(REGULAR_FONT_PATH), 32),
            "meta": ImageFont.truetype(str(REGULAR_FONT_PATH), 24),
            "cinema": ImageFont.truetype(str(BOLD_FONT_PATH), 28),
            "times": ImageFont.truetype(str(REGULAR_FONT_PATH), 28),
        }
    except:
        d = ImageFont.load_default()
        return {k: d for k in ["cover_main", "cover_sub", "title_jp", "title_en", "meta", "cinema", "times"]}

def draw_centered_text(draw, y, text, font, fill, canvas_width=CANVAS_WIDTH):
    length = draw.textlength(text, font=font)
    x = (canvas_width - length) // 2
    draw.text((x, y), text, font=font, fill=fill)
    return y + font.size + 10 

# --- REPLICATE / FLUX PIPELINE (Soft Stack) ---

def create_soft_stack_composite(images, width=896, height=1152):
    """
    Stacks images vertically using gradient masks to blend them smoothly.
    This removes the hard 'grid' lines BEFORE the AI sees it.
    """
    canvas = Image.new("RGB", (width, height), (0,0,0))
    if not images: return canvas
    
    # Use top 3 images
    source_imgs = images[:3]
    while len(source_imgs) < 3:
        source_imgs.append(source_imgs[0])
    
    # Helper to resize image to full width and specific height
    def prepare_slice(img, w, h):
        ratio = img.width / img.height
        target_h = int(w / ratio)
        if target_h < h:
            scale = h / target_h
            new_w = int(w * scale)
            new_h = h
            resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            left = (new_w - w) // 2
            return resized.crop((left, 0, left+w, h))
        else:
            resized = img.resize((w, target_h), Image.Resampling.LANCZOS)
            return resized.crop((0, 0, w, h))

    # Layer 1: Full background (Img 3 blurred)
    base = prepare_slice(source_imgs[2], width, height)
    base = base.filter(ImageFilter.GaussianBlur(20)) 
    canvas.paste(base, (0,0))
    
    # Layer 2: Img 1 at Top (Gradient fade out at bottom)
    img1 = prepare_slice(source_imgs[0], width, int(height*0.6))
    mask1 = Image.new('L', (width, img1.height), 255)
    draw1 = ImageDraw.Draw(mask1)
    fade_start = int(img1.height * 0.6)
    for y in range(fade_start, img1.height):
        alpha = int(255 * (1 - (y - fade_start) / (img1.height - fade_start)))
        draw1.line([(0, y), (width, y)], fill=alpha)
    canvas.paste(img1, (0, 0), mask1)
    
    # Layer 3: Img 2 at Bottom (Gradient fade out at top)
    img2 = prepare_slice(source_imgs[1], width, int(height*0.6))
    mask2 = Image.new('L', (width, img2.height), 255)
    draw2 = ImageDraw.Draw(mask2)
    fade_end = int(img2.height * 0.4)
    for y in range(fade_end):
        alpha = int(255 * (y / fade_end))
        draw2.line([(0, y), (width, y)], fill=alpha)
    canvas.paste(img2, (0, height - img2.height), mask2)
    
    # Optional: Middle strip blend of Img 3?
    img3_mid = prepare_slice(source_imgs[2], width, int(height*0.4))
    mask3 = Image.new('L', (width, img3_mid.height), 80) # Low opacity
    canvas.paste(img3_mid, (0, int(height*0.3)), mask3)
        
    return canvas

def add_pre_grain(img: Image.Image) -> Image.Image:
    """
    V48 New: Adds slight noise to the input before AI to prevent 'plastic' smoothing.
    Tricks Flux into thinking there is texture detail it must preserve.
    """
    img = img.convert("RGB")
    width, height = img.size
    
    # Generate random noise pattern
    noise_data = os.urandom(width * height)
    noise_layer = Image.frombytes('L', (width, height), noise_data)
    
    # Blend it softly (8% opacity)
    return Image.blend(img, noise_layer.convert("RGB"), alpha=0.08)

def generate_flux_mashup(images: list[Image.Image]) -> Image.Image | None:
    print("🎨 Preparing Flux Dev (Analog/Grit Mode)...")
    
    if not REPLICATE_AVAILABLE or not REPLICATE_API_TOKEN:
        print("⚠️ Replicate Not Configured.")
        return None

    try:
        # 1. Create Soft Stack Input
        raw_stack = create_soft_stack_composite(images, width=896, height=1152)
        
        # 2. V48 Fix: Add Grain BEFORE sending to AI
        init_img = add_pre_grain(raw_stack)
        
        temp_path = BASE_DIR / "temp_init_flux.png"
        init_img.save(temp_path, format="PNG")
        
        print("🚀 Sending to Replicate (black-forest-labs/flux-dev)...")
        
        # 3. Call Flux with "Dirty" Prompt parameters
        output = replicate.run(
            "black-forest-labs/flux-dev",
            input={
                "image": open(temp_path, "rb"),
                # V48 Prompt: Removed "Masterpiece", added "35mm film scan, raw"
                "prompt": "Double exposure movie poster, 35mm film scan, heavy film grain, noise, analog photography, raw style, high contrast, textured paper.",
                "go_fast": True,
                "guidance": 3.0,       # Lowered from 3.5 to reduce "frying"
                "megapixels": "1",
                "num_outputs": 1,
                "aspect_ratio": "4:5",
                "output_format": "png",
                "output_quality": 90,
                "prompt_strength": 0.55, # Lowered from 0.65 to keep original likeness
                "num_inference_steps": 28
            }
        )
        
        if temp_path.exists(): os.remove(temp_path)

        if output:
            image_url = str(output[0])
            print(f"📥 Downloading result: {image_url}")
            resp = requests.get(image_url)
            if resp.status_code == 200:
                return Image.open(BytesIO(resp.content))
            
    except Exception as e:
        print(f"⚠️ Replicate Pipeline failed: {e}")
        return None
    
    return None

def draw_final_cover(ai_image, fonts, date_str, day_str, is_story=False):
    width = CANVAS_WIDTH
    height = STORY_CANVAS_HEIGHT if is_story else CANVAS_HEIGHT
    bg = Image.new("RGB", (width, height), (20,20,20))
    
    if ai_image:
        img_ratio = ai_image.width / ai_image.height
        target_ratio = width / height
        if img_ratio > target_ratio:
            new_h = height
            new_w = int(new_h * img_ratio)
            resized = ai_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
            left = (new_w - width) // 2
            bg.paste(resized, (-left, 0))
        else:
            new_w = width
            new_h = int(new_w / img_ratio)
            resized = ai_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
            top = (new_h - height) // 2
            bg.paste(resized, (0, -top))
    
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 100))
    bg.paste(overlay, (0, 0), overlay)
    
    draw = ImageDraw.Draw(bg)
    cx, cy = width // 2, height // 2
    offset = -80 if is_story else 0
    
    draw.text((cx, cy - 120 + offset), "TOKYO", font=fonts['cover_main'], fill=(255,255,255), anchor="mm")
    draw.text((cx, cy + offset), "CINEMA", font=fonts['cover_main'], fill=(255,255,255), anchor="mm")
    
    try:
        daily_font = ImageFont.truetype(str(BOLD_FONT_PATH), 40)
    except:
        daily_font = fonts['cover_sub']
        
    draw.text((cx, cy + 100 + offset), "DAILY", font=daily_font, fill=(255, 215, 0), anchor="mm")
    draw.text((cx, cy + 200 + offset), f"{date_str} • {day_str}", font=fonts['meta'], fill=(220,220,220), anchor="mm")
    return bg

# --- Standard Slide Logic ---
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
    if film.get('year'): meta_parts.append(str(film['year']))
    if film.get('tmdb_runtime'): meta_parts.append(f"{film['tmdb_runtime']}m")
    if film.get('genres'): meta_parts.append(film['genres'][0].upper())
    meta_str = "  •  ".join(meta_parts)
    cursor_y = draw_centered_text(draw, cursor_y, meta_str, fonts['meta'], (200, 200, 200), width)
    cursor_y += 15

    jp_title = film.get('clean_title_jp') or film.get('movie_title', '')
    en_title = film.get('movie_title_en')
    if normalize_string(jp_title) == normalize_string(en_title): en_title = None
        
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
    except:
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

def draw_fallback_cover(images, fonts, date_str, day_str, is_story=False):
    width = CANVAS_WIDTH
    height = STORY_CANVAS_HEIGHT if is_story else CANVAS_HEIGHT
    if images:
        bg = images[0].resize((width, int(width * images[0].height / images[0].width)))
        if bg.height < height: bg = bg.resize((int(height * bg.width / bg.height), height))
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
    draw.text((cx, cy - 120 + offset), "TOKYO", font=fonts['cover_main'], fill=(255,255,255), anchor="mm")
    draw.text((cx, cy + offset), "CINEMA", font=fonts['cover_main'], fill=(255,255,255), anchor="mm")
    draw.text((cx, cy + 180 + offset), f"{date_str} • {day_str}", font=fonts['cover_sub'], fill=(220,220,220), anchor="mm")
    return bg

# --- Main Execution ---

def main():
    print("--- Starting V48 (Flux Analog/Grit) ---")
    
    for f in glob.glob(str(BASE_DIR / "post_v3_*.png")): os.remove(f)
    for f in glob.glob(str(BASE_DIR / "story_v3_*.png")): os.remove(f)

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
        print(f"Processing: {film.get('clean_title_jp') or film.get('movie_title')}")
        img = download_image(film.get('tmdb_backdrop_path'))
        if img:
            slide_data.append({"film": film, "img": img})
            cover_images.append(img)
            
    if not slide_data: return

    d_str, day_str = get_bilingual_date()
    ai_art = generate_flux_mashup(cover_images)
    
    if ai_art:
        print("✅ Flux Mashup Successful!")
        cover_feed = draw_final_cover(ai_art, fonts, d_str, day_str, is_story=False)
        cover_story = draw_final_cover(ai_art, fonts, d_str, day_str, is_story=True)
        cover_feed.save(BASE_DIR / "post_v3_image_00.png")
        cover_story.save(BASE_DIR / "story_v3_image_00.png")
    else:
        print("⚠️ AI Failed. Using Fallback.")
        fb_feed = draw_fallback_cover(cover_images, fonts, d_str, day_str, is_story=False)
        fb_feed.save(BASE_DIR / "post_v3_image_00.png")
        fb_story = draw_fallback_cover(cover_images, fonts, d_str, day_str, is_story=True)
        fb_story.save(BASE_DIR / "story_v3_image_00.png")

    caption_lines = [f"🗓️ {date_str} Tokyo Cinema Daily\n"]
    
    for i, item in enumerate(slide_data):
        film = item['film']
        img = item['img']
        slide_feed = draw_poster_slide(film, img, fonts, is_story=False)
        slide_feed.save(BASE_DIR / f"post_v3_image_{i+1:02}.png")
        slide_story = draw_poster_slide(film, img, fonts, is_story=True)
        slide_story.save(BASE_DIR / f"story_v3_image_{i+1:02}.png")
        
        t_jp = film.get('clean_title_jp') or film.get('movie_title')
        caption_lines.append(f"{t_jp}") 
        if film.get('movie_title_en'): caption_lines.append(f"{film['movie_title_en']}")
        for cin, t in film['showings'].items():
            t.sort()
            caption_lines.append(f"{cin}: {', '.join(t)}")
        caption_lines.append("")
        
    caption_lines.append("\nLink in Bio for Full Schedule")
    caption_lines.append("#TokyoIndieCinema #MiniTheater #MovieLog")
    
    with open(OUTPUT_CAPTION_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(caption_lines))
        
    print("Done. V48 Generated.")

if __name__ == "__main__":
    main()
