"""
Generate Post 3: Cinema Mashup (V3).
- Concept: "Surreal Street Photography"
- Visuals: Cinema Facade populated by characters from the films screening there.
- Layout: Cover (Mashup) + Grid Slides (4 films per page).
- Tech: Gemini Search (Cinema Img) + Replicate (RemBG) + Pillow (Compositing).
"""
import json
import os
import random
import requests
import textwrap
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps

# --- Reuse Core Logic from V2 ---
# We import these to ensure visual consistency
from generate_post2 import (
    get_fonts, get_faithful_colors, create_textured_bg, apply_film_grain,
    draw_centered_text, download_image, remove_background, create_sticker_style,
    JST, get_today_jst, clean_display_title,
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

# --- Helpers ---

def load_json(path):
    if not path.exists(): return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_cinema_photo(cinema_name):
    """
    Finds a photo of the cinema. Checks local cache first, then Gemini Search.
    """
    safe_name = "".join(x for x in cinema_name if x.isalnum())
    local_path = CINEMA_ASSETS_DIR / f"{safe_name}.jpg"
    
    # 1. Local Check
    if local_path.exists():
        print(f"📂 Found local image for {cinema_name}")
        return Image.open(local_path).convert("RGB")
    
    # 2. Gemini Search
    print(f"🌐 Searching web for photo of: {cinema_name}...")
    if not GEMINI_AVAILABLE: return None

    client = genai.Client(api_key=GEMINI_API_KEY)
    tool = types.Tool(google_search=types.GoogleSearch())
    
    prompt = f"""
    Find a high-quality, aesthetic photo of the exterior (facade) or interior of the movie theater "{cinema_name}" in Tokyo.
    Prioritize images that show the building clearly.
    Return ONLY a valid JSON object: {{ "image_url": "..." }}
    """
    
    try:
        resp = client.models.generate_content(
            model='gemini-2.5-flash', contents=prompt,
            config=types.GenerateContentConfig(tools=[tool], response_mime_type="application/json")
        )
        url = json.loads(resp.text).get("image_url")
        
        if url:
            print(f"⬇️  Downloading: {url}")
            headers = {'User-Agent': 'Mozilla/5.0'} 
            img_resp = requests.get(url, headers=headers, timeout=10)
            if img_resp.status_code == 200:
                img = Image.open(BytesIO(img_resp.content)).convert("RGB")
                img.save(local_path)
                return img
    except Exception as e:
        print(f"⚠️ Image Search Failed: {e}")
    
    return None

def analyze_lineup_vibe(cinema_name, films):
    """Gemini writes the caption intro."""
    print("🧠 Analyzing lineup vibe...")
    titles = [f['title'] for f in films]
    titles_text = ", ".join(titles[:15])
    
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
    """
    Composes Film Characters INTO the Cinema Scene.
    """
    width = CANVAS_WIDTH
    height = STORY_CANVAS_HEIGHT if is_story else CANVAS_HEIGHT
    
    # 1. Prepare Background (Cinema)
    # Resize to fill canvas
    bg = ImageOps.fit(cinema_img, (width, height), method=Image.Resampling.LANCZOS)
    
    # Darken slightly to make text/stickers pop
    bg = ImageEnhance.Brightness(bg).enhance(0.8)
    # Add blur to background to give depth of field effect? No, let's keep it sharp for the "venue" feel.
    
    # 2. Process Stickers (Film Characters)
    stickers = []
    print(f"✂️  Processing {len(film_imgs)} film cutouts...")
    for img in film_imgs:
        cutout = remove_background(img)
        if cutout:
            # Add a white border (Sticker style) to separate from complex background
            sticker = create_sticker_style(cutout)
            stickers.append(sticker)
            
    # 3. Place Stickers (Random "Crowd" Logic)
    # We want them at the bottom/mid, looking like they are hanging out.
    random.shuffle(stickers)
    
    # Define "Placement Zones" (Bottom Left, Bottom Right, Mid Right)
    # Avoiding the top center where the cinema sign usually is.
    zones = [
        (int(width * 0.2), int(height * 0.7)),
        (int(width * 0.8), int(height * 0.7)),
        (int(width * 0.8), int(height * 0.4)),
        (int(width * 0.2), int(height * 0.4)),
    ]
    
    for i, sticker in enumerate(stickers[:4]): # Max 4 stickers
        # Randomize Scale
        scale = random.uniform(0.35, 0.6)
        
        # Resize
        ratio = sticker.width / sticker.height
        new_w = int(width * scale)
        new_h = int(new_w / ratio)
        s_resized = sticker.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        # Pick Zone
        if i < len(zones):
            zx, zy = zones[i]
        else:
            zx, zy = width//2, height//2
            
        # Jitter
        x = zx + random.randint(-100, 100) - (new_w // 2)
        y = zy + random.randint(-50, 50) - (new_h // 2)
        
        # Clamp to canvas
        x = max(-50, min(x, width - 50))
        y = max(50, min(y, height - 50))
        
        bg.paste(s_resized, (x, y), s_resized)

    # 4. Unify (Film Grain)
    # This acts as the "Inpainting" glue to make them feel like they belong in the same photo
    bg = apply_film_grain(bg)
    
    # 5. Overlay Text
    draw = ImageDraw.Draw(bg)
    
    # "THIS WEEK AT"
    draw_centered_text(draw, 120, "THIS WEEK AT", fonts['meta'], (255,255,255), width)
    
    # Cinema Name (Big)
    wrapper = textwrap.TextWrapper(width=15)
    lines = wrapper.wrap(cinema_name.upper())
    y_text = 180
    for line in lines:
        y_text = draw_centered_text(draw, y_text, line, fonts['cover_main_jp'], (255,255,255), width)
        
    return bg

# --- GRID SLIDE GENERATION ---

def draw_grid_slide(films_batch, fonts, is_story=False):
    """
    Draws a 2x2 grid of films.
    """
    width = CANVAS_WIDTH
    height = STORY_CANVAS_HEIGHT if is_story else CANVAS_HEIGHT
    
    bg = Image.new("RGB", (width, height), (20, 20, 20))
    draw = ImageDraw.Draw(bg)
    
    # Grid config
    margin = 40
    col_gap = 30
    row_gap = 60
    header_height = 100
    
    # Available area
    grid_w = width - (2 * margin)
    cell_w = (grid_w - col_gap) // 2
    
    # 2x2 Layout
    cells = [
        (margin, header_height + margin), # Top Left
        (margin + cell_w + col_gap, header_height + margin), # Top Right
        (margin, header_height + margin + 550 + row_gap), # Bottom Left
        (margin + cell_w + col_gap, header_height + margin + 550 + row_gap) # Bottom Right
    ]
    
    # Header
    draw.text((margin, 50), "NOW SHOWING", font=fonts['title_en'], fill=(200,200,200))
    
    for i, film in enumerate(films_batch):
        if i >= 4: break
        
        x, y = cells[i]
        
        # 1. Poster
        poster_h = 500
        p_img = download_image(film['poster_path'])
        
        if p_img:
            # Crop/Fit poster to cell width
            p_ratio = p_img.width / p_img.height
            target_ratio = cell_w / poster_h
            
            p_resized = ImageOps.fit(p_img, (cell_w, poster_h), method=Image.Resampling.LANCZOS)
            bg.paste(p_resized, (x, y))
        else:
            # Fallback placeholder
            draw.rectangle([x, y, x+cell_w, y+poster_h], fill=(40,40,40))
            
        # 2. Text Info
        text_y = y + poster_h + 20
        
        # Title
        title = clean_display_title(film['title'])
        # Truncate if too long
        if len(title) > 12: title = title[:11] + "…"
        
        draw.text((x, text_y), title, font=fonts['cinema'], fill=(255,255,255))
        
        # Time
        time_str = film['time']
        draw.text((x, text_y + 40), f"Start: {time_str}", font=fonts['meta'], fill=(180,180,180))

    return bg

# --- MAIN ---

def main():
    print("--- Starting V3 (Cinema Mashup) ---")
    
    # 1. Load Data
    raw_data = load_json(SHOWTIMES_PATH)
    history = load_json(CINEMA_HISTORY_PATH)
    
    # 2. Pick Cinema (Round Robin)
    today = get_today_jst().date()
    # Look at next 5 days
    target_dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(5)]
    
    active_cinemas = defaultdict(list)
    for item in raw_data:
        if item.get('date_text') in target_dates:
            if item.get('tmdb_poster_path'):
                active_cinemas[item['cinema_name']].append({
                    "title": item['movie_title'],
                    "poster_path": item['tmdb_poster_path'],
                    "date": item['date_text'],
                    "time": item['showtime']
                })

    # Filter candidates
    candidates = [c for c in active_cinemas.keys() if c not in history.values()]
    if not candidates:
        print("All cinemas featured recently. Resetting history.")
        candidates = list(active_cinemas.keys())
        history = {}

    target_cinema = random.choice(candidates)
    print(f"🎯 Selected Cinema: {target_cinema}")
    
    # Update history
    history[str(datetime.now().timestamp())] = target_cinema
    save_json(CINEMA_HISTORY_PATH, history)
    
    # 3. Get Assets
    cinema_img = get_cinema_photo(target_cinema)
    if not cinema_img:
        print("❌ Could not find cinema image. Aborting.")
        return

    # Gather films for stickers (Top 4 unique films)
    unique_films_map = {f['title']: f for f in active_cinemas[target_cinema]}
    unique_films = list(unique_films_map.values())
    random.shuffle(unique_films)
    
    sticker_sources = []
    print("📥 Downloading poster assets for mashup...")
    for f in unique_films[:4]:
        img = download_image(f['poster_path'])
        if img: sticker_sources.append(img)
        
    fonts = get_fonts()
    
    # 4. Generate Cover (Mashup)
    print("🎨 Generating Mashup Cover...")
    cover = create_mashup_cover(cinema_img, sticker_sources, fonts, target_cinema, is_story=False)
    cover.save(OUTPUT_DIR / "post_v3_00.png")
    
    cover_story = create_mashup_cover(cinema_img, sticker_sources, fonts, target_cinema, is_story=True)
    cover_story.save(OUTPUT_DIR / "story_v3_00.png")
    
    # 5. Generate Grid Slides
    print("🎞️  Generating Schedule Slides...")
    # Group films into chunks of 4
    chunk_size = 4
    film_list = sorted(unique_films, key=lambda x: x['time'])
    chunks = [film_list[i:i + chunk_size] for i in range(0, len(film_list), chunk_size)]
    
    for i, batch in enumerate(chunks):
        # Stop after 3 schedule slides (12 films max) to avoid spam
        if i >= 3: break 
        slide = draw_grid_slide(batch, fonts, is_story=False)
        slide.save(OUTPUT_DIR / f"post_v3_{i+1:02}.png")
        
        # Story version? (Re-use same layout or adapt)
        # For simplicity, we stick to Feed slides for schedule, or adapt logic if needed.
        # Let's save the same slide for story for now, maybe padded.
        slide_story = ImageOps.pad(slide, (CANVAS_WIDTH, STORY_CANVAS_HEIGHT), color=(20,20,20))
        slide_story.save(OUTPUT_DIR / f"story_v3_{i+1:02}.png")

    # 6. Generate Caption
    vibe_text = analyze_lineup_vibe(target_cinema, film_list)
    
    schedule_text = f"{vibe_text}\n\n📍 {target_cinema} Schedule Highlights:\n"
    
    # Simple list for caption
    for f in film_list[:10]:
        schedule_text += f"• {f['time']} {f['title']}\n"
            
    schedule_text += "\n#TokyoIndieCinema #MiniTheater"
    
    with open(OUTPUT_CAPTION_PATH, "w", encoding="utf-8") as f:
        f.write(schedule_text)
        
    print(f"✅ V3 Mashup Generated for {target_cinema}!")

if __name__ == "__main__":
    main()
