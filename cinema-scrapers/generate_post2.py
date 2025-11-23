"""
Generate Instagram-ready image carousel (V17 - Pop-Art / Toiletpaper Style).

- Visuals: Procedural Geometric Patterns (Dots, Rays, Zigzags).
- Image: "Sticker" effect (White border + Hard Shadow).
- Logic: Title deduplication, Single-line metadata, Overflow protection.
- Vibe: Bold, Kitsch, High-Saturation.
"""
from __future__ import annotations

import json
import random
import textwrap
import os
import glob
import requests
import colorsys
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageOps

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"
BOLD_FONT_PATH = BASE_DIR / "NotoSansJP-Bold.ttf"
REGULAR_FONT_PATH = BASE_DIR / "NotoSansJP-Regular.ttf"
OUTPUT_CAPTION_PATH = BASE_DIR / "post_v2_caption.txt"

# Layout Dimensions
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350
MARGIN = 60 

# --- Helpers ---

def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")

def get_bilingual_date():
    today = datetime.now()
    return today.strftime("%Y.%m.%d"), today.strftime("%A").upper()

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

def extract_pop_colors(pil_img: Image.Image) -> tuple[tuple, tuple]:
    """
    Extracts two high-contrast colors for patterns.
    """
    small = pil_img.resize((100, 100))
    result = small.quantize(colors=5, method=2)
    palette = result.getpalette()
    
    # Get two dominant colors
    c1 = (palette[0], palette[1], palette[2])
    c2 = (palette[3], palette[4], palette[5])
    
    # Helper to boost saturation
    def pop_color(c, boost_v=False):
        r, g, b = c
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        
        # Toiletpaper Style: High Saturation, High Brightness
        new_s = max(s, 0.6)
        if boost_v: new_v = max(v, 0.8)
        else: new_v = max(v, 0.3)
            
        nr, ng, nb = colorsys.hsv_to_rgb(h, new_s, new_v)
        return (int(nr*255), int(ng*255), int(nb*255))

    return pop_color(c1, boost_v=False), pop_color(c2, boost_v=True)

