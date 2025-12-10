"""
Generate Post 3: The "Creative Director" Engine (Cinema Spotlight).
- Logic: Round-Robin Cinema Selection -> AI "Creative Director" -> Asset Fetching -> Composition.
- Features: 
    - Cinema History Tracking (ensures rotation).
    - Search Grounding for Context & Backup Images.
    - Replicate (RemBG) for depth effects.
    - "Pop-out" poster composition.
"""

import os
import json
import random
import requests
import textwrap
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import List, Dict, Any, Optional
from io import BytesIO

# --- LIBRARIES ---
try:
    from google import genai
    from google.genai import types
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageEnhance
    import replicate
except ImportError as e:
    print(f"⚠️ Missing dependencies: {e}")
    print("pip install google-genai replicate requests Pillow tzdata")
    exit(1)

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "ig_posts"
CINEMA_ASSETS_DIR = BASE_DIR / "cinema_assets"
FONTS_DIR = BASE_DIR / "fonts"

# FILES
SHOWTIMES_PATH = DATA_DIR / "showtimes.json"
CINEMA_HISTORY_PATH = DATA_DIR / "cinema_history.json" # Tracks which CINEMA was last featured

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CINEMA_ASSETS_DIR.mkdir(parents=True, exist_ok=True)

JST = ZoneInfo("Asia/Tokyo")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")

# --- 1. SELECTION ENGINE (ROUND ROBIN FOR CINEMAS) ---

def load_cinema_history():
    if CINEMA_HISTORY_PATH.exists():
        with open(CINEMA_HISTORY_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_cinema_history(history):
    with open(CINEMA_HISTORY_PATH, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def select_target_cinema(todays_showtimes: List[Dict]) -> str:
    """
    Selects a cinema that hasn't been featured recently.
    """
    history = load_cinema_history()
    
    # 1. Get all cinemas active today
    active_cinemas = list(set(f['cinema_name'] for f in todays_showtimes))
    
    if not active_cinemas:
        return None

    # 2. Sort by last featured date (None/'0000' = never featured)
    def get_last_date(name):
        return history.get(name, "0000-00-00")

    # Sort: Oldest date first (Ascending)
    active_cinemas.sort(key=get_last_date)
    
    target = active_cinemas[0]
    last_date = history.get(target, "Never")
    
    print(f"🎯 Selection Logic: Found {len(active_cinemas)} active cinemas.")
    print(f"   Selected: {target} (Last Featured: {last_date})")
    
    # Update History IMMEDIATELY
    history[target] = datetime.now(JST).strftime("%Y-%m-%d")
    save_cinema_history(history)
    
    return target

# --- 2. THE CREATIVE DIRECTOR (GEMINI AGENT) ---

class CreativeDirector:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.5-flash" 

    def create_editorial_plan(self, cinema_name: str, films: List[Dict]) -> Dict:
        """
        Analyzes the cinema's lineup and generates a bespoke slide plan.
        """
        print(f"🧠 Creative Director is analyzing {cinema_name}...")
        
        # 1. Summarize Assets for the AI
        film_inventory = []
        for f in films:
            film_inventory.append({
                "title": f.get('movie_title'),
                "has_poster": bool(f.get('tmdb_poster_path')),
                "director": f.get('director'),
                "showtime": f.get('showtime')
            })
            
        # 2. The Prompt
        prompt = f"""
        You are the Creative Director for a Tokyo cinema Instagram account.
        Today's Focus: {cinema_name}
        Lineup:
        {json.dumps(film_inventory, indent=2, ensure_ascii=False)}

        YOUR TASK:
        1. Analyze the lineup. Detect a theme (e.g. "French New Wave", "Mads Mikkelsen Season", "Indie Mix").
        2. Create a JSON SLIDE PLAN (Max 6 slides).
        3. Decide visual style (fonts, colors).

        CRITICAL RULES FOR IMAGES:
        - If 'has_poster' is TRUE: You can use 'POPOUT_SPOTLIGHT' or 'HERO_PORTAL'.
        - If 'has_poster' is FALSE: You MUST use 'TYPOGRAPHIC_QUOTE' (Text only) OR provide a 'search_query' for Gemini to find an image.
        - Do not plan 6 posters in a row. Mix it up.

        AVAILABLE SLIDE TYPES:
        - "HERO_PORTAL": Cover slide. Blends cinema photo + film image.
        - "POPOUT_SPOTLIGHT": Character cutout over text. Needs high-res image.
        - "TYPOGRAPHIC_QUOTE": Big text, review, or tagline. No image needed. 
        - "TIMELINE_STRIP": Visual schedule. Good for the last slide.

        OUTPUT JSON ONLY:
        {{
            "editorial_title": "Catchy Headline (e.g. 'MIDNIGHT IN SHINJUKU')",
            "visual_vibe": "Description of colors/fonts",
            "accent_color": "#HEXCODE",
            "slides": [
                {{ "type": "HERO_PORTAL", "film_focus": "Film A" }},
                {{ "type": "TYPOGRAPHIC_QUOTE", "film_focus": "Film B", "search_query": "search query to find a review for Film B" }},
                {{ "type": "TIMELINE_STRIP" }}
            ]
        }}
        """

        grounding = types.Tool(google_search=types.GoogleSearch())
        
        try:
            resp = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[grounding],
                    response_mime_type="application/json",
                    temperature=0.5
                )
            )
            return json.loads(resp.text)
        except Exception as e:
            print(f"❌ Director Error: {e}")
            return {
                "editorial_title": f"Today at {cinema_name}",
                "accent_color": "#FFFF00",
                "slides": [{"type": "TIMELINE_STRIP"}]
            }

    def get_film_quote(self, film_title: str) -> str:
        # Fetch text content if we have no images
        try:
            prompt = f"Write a short, punchy, 1-sentence tagline or find a famous short review quote for the movie '{film_title}'. Return JUST the text."
            # We don't necessarily need search for a tagline, but it helps for reviews
            grounding = types.Tool(google_search=types.GoogleSearch())
            resp = self.client.models.generate_content(
                model=self.model, 
                contents=prompt,
                config=types.GenerateContentConfig(tools=[grounding])
            )
            return resp.text.strip().replace('"', '')
        except:
            return film_title.upper()

