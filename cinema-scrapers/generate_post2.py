"""
Generate Instagram-ready image carousel (V28 - With Stories).

- Visuals: Faithful Colors, Texture Engine (Scratches/Grain).
- Layout: 
    1. FEED (4:5) - Optimized for visual impact.
    2. STORY (9:16) - Vertical layout with larger artwork area.
- Logic: Smart-Fit Showtimes automatically centers in remaining space.
"""
from __future__ import annotations

import json
import random
import textwrap
import os
import glob
import requests
import colorsys
import re
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"
BOLD_FONT_PATH = BASE_DIR / "NotoSansJP-Bold.ttf"
REGULAR_FONT_PATH = BASE_DIR / "NotoSansJP-Regular.ttf"
OUTPUT_CAPTION_PATH = BASE_DIR / "post_v2_caption.txt"

# Layout Dimensions
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350       # 4:5 Aspect Ratio (Feed)
STORY_CANVAS_HEIGHT = 1920 # 9:16 Aspect Ratio (Story)
MARGIN = 80

# --- Cinema Name Mapping (JP -> EN) ---
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
    num_lines = int(40 * (height / 1350)) # Scale lines based on height
    
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
        return {k: ImageFont.load_default() for k in ["cover_main", "cover_sub", "title_jp", "title_en", "meta", "cinema", "times"]}

def draw_centered_text(draw, y, text, font, fill, canvas_width=CANVAS_WIDTH):
    length = draw.textlength(text, font=font)
    x = (canvas_width - length) // 2
    draw.text((x, y), text, font=font, fill=fill)
    return y + font.size + 10 

def draw_cover_slide(images, fonts, date_str, day_str, is_story=False):
    width = CANVAS_WIDTH
    height = STORY_CANVAS_HEIGHT if is_story else CANVAS_HEIGHT
    
    c1, c2 = get_faithful_colors(images[0])
    bg = create_textured_bg(c1, c2, width, height)
    bg = apply_film_grain(bg)
    draw = ImageDraw.Draw(bg)
    
    cx, cy = width // 2, height // 2
    
    # Adjust vertical position for Stories to be higher up
    offset = -100 if is_story else 0
    
    draw.text((cx, cy - 80 + offset), "TOKYO", font=fonts['cover_main'], fill=(255,255,255), anchor="mm")
    draw.text((cx, cy + 40 + offset), "CINEMA", font=fonts['cover_main'], fill=(255,255,255), anchor="mm")
    draw.text((cx, cy + 160 + offset), f"{date_str} • {day_str}", font=fonts['cover_sub'], fill=(220,220,220), anchor="mm")
    return bg

def draw_poster_slide(film, img_obj, fonts, is_story=False):
    width = CANVAS_WIDTH
    height = STORY_CANVAS_HEIGHT if is_story else CANVAS_HEIGHT
    
    # 1. Textured Background
    c_base, c_accent = get_faithful_colors(img_obj)
    bg = create_textured_bg(c_base, c_accent, width, height)
    canvas = apply_film_grain(bg)
    draw = ImageDraw.Draw(canvas)
    
    # 2. Layout Dimensions
    if is_story:
        target_w = 950
        target_h = 850  # Taller image for stories
        img_y = 180     # Lower starting point for aesthetics
    else:
        target_w = 900
        target_h = 640
        img_y = 140
        
    # Resize Image
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
    
    # 3. Typography
    
    # Metadata
    meta_parts = []
    if film.get('year'): meta_parts.append(str(film['year']))
    if film.get('tmdb_runtime'): meta_parts.append(f"{film['tmdb_runtime']}m")
    if film.get('genres'): meta_parts.append(film['genres'][0].upper())
    
    meta_str = "  •  ".join(meta_parts)
    cursor_y = draw_centered_text(draw, cursor_y, meta_str, fonts['meta'], (200, 200, 200), width)
    cursor_y += 15

    # Japanese Title
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

    # English Title
    if en_title:
        cursor_y = draw_centered_text(draw, cursor_y, en_title.upper(), fonts['title_en'], (200, 200, 200), width)
    
    # Director
    director = film.get('tmdb_director') or film.get('director')
    if director:
        cursor_y += 15
        draw_centered_text(draw, cursor_y, f"Dir. {director}", fonts['meta'], (150, 150, 150), width)
        cursor_y += 20
        
    # 5. Showtimes (Smart-Fit)
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

def main():
    print("--- Starting V28 (With Stories) ---")
    
    # Clean up old files
    for f in glob.glob(str(BASE_DIR / "post_v2_*.png")): os.remove(f)
    for f in glob.glob(str(BASE_DIR / "story_v2_*.png")): os.remove(f)

    date_str = get_today_str()
    
    if not SHOWTIMES_PATH.exists(): return
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
    all_images = []
    
    for film in selected:
        print(f"Processing: {film.get('clean_title_jp') or film.get('movie_title')}")
        img = download_image(film.get('tmdb_backdrop_path'))
        if img:
            all_images.append(img)
            slide_data.append({"film": film, "img": img})
            
    if all_images:
        d_str, day_str = get_bilingual_date()
        
        # Draw Cover (Feed)
        cover_feed = draw_cover_slide(all_images, fonts, d_str, day_str, is_story=False)
        cover_feed.save(BASE_DIR / "post_v2_image_00.png")

        # Draw Cover (Story)
        cover_story = draw_cover_slide(all_images, fonts, d_str, day_str, is_story=True)
        cover_story.save(BASE_DIR / "story_v2_image_00.png")
        
    caption_lines = [f"🗓️ {date_str} Tokyo Cinema Selection\n"]
    
    for i, item in enumerate(slide_data):
        film = item['film']
        img = item['img']
        
        # Draw Feed Slide
        slide_feed = draw_poster_slide(film, img, fonts, is_story=False)
        slide_feed.save(BASE_DIR / f"post_v2_image_{i+1:02}.png")

        # Draw Story Slide
        slide_story = draw_poster_slide(film, img, fonts, is_story=True)
        slide_story.save(BASE_DIR / f"story_v2_image_{i+1:02}.png")
        
        # Build Caption
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
        
    print("Done. V28 Generated (Feed + Stories).")

if __name__ == "__main__":
    main()
