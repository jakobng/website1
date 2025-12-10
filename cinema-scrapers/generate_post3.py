"""
Generate Post 3: Cinema Mashup (V3) - Local Assets Edition.
- Concept: "Surreal Street Photography"
- Visuals: Cinema Facade (Local Asset) + Movie Characters (Mashup).
- Layout: Cover (Mashup) + Grid Slides (4 films per page).
- Tech: Local File Lookup + Replicate (RemBG) + Pillow (Compositing).
"""
import json
import os
import random
import requests
import textwrap
import math
import re
import difflib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps

# --- Reuse Core Logic from V2 ---
from generate_post2 import (
    get_fonts, get_faithful_colors, create_textured_bg, apply_film_grain,
    draw_centered_text, download_image, remove_background, create_sticker_style,
    JST, get_today_jst,
    CANVAS_WIDTH, CANVAS_HEIGHT, STORY_CANVAS_HEIGHT,
    OUTPUT_DIR, DATA_DIR, SHOWTIMES_PATH, HISTORY_PATH
)

# --- Config ---
CINEMA_ASSETS_DIR = Path(__file__).resolve().parent / "cinema_assets"
CINEMA_ASSETS_DIR.mkdir(exist_ok=True)
CINEMA_HISTORY_PATH = DATA_DIR / "cinema_history.json"
OUTPUT_CAPTION_PATH = OUTPUT_DIR / "post_v3_caption.txt"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# --- Gemini Setup ---
try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# --- Cinema Names Mapping (For File Lookup) ---
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

def load_json(path):
    if not path.exists(): return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def clean_display_title(title: str) -> str:
    """Removes noise (brackets, 4K, etc) from titles for cleaner display."""
    if not title: return ""
    title = re.sub(r'[\(（].*?[\)）]', '', title)
    title = re.sub(r'[\[【].*?[\]】]', '', title)
    noise = ["4K", "2K", "IMAX", "Dolby", "Atmos", "3D", "Restored", "Remastered", "Digital", "Director's Cut", "Final Cut", "劇場版", "完全版", "特集", "上映", "吹替", "字幕"]
    for word in noise:
        title = title.replace(word, "")
    return title.strip()

def normalize_name(s):
    s = str(s).lower()
    return re.sub(r'[^a-z0-9]', '', s)

def get_cinema_photo(cinema_name):
    """
    STRICTLY LOCAL LOOKUP.
    Tries to find a matching image in 'cinema_assets' using fuzzy matching.
    """
    if not CINEMA_ASSETS_DIR.exists():
        print(f"⚠️ Assets directory missing: {CINEMA_ASSETS_DIR}")
        return None

    # 1. Define Search Targets
    targets = [normalize_name(cinema_name)]
    
    # Add English name if available
    english_name = CINEMA_ENGLISH_NAMES.get(cinema_name)
    if english_name:
        targets.append(normalize_name(english_name))

    print(f"📂 Looking for asset matching: {targets}")

    # 2. Scan Directory
    candidates = list(CINEMA_ASSETS_DIR.glob("*"))
    best_match = None
    highest_ratio = 0.0
    
    for f in candidates:
        if f.suffix.lower() not in ['.jpg', '.jpeg', '.png', '.webp']: continue
        f_name = normalize_name(f.stem)
        
        # Exact substring match (high priority)
        for t in targets:
            if t in f_name or f_name in t:
                print(f"   ✅ Found match: {f.name}")
                return Image.open(f).convert("RGB")
        
        # Fuzzy match (fallback)
        for t in targets:
            ratio = difflib.SequenceMatcher(None, t, f_name).ratio()
            if ratio > highest_ratio:
                highest_ratio = ratio
                best_match = f

    # 3. Return Best Fuzzy Match if confident enough
    if highest_ratio > 0.4:
        print(f"   ✅ Fuzzy match ({highest_ratio:.2f}): {best_match.name}")
        return Image.open(best_match).convert("RGB")

    print(f"❌ No local asset found for {cinema_name}")
    return None

