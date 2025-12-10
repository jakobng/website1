"""
Generate Post 3: The "Creative Director" Engine (Cinema Spotlight).
v3.3 DEBUG EDITION
- Features: Verbose Logging, JSON Inspection, Asset Health Checks.
"""

import os
import json
import random
import requests
import textwrap
import time
import re
import traceback
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
    print(f"🛑 CRITICAL: Missing dependencies: {e}")
    print("Run: pip install google-genai replicate requests Pillow tzdata")
    exit(1)

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "ig_posts"
CINEMA_ASSETS_DIR = BASE_DIR / "cinema_assets"
FONTS_DIR = BASE_DIR / "fonts"

# FILES
SHOWTIMES_PATH = DATA_DIR / "showtimes.json"
CINEMA_HISTORY_PATH = DATA_DIR / "cinema_history.json"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CINEMA_ASSETS_DIR.mkdir(parents=True, exist_ok=True)

JST = ZoneInfo("Asia/Tokyo")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")

# --- LOGGER UTILS ---
def log(msg, level="INFO"):
    icons = {"INFO": "🔵", "WARN": "⚠️ ", "ERROR": "🛑", "AI": "🧠", "SUCCESS": "✅"}
    icon = icons.get(level, "🔹")
    print(f"{icon} [{level}] {msg}")

def check_environment():
    log("Checking Environment...", "INFO")
    if not GEMINI_API_KEY:
        log("GEMINI_API_KEY is missing!", "ERROR")
    else:
        log("GEMINI_API_KEY found.", "SUCCESS")
        
    if not REPLICATE_API_TOKEN:
        log("REPLICATE_API_TOKEN is missing. Background removal will be skipped.", "WARN")
    else:
        log("REPLICATE_API_TOKEN found.", "SUCCESS")

    if not SHOWTIMES_PATH.exists():
        log(f"showtimes.json not found at {SHOWTIMES_PATH}", "ERROR")

# --- 1. SELECTION ENGINE ---

