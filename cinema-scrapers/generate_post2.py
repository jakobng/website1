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
    
    colors = thumb.getcolors(80*45)
    if not colors:
        return (20, 20, 20), (230, 230, 230)
    
    colors.sort(key=lambda x: x[0], reverse=True)
    dominant = [c[1] for c in colors[:12]]
    
    def is_too_close(c1, c2, thresh=25):
        return sum((a-b)**2 for a, b in zip(c1, c2)) ** 0.5 < thresh
    
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
        
        nr, ng, nb = colorsys.hsv_to_hsv(h, s, v) if False else colorsys.hsv_to_rgb(h, s, v)
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
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
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
    except Exception:
        return {
            k: ImageFont.load_default()
            for k in [
                "cover_main",
                "cover_sub",
                "title_jp",
                "title_en",
                "meta",
                "logline",
                "cinema",
                "times",
            ]
        }

def _measure_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont):
    """
    Pillow >=10 removed textsize; use textbbox instead.
    Returns (width, height).
    """
    if not text:
        return 0, 0
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    return w, h

def draw_centered_text(draw, y, text, font, fill):
    if not text:
        return y
    w, h = _measure_text(draw, text, font)
    x = (CANVAS_WIDTH - w) // 2
    draw.text((x, y), text, font=font, fill=fill)
    return y + int(h * 1.15)

def draw_cover_slide(images, fonts, date_str, day_str):
    if not images:
        bg = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), (12, 12, 16))
        draw = ImageDraw.Draw(bg)
        cx, cy = CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2
        draw.text(
            (cx, cy - 80),
            "TOKYO",
            font=fonts["cover_main"],
            fill=(255, 255, 255),
            anchor="mm",
        )
        draw.text(
            (cx, cy + 40),
            "CINEMA",
            font=fonts["cover_main"],
            fill=(255, 255, 255),
            anchor="mm",
        )
        draw.text(
            (cx, cy + 160),
            f"{date_str} • {day_str}",
            font=fonts["cover_sub"],
            fill=(220, 220, 220),
            anchor="mm",
        )
        return bg

    merged = images[0]
    c1, c2 = get_faithful_colors(merged)
    bg = create_textured_bg(c1, c2, CANVAS_WIDTH, CANVAS_HEIGHT)
    bg = apply_film_grain(bg)
    draw = ImageDraw.Draw(bg)

    cx, cy = CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2
    draw.text(
        (cx, cy - 80),
        "TOKYO",
        font=fonts["cover_main"],
        fill=(255, 255, 255),
        anchor="mm",
    )
    draw.text(
        (cx, cy + 40),
        "CINEMA",
        font=fonts["cover_main"],
        fill=(255, 255, 255),
        anchor="mm",
    )
    draw.text(
        (cx, cy + 160),
        f"{date_str} • {day_str}",
        font=fonts["cover_sub"],
        fill=(220, 220, 220),
        anchor="mm",
    )
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
        img_final = img_resized.crop((left, 0, left + target_w, target_h)
