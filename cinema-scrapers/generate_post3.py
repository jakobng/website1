"""
Generate Instagram-ready image carousel (V34 - No AI Creativity).

- Logic: STRICTLY uses Google Search to find official taglines OR extracts existing text.
- User Requirement: "Not gemini writing its own tagline."
- Model: Gemini 2.5 Flash + Google Search Grounding.
"""
from __future__ import annotations

import json
import random
import textwrap
import os
import time
import requests
import colorsys
import math
import re
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
CANVAS_HEIGHT = 1350

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

# --- Gemini API Helper (2.5 Flash + Search) ---
def generate_gemini_taglines(film_data):
    """
    Calls Gemini 2.5 Flash API with Google Search Grounding.
    Purpose: Find OFFICIAL taglines or EXTRACT text. No creative writing.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("⚠️ GEMINI_API_KEY not found. Skipping AI text generation.")
        return "", ""

    title = film_data.get('movie_title', '')
    title_en = film_data.get('movie_title_en', '')
    synopsis = film_data.get('synopsis', '') or film_data.get('tmdb_overview_jp', '')
    
    # Prompt: STICTLY prohibiting creative writing
    prompt = f"""
    Task: Identify the official tagline (catch copy) for the movie '{title}' ({title_en}).
    
    Provided Synopsis: {synopsis}
    
    STRICT RULES:
    1. USE GOOGLE SEARCH to find the official Japanese and English taglines used on posters.
    2. If NO official tagline exists, EXTRACT a short, impactful sentence verbatim from the synopsis.
    3. DO NOT write your own creative slogan. Use existing text only.
    4. Translate the extracted text if necessary to provide both JP and EN versions.
    
    Constraints:
    - Japanese: Max 30 characters.
    - English: Max 12 words.
    
    Output Format (JSON Only):
    {{
      "jp": "...",
      "en": "..."
    }}
    """

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [
            {"googleSearch": {}} 
        ]
    }

    try:
        print("  ...Waiting 5s for API rate limit...")
        time.sleep(5) 
        
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            result = response.json()
            if 'candidates' not in result or not result['candidates']:
                return "", ""

            raw_text = result['candidates'][0]['content']['parts'][0]['text']
            
            # Clean markdown if present
            clean_text = re.sub(r"```json|```", "", raw_text).strip()
            
            try:
                data = json.loads(clean_text)
                return data.get('jp', ''), data.get('en', '')
            except json.JSONDecodeError:
                print(f"⚠️ Failed to parse JSON for '{title}'.")
                return "", ""
        else:
            print(f"❌ Gemini API Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ Gemini Request Failed for '{title}': {e}")

    return "", ""

# --- Visual Helpers ---

def get_bilingual_date():
    today = datetime.now()
    return today.strftime("%Y.%m.%d"), today.strftime("%A").upper()

def download_image(path: str) -> Image.Image | None:
    if not path: return None
    if path.startswith("http"):
        url = path
    else:
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
            new_v = max(v, 0.5) 
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
    
    for _ in range(40):
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
    return Image.blend(img, noise_img, alpha=0.05)

def draw_centered_text(draw, y, text, font, fill):
    length = draw.textlength(text, font=font)
    x = (CANVAS_WIDTH - length) // 2
    draw.text((x, y), text, font=font, fill=fill)
    return y + font.size + 12

# --- Slide Generators ---

def draw_cover_slide(images, fonts, date_str, day_str):
    c1, c2 = get_faithful_colors(images[0])
    bg = create_textured_bg(c1, c2, CANVAS_WIDTH, CANVAS_HEIGHT)
    bg = apply_film_grain(bg)
    draw = ImageDraw.Draw(bg)
    
    cx, cy = CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2
    
    draw.text((cx, cy - 80), "TOKYO", font=fonts['cover_main'], fill=(255,255,255), anchor="mm")
    draw.text((cx, cy + 40), "CINEMA", font=fonts['cover_main'], fill=(255,255,255), anchor="mm")
    draw.text((cx, cy + 160), f"{date_str} • {day_str}", font=fonts['cover_sub'], fill=(220,220,220), anchor="mm")
    
    return bg

def draw_poster_slide(film, img_obj, fonts):
    c_base, c_accent = get_faithful_colors(img_obj)
    bg = create_textured_bg(c_base, c_accent, CANVAS_WIDTH, CANVAS_HEIGHT)
    canvas = apply_film_grain(bg)
    draw = ImageDraw.Draw(canvas)
    
    tagline_jp = film.get('gen_tagline_jp', '')
    tagline_en = film.get('gen_tagline_en', '')
    has_tagline = bool(tagline_jp or tagline_en)
    
    target_w = 900
    if has_tagline:
        img_y = 120
        target_h = 550
    else:
        img_y = 180
        target_h = 600
        
    img_ratio = img_obj.width / img_obj.height
    if img_ratio > (target_w / target_h):
        new_h = target_h
        new_w = int(new_h * img_ratio)
        img_resized = img_obj.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - target_w) // 2
        img_cropped = img_resized.crop((left, 0, left + target_w, target_h))
    else:
        new_w = target_w
        new_h = int(new_w / img_ratio)
        img_resized = img_obj.resize((new_w, new_h), Image.LANCZOS)
        top = (new_h - target_h) // 2
        img_cropped = img_resized.crop((0, top, target_w, top + target_h))
        
    shadow = Image.new("RGB", (target_w + 20, target_h + 20), (0,0,0))
    canvas.paste(shadow, ((CANVAS_WIDTH - target_w)//2 + 10, img_y + 10))
    canvas.paste(img_cropped, ((CANVAS_WIDTH - target_w)//2, img_y))
    
    cursor_y = img_y + target_h + 40
    
    title_jp = film.get('clean_title_jp') or film.get('movie_title')
    title_en = film.get('movie_title_en')
    
    cursor_y = draw_centered_text(draw, cursor_y, title_jp, fonts['cover_main'], (255, 255, 255))
    if title_en:
        cursor_y = draw_centered_text(draw, cursor_y, title_en, fonts['cover_sub'], (200, 200, 200))
    
    cursor_y += 20

    available_h = CANVAS_HEIGHT - cursor_y - 350
    if has_tagline and available_h > 50:
        if tagline_jp:
            wrapper_jp = textwrap.TextWrapper(width=26) 
            for line in wrapper_jp.wrap(tagline_jp):
                cursor_y = draw_centered_text(draw, cursor_y, line, fonts['logline'], (230, 230, 230))
            cursor_y += 8
            
        if tagline_en:
            wrapper_en = textwrap.TextWrapper(width=50)
            for line in wrapper_en.wrap(tagline_en):
                cursor_y = draw_centered_text(draw, cursor_y, line, fonts['logline'], (180, 180, 180))

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
        dyn_font_cin = fonts['cover_sub']
        dyn_font_time = fonts['cover_sub']

    for cinema in sorted_cinemas:
        times = film['showings'][cinema]
        times.sort()
        
        display_name = CINEMA_ENGLISH_NAMES.get(cinema, cinema)
        draw_centered_text(draw, cursor_y, display_name, dyn_font_cin, (255, 215, 0))
        cursor_y += final_font_size * 1.4
        
        time_str = " / ".join(times)
        draw_centered_text(draw, cursor_y, time_str, dyn_font_time, (255, 255, 255))
        cursor_y += final_font_size * 1.4 + final_gap

    return canvas

# --- Main Execution ---
if __name__ == "__main__":
    print("Starting V34 (No AI Creativity)...")
    
    try:
        with open(SHOWTIMES_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("❌ Error: showtimes.json not found.")
        exit(1)
        
    # Group by movie
    movies = {}
    for show in data:
        title = show['movie_title']
        if title not in movies:
            movies[title] = show.copy()
            movies[title]['showings'] = {}
            
        cin = show['cinema_name']
        time_str = show['showtime']
        if cin not in movies[title]['showings']:
            movies[title]['showings'][cin] = []
        if time_str not in movies[title]['showings'][cin]:
            movies[title]['showings'][cin].append(time_str)
            
    selected_candidates = list(movies.values())
    
    # Load Fonts
    try:
        fonts = {
            'cover_main': ImageFont.truetype(str(BOLD_FONT_PATH), 120),
            'cover_sub': ImageFont.truetype(str(REGULAR_FONT_PATH), 40),
            'title': ImageFont.truetype(str(BOLD_FONT_PATH), 50),
            'logline': ImageFont.truetype(str(REGULAR_FONT_PATH), 30),
            'cinema': ImageFont.truetype(str(BOLD_FONT_PATH), 28),
            'time': ImageFont.truetype(str(REGULAR_FONT_PATH), 28),
        }
    except OSError:
        print("⚠️ Fonts not found. Using default.")
        fonts = {k: ImageFont.load_default() for k in ['cover_main', 'cover_sub', 'title', 'logline', 'cinema', 'time']}

    all_images = []
    slide_data = []
    
    print(f"Candidates found: {len(selected_candidates)}")
    print("Will stop after 9 successful slides.")
    
    for i, film in enumerate(selected_candidates):
        if len(slide_data) >= 9:
            print("🛑 Limit reached (9 items). Stopping.")
            break
            
        t_jp = film.get('clean_title_jp') or film.get('movie_title')
        print(f"[{i+1}/{len(selected_candidates)}] Processing: {t_jp}")
        
        img_path = film.get('tmdb_backdrop_path')
        img = download_image(img_path)
        
        if img:
            tag_jp, tag_en = generate_gemini_taglines(film)
            film['gen_tagline_jp'] = tag_jp
            film['gen_tagline_en'] = tag_en
            
            all_images.append(img)
            slide_data.append({"film": film, "img": img})
            print(f"  ✅ Added slide {len(slide_data)}/9")
        else:
            print(f"  ...Skipping {t_jp} (No image)")
            
    if all_images:
        d_str, day_str = get_bilingual_date()
        cover = draw_cover_slide(all_images, fonts, d_str, day_str)
        cover.save(BASE_DIR / "post_v2_image_00.png")
        print("✅ Saved cover slide.")
        
    caption_lines = [f"🗓️ {get_bilingual_date()[0]} Tokyo Cinema Selection\n"]
    
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
        
    with open(OUTPUT_CAPTION_PATH, 'w', encoding='utf-8') as f:
        f.write("\n".join(caption_lines))
        
    print("🎉 Done! Images and caption generated.")
