"""
Generate Post 3: The "Creative Director" Engine (V4.1 - Fixes).
- Fixes RGBA>JPEG error for Replicate.
- Updates Replicate Model IDs to latest SDXL.
- Adds missing handlers for Typographic/Timeline slides.
- Adds solid fallbacks so failed AI calls don't look "broken".
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
import base64

# --- LIBRARIES ---
try:
    from google import genai
    from google.genai import types
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageEnhance
    import replicate
except ImportError as e:
    print(f"🛑 CRITICAL: Missing dependencies: {e}")
    exit(1)

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "ig_posts"
CINEMA_ASSETS_DIR = BASE_DIR / "cinema_assets"
FONTS_DIR = BASE_DIR / "fonts"
SHOWTIMES_PATH = DATA_DIR / "showtimes.json"
CINEMA_HISTORY_PATH = DATA_DIR / "cinema_history.json"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CINEMA_ASSETS_DIR.mkdir(parents=True, exist_ok=True)

JST = ZoneInfo("Asia/Tokyo")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")

# --- LOGGER UTILS ---
def log(msg, level="INFO"):
    icons = {"INFO": "🔵", "WARN": "⚠️ ", "ERROR": "🛑", "AI": "🧠", "GEN": "🎨", "SUCCESS": "✅"}
    print(f"{icons.get(level, '🔹')} [{level}] {msg}")

def check_environment():
    if not GEMINI_API_KEY: log("GEMINI_API_KEY missing!", "ERROR")
    if not REPLICATE_API_TOKEN: log("REPLICATE_API_TOKEN missing!", "ERROR")

# --- 1. SELECTION ENGINE ---

def load_cinema_history():
    if CINEMA_HISTORY_PATH.exists():
        with open(CINEMA_HISTORY_PATH, 'r', encoding='utf-8') as f: return json.load(f)
    return {}

def save_cinema_history(history):
    with open(CINEMA_HISTORY_PATH, 'w', encoding='utf-8') as f: json.dump(history, f, indent=2, ensure_ascii=False)

def select_target_cinema(todays_showtimes: List[Dict]) -> str:
    history = load_cinema_history()
    active_cinemas = list(set(f['cinema_name'] for f in todays_showtimes))
    if not active_cinemas: return None
    active_cinemas.sort(key=lambda name: history.get(name, "0000-00-00"))
    target = active_cinemas[0]
    log(f"Selected Target: {target} (Last Featured: {history.get(target, 'Never')})", "SUCCESS")
    history[target] = datetime.now(JST).strftime("%Y-%m-%d")
    save_cinema_history(history)
    return target

# --- 2. THE CREATIVE DIRECTOR ---

class CreativeDirector:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.5-flash" 

    def _clean_json_text(self, text: str) -> str:
        pattern = r"```(?:json)?\s*(.*?)\s*```"
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1) if match else text.strip()

    def create_editorial_plan(self, cinema_name: str, films: List[Dict]) -> Dict:
        log(f"🧠 Analyzing metadata for {len(films)} films...", "AI")
        
        clean_films = []
        for f in films:
            f['has_poster'] = bool(f.get('tmdb_poster_path'))
            f['has_backdrop'] = bool(f.get('tmdb_backdrop_path'))
            clean_films.append(f)

        prompt = f"""
        You are an Avant-Garde Art Director for a Tokyo cinema.
        Cinema: {cinema_name}
        Films: {json.dumps(clean_films, indent=2, ensure_ascii=False, default=str)}

        TASK: 
        Create a visual journey (Max 6 slides). Use the FULL variety of tools.
        
        TOOLS:
        - "HERO_HALLUCINATION": Cinema building transformed by AI into a movie scene.
        - "ENSEMBLE_COLLAGE": Characters from DIFFERENT films mixed together.
        - "POPOUT_POSTER": Vertical poster with depth effect.
        - "CINEMATIC_STILL": Horizontal backdrop with minimal text.
        - "TYPOGRAPHIC_REVIEW": Giant text for impactful quotes.
        - "TIMELINE_STRIP": A visual schedule (good for last slide).

        OUTPUT JSON ONLY:
        {{
            "editorial_title": "Headline",
            "visual_vibe": "Description",
            "accent_color": "#HEX",
            "slides": [
                {{ "type": "HERO_HALLUCINATION", "film_focus": "Film A", "visual_prompt": "cyberpunk city..." }},
                {{ "type": "ENSEMBLE_COLLAGE", "film_titles": ["Film A", "Film B"], "note": "Meeting..." }},
                {{ "type": "POPOUT_POSTER", "film_focus": "Film C" }},
                {{ "type": "TYPOGRAPHIC_REVIEW", "film_focus": "Film D" }},
                {{ "type": "TIMELINE_STRIP" }}
            ]
        }}
        """

        try:
            resp = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())], temperature=0.7)
            )
            return json.loads(self._clean_json_text(resp.text))
        except Exception as e:
            log(f"Gemini Error: {e}", "ERROR")
            return {"editorial_title": cinema_name, "slides": [{"type": "TIMELINE_STRIP"}]}

    def get_quote(self, film_title: str) -> str:
        try:
            prompt = f"Find a short, famous review quote or tagline for '{film_title}'."
            resp = self.client.models.generate_content(model=self.model, contents=prompt, config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]))
            return resp.text.strip().replace('"', '')
        except: return film_title

# --- 3. ASSET UTILS ---

def download_asset(url: str) -> Optional[Image.Image]:
    if not url: return None
    try:
        resp = requests.get(url, timeout=10)
        return Image.open(BytesIO(resp.content)).convert("RGBA")
    except: return None

def get_cinema_bg(cinema_name: str) -> Image.Image:
    safe_name = cinema_name.replace(" ", "_").lower()
    matches = list(CINEMA_ASSETS_DIR.glob(f"*{safe_name}*"))
    if matches: return Image.open(matches[0]).convert("RGBA")
    return Image.new("RGBA", (1080, 1350), (20,20,20)) # Dark Grey Fallback

# --- 4. GENERATIVE AI TOOLS (FIXED) ---

class AIStudio:
    def rembg(self, image: Image.Image) -> Image.Image:
        if not REPLICATE_API_TOKEN: return image
        try:
            buf = BytesIO()
            image.save(buf, format="PNG")
            output = replicate.run("cjwbw/rembg:fb8af171cfa1616ddcf1242c093f9c46bcada5ad4cf6f2fbe8b81b330ec5c003", input={"image": buf})
            return download_asset(output)
        except: return image

    def hallucinate_building(self, cinema_img: Image.Image, prompt: str) -> Image.Image:
        """Fix: Converts RGBA to RGB before sending to SDXL."""
        if not REPLICATE_API_TOKEN: return cinema_img
        log(f"🎨 Hallucinating: '{prompt}'...", "GEN")
        
        try:
            # FIX 1: Convert to RGB (JPEG doesn't support Alpha)
            init_img = ImageOps.fit(cinema_img, (1024, 1344)).convert("RGB") 
            buf = BytesIO()
            init_img.save(buf, format="JPEG", quality=95)
            
            # FIX 2: Use Latest SDXL
            output = replicate.run(
                "stability-ai/sdxl:7762fd07cf82c948538e41f63f77d685e02a319a1523bbb43f3af8fa0a590163",
                input={
                    "prompt": f"{prompt}, cinematic, masterpiece, 8k",
                    "image": buf,
                    "strength": 0.60, # 0.6 allows significant change but keeps structure
                    "negative_prompt": "text, watermark, ugly, blurry"
                }
            )
            return download_asset(output[0])
        except Exception as e:
            log(f"Hallucination failed: {e}", "ERROR")
            return cinema_img

    def inpaint_ensemble(self, collage_img: Image.Image, mask_img: Image.Image, prompt: str) -> Image.Image:
        """Fix: Uses SDXL for inpainting (requires inverted mask often)."""
        if not REPLICATE_API_TOKEN: return collage_img
        log(f"🎨 Inpainting background: '{prompt}'...", "GEN")
        
        try:
            img_buf = BytesIO()
            # SDXL Inpainting usually wants RGB image + Mask
            collage_img.convert("RGB").save(img_buf, format="PNG")
            
            mask_buf = BytesIO()
            mask_img.save(mask_buf, format="PNG")
            
            # FIX 3: Use SDXL (it supports mask input)
            output = replicate.run(
                "stability-ai/sdxl:7762fd07cf82c948538e41f63f77d685e02a319a1523bbb43f3af8fa0a590163",
                input={
                    "prompt": f"background of {prompt}, highly detailed, depth of field, no text",
                    "image": img_buf,
                    "mask": mask_buf,
                    "strength": 0.99 # Re-generate the masked area entirely
                }
            )
            return download_asset(output[0])
        except Exception as e:
            log(f"Inpainting failed: {e}", "ERROR")
            return collage_img

# --- 5. RENDERER ---

class Compositor:
    def __init__(self):
        self.W, self.H = 1080, 1350
        self.ai = AIStudio()
        self.fonts = self._load_fonts()

    def _load_fonts(self):
        def _f(n, s): 
            return ImageFont.truetype(str(FONTS_DIR/n), s) if (FONTS_DIR/n).exists() else ImageFont.load_default()
        return {
            "h1": _f("Manrope-Bold.ttf", 110),
            "h2": _f("Manrope-Bold.ttf", 70),
            "body": _f("Manrope-Regular.ttf", 45),
            "quote": _f("Manrope-Bold.ttf", 85)
        }

    def render_hallucination(self, cinema_img, visual_prompt, title, accent):
        hallucinated = self.ai.hallucinate_building(cinema_img, visual_prompt)
        canvas = ImageOps.fit(hallucinated, (self.W, self.H))
        
        draw = ImageDraw.Draw(canvas)
        # Gradient Scrim
        grad = Image.new("L", (self.W, 600), 0)
        gdraw = ImageDraw.Draw(grad)
        for y in range(600): gdraw.line([(0,y), (self.W,y)], fill=int(y/600 * 220))
        canvas.paste(Image.new("RGB", (self.W, 600), "black"), (0, self.H-600), grad)
        
        draw.text((60, self.H-250), title.upper(), font=self.fonts['h1'], fill=accent)
        return canvas

    def render_ensemble(self, film_datas, note, accent):
        # Start with a Dark Gradient Background (Fallback if Inpainting fails)
        canvas = Image.new("RGBA", (self.W, self.H), (20,20,20,255))
        draw_bg = ImageDraw.Draw(canvas)
        draw_bg.rectangle([(0,0), (self.W, self.H)], fill="#1a1a1a")
        
        mask = Image.new("L", (self.W, self.H), 255) # White = Inpaint Area (Replace)
        
        # Staggered placement
        positions = [(50, 400), (350, 300), (600, 450)] 
        
        for i, fdata in enumerate(film_datas[:3]):
            if not fdata.get('tmdb_poster_path'): continue
            poster = download_asset(f"https://image.tmdb.org/t/p/w780{fdata['tmdb_poster_path']}")
            if not poster: continue
            
            cutout = self.ai.rembg(poster)
            cutout = ImageOps.contain(cutout, (600, 900))
            
            x, y_base = positions[i] if i < 3 else (100, 400)
            y = self.H - cutout.height - 50
            
            # Paste character
            canvas.paste(cutout, (x, y), cutout)
            
            # Update Mask (Black = Keep Character)
            # Invert alpha channel to get "Black where character is"
            alpha = cutout.split()[3]
            mask_cutout = ImageOps.invert(alpha)
            mask.paste(0, (x, y), alpha) # Paste Black (0) where Alpha is high

        # AI Inpaint Background (Fills the White areas of mask)
        filled_bg = self.ai.inpaint_ensemble(canvas, mask, "cinematic movie scene background, neon, fog, detailed")
        
        draw = ImageDraw.Draw(filled_bg)
        draw.rectangle([(0,0), (self.W, 200)], fill="black")
        draw.text((50, 50), "FEATURED SELECTION", font=self.fonts['h2'], fill=accent)
        return filled_bg

    def render_typographic(self, text, film_title, accent):
        img = Image.new("RGB", (self.W, self.H), "#111")
        draw = ImageDraw.Draw(img)
        draw.text((40, 100), "“", font=self.fonts['h1'].font_variant(size=300), fill=accent)
        lines = textwrap.wrap(text, width=12)
        y = 400
        for line in lines:
            draw.text((60, y), line.upper(), font=self.fonts['quote'], fill="white")
            y += 110
        draw.text((60, y+80), film_title, font=self.fonts['h2'], fill="gray")
        return img

    def render_timeline(self, films, accent):
        img = Image.new("RGB", (self.W, self.H), "#F8F7F2")
        draw = ImageDraw.Draw(img)
        draw.text((50, 60), "TODAY'S SCHEDULE", font=self.fonts['h2'], fill="black")
        y = 250
        for f in films[:7]:
            draw.rectangle([(50, y), (230, y+80)], fill="black")
            draw.text((75, y+20), f['showtime'], font=self.fonts['body'], fill=accent)
            draw.text((260, y+20), f.get('clean_title_jp', f['movie_title']), font=self.fonts['body'], fill="black")
            y += 130
        return img
    
    # ... render_popout and render_cinematic_still are same as V4.0 (omitted for brevity, assume included) ...
    def render_popout(self, film_data, accent):
        poster_url = f"https://image.tmdb.org/t/p/original{film_data['tmdb_poster_path']}"
        poster = download_asset(poster_url)
        if not poster: return Image.new("RGB", (self.W, self.H), "black")
        bg = poster.copy()
        bg = ImageOps.fit(bg, (self.W, self.H))
        bg = bg.filter(ImageFilter.GaussianBlur(30))
        bg = ImageEnhance.Brightness(bg).enhance(0.4)
        draw = ImageDraw.Draw(bg)
        title = film_data.get('clean_title_jp', film_data['movie_title'])
        fsize = 130 if len(title) < 8 else 80
        font = self.fonts['h1'].font_variant(size=fsize)
        bbox = draw.textbbox((0,0), title, font=font)
        draw.text(((self.W - (bbox[2]-bbox[0]))//2, 300), title, font=font, fill="white")
        cutout = self.ai.rembg(poster)
        cutout = ImageOps.contain(cutout, (int(self.W*0.95), int(self.H*0.75)))
        bg.paste(cutout, ((self.W - cutout.width)//2, self.H - cutout.height), cutout)
        draw.rectangle([(0, self.H-100), (self.W, self.H)], fill=accent)
        draw.text((50, self.H-80), f"{film_data['showtime']} • {film_data.get('director')}", font=self.fonts['body'], fill="black")
        return bg

    def render_cinematic_still(self, film_data, accent):
        url = f"https://image.tmdb.org/t/p/original{film_data.get('tmdb_backdrop_path')}"
        img = download_asset(url)
        if not img: return None 
        canvas = ImageOps.fit(img, (self.W, self.H))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle([(0,0), (self.W, 150)], fill="black")
        draw.rectangle([(0, self.H-300), (self.W, self.H)], fill="black")
        draw.text((50, self.H-200), film_data.get('clean_title_jp', film_data['movie_title']), font=self.fonts['h1'], fill="white")
        return canvas

# --- MAIN WORKFLOW ---

def main():
    print("\n🎬 --- CINEMA SCRAPER V4.1 (FIXED) ---")
    check_environment()
    
    with open(SHOWTIMES_PATH, 'r', encoding='utf-8') as f: data = json.load(f)
    today_str = datetime.now(JST).strftime("%Y-%m-%d")
    todays_data = [x for x in data if x.get('date_text') == today_str]
    if not todays_data: return log("No shows today.", "WARN")

    target_cinema = select_target_cinema(todays_data)
    if not target_cinema: return log("No cinema selected.", "ERROR")
    cinema_films = [x for x in todays_data if x['cinema_name'] == target_cinema]
    
    director = CreativeDirector(GEMINI_API_KEY)
    plan = director.create_editorial_plan(target_cinema, cinema_films)
    
    compositor = Compositor()
    accent = plan.get('accent_color', '#FDB813')
    slide_count = 0
    caption_text = f"🎞️ {plan.get('editorial_title')}\n📍 {target_cinema}\n\n"

    for i, slide in enumerate(plan.get('slides', [])):
        print(f"\n🔸 Processing Slide {i+1}: {slide['type']}")
        img = None
        
        try:
            if slide['type'] == 'HERO_HALLUCINATION':
                cinema_img = get_cinema_bg(target_cinema)
                prompt = slide.get('visual_prompt', 'cinematic lighting')
                img = compositor.render_hallucination(cinema_img, prompt, plan.get('editorial_title'), accent)
                
            elif slide['type'] == 'ENSEMBLE_COLLAGE':
                titles = slide.get('film_titles', [])
                fdatas = [next((x for x in cinema_films if x['movie_title'] == t), None) for t in titles]
                fdatas = [x for x in fdatas if x] 
                img = compositor.render_ensemble(fdatas, slide.get('note', ''), accent)
                
            elif slide['type'] == 'POPOUT_POSTER':
                fname = slide.get('film_focus')
                fdata = next((x for x in cinema_films if x['movie_title'] == fname), None)
                if fdata: img = compositor.render_popout(fdata, accent)

            elif slide['type'] == 'CINEMATIC_STILL':
                fname = slide.get('film_focus')
                fdata = next((x for x in cinema_films if x['movie_title'] == fname), None)
                if fdata: img = compositor.render_cinematic_still(fdata, accent)
                
            # --- FIX: Added Missing Handlers ---
            elif slide['type'] == 'TYPOGRAPHIC_REVIEW':
                fname = slide.get('film_focus')
                quote = director.get_quote(fname)
                img = compositor.render_typographic(quote, fname, accent)

            elif slide['type'] == 'TIMELINE_STRIP':
                img = compositor.render_timeline(cinema_films, accent)

            if img:
                filename = f"post_v3_{i:02}.png"
                img.save(OUTPUT_DIR / filename)
                story = Image.new("RGB", (1080, 1920), "#111")
                story.paste(img, (0, (1920-1350)//2))
                story.save(OUTPUT_DIR / f"story_v3_{i:02}.png")
                log(f"Saved {filename}", "SUCCESS")
                slide_count += 1
                
        except Exception as e:
            log(f"Slide Failed: {e}", "ERROR")
            traceback.print_exc()

    with open(OUTPUT_DIR / "post_v3_caption.txt", "w", encoding='utf-8') as f:
        f.write(caption_text + "\n#TokyoCinema")

if __name__ == "__main__":
    main()