# --- 3. ASSET & RENDER UTILS ---

def download_asset(url: str) -> Optional[Image.Image]:
    if not url: return None
    try:
        resp = requests.get(url, timeout=10)
        img = Image.open(BytesIO(resp.content)).convert("RGBA")
        return img
    except:
        return None

def remove_bg(image: Image.Image) -> Image.Image:
    """Uses Replicate's RemBG to get a cutout."""
    if not REPLICATE_API_TOKEN: 
        print("   ⚠️ No Replicate Token. Skipping Cutout.")
        return image
    try:
        buf = BytesIO()
        image.save(buf, format="PNG")
        buf.seek(0)
        output = replicate.run(
            "cjwbw/rembg:fb8af171cfa1616ddcf1242c093f9c46bcada5ad4cf6f2fbe8b81b330ec5c003",
            input={"image": buf}
        )
        return download_asset(output)
    except Exception as e:
        print(f"   ⚠️ RemBG Failed: {e}")
        return image

def get_cinema_bg(cinema_name: str) -> Image.Image:
    safe_name = cinema_name.replace(" ", "_").lower()
    matches = list(CINEMA_ASSETS_DIR.glob(f"*{safe_name}*"))
    if not matches:
        matches = list(CINEMA_ASSETS_DIR.glob("*.jpg")) # Fallback to any cinema photo
    
    if matches:
        return Image.open(matches[0]).convert("RGBA")
    return Image.new("RGBA", (1080, 1350), (30,30,30))

def load_fonts(d: Path):
    def _load(name, size):
        p = d / name
        return ImageFont.truetype(str(p), size) if p.exists() else ImageFont.load_default()
    
    return {
        "h1": _load("Manrope-Bold.ttf", 110),
        "h2": _load("Manrope-Bold.ttf", 70),
        "body": _load("Manrope-Regular.ttf", 45),
        "big_quote": _load("Manrope-Bold.ttf", 85)
    }

# --- 4. RENDERER (The Compositor) ---

