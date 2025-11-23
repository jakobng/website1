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

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"
BOLD_FONT_PATH = BASE_DIR / "NotoSansJP-Bold.ttf"
REGULAR_FONT_PATH = BASE_DIR / "NotoSansJP-Regular.ttf"
OUTPUT_CAPTION_PATH = BASE_DIR / "post_v2_caption.txt"

# Layout Dimensions
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350
MARGIN = 80

# --- Cinema Name Mapping (JP -> EN) ---
CINEMA_ENGLISH_NAMES = {
    "Bunkamura ル・シネマ 渋谷宮下": "Bunkamura Le Cinéma",
    "K's Cinema (ケイズシネマ)": "K's Cinema",
    "シネマヴェーラ渋谷": "Cinema Vera Shibuya",
    "シアター・イメージフォーラム": "Image Forum Shibuya",
    "ユーロスペース": "Eurospace",
    "ポレポレ東中野": "Pole Pole Higashinakano",
    "テアトル新宿": "Theatre Shinjuku",
    "シネマート新宿": "Cinem@rt Shinjuku",
    "アップリンク吉祥寺": "Uplink Kichijoji",
    "ユジク阿佐ヶ谷": "Yujiku Asagaya",
    "下北沢トリウッド": "Tollywood Shimokitazawa",
    "シモキタ - エキマエ - シネマ K2": "Shimokita Ekimae Cinema K2",
    "シネスイッチ銀座": "Cine Switch Ginza",
    "ヒューマントラストシネマ渋谷": "Human Trust Cinema Shibuya",
    "ヒューマントラストシネマ有楽町": "Human Trust Cinema Yurakucho",
    "角川シネマ有楽町": "Kadokawa Cinema Yurakucho",
    "新宿武蔵野館": "Shinjuku Musashinokan",
    "シネマカリテ": "Cinema Qualite",
    "渋谷シネクイント": "Cine Quinto Shibuya",
    "シネマート心斎橋": "Cinem@rt Shinsaibashi",
    "Cinem@rt新宿": "Cinem@rt Shinjuku",
    "kino cinéma横浜みなとみらい": "Kino Cinema Yokohama Minatomirai",
    "kino cinéma天神": "Kino Cinema Tenjin",
    "kino cinéma神戸国際": "Kino Cinema Kobe",
    "Kino cinéma立川髙島屋S.C.館": "Kino Cinema Tachikawa",
    "アップリンク京都": "Uplink Kyoto",
    "アップリンク渋谷": "Uplink Shibuya",
    "シネマ・ジャック＆ベティ": "Cinema Jack & Betty",
    "イメージフォーラム": "Image Forum Shibuya",
    "Image Forum Shibuya": "Image Forum Shibuya",
    "Eurospace": "Eurospace",
    "K's cinema": "K's Cinema",
    "Tollywood": "Tollywood Shimokitazawa",
    "Tollywood Shimokitazawa": "Tollywood Shimokitazawa",
    "Morc阿佐ヶ谷": "Morc Asagaya",
    "Morc Asagaya": "Morc Asagaya",
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
                return text[:idx + 1]
        return text
    else:
        for sep in ".!?":
            idx = text.find(sep)
            if idx != -1:
                return text[:idx + 1].strip()
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
        max_chars = 110  # ~1–2 lines
    else:
        tagline = (film.get("tmdb_tagline_jp") or "").strip()
        overview = (film.get("tmdb_overview_jp") or "").strip()
        max_chars = 60   # JP chars are denser

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
    if not s:
        return ""
    return re.sub(r'\W+', '', str(s)).lower()

def download_image(path: str) -> Image.Image | None:
    if not path:
        return None
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
    palette = thumb.getpalette()
    if not palette:
        # Fallback if palette isn't available
        colors = thumb.getcolors(80 * 45)
        if not colors:
            return (20, 20, 20), (230, 230, 230)
        colors.sort(key=lambda x: x[0], reverse=True)
        c1 = colors[0][1]
        c2 = colors[1][1] if len(colors) > 1 else c1
        return c1, c2

    # Use first two palette entries as base
    c1 = (palette[0], palette[1], palette[2])
    c2 = (palette[3], palette[4], palette[5])
    
    def adjust_for_bg(rgb_tuple, is_accent=False):
        r, g, b = rgb_tuple
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        
        if is_accent:
            # Accent: Just needs to be visible against Base. 
            # Slight boost to brightness if it's too dark.
            new_v = max(v, 0.4)
            new_s = s  # Keep saturation faithful
        else:
            # Base: Needs to support white text.
            # Darken if too bright, Brighten if pitch black.
            new_v = 0.22  # Standard "Dark Mode" grey level
            new_s = min(max(s, 0.4), 0.9)  # Ensure some color remains
            
            # Special case: True B&W
            if s < 0.05: 
                new_s = 0.02
                new_v = 0.20
        
        nr, ng, nb = colorsys.hsv_to_rgb(h, new_s, new_v)
        return (int(nr*255), int(ng*255), int(nb*255))

    return adjust_for_bg(c1), adjust_for_bg(c2, is_accent=True)

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
    """
    Adds subtle luminance noise to simulate film grain.
    """
    width, height = img.size
    noise = Image.effect_noise((width, height), 64)
    noise = noise.convert("L")
    noise = ImageEnhance.Contrast(noise).enhance(1.5)
    noise = ImageEnhance.Brightness(noise).enhance(1.1)
    
    if img.mode != "RGB":
        img = img.convert("RGB")
    
    grain = Image.merge("RGB", (noise, noise, noise))
    return Image.blend(img, grain, alpha=intensity)

def get_fonts():
    """
    Load fonts for different tiers of typography.
    """
    try:
        fonts = {
            "cover_main": ImageFont.truetype(str(BOLD_FONT_PATH), 110),
            "cover_sub": ImageFont.truetype(str(REGULAR_FONT_PATH), 32),
            "title_jp": ImageFont.truetype(str(BOLD_FONT_PATH), 56),
            "title_en": ImageFont.truetype(str(REGULAR_FONT_PATH), 30),
            "meta": ImageFont.truetype(str(REGULAR_FONT_PATH), 24),
            "logline": ImageFont.truetype(str(REGULAR_FONT_PATH), 26),
            "cinema": ImageFont.truetype(str(BOLD_FONT_PATH), 28),
            "times": ImageFont.truetype(str(REGULAR_FONT_PATH), 28),
        }
    except Exception as e:
        print("Font load error:", e)
        fonts = {
            "cover_main": ImageFont.load_default(),
            "cover_sub": ImageFont.load_default(),
            "title_jp": ImageFont.load_default(),
            "title_en": ImageFont.load_default(),
            "meta": ImageFont.load_default(),
            "logline": ImageFont.load_default(),
            "cinema": ImageFont.load_default(),
            "times": ImageFont.load_default(),
        }
    return fonts

def draw_centered_text(draw, y, text, font, fill):
    if not text:
        return y
    length = draw.textlength(text, font=font)
    x = (CANVAS_WIDTH - length) // 2
    draw.text((x, y), text, font=font, fill=fill)
    return y + font.size + 10 

def draw_cover_slide(images, fonts, date_str, day_str):
    c1, c2 = get_faithful_colors(images[0])
    bg = create_textured_bg(c1, c2, CANVAS_WIDTH, CANVAS_HEIGHT)
    bg = apply_film_grain(bg)
    draw = ImageDraw.Draw(bg)
    
    title = "TOKYO"
    subtitle = "CINEMA"
    header_y = 260
    
    y = header_y
    y = draw_centered_text(draw, y, title, fonts['cover_main'], (255,255,255))
    y = draw_centered_text(draw, y, subtitle, fonts['cover_main'], (255,255,255))
    
    date_line = f"{date_str} • {day_str}"
    draw_centered_text(draw, y + 10, date_line, fonts['cover_sub'], (220,220,220))
    
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
        target_h = 550
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
    
    cursor_y = img_y + target_h + 50
    
    # 3. Metadata line (Year, Runtime, Genre)
    meta_parts = []
    if film.get('year'):
        meta_parts.append(str(film['year']))
    if film.get('tmdb_runtime'):
        meta_parts.append(f"{film['tmdb_runtime']}m")
    if film.get('genres'):
        meta_parts.append(film['genres'][0].upper())
    meta_str = "  •  ".join(meta_parts)
    
    if meta_str:
        cursor_y = draw_centered_text(draw, cursor_y, meta_str, fonts['meta'], (210,210,210))
        cursor_y += 15
    
    # 3b. Titles (JP + optional EN)
    jp_title = film.get('clean_title_jp') or film.get('movie_title', '')
    en_title = film.get('movie_title_en')
    
    if normalize_string(jp_title) == normalize_string(en_title):
        en_title = None
    
    # Japanese Title (wrap if long)
    if len(jp_title) > 15:
        wrapper = textwrap.TextWrapper(width=15)
        lines = wrapper.wrap(jp_title)
        for line in lines:
            cursor_y = draw_centered_text(draw, cursor_y, line, fonts['title_jp'], (255,255,255))
    else:
        cursor_y = draw_centered_text(draw, cursor_y, jp_title, fonts['title_jp'], (255,255,255))
    
    cursor_y += 5
    
    # English Title (if different)
    if en_title:
        cursor_y = draw_centered_text(draw, cursor_y, en_title.upper(), fonts['title_en'], (210,210,210))
    
    # Director
    director = film.get('tmdb_director') or film.get('director')
    if director:
        cursor_y += 15
        draw_centered_text(draw, cursor_y, f"Dir. {director}", fonts['meta'], (150, 150, 150))
        cursor_y += 30

    # 4. Logline (JP + EN)
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
        
    for cinema in sorted_cinemas:
        times = sorted(film['showings'][cinema])
        times_str = " ".join(times)
        cinema_en = CINEMA_ENGLISH_NAMES.get(cinema, cinema)
        
        len_c = draw.textlength(cinema_en, font=dyn_font_cin)
        x_c = (CANVAS_WIDTH - len_c) // 2
        draw.text((x_c, start_y), cinema_en, font=dyn_font_cin, fill=(255, 255, 255))
        
        y_time = start_y + final_font_size + 5 
        len_t = draw.textlength(times_str, font=dyn_font_time)
        x_t = (CANVAS_WIDTH - len_t) // 2
        draw.text((x_t, y_time), times_str, font=dyn_font_time, fill=(200, 200, 200))
        
        start_y += unit_height

    return canvas

def load_showtimes_for_today():
    """
    Load showtimes.json and group films by tmdb_id (or title if no id),
    building a mapping of film -> showtimes per cinema.
    """
    if not SHOWTIMES_PATH.exists():
        print("No showtimes.json found.")
        return []

    date_str = get_today_str()
    with open(SHOWTIMES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    films_map = {}
    for item in data:
        if item.get("date_text") != date_str:
            continue
        if not item.get("tmdb_backdrop_path"):
            continue
        
        key = item.get("tmdb_id") or item.get("movie_title")
        
        if key not in films_map:
            films_map[key] = item
            films_map[key]["showings"] = defaultdict(list)
        films_map[key]["showings"][item.get("cinema_name", "")].append(item.get("showtime", ""))
    
    films = list(films_map.values())
    return films

def build_caption(slide_data, date_str):
    """
    Build a multi-line caption listing all selected films and showtimes.
    """
    caption_lines = [f"🗓️ {date_str} Tokyo Cinema Selection\n"]
    
    for item in slide_data:
        film = item["film"]
        title_jp = film.get("clean_title_jp") or film.get("movie_title", "")
        title_en = film.get("movie_title_en")
        
        caption_lines.append(title_jp)
        if title_en and normalize_string(title_en) != normalize_string(title_jp):
            caption_lines.append(title_en)
        
        for cin, times in film["showings"].items():
            times = sorted(times)
            caption_lines.append(f"{cin}: {', '.join(times)}")
        caption_lines.append("")
    
    caption_lines.append("\nLink in Bio for Full Schedule")
    caption_lines.append("#TokyoIndieCinema #MiniTheater #MovieLog")
    
    return "\n".join(caption_lines)

def main():
    print("--- Starting V26 (Subtle Texture) ---")
    
    # 1. Clean old outputs
    for f in glob.glob(str(BASE_DIR / "post_v2_image_*.png")):
        os.remove(f)
    
    date_str = get_today_str()
    
    # 2. Load films for today
    films = load_showtimes_for_today()
    if not films:
        print("No films found for today.")
        return
    
    random.shuffle(films)
    selected = films[:9]
    print(f"Selected {len(selected)} films.")
    
    fonts = get_fonts()
    slide_data = []
    all_images = []
    
    for film in selected:
        # Attach short JP/EN loglines based on TMDB tagline/overview
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
    else:
        print("No images downloaded; skipping cover slide.")
        return
    
    # 3. Poster slides
    for idx, item in enumerate(slide_data, start=1):
        film = item["film"]
        img = item["img"]
        slide = draw_poster_slide(film, img, fonts)
        slide.save(BASE_DIR / f"post_v2_image_{idx:02d}.png")
    
    # 4. Caption
    caption = build_caption(slide_data, date_str)
    with open(OUTPUT_CAPTION_PATH, "w", encoding="utf-8") as f:
        f.write(caption)
    
    print("Done. V26 Generated.")

if __name__ == "__main__":
    main()
