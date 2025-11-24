"""
Generate Instagram-ready image carousel (V47 - Flux Soft Stack).

- Layout: Uses Python to creating a "Soft Vertical Stack" of images with 
  gradient overlaps (standard movie poster composition).
- AI: Flux.1 Dev with LOWER strength (0.65). 
- Goal: Forces AI to keep the original actors/scenes but "heal" the blend lines.
"""
from __future__ import annotations

import json
import random
import os
import glob
import requests
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

# --- API Setup ---
try:
    import replicate
    REPLICATE_AVAILABLE = True
except ImportError:
    print("⚠️ Replicate library not found.")
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

# --- Cinema Name Mapping (Truncated) ---
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

# --- REPLICATE / FLUX PIPELINE (Soft Stack Mode) ---

def create_soft_stack_composite(images, width=896, height=1152):
    """
    Stacks images vertically using gradient masks to blend them smoothly.
    This removes the hard 'grid' lines BEFORE the AI sees it.
    """
    canvas = Image.new("RGB", (width, height), (0,0,0))
    if not images: return canvas
    
    # Use top 3 images for a balanced stack
    source_imgs = images[:3]
    
    # Helper to resize image to full width and specific height
    def prepare_slice(img, w, h):
        ratio = img.width / img.height
        # Resize to fill width
        target_h = int(w / ratio)
        if target_h < h:
            # If too short, scale up
            scale = h / target_h
            new_w = int(w * scale)
            new_h = h
            resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            # Crop center width
            left = (new_w - w) // 2
            return resized.crop((left, 0, left+w, h))
        else:
            # Too tall, just resize width and crop height
            resized = img.resize((w, target_h), Image.Resampling.LANCZOS)
            return resized.crop((0, 0, w, h))

    # We want them to overlap. 
    # Img 1: Top 40%
    # Img 2: Middle 40% (Overlaps 1 and 3)
    # Img 3: Bottom 40%
    
    slice_h = int(height * 0.45)
    
    # 1. Bottom Layer (Img 3) - Placed at bottom
    img3 = prepare_slice(source_imgs[2] if len(source_imgs)>2 else source_imgs[0], width, slice_h)
    canvas.paste(img3, (0, height - slice_h))
    
    # 2. Middle Layer (Img 2) - Placed in middle, masked
    img2 = prepare_slice(source_imgs[1] if len(source_imgs)>1 else source_imgs[0], width, slice_h)
    
    # Create gradient mask for bottom of Img 2 so it fades into Img 3
    # Actually, easier to just paste Img 2 at the top, then Img 3 at bottom, then Img 1...
    
    # Let's restart the layering strategy:
    # Layer 1: Full background (Img 3 blurred/darkened)
    base = prepare_slice(source_imgs[-1], width, height)
    base = base.filter(ImageFilter.GaussianBlur(10)) # Abstract BG
    canvas.paste(base, (0,0))
    
    # Layer 2: Img 1 at Top (Gradient fade to transparent at bottom)
    img1 = prepare_slice(source_imgs[0], width, int(height*0.6))
    mask1 = Image.new('L', (width, img1.height), 255)
    draw1 = ImageDraw.Draw(mask1)
    # Fade out the bottom 30% of this image
    for y in range(int(img1.height * 0.7), img1.height):
        alpha = int(255 * (1 - (y - img1.height * 0.7) / (img1.height * 0.3)))
        draw1.line([(0, y), (width, y)], fill=alpha)
    canvas.paste(img1, (0, 0), mask1)
    
    # Layer 3: Img 2 at Bottom (Gradient fade to transparent at top)
    if len(source_imgs) > 1:
        img2 = prepare_slice(source_imgs[1], width, int(height*0.6))
        mask2 = Image.new('L', (width, img2.height), 255)
        draw2 = ImageDraw.Draw(mask2)
        # Fade out the top 30% of this image
        for y in range(int(img2.height * 0.3)):
            alpha = int(255 * (y / (img2.height * 0.3)))
            draw2.line([(0, y), (width, y)], fill=alpha)
        canvas.paste(img2, (0, height - img2.height), mask2)
        
    return canvas

def generate_flux_mashup(images: list[Image.Image]) -> Image.Image | None:
    print("🎨 Preparing Flux Dev (Soft Stack)