class Compositor:
    def __init__(self):
        self.W, self.H = 1080, 1350
        self.fonts = load_fonts(FONTS_DIR)

    def draw_hero(self, cinema_img, film_img, title, accent):
        canvas = ImageOps.fit(cinema_img, (self.W, self.H))
        
        # Darken Cinema Background
        overlay = Image.new("RGBA", (self.W, self.H), (0,0,0,140))
        canvas = Image.alpha_composite(canvas, overlay)
        
        # Blend Film Image (Dreamy Portal Effect)
        if film_img:
            # Resize film to width, but fade it out
            film_layer = ImageOps.fit(film_img, (self.W, int(self.H * 0.6)))
            
            # Create Gradient Mask
            mask = Image.new("L", (self.W, int(self.H * 0.6)), 0)
            draw = ImageDraw.Draw(mask)
            for y in range(int(self.H * 0.6)):
                # Fade from opaque (255) to transparent (0)
                alpha = int(255 * (1 - (y / (self.H * 0.6))**0.5)) 
                draw.line([(0,y), (self.W,y)], fill=alpha)
            
            # Composite
            canvas.paste(film_layer, (0, 100), mask)

        draw = ImageDraw.Draw(canvas)
        
        # Big Typography
        margin = 60
        draw.text((margin, 850), title.upper(), font=self.fonts['h1'], fill=accent)
        draw.text((margin, 980), datetime.now(JST).strftime("%B %d, %Y"), font=self.fonts['h2'], fill="white")
        
        return canvas

    def draw_popout(self, film_data, accent):
        # 1. Background (Blurred Poster)
        poster_url = f"https://image.tmdb.org/t/p/original{film_data['tmdb_poster_path']}"
        poster = download_asset(poster_url)
        
        if not poster: 
            return Image.new("RGB", (self.W, self.H), "black")
        
        bg = poster.copy()
        bg = ImageOps.fit(bg, (self.W, self.H))
        bg = bg.filter(ImageFilter.GaussianBlur(30)) # Heavy Blur
        bg = ImageEnhance.Brightness(bg).enhance(0.4) # Darken
        
        # 2. Big Text (Behind the subject)
        draw = ImageDraw.Draw(bg)
        title = film_data.get('clean_title_jp', film_data['movie_title'])
        
        # Font Scaling
        font_size = 130
        if len(title) > 8: font_size = 100
        if len(title) > 15: font_size = 70
        t_font = self.fonts['h1'].font_variant(size=font_size)

        # Draw Text Centered
        bbox = draw.textbbox((0,0), title, font=t_font)
        tx_w = bbox[2] - bbox[0]
        draw.text( ((self.W - tx_w)//2, 300), title, font=t_font, fill="white" )

        # 3. The Cutout (Foreground)
        print(f"   ✂️  Generating Pop-out for: {title}")
        cutout = remove_bg(poster)
        cutout = ImageOps.contain(cutout, (int(self.W*0.95), int(self.H*0.75)))
        
        # Place at bottom center
        bg.paste(cutout, ((self.W - cutout.width)//2, self.H - cutout.height), cutout)
        
        # 4. Info Badge
        draw.rectangle([(0, self.H-120), (self.W, self.H)], fill=accent)
        info = f"{film_data['showtime']} • {film_data.get('director','')}"
        draw.text((50, self.H-90), info, font=self.fonts['body'], fill="black")
        
        return bg

    def draw_quote(self, text, film_title, accent):
        # Swiss Design / Editorial Style
        img = Image.new("RGB", (self.W, self.H), "#1a1a1a")
        draw = ImageDraw.Draw(img)
        
        # Big Quotation Mark
        draw.text((40, 100), "“", font=self.fonts['h1'].font_variant(size=300), fill=accent)
        
        # Wrapped Text
        lines = textwrap.wrap(text, width=14)
        y = 400
        for line in lines:
            draw.text((60, y), line.upper(), font=self.fonts['big_quote'], fill="white")
            y += 100
            
        # Attribution
        draw.rectangle([(60, y+50), (160, y+60)], fill=accent) # Decorative line
        draw.text((60, y+80), film_title, font=self.fonts['h2'], fill="gray")
        
        return img

    def draw_timeline(self, films, accent):
        img = Image.new("RGB", (self.W, self.H), "#F8F7F2")
        draw = ImageDraw.Draw(img)
        
        draw.text((50, 60), "TODAY'S SCHEDULE", font=self.fonts['h2'], fill="black")
        
        # Simple Gantt-chart style blocks
        y = 250
        for f in films[:7]: # Limit to fit
            t_str = f['showtime']
            title = f.get('clean_title_jp', f['movie_title'])
            
            # Time Box
            draw.rectangle([(50, y), (230, y+80)], fill="black")
            draw.text((75, y+20), t_str, font=self.fonts['body'], fill=accent)
            
            # Title Line
            draw.text((260, y+20), title, font=self.fonts['body'], fill="black")
            
            # Divider
            draw.line([(260, y+90), (900, y+90)], fill="#ddd", width=2)
            y += 130
            
        return img

# --- MAIN WORKFLOW ---

def main():
    print("🎬 Starting CinemaScraper Creative Engine v3.1")
    
    # 1. Load Data
    if not SHOWTIMES_PATH.exists():
        print("❌ No showtimes.json found.")
        return

    with open(SHOWTIMES_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Filter Today
    today_str = datetime.now(JST).strftime("%Y-%m-%d")
    todays_data = [x for x in data if x.get('date_text') == today_str]
    
    if not todays_data:
        print(f"❌ No showtimes found for today ({today_str}).")
        return

    # 2. Select Cinema (Round Robin)
    target_cinema = select_target_cinema(todays_data)
    if not target_cinema:
        print("❌ Could not select a target cinema.")
        return

    cinema_films = [x for x in todays_data if x['cinema_name'] == target_cinema]
    print(f"📍 Target Locked: {target_cinema} ({len(cinema_films)} films)")

    # 3. AI Creative Direction
    director = CreativeDirector(GEMINI_API_KEY)
    plan = director.create_editorial_plan(target_cinema, cinema_films)
    
    print(f"\n🎨 Plan: {plan.get('editorial_title')}")
    print(f"🎨 Vibe: {plan.get('visual_vibe')}")
    
    # 4. Production (Rendering)
    compositor = Compositor()
    accent = plan.get('accent_color', '#FDB813')
    
    slide_count = 0
    caption_text = f"🎞️ {plan.get('editorial_title')}\n📍 {target_cinema}\n\n"
    
    for i, slide in enumerate(plan.get('slides', [])):
        print(f"   🔨 Rendering Slide {i+1}: {slide['type']}")
        img = None
        
        try:
            # --- HERO PORTAL ---
            if slide['type'] == 'HERO_PORTAL':
                cinema_img = get_cinema_bg(target_cinema)
                # Find film
                fname = slide.get('film_focus')
                fdata = next((x for x in cinema_films if x['movie_title'] == fname), cinema_films[0])
                
                poster_url = None
                if fdata.get('tmdb_poster_path'):
                     poster_url = f"https://image.tmdb.org/t/p/w780{fdata['tmdb_poster_path']}"
                
                poster = download_asset(poster_url)
                img = compositor.draw_hero(cinema_img, poster, plan.get('editorial_title'), accent)
                
            # --- POPOUT SPOTLIGHT ---
            elif slide['type'] == 'POPOUT_SPOTLIGHT':
                fname = slide.get('film_focus') or slide.get('film')
                fdata = next((x for x in cinema_films if x['movie_title'] == fname), None)
                
                if fdata and fdata.get('tmdb_poster_path'):
                    img = compositor.draw_popout(fdata, accent)
                    caption_text += f"► {fname}\n"
                else:
                    print("     ⚠️ Missing poster for popout. Switching to Quote.")
                    # Fallback to Quote if logic fails
                    slide['type'] = 'TYPOGRAPHIC_QUOTE' 
                    # ...continue to next elif block effectively (in real recursion, but here we just flow down if we restructured, 
                    # for now let's just create the quote manually here to save the slide)
                    text = director.get_film_quote(fname)
                    img = compositor.draw_quote(text, fname, accent)
                
            # --- TIMELINE ---
            elif slide['type'] == 'TIMELINE_STRIP':
                img = compositor.draw_timeline(cinema_films, accent)
                
            # --- TYPOGRAPHIC QUOTE (Fallback or Choice) ---
            elif slide['type'] == 'TYPOGRAPHIC_QUOTE':
                fname = slide.get('film_focus')
                text = director.get_film_quote(fname)
                img = compositor.draw_quote(text, fname, accent)

            # SAVE
            if img:
                filename = f"post_v3_{i:02}.png"
                img.save(OUTPUT_DIR / filename)
                
                # Story Version (Simple Center)
                story_bg = Image.new("RGB", (1080, 1920), "#111")
                story_bg.paste(img, (0, (1920-1350)//2))
                story_bg.save(OUTPUT_DIR / f"story_v3_{i:02}.png")
                
                slide_count += 1
                
        except Exception as e:
            print(f"   ❌ Slide Failed: {e}")

    # 5. Write Caption
    with open(OUTPUT_DIR / "post_v3_caption.txt", "w", encoding='utf-8') as f:
        f.write(caption_text + "\n#TokyoCinema #FilmLife")

    print(f"\n✅ Done. {slide_count} slides generated.")

if __name__ == "__main__":
    main()