def analyze_lineup_vibe(cinema_name, films):
    """Gemini writes the caption intro."""
    print("🧠 Analyzing lineup vibe...")
    titles = [f['title'] for f in films]
    titles_text = ", ".join(titles[:15])
    
    if not GEMINI_AVAILABLE or not GEMINI_API_KEY:
        return f"Weekly Spotlight: {cinema_name}\nChecking out the lineup for this week!"

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""
    You are a Tokyo film critic.
    The cinema "{cinema_name}" is showing these films this week: {titles_text}.
    
    Write a SHORT, cool Instagram caption intro (2-3 sentences) analyzing this specific curation.
    Is it focused on a specific director? Is it horror heavy? Is it classic cinema?
    Capture the "vibe" of the theater this week.
    Start with "Weekly Spotlight: {cinema_name}".
    """
    try:
        resp = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return resp.text.strip()
    except:
        return f"Weekly Spotlight: {cinema_name}\nChecking out the lineup for this week!"

# --- MASHUP GENERATION ---

def create_mashup_cover(cinema_img, film_imgs, fonts, cinema_name, is_story=False):
    width = CANVAS_WIDTH
    height = STORY_CANVAS_HEIGHT if is_story else CANVAS_HEIGHT
    
    # 1. Background
    bg = ImageOps.fit(cinema_img, (width, height), method=Image.Resampling.LANCZOS)
    bg = ImageEnhance.Brightness(bg).enhance(0.7) # Darker for contrast
    
    # 2. Stickers
    stickers = []
    print(f"✂️  Processing {len(film_imgs)} film cutouts...")
    for img in film_imgs:
        cutout = remove_background(img)
        if cutout:
            sticker = create_sticker_style(cutout)
            stickers.append(sticker)
            
    random.shuffle(stickers)
    
    # Placement Zones (Bottom half focus)
    zones = [
        (int(width * 0.2), int(height * 0.7)),
        (int(width * 0.8), int(height * 0.7)),
        (int(width * 0.8), int(height * 0.45)),
        (int(width * 0.2), int(height * 0.45)),
    ]
    
    for i, sticker in enumerate(stickers[:4]): 
        scale = random.uniform(0.35, 0.6)
        ratio = sticker.width / sticker.height
        new_w = int(width * scale)
        new_h = int(new_w / ratio)
        s_resized = sticker.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        if i < len(zones):
            zx, zy = zones[i]
        else:
            zx, zy = width//2, height//2
            
        x = zx + random.randint(-80, 80) - (new_w // 2)
        y = zy + random.randint(-40, 40) - (new_h // 2)
        
        # Clamp
        x = max(-50, min(x, width - 50))
        y = max(50, min(y, height - 50))
        
        bg.paste(s_resized, (x, y), s_resized)

    # 3. Unify
    bg = apply_film_grain(bg)
    
    # 4. Text Overlay
    draw = ImageDraw.Draw(bg)
    draw_centered_text(draw, 120, "THIS WEEK AT", fonts['meta'], (255,255,255), width)
    
    wrapper = textwrap.TextWrapper(width=15)
    lines = wrapper.wrap(cinema_name.upper())
    y_text = 180
    for line in lines:
        y_text = draw_centered_text(draw, y_text, line, fonts['cover_main_jp'], (255,255,255), width)
        
    return bg

# --- GRID SLIDE GENERATION ---

def draw_grid_slide(films_batch, fonts, is_story=False):
    width = CANVAS_WIDTH
    height = STORY_CANVAS_HEIGHT if is_story else CANVAS_HEIGHT
    
    bg = Image.new("RGB", (width, height), (20, 20, 20))
    draw = ImageDraw.Draw(bg)
    
    margin = 40
    col_gap = 30
    row_gap = 60
    header_height = 100
    
    grid_w = width - (2 * margin)
    cell_w = (grid_w - col_gap) // 2
    
    cells = [
        (margin, header_height + margin), 
        (margin + cell_w + col_gap, header_height + margin), 
        (margin, header_height + margin + 550 + row_gap), 
        (margin + cell_w + col_gap, header_height + margin + 550 + row_gap)
    ]
    
    draw.text((margin, 50), "NOW SHOWING", font=fonts['title_en'], fill=(200,200,200))
    
    for i, film in enumerate(films_batch):
        if i >= 4: break
        
        x, y = cells[i]
        
        # 1. Poster
        poster_h = 500
        p_img = download_image(film['poster_path'])
        
        if p_img:
            p_resized = ImageOps.fit(p_img, (cell_w, poster_h), method=Image.Resampling.LANCZOS)
            bg.paste(p_resized, (x, y))
        else:
            draw.rectangle([x, y, x+cell_w, y+poster_h], fill=(40,40,40))
            
        # 2. Text Info
        text_y = y + poster_h + 20
        title = clean_display_title(film['title'])
        if len(title) > 12: title = title[:11] + "…"
        
        draw.text((x, text_y), title, font=fonts['cinema'], fill=(255,255,255))
        
        time_str = film['time']
        draw.text((x, text_y + 40), f"Start: {time_str}", font=fonts['meta'], fill=(180,180,180))

    return bg

# --- MAIN ---

def main():
    print("--- Starting V3 (Cinema Mashup - Local Assets) ---")
    
    raw_data = load_json(SHOWTIMES_PATH)
    history = load_json(CINEMA_HISTORY_PATH)
    
    if not raw_data:
        print("❌ showtimes.json is empty or missing.")
        return

    # 1. Filter Cinemas Active This Week
    today = get_today_jst().date()
    target_dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(5)]
    
    active_cinemas = defaultdict(list)
    for item in raw_data:
        if item.get('date_text') in target_dates:
            # We require a poster for at least some films to make the mashup work
            poster = item.get('tmdb_poster_path')
            active_cinemas[item['cinema_name']].append({
                "title": item['movie_title'],
                "poster_path": poster,
                "date": item['date_text'],
                "time": item['showtime']
            })

    if not active_cinemas:
        print("⚠️ No active cinemas found.")
        return

    candidates = [c for c in active_cinemas.keys() if c not in history.values()]
    if not candidates:
        print("All cinemas featured recently. Resetting history.")
        candidates = list(active_cinemas.keys())
        history = {}

    target_cinema = random.choice(candidates)
    print(f"🎯 Selected Cinema: {target_cinema}")
    
    # 2. Get Cinema Image (Local with Fallback)
    cinema_img = get_cinema_photo(target_cinema)
    
    # --- PLACEHOLDER FALLBACK ---
    if not cinema_img:
        print(f"⚠️ Missing asset for {target_cinema}. Generating placeholder.")
        cinema_img = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), (40, 40, 50))
        draw = ImageDraw.Draw(cinema_img)
        draw.text((100, 500), f"MISSING ASSET:\n{target_cinema}", fill=(255, 100, 100))
    # ----------------------------

    history[str(datetime.now().timestamp())] = target_cinema
    save_json(CINEMA_HISTORY_PATH, history)

    # 3. Get Film Assets
    unique_films_map = {f['title']: f for f in active_cinemas[target_cinema]}
    unique_films = list(unique_films_map.values())
    random.shuffle(unique_films)
    
    sticker_sources = []
    print("📥 Downloading poster assets...")
    for f in unique_films[:4]:
        if f['poster_path']:
            img = download_image(f['poster_path'])
            if img: sticker_sources.append(img)
            
    fonts = get_fonts()
    
    # 4. Generate Images
    print("🎨 Generating Mashup Cover...")
    cover = create_mashup_cover(cinema_img, sticker_sources, fonts, target_cinema, is_story=False)
    cover.save(OUTPUT_DIR / "post_v3_00.png")
    
    cover_story = create_mashup_cover(cinema_img, sticker_sources, fonts, target_cinema, is_story=True)
    cover_story.save(OUTPUT_DIR / "story_v3_00.png")
    
    print("🎞️  Generating Schedule Slides...")
    chunk_size = 4
    film_list = sorted(unique_films, key=lambda x: x['time'])
    chunks = [film_list[i:i + chunk_size] for i in range(0, len(film_list), chunk_size)]
    
    if not chunks:
        print("⚠️ No films found for grid. Skipping slides.")

    for i, batch in enumerate(chunks):
        if i >= 3: break 
        slide = draw_grid_slide(batch, fonts, is_story=False)
        slide.save(OUTPUT_DIR / f"post_v3_{i+1:02}.png")
        
        slide_story = ImageOps.pad(slide, (CANVAS_WIDTH, STORY_CANVAS_HEIGHT), color=(20,20,20))
        slide_story.save(OUTPUT_DIR / f"story_v3_{i+1:02}.png")

    # 5. Generate Caption
    try:
        vibe_text = analyze_lineup_vibe(target_cinema, film_list)
    except Exception as e:
        vibe_text = f"Weekly Spotlight: {target_cinema}"

    schedule_text = f"{vibe_text}\n\n📍 {target_cinema} Schedule Highlights:\n"
    for f in film_list[:10]:
        schedule_text += f"• {f['time']} {f['title']}\n"
    schedule_text += "\n#TokyoIndieCinema #MiniTheater"
    
    with open(OUTPUT_CAPTION_PATH, "w", encoding="utf-8") as f:
        f.write(schedule_text)
        
    print(f"✅ V3 Mashup Generated for {target_cinema}!")

if __name__ == "__main__":
    main()
