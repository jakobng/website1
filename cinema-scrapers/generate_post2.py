"""
Generate Instagram-ready image carousel (V26 - Subtle Texture / Faithful Colors).

- Base: V22 (Smart-Fit Layout).
- Visuals:
  1. Faithful Colors: No artificial contrast boosting. Uses real image palette.
  2. Texture Engine: Generates thin, diagonal scratches/streaks.
  3. Subtlety: Low opacity, slight blur. "Paper grain" feel.
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

from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter, ImageChops

BASE_DIR = Path(__file__).resolve().parent
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"
OUTPUT_CAPTION_PATH = BASE_DIR / "post_v2_caption.txt"

CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350

BOLD_FONT_PATH = BASE_DIR / "fonts" / "NotoSansCJKjp-Bold.otf"
REGULAR_FONT_PATH = BASE_DIR / "fonts" / "NotoSansCJKjp-Regular.otf"

CINEMA_NAME_MAPPING = {
    "K's cinema": "K's Cinema",
    "Yebisu Garden Cinema": "Yebisu Garden Cinema",
    "イメージフォーラム": "Image Forum Shibuya",
    "Image Forum Shibuya": "Image Forum Shibuya",
    "UPLINK吉祥寺": "Uplink Kichijoji",
    "UPLINK Shibuya": "Uplink Shibuya",
    "Shin Bungeiza": "Shin Bungeiza",
    "Shin-Bungeiza": "Shin Bungeiza",
    "Cine Libre Ikebukuro": "Cine Libre Ikebukuro",
    "Cine Libre": "Cine Libre Ikebukuro",
    "Eurospace": "Eurospace",
    "シネマヴェーラ渋谷": "Cinema Vera Shibuya",
    "Cinemavera Shibuya": "Cinema Vera Shibuya",
    "Cinem@rt Shinjuku": "Cinem@rt Shinjuku",
    "Cinem@rt": "Cinem@rt Shinjuku",
    "Shinjuku Piccadilly": "Shinjuku Piccadilly",
    "新宿ピカデリー": "Shinjuku Piccadilly",
    "Shinjuku Musashinokan": "Shinjuku Musashinokan",
    "新宿武蔵野館": "Shinjuku Musashinokan",
    "Human Trust Cinema Shibuya": "Human Trust Cinema Shibuya",
    "ヒューマントラストシネマ渋谷": "Human Trust Cinema Shibuya",
    "Human Trust Cinema Yurakucho": "Human Trust Cinema Yurakucho",
    "ヒューマントラストシネマ有楽町": "Human Trust Cinema Yurakucho",
    "Cinema Rosa": "Cinema Rosa Ikebukuro",
    "シネマ・ロサ": "Cinema Rosa Ikebukuro",
    "Uplink Kichijoji": "Uplink Kichijoji",
    "Uplink X": "Uplink Shibuya",
    "Kichijoji Baus Theater": "Kichijoji Baus Theater",
    "吉祥寺バウスシアター": "Kichijoji Baus Theater",
    "Shibuya Eurospace": "Eurospace",
    "シネクイント": "Cine Quinto Shibuya",
    "アップリンク吉祥寺": "Uplink Kichijoji",
    "Morc阿佐ヶ谷": "Morc Asagaya",
    "Morc Asagaya": "Morc Asagaya",
    "TULLYWOOD": "Tollywood",
    "Tollywood": "Tollywood"
}

# --- Helpers ---

def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")

def get_bilingual_date():
    today = datetime.now()
    return today.strftime("%Y.%m.%d"), today.strftime("%A").upper()

def first_sentence(text: str, lang: str) -> str:
    if not text:
        return ""
    if lang == "jp":
        for sep in "。！？":
            idx = text.find(sep)
            if idx != -1:
                return text[:idx+1]
        return text
    else:
        for sep in ".!?":
            idx = text.find(sep)
            if idx != -1:
                return text[:idx+1].strip()
        return text.strip()

def truncate_chars(text: str, max_chars: int) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"

def build_logline(film: dict, lang: str) -> str:
    if lang == "en":
        tagline = (film.get("tmdb_tagline_en") or "").strip()
        overview = (film.get("tmdb_overview_en") or "").strip()
        max_chars = 110
    else:
        tagline = (film.get("tmdb_tagline_jp") or "").strip()
        overview = (film.get("tmdb_overview_jp") or "").strip()
        max_chars = 60

    candidates = []
    if tagline:
        candidates.append(tagline)
    if overview:
        candidates.append(first_sentence(overview, "jp" if lang == "jp" else "en"))

    for c in candidates:
        if len(c) >= 8:
            return truncate_chars(c, max_chars)
    return ""

def normalize_string(s):
    if not s: return ""
    return re.sub(r'\W+', '', str(s)).lower()

def download_image(path: str) -> Image.Image | None:
    if not path: return None
    url = f"https://image.tmdb.org/t/p/w1280{path}"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        img = Image.open(BytesIO(r.content)).convert("RGB")
        return img
    except Exception as e:
        print(f"Error downloading image: {e}")
        return None

def get_faithful_colors(img: Image.Image):
    """
    Extracts two representative colors (background + accent) from the image
    and gently nudges them to remain faithful, without oversaturating.
    """
    thumb = img.resize((80, 45))
    thumb = thumb.convert("RGB")
    
    colors = thumb.getcolors(80*45)
    if not colors:
        return (20, 20, 20), (230, 230, 230)
    
    colors.sort(key=lambda x: x[0], reverse=True)
    dominant = [c[1] for c in colors[:12]]
    
    def is_too_close(c1, c2, thresh=25):
        return sum((a-b)**2 for a,b in zip(c1,c2)) ** 0.5 < thresh
    
    bg = dominant[0]
    accent = None
    for c in dominant[1:]:
        if not is_too_close(bg, c, 80):
            accent = c
            break
    if accent is None:
        accent = bg
    
    def adjust_for_bg(c, is_accent=False):
        r, g, b = c
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        
        if not is_accent:
            v = v * 0.45 + 0.1
            v = max(min(v, 0.45), 0.12)
            s = s * 0.7
        else:
            s = min(s * 1.05 + 0.04, 0.95)
            v = v * 0.9 + 0.05
            v = max(min(v, 0.92), 0.25)
        
        if not is_accent:
            luminance = 0.299*r + 0.587*g + 0.114*b
            if luminance > 190:
                v = 0.24
                s = min(s+0.08, 0.8)
        else:
            if v < 0.25:
                v = 0.45
            if s < 0.15:
                s = 0.3
        
        nr, ng, nb = colorsys.hsv_to_rgb(h, s, v)
        return (int(nr*255), int(ng*255), int(nb*255))

    c1 = adjust_for_bg(bg, is_accent=False)
    c2 = adjust_for_bg(accent, is_accent=True)
    
    def ensure_contrast(c1, c2):
        def luminance(c):
            r, g, b = [x/255 for x in c]
            return 0.2126*r + 0.7152*g + 0.0722*b
        l1, l2 = luminance(c1), luminance(c2)
        if l1 < l2:
            c1, c2 = c2, c1
            l1, l2 = l2, l1
        ratio = (l1 + 0.05) / (l2 + 0.05)
        if ratio < 2.9:
            h, s, v = colorsys.rgb_to_hsv(c2[0]/255, c2[1]/255, c2[2]/255)
            v *= 0.55
            s *= 0.8
            nr, ng, nb = colorsys.hsv_to_rgb(h, s, v)
            c2 = (int(nr*255), int(ng*255), int(nb*255))
        return c1, c2
    
    c1, c2 = ensure_contrast(c1, c2)
    return c1, c2

def create_textured_bg(base_color, accent_color, width, height):
    """
    Creates a background with thin, subtle diagonal streaks.
    """
    base = Image.new("RGB", (width, height), base_color)
    texture = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(texture)
    
    accent = (*accent_color, 26)
    mid = (*accent_color, 18)
    bright = (255, 255, 255, 14)
    
    num_clusters = 18
    for _ in range(num_clusters):
        start_x = random.randint(-width // 3, width)
        start_y = random.randint(-height // 3, height)
        length = random.randint(width // 2, int(width * 1.4))
        thickness_base = random.uniform(1.0, 3.2)
        
        angle = random.uniform(-35, -55)
        angle_rad = math.radians(angle)
        
        dx = math.cos(angle_rad)
        dy = math.sin(angle_rad)
        
        num_segments = random.randint(9, 15)
        for i in range(num_segments):
            seg_frac = i / max(1, num_segments - 1)
            seg_len = length * random.uniform(0.06, 0.16)
            
            cx = start_x + dx * length * seg_frac
            cy = start_y + dy * length * seg_frac
            
            offset = random.uniform(-18, 18)
            cx += -dy * offset
            cy += dx * offset
            
            x1 = cx - dx * seg_len / 2
            y1 = cy - dy * seg_len / 2
            x2 = cx + dx * seg_len / 2
            y2 = cy + dy * seg_len / 2
            
            width_scale = (1.0 - abs(seg_frac - 0.5) * 1.4)
            width_scale = max(width_scale, 0.2)
            w = max(1, int(thickness_base * width_scale))
            
            if seg_frac < 0.25 or seg_frac > 0.75:
                line_color = accent
            else:
                line_color = mid if random.random() < 0.7 else bright
            
            tdraw.line([(x1, y1), (x2, y2)], fill=line_color, width=w)
        
        for _ in range(3):
            ripple_x = start_x + random.randint(-40, 40)
            ripple_y = start_y + random.randint(-40, 40)
            ripple_len = random.randint(40, 110)
            angle2 = angle + random.uniform(-18, 18)
            angle2_rad = math.radians(angle2)
            dx2 = math.cos(angle2_rad)
            dy2 = math.sin(angle2_rad)
            
            x1 = ripple_x
            y1 = ripple_y
            x2 = ripple_x + dx2 * ripple_len
            y2 = ripple_y + dy2 * ripple_len
            
            ripple_color = (accent_color[0], accent_color[1], accent_color[2], 22)
            tdraw.line([(x1, y1), (x2, y2)], fill=ripple_color, width=1)
    
    texture = texture.filter(ImageFilter.GaussianBlur(radius=2))
    base = base.convert("RGBA")
    base = Image.alpha_composite(base, texture)
    return base.convert("RGB")

def apply_film_grain(img, intensity=0.08):
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
            "logline": ImageFont.truetype(str(REGULAR_FONT_PATH), 26),
            "cinema": ImageFont.truetype(str(BOLD_FONT_PATH), 28),
            "times": ImageFont.truetype(str(REGULAR_FONT_PATH), 28),
        }
    except:
        return {k: ImageFont.load_default() for k in ["cover_main", "cover_sub", "title_jp", "title_en", "meta", "logline", "cinema", "times"]}

def draw_centered_text(draw, y, text, font, fill):
    if not text:
        return y
    w, h = draw.textsize(text, font=font)
    x = (CANVAS_WIDTH - w) // 2
    draw.text((x, y), text, font=font, fill=fill)
    return y + int(h * 1.15)

def draw_cover_slide(images, fonts, date_str, day_str):
    if not images:
        bg = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), (12, 12, 16))
        draw = ImageDraw.Draw(bg)
        cx, cy = CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2
        draw.text((cx, cy - 80), "TOKYO", font=fonts['cover_main'], fill=(255,255,255), anchor="mm")
        draw.text((cx, cy + 40), "CINEMA", font=fonts['cover_main'], fill=(255,255,255), anchor="mm")
        draw.text((cx, cy + 160), f"{date_str} • {day_str}", font=fonts['cover_sub'], fill=(220,220,220), anchor="mm")
        return bg
    
    merged = images[0]
    c1, c2 = get_faithful_colors(merged)
    bg = create_textured_bg(c1, c2, CANVAS_WIDTH, CANVAS_HEIGHT)
    bg = apply_film_grain(bg)
    draw = ImageDraw.Draw(bg)
    
    cx, cy = CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2
    draw.text((cx, cy - 80), "TOKYO", font=fonts['cover_main'], fill=(255,255,255), anchor="mm")
    draw.text((cx, cy + 40), "CINEMA", font=fonts['cover_main'], fill=(255,255,255), anchor="mm")
    draw.text((cx, cy + 160), f"{date_str} • {day_str}", font=fonts['cover_sub'], fill=(220,220,220), anchor="mm")
    return bg

def draw_poster_slide(film, img_obj, fonts):
    # 1. Textured Background
    c_base, c_accent = get_faithful_colors(img_obj)
    bg = create_textured_bg(c_base, c_accent, CANVAS_WIDTH, CANVAS_HEIGHT)
    canvas = apply_film_grain(bg)
    draw = ImageDraw.Draw(canvas)
    
    # 2. Layout Logic
    logline_jp = (film.get("logline_jp") or "").strip()
    logline_en = (film.get("logline_en") or "").strip()
    has_logline = bool(logline_jp or logline_en)
    
    target_w = 900
    if has_logline:
        img_y = 120
        target_h = 520
    else:
        img_y = 180
        target_h = 600
    
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
    
    img_x = (CANVAS_WIDTH - target_w) // 2
    canvas.paste(img_final, (img_x, img_y))
    
    cursor_y = img_y + target_h + 70
    
    # 3. Typography
    
    # Metadata
    meta_parts = []
    if film.get('year'): meta_parts.append(str(film['year']))
    if film.get('tmdb_runtime'): meta_parts.append(f"{film['tmdb_runtime']}m")
    if film.get('genres'): meta_parts.append(film['genres'][0].upper())
    
    meta_str = "  •  ".join(meta_parts)
    cursor_y = draw_centered_text(draw, cursor_y, meta_str, fonts['meta'], (200, 200, 200))
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
            cursor_y = draw_centered_text(draw, cursor_y, line, fonts['title_jp'], (255, 255, 255))
    else:
        cursor_y = draw_centered_text(draw, cursor_y, jp_title, fonts['title_jp'], (255, 255, 255))
    
    cursor_y += 10

    # English Title
    if en_title:
        cursor_y = draw_centered_text(draw, cursor_y, en_title.upper(), fonts['title_en'], (200, 200, 200))
    
    # Director
    director = film.get('tmdb_director') or film.get('director')
    if director:
        cursor_y += 15
        draw_centered_text(draw, cursor_y, f"Dir. {director}", fonts['meta'], (150, 150, 150))
        cursor_y += 30

    # 4. Loglines (JP + EN)
    if has_logline:
        cursor_y += 20
        available_h = (CANVAS_HEIGHT - 200) - cursor_y
        if available_h > 80:
            # Japanese logline
            if logline_jp:
                wrapper_jp = textwrap.TextWrapper(width=18)
                jp_lines = wrapper_jp.wrap(logline_jp)[:2]
                for line in jp_lines:
                    cursor_y = draw_centered_text(
                        draw, cursor_y, line, fonts['logline'], (190, 190, 190)
                    )
                cursor_y += 8
            # English logline
            if logline_en:
                wrapper_en = textwrap.TextWrapper(width=32)
                en_lines = wrapper_en.wrap(logline_en)[:2]
                for line in en_lines:
                    cursor_y = draw_centered_text(
                        draw, cursor_y, line, fonts['logline'], (170, 170, 170)
                    )
                cursor_y += 10
    
    
    # 5. Showtimes (Smart-Fit V2)
    sorted_cinemas = sorted(film['showings'].keys())
    num_cinemas = len(sorted_cinemas)
    
    available_space = CANVAS_HEIGHT - cursor_y - 50
    std_font_size = 28
    std_gap = 50
    
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
    
    for cin in sorted_cinemas:
        times = sorted(film['showings'][cin])
        clean_cin = CINEMA_NAME_MAPPING.get(cin, cin)
        
        w_cin, h_cin = draw.textsize(clean_cin, font=dyn_font_cin)
        w_times, h_times = draw.textsize(", ".join(times), font=dyn_font_time)
        
        total_height = h_cin + h_times + int(final_gap * 0.6)
        
        x_cin = (CANVAS_WIDTH - w_cin) // 2
        draw.text((x_cin, start_y), clean_cin, font=dyn_font_cin, fill=(255, 255, 255))
        
        x_times = (CANVAS_WIDTH - w_times) // 2
        draw.text((x_times, start_y + h_cin + int(final_gap * 0.3)), ", ".join(times), font=dyn_font_time, fill=(220, 220, 220))
        
        start_y += unit_height
    
    return canvas

def main():
    print("--- Starting V26 (Subtle Texture) ---")
    
    for f in glob.glob(str(BASE_DIR / "post_v2_*.png")): os.remove(f)
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
        film["logline_en"] = build_logline(film, "en")
        film["logline_jp"] = build_logline(film, "jp")
        print(f"Processing: {film.get('clean_title_jp') or film.get('movie_title')}")
        img = download_image(film.get('tmdb_backdrop_path'))
        if img:
            all_images.append(img)
            slide_data.append({"film": film, "img": img})
            
    if all_images:
        d_str, day_str = get_bilingual_date()
        cover = draw_cover_slide(all_images, fonts, d_str, day_str)
        cover.save(BASE_DIR / "post_v2_image_00.png")
        
    caption_lines = [f"🗓️ {date_str} Tokyo Cinema Selection\n"]
    
    for i, item in enumerate(slide_data):
        film = item['film']
        img = item['img']
        slide = draw_poster_slide(film, img, fonts)
        slide.save(BASE_DIR / f"post_v2_image_{i+1:02}.png")
        
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
        
    print("Done. V26 Generated.")

if __name__ == "__main__":
    main()