def load_cinema_history():
    if CINEMA_HISTORY_PATH.exists():
        with open(CINEMA_HISTORY_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_cinema_history(history):
    with open(CINEMA_HISTORY_PATH, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def select_target_cinema(todays_showtimes: List[Dict]) -> str:
    log("Selecting Cinema Candidate...", "INFO")
    history = load_cinema_history()
    
    # Get active cinemas
    active_cinemas = list(set(f['cinema_name'] for f in todays_showtimes))
    log(f"Found {len(active_cinemas)} cinemas with shows today.", "INFO")
    
    if not active_cinemas:
        return None

    # Sort by last featured date
    def get_last_date(name):
        return history.get(name, "0000-00-00")

    active_cinemas.sort(key=get_last_date)
    
    target = active_cinemas[0]
    last_date = history.get(target, "Never")
    
    log(f"Selected Target: {target} (Last Featured: {last_date})", "SUCCESS")
    
    # Update History
    history[target] = datetime.now(JST).strftime("%Y-%m-%d")
    save_cinema_history(history)
    
    return target

# --- 2. THE CREATIVE DIRECTOR ---

class CreativeDirector:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.5-flash" 

    def _clean_json_text(self, text: str) -> str:
        # Regex to find JSON block
        pattern = r"```(?:json)?\s*(.*?)\s*```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1)
        return text.strip()

    def create_editorial_plan(self, cinema_name: str, films: List[Dict]) -> Dict:
        log(f"Asking Gemini to direct content for {cinema_name}...", "AI")
        
        film_inventory = []
        for f in films:
            film_inventory.append({
                "title": f.get('movie_title'),
                "has_poster": bool(f.get('tmdb_poster_path')),
                "director": f.get('director'),
                "showtime": f.get('showtime')
            })
            
        prompt = f"""
        You are the Creative Director for a Tokyo cinema Instagram.
        Today's Focus: {cinema_name}
        Lineup:
        {json.dumps(film_inventory, indent=2, ensure_ascii=False)}

        Analyze the lineup (Theme? Vibe?).
        Create a JSON SLIDE PLAN (Max 6 slides).
        
        RULES:
        - If 'has_poster' is TRUE: Use 'POPOUT_SPOTLIGHT' or 'HERO_PORTAL'.
        - If 'has_poster' is FALSE: Use 'TYPOGRAPHIC_QUOTE' (Text only) or 'TIMELINE_STRIP'.
        
        OUTPUT JSON ONLY:
        {{
            "editorial_title": "Headline",
            "visual_vibe": "Colors/Fonts description",
            "accent_color": "#HEXCODE",
            "slides": [
                {{ "type": "HERO_PORTAL", "film_focus": "Film A" }},
                {{ "type": "TYPOGRAPHIC_QUOTE", "film_focus": "Film B", "search_query": "search query" }},
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
                    temperature=0.5
                )
            )
            
            # --- DEBUG LOGGING ---
            # Save raw text to file in case of crash
            with open(OUTPUT_DIR / "last_gemini_raw_response.txt", "w", encoding="utf-8") as f:
                f.write(resp.text)
            
            clean_text = self._clean_json_text(resp.text)
            plan = json.loads(clean_text)
            log("Director's Plan acquired successfully.", "SUCCESS")
            return plan

        except json.JSONDecodeError as e:
            log(f"JSON Parse Error: {e}", "ERROR")
            log(f"RAW TEXT RECEIVED:\n{resp.text[:500]}...", "WARN") # Print first 500 chars
            return self._fallback_plan(cinema_name)
            
        except Exception as e:
            log(f"Gemini API Error: {e}", "ERROR")
            return self._fallback_plan(cinema_name)

    def _fallback_plan(self, cinema_name):
        return {
            "editorial_title": f"Today at {cinema_name}",
            "accent_color": "#FFFF00",
            "slides": [{"type": "TIMELINE_STRIP"}]
        }

    def get_film_quote(self, film_title: str) -> str:
        try:
            prompt = f"Write a short 1-sentence tagline for '{film_title}'."
            resp = self.client.models.generate_content(model=self.model, contents=prompt)
            return resp.text.strip().replace('"', '')
        except:
            return film_title.upper()

# --- 3. ASSET UTILS ---

def download_asset(url: str) -> Optional[Image.Image]:
    if not url: return None
    try:
        log(f"Downloading: {url[:50]}...", "INFO")
        resp = requests.get(url, timeout=10)
        img = Image.open(BytesIO(resp.content)).convert("RGBA")
        log(f"   -> Image loaded: {img.size}", "SUCCESS")
        return img
    except Exception as e:
        log(f"   -> Download failed: {e}", "WARN")
        return None

def remove_bg(image: Image.Image) -> Image.Image:
    if not REPLICATE_API_TOKEN: return image
    try:
        log("Sending to Replicate (RemBG)...", "AI")
        buf = BytesIO()
        image.save(buf, format="PNG")
        buf.seek(0)
        output = replicate.run(
            "cjwbw/rembg:fb8af171cfa1616ddcf1242c093f9c46bcada5ad4cf6f2fbe8b81b330ec5c003",
            input={"image": buf}
        )
        return download_asset(output)
    except Exception as e:
        log(f"Replicate failed: {e}", "ERROR")
        return image

def get_cinema_bg(cinema_name: str) -> Image.Image:
    safe_name = cinema_name.replace(" ", "_").lower()
    matches = list(CINEMA_ASSETS_DIR.glob(f"*{safe_name}*"))
    
    if matches:
        log(f"Found local cinema photo: {matches[0].name}", "SUCCESS")
        return Image.open(matches[0]).convert("RGBA")
    
    log(f"No photo for {cinema_name}. Using generic fallback.", "WARN")
    return Image.new("RGBA", (1080, 1350), (30,30,30))

def load_fonts(d: Path):
    log("Loading Fonts...", "INFO")
    def _load(name, size):
        p = d / name
        if p.exists():
            return ImageFont.truetype(str(p), size)
        else:
            log(f"   -> Missing {name}, using default.", "WARN")
            return ImageFont.load_default()
    
    return {
        "h1": _load("Manrope-Bold.ttf", 110),
        "h2": _load("Manrope-Bold.ttf", 70),
        "body": _load("Manrope-Regular.ttf", 45),
        "big_quote": _load("Manrope-Bold.ttf", 85)
    }

# --- 4. RENDERER ---

class Compositor:
    def __init__(self):
        self.W, self.H = 1080, 1350
        self.fonts = load_fonts(FONTS_DIR)

    def draw_hero(self, cinema_img, film_img, title, accent):
        canvas = ImageOps.fit(cinema_img, (self.W, self.H))
        overlay = Image.new("RGBA", (self.W, self.H), (0,0,0,140))
        canvas = Image.alpha_composite(canvas, overlay)
        
        if film_img:
            film_layer = ImageOps.fit(film_img, (self.W, int(self.H * 0.6)))
            mask = Image.new("L", (self.W, int(self.H * 0.6)), 0)
            draw = ImageDraw.Draw(mask)
            for y in range(int(self.H * 0.6)):
                alpha = int(255 * (1 - (y / (self.H * 0.6))**0.5)) 
                draw.line([(0,y), (self.W,y)], fill=alpha)
            canvas.paste(film_layer, (0, 100), mask)

        draw = ImageDraw.Draw(canvas)
        margin = 60
        draw.text((margin, 850), title.upper(), font=self.fonts['h1'], fill=accent)
        draw.text((margin, 980), datetime.now(JST).strftime("%B %d, %Y"), font=self.fonts['h2'], fill="white")
        return canvas

    def draw_popout(self, film_data, accent):
        poster_url = f"https://image.tmdb.org/t/p/original{film_data['tmdb_poster_path']}"
        poster = download_asset(poster_url)
        
        if not poster: 
            return Image.new("RGB", (self.W, self.H), "black")
        
        bg = poster.copy()
        bg = ImageOps.fit(bg, (self.W, self.H))
        bg = bg.filter(ImageFilter.GaussianBlur(30))
        bg = ImageEnhance.Brightness(bg).enhance(0.4)
        
        draw = ImageDraw.Draw(bg)
        title = film_data.get('clean_title_jp', film_data['movie_title'])
        
        font_size = 130
        if len(title) > 8: font_size = 100
        if len(title) > 15: font_size = 70
        t_font = self.fonts['h1'].font_variant(size=font_size)

        bbox = draw.textbbox((0,0), title, font=t_font)
        tx_w = bbox[2] - bbox[0]
        draw.text( ((self.W - tx_w)//2, 300), title, font=t_font, fill="white" )

        cutout = remove_bg(poster)
        cutout = ImageOps.contain(cutout, (int(self.W*0.95), int(self.H*0.75)))
        bg.paste(cutout, ((self.W - cutout.width)//2, self.H - cutout.height), cutout)
        
        draw.rectangle([(0, self.H-120), (self.W, self.H)], fill=accent)
        info = f"{film_data['showtime']} • {film_data.get('director','')}"
        draw.text((50, self.H-90), info, font=self.fonts['body'], fill="black")
        return bg

    def draw_quote(self, text, film_title, accent):
        img = Image.new("RGB", (self.W, self.H), "#1a1a1a")
        draw = ImageDraw.Draw(img)
        draw.text((40, 100), "“", font=self.fonts['h1'].font_variant(size=300), fill=accent)
        
        lines = textwrap.wrap(text, width=14)
        y = 400
        for line in lines:
            draw.text((60, y), line.upper(), font=self.fonts['big_quote'], fill="white")
            y += 100
            
        draw.rectangle([(60, y+50), (160, y+60)], fill=accent)
        draw.text((60, y+80), film_title, font=self.fonts['h2'], fill="gray")
        return img

    def draw_timeline(self, films, accent):
        img = Image.new("RGB", (self.W, self.H), "#F8F7F2")
        draw = ImageDraw.Draw(img)
        draw.text((50, 60), "TODAY'S SCHEDULE", font=self.fonts['h2'], fill="black")
        
        y = 250
        for f in films[:7]:
            t_str = f['showtime']
            title = f.get('clean_title_jp', f['movie_title'])
            draw.rectangle([(50, y), (230, y+80)], fill="black")
            draw.text((75, y+20), t_str, font=self.fonts['body'], fill=accent)
            draw.text((260, y+20), title, font=self.fonts['body'], fill="black")
            draw.line([(260, y+90), (900, y+90)], fill="#ddd", width=2)
            y += 130
        return img

# --- MAIN WORKFLOW ---

def main():
    print("\n🎬 --- CINEMA SCRAPER V3.3 START ---")
    check_environment()
    
    # 1. Load Data
    with open(SHOWTIMES_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    today_str = datetime.now(JST).strftime("%Y-%m-%d")
    todays_data = [x for x in data if x.get('date_text') == today_str]
    log(f"Date: {today_str} | Shows found: {len(todays_data)}", "INFO")
    
    if not todays_data:
        log("No showtimes for today. Exiting.", "WARN")
        return

    # 2. Select Cinema
    target_cinema = select_target_cinema(todays_data)
    if not target_cinema:
        log("Selection logic returned None.", "ERROR")
        return

    cinema_films = [x for x in todays_data if x['cinema_name'] == target_cinema]
    log(f"Locked Target: {target_cinema} ({len(cinema_films)} films)", "SUCCESS")

    # 3. AI Planning
    director = CreativeDirector(GEMINI_API_KEY)
    plan = director.create_editorial_plan(target_cinema, cinema_films)
    
    # Dump Plan to log for debugging
    print(f"\n📋 PLAN SUMMARY:\nTitle: {plan.get('editorial_title')}\nVibe: {plan.get('visual_vibe')}\nSlide Types: {[s['type'] for s in plan.get('slides', [])]}\n")

    # 4. Rendering
    compositor = Compositor()
    accent = plan.get('accent_color', '#FDB813')
    slide_count = 0
    caption_text = f"🎞️ {plan.get('editorial_title')}\n📍 {target_cinema}\n\n"
    
    for i, slide in enumerate(plan.get('slides', [])):
        print(f"\n🔸 Processing Slide {i+1}: {slide['type']}")
        img = None
        
        try:
            if slide['type'] == 'HERO_PORTAL':
                cinema_img = get_cinema_bg(target_cinema)
                fname = slide.get('film_focus')
                fdata = next((x for x in cinema_films if x['movie_title'] == fname), cinema_films[0])
                
                poster_url = None
                if fdata.get('tmdb_poster_path'):
                     poster_url = f"https://image.tmdb.org/t/p/w780{fdata['tmdb_poster_path']}"
                
                poster = download_asset(poster_url)
                img = compositor.draw_hero(cinema_img, poster, plan.get('editorial_title'), accent)
                
            elif slide['type'] == 'POPOUT_SPOTLIGHT':
                fname = slide.get('film_focus') or slide.get('film')
                fdata = next((x for x in cinema_films if x['movie_title'] == fname), None)
                
                if fdata and fdata.get('tmdb_poster_path'):
                    img = compositor.draw_popout(fdata, accent)
                    caption_text += f"► {fname}\n"
                else:
                    log("Missing poster for popout. Switching to Quote.", "WARN")
                    slide['type'] = 'TYPOGRAPHIC_QUOTE' 
                    text = director.get_film_quote(fname)
                    img = compositor.draw_quote(text, fname, accent)
                
            elif slide['type'] == 'TIMELINE_STRIP':
                img = compositor.draw_timeline(cinema_films, accent)
                
            elif slide['type'] == 'TYPOGRAPHIC_QUOTE':
                fname = slide.get('film_focus')
                text = director.get_film_quote(fname)
                img = compositor.draw_quote(text, fname, accent)

            if img:
                filename = f"post_v3_{i:02}.png"
                img.save(OUTPUT_DIR / filename)
                
                story_bg = Image.new("RGB", (1080, 1920), "#111")
                story_bg.paste(img, (0, (1920-1350)//2))
                story_bg.save(OUTPUT_DIR / f"story_v3_{i:02}.png")
                
                log(f"Saved {filename}", "SUCCESS")
                slide_count += 1
            else:
                log("Image generation resulted in None.", "ERROR")
                
        except Exception as e:
            log(f"Slide Failed: {e}", "ERROR")
            traceback.print_exc()

    with open(OUTPUT_DIR / "post_v3_caption.txt", "w", encoding='utf-8') as f:
        f.write(caption_text + "\n#TokyoCinema #FilmLife")

    print(f"\n✅ --- FINISHED. Generated {slide_count} slides ---")

if __name__ == "__main__":
    main()