def create_pop_pattern(c1, c2, width, height):
    """Generates a random geometric pattern (Dots, Rays, or Solids)."""
    img = Image.new("RGB", (width, height), c1)
    draw = ImageDraw.Draw(img)
    
    pattern_type = random.choice(['dots', 'rays', 'zigzag', 'solid'])
    
    if pattern_type == 'dots':
        step = 60
        radius = 20
        for y in range(0, height, step):
            for x in range(0, width, step):
                offset = (step // 2) if (y // step) % 2 == 0 else 0
                draw.ellipse(
                    (x + offset - radius, y - radius, x + offset + radius, y + radius), 
                    fill=c2
                )
                
    elif pattern_type == 'rays':
        cx, cy = width // 2, height // 2
        num_rays = 24
        for i in range(0, 360, 360 // num_rays):
            if (i // (360 // num_rays)) % 2 == 0:
                # Draw triangle slice
                angle1 = math.radians(i)
                angle2 = math.radians(i + (360 // num_rays))
                r = max(width, height) * 1.5
                x1 = cx + r * math.cos(angle1)
                y1 = cy + r * math.sin(angle1)
                x2 = cx + r * math.cos(angle2)
                y2 = cy + r * math.sin(angle2)
                draw.polygon([(cx, cy), (x1, y1), (x2, y2)], fill=c2)
                
    elif pattern_type == 'zigzag':
        step = 100
        thickness = 30
        for y in range(0, height + step, step // 2):
            points = []
            for x in range(0, width + step, step):
                points.append((x, y))
                points.append((x + step//2, y + step//2))
            
            # Offset every other line
            draw.line(points, fill=c2, width=thickness)
            
    # 'solid' just returns the base color c1, which is also a valid "Pop" choice
    
    return img

def create_sticker_image(img_obj, target_w):
    """Adds a white border and drop shadow to make it look like a sticker."""
    # 1. Resize
    target_h = int(target_w * 0.65) # Landscape
    img_ratio = img_obj.width / img_obj.height
    
    if img_ratio > (target_w / target_h):
        new_h = target_h
        new_w = int(new_h * img_ratio)
        img = img_obj.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - target_w) // 2
        img = img.crop((left, 0, left + target_w, target_h))
    else:
        new_w = target_w
        new_h = int(new_w / img_ratio)
        img = img_obj.resize((new_w, new_h), Image.Resampling.LANCZOS)
        top = (new_h - target_h) // 2
        img = img.crop((0, top, target_w, top + target_h))
        
    # 2. Add White Border
    border_w = 20
    img = ImageOps.expand(img, border=border_w, fill='white')
    
    # 3. Create Shadow
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 255))
    
    # 4. Composite
    # We return the image and shadow separate so we can offset them on the main canvas
    return img, shadow

def fit_text(draw, text, font_path, max_width, max_size, min_size=30):
    size = max_size
    font = ImageFont.truetype(str(font_path), size)
    while size > min_size:
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_width: return font, bbox[3] - bbox[1]
        size -= 5
        font = ImageFont.truetype(str(font_path), size)
    return font, size

def get_fonts():
    try:
        return {
            "cover_main": ImageFont.truetype(str(BOLD_FONT_PATH), 140),
            "cover_sub": ImageFont.truetype(str(BOLD_FONT_PATH), 40),
            "title": ImageFont.truetype(str(BOLD_FONT_PATH), 70),
            "meta": ImageFont.truetype(str(BOLD_FONT_PATH), 28),
            "logline": ImageFont.truetype(str(REGULAR_FONT_PATH), 28),
            "cinema": ImageFont.truetype(str(BOLD_FONT_PATH), 30),
            "times": ImageFont.truetype(str(REGULAR_FONT_PATH), 30),
        }
    except:
        return {k: ImageFont.load_default() for k in ["cover_main", "cover_sub", "title", "meta", "logline", "cinema", "times"]}

def draw_cover(images, fonts, date_str, day_str):
    # Use bright pop pattern
    c1, c2 = extract_pop_colors(images[0])
    bg = create_pop_pattern(c1, c2, CANVAS_WIDTH, CANVAS_HEIGHT)
    
    # Dim it slightly for text readability
    overlay = Image.new("RGBA", bg.size, (0,0,0,80))
    bg.paste(overlay, (0,0), overlay)
    
    draw = ImageDraw.Draw(bg)
    cx, cy = CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2
    
    # Brutalist Text Box
    box_w, box_h = 800, 600
    draw.rectangle(
        [(cx - box_w//2 + 15, cy - box_h//2 + 15), (cx + box_w//2 + 15, cy + box_h//2 + 15)], 
        fill="black"
    )
    draw.rectangle(
        [(cx - box_w//2, cy - box_h//2), (cx + box_w//2, cy + box_h//2)], 
        fill="white"
    )
    
    draw.text((cx, cy - 100), "TOKYO", font=fonts['cover_main'], fill="black", anchor="mm")
    draw.text((cx, cy + 40), "CINEMA", font=fonts['cover_main'], fill="black", anchor="mm")
    
    # Yellow Tape for Date
    draw.rectangle([(cx - 250, cy + 160), (cx + 250, cy + 220)], fill=(255, 230, 0))
    draw.text((cx, cy + 190), f"{date_str} {day_str}", font=fonts['cover_sub'], fill="black", anchor="mm")
    
    return bg

def normalize_title(t):
    if not t: return ""
    return "".join(t.lower().split())

def draw_slide(film, img_obj, fonts):
    # 1. Generate Pattern Background
    c1, c2 = extract_pop_colors(img_obj)
    canvas = create_pop_pattern(c1, c2, CANVAS_WIDTH, CANVAS_HEIGHT)
    draw = ImageDraw.Draw(canvas)
    
    # 2. Sticker Image
    sticker_w = CANVAS_WIDTH - (MARGIN * 2)
    sticker_img, sticker_shadow = create_sticker_image(img_obj, sticker_w)
    
    # Draw Shadow first
    img_x = MARGIN
    img_y = 120
    shadow_offset = 20
    canvas.paste(sticker_shadow, (img_x + shadow_offset, img_y + shadow_offset), sticker_shadow)
    canvas.paste(sticker_img, (img_x, img_y))
    
    cursor_y = img_y + sticker_img.height + 50
    
    # 3. Title Block (Black Box for readability against patterns)
    jp_title = film.get('clean_title_jp') or film.get('movie_title', '')
    en_title = film.get('movie_title_en', '')
    
    # Deduplication: If EN title is basically same as JP, ignore EN
    if normalize_title(jp_title) == normalize_title(en_title):
        en_title = ""
    
    # Draw Text Box Background (Dynamic height calculation would be better, but fixed is safer for now)
    # Let's draw a semi-transparent black pane for the bottom half
    pane_y = cursor_y - 30
    draw.rectangle([(0, pane_y), (CANVAS_WIDTH, CANVAS_HEIGHT)], fill=(20, 20, 20))
    
    # JP Title
    jp_font, jp_h = fit_text(draw, jp_title, BOLD_FONT_PATH, CANVAS_WIDTH - (MARGIN*2), 70)
    draw.text((MARGIN, cursor_y), jp_title, font=jp_font, fill="white")
    cursor_y += jp_h + 15
    
    # EN Title
    if en_title:
        en_font, en_h = fit_text(draw, en_title.upper(), BOLD_FONT_PATH, CANVAS_WIDTH - (MARGIN*2), 35)
        draw.text((MARGIN, cursor_y), en_title.upper(), font=en_font, fill=(200, 200, 200))
        cursor_y += en_h + 25
    else:
        cursor_y += 15
        
    # 4. Metadata Strip (Single Line)
    meta_items = []
    if film.get('year'): meta_items.append(str(film['year']))
    if film.get('tmdb_runtime'): meta_items.append(f"{film['tmdb_runtime']}m")
    if film.get('genres'): meta_items.append(film['genres'][0].upper())
    if film.get('production_countries'): meta_items.append(film['production_countries'][0])
    
    meta_str = "  //  ".join(meta_items)
    draw.text((MARGIN, cursor_y), meta_str, font=fonts['meta'], fill=(255, 230, 0)) # Pop Yellow
    cursor_y += 45
    
    # 5. Logline (Synopsis)
    synopsis = film.get('tmdb_overview_jp')
    if synopsis:
        # Calculate space left for showtimes (need ~200px minimum)
        space_left = (CANVAS_HEIGHT - 200) - cursor_y
        if space_left > 60:
            wrapper = textwrap.TextWrapper(width=36)
            lines = wrapper.wrap(synopsis)
            max_lines = int(space_left / 35)
            for line in lines[:max_lines]:
                draw.text((MARGIN, cursor_y), line, font=fonts['logline'], fill=(220, 220, 220))
                cursor_y += 35
            cursor_y += 30
            
    # Divider
    draw.line([(MARGIN, cursor_y), (CANVAS_WIDTH - MARGIN, cursor_y)], fill=(100, 100, 100), width=2)
    cursor_y += 30
    
    # 6. Showtimes
    sorted_cinemas = sorted(film['showings'].keys())
    for cinema in sorted_cinemas:
        if cursor_y > CANVAS_HEIGHT - 50: break
        
        times = sorted(film['showings'][cinema])
        # Check width to see if we need new line
        times_str = "  ".join(times)
        
        # Cinema Name
        draw.text((MARGIN, cursor_y), f"📍 {cinema}", font=fonts['cinema'], fill="white")
        
        # If times string is short, put on same line? No, keep clean.
        cursor_y += 40
        draw.text((MARGIN + 35, cursor_y), times_str, font=fonts['times'], fill=(180, 180, 180))
        cursor_y += 60

    return canvas

def main():
    print("--- Starting V17 (Pop-Art Sticker) ---")
    for f in glob.glob(str(BASE_DIR / "post_v2_*.png")): os.remove(f)
    
    if not SHOWTIMES_PATH.exists(): return
    with open(SHOWTIMES_PATH, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
        
    date_str = get_today_str()
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
    
    fonts = get_fonts()
    slide_data = []
    all_images = []
    
    for film in selected:
        print(f"Processing: {film.get('clean_title_jp')}")
        img = download_image(film.get('tmdb_backdrop_path'))
        if img:
            all_images.append(img)
            slide_data.append({"film": film, "img": img})
            
    if all_images:
        d_str, day_str = get_bilingual_date()
        cover = draw_cover(all_images, fonts, d_str, day_str)
        cover.save(BASE_DIR / "post_v2_image_00.png")
        
    caption_lines = [f"🗓️ {date_str} Tokyo Cinema Selection\n"]
    
    for i, item in enumerate(slide_data):
        film = item['film']
        img = item['img']
        slide = draw_slide(film, img, fonts)
        slide.save(BASE_DIR / f"post_v2_image_{i+1:02}.png")
        
        t_jp = film.get('clean_title_jp') or film.get('movie_title')
        caption_lines.append(f"{t_jp}")
        for cin, t in film['showings'].items():
            t.sort()
            caption_lines.append(f"{cin}: {', '.join(t)}")
        caption_lines.append("")
        
    caption_lines.append("#TokyoIndieCinema #MiniTheater")
    with open(OUTPUT_CAPTION_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(caption_lines))

    print("Done. V17 Generated.")

if __name__ == "__main__":
    main()
