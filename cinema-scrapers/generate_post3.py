"""
Generate Post 3: The "Creative Director" Engine (V4.0 - Generative Edition).
- Logic: Full Metadata Analysis -> Generative Art Direction -> Asset Fetching -> AI Composition.
- New Tools: 
    - SDXL Img2Img (Hallucinating the Cinema).
    - RemBG + Collage (The Ensemble).
    - Backdrop/Poster awareness.
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
    print("Run: pip install google-genai replicate requests Pillow tzdata")
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
    icon = icons.get(level, "🔹")
    print(f"{icon} [{level}] {msg}")

def check_environment():
    if not GEMINI_API_KEY: log("GEMINI_API_KEY missing!", "ERROR")
    if not REPLICATE_API_TOKEN: log("REPLICATE_API_TOKEN missing!", "ERROR")

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
    history = load_cinema_history()
    active_cinemas = list(set(f['cinema_name'] for f in todays_showtimes))
    
    if not active_cinemas: return None

    # Sort by staleness
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
        log(f"🧠 analyzing metadata for {len(films)} films...", "AI")
        
        # 1. Prepare FULL Metadata (The Firehose)
        # We strip unnecessary long fields to save tokens if needed, but for now sending full.
        clean_films = []
        for f in films:
            # Add availability flags
            f['has_poster'] = bool(f.get('tmdb_poster_path'))
            f['has_backdrop'] = bool(f.get('tmdb_backdrop_path'))
            clean_films.append(f)

        prompt = f"""
        You are the Avant-Garde Creative Director for a Tokyo cinema.
        Cinema: {cinema_name}
        
        FULL DATA DUMP:
        {json.dumps(clean_films, indent=2, ensure_ascii=False, default=str)}

        YOUR MISSION:
        1. Curate a visual journey. Do not just list films. Group them (e.g., "The Anime Corner", "Midnight Horror", "Human Drama").
        2. "Do Justice" to the lineup. If there is variety, show it. 
        3. You can request MULTIPLE slides for a single major film (e.g. Slide 1: Poster, Slide 2: Scene/Backdrop).

        AVAILABLE TOOLS (Slide Types):
        - "HERO_HALLUCINATION": Takes the cinema building photo and AI-transforms it into the style of a specific film. (Requires 'visual_prompt').
        - "ENSEMBLE_COLLAGE": Cutouts of characters from 2-3 DIFFERENT films standing together. (Requires 'film_titles' list).
        - "POPOUT_POSTER": Vertical poster with subject popping out over text. (Needs 'has_poster').
        - "CINEMATIC_STILL": Horizontal backdrop with minimal text. (Needs 'has_backdrop').
        - "TYPOGRAPHIC_REVIEW": Big text/quote. (Fallback).

        OUTPUT JSON ONLY:
        {{
            "editorial_title": "Headline",
            "visual_vibe": "Description of style",
            "accent_color": "#HEX",
            "slides": [
                {{ 
                    "type": "HERO_HALLUCINATION", 
                    "film_focus": "Akira", 
                    "visual_prompt": "Neo-Tokyo cyberpunk city, red motorcycle lights, gritty detailed 80s anime style" 
                }},
                {{ 
                    "type": "ENSEMBLE_COLLAGE", 
                    "film_titles": ["Film A", "Film B"], 
                    "note": "Mix these characters" 
                }},
                {{ 
                    "type": "CINEMATIC_STILL", 
                    "film_focus": "Film C",
                    "reason": "Beautiful cinematography"
                }}
            ]
        }}
        """

        grounding = types.Tool(google_search=types.GoogleSearch())
        
        try:
            resp = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(tools=[grounding], temperature=0.7) # Higher temp for creativity
            )
            
            clean_text = self._clean_json_text(resp.text)
            return json.loads(clean_text)

        except Exception as e:
            log(f"Gemini Error: {e}", "ERROR")
            # Minimal Fallback
            return {"editorial_title": cinema_name, "slides": [{"type": "TIMELINE"}]}

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
    return Image.new("RGBA", (1080, 1350), (30,30,30))

def image_to_base64(img):
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode('utf-8')

# --- 4. GENERATIVE AI TOOLS (REPLICATE) ---

class AIStudio:
    """Wraps Replicate API for advanced image manipulation."""
    
    def rembg(self, image: Image.Image) -> Image.Image:
        """Standard Background Removal"""
        if not REPLICATE_API_TOKEN: return image
        try:
            buf = BytesIO()
            image.save(buf, format="PNG")
            output = replicate.run("cjwbw/rembg:fb8af171cfa1616ddcf1242c093f9c46bcada5ad4cf6f2fbe8b81b330ec5c003", input={"image": buf})
            return download_asset(output)
        except: return image

    def hallucinate_building(self, cinema_img: Image.Image, prompt: str) -> Image.Image:
        """
        Uses SDXL Image-to-Image. 
        Input: Cinema Photo. 
        Prompt: Movie style. 
        Result: Cinema photo transformed into that style.
        """
        if not REPLICATE_API_TOKEN: return cinema_img
        log(f"🎨 Hallucinating: '{prompt}' over cinema photo...", "GEN")
        
        try:
            # Resize for SDXL (should be roughly 1024x1024 or similar aspect)
            init_img = ImageOps.fit(cinema_img, (1024, 1280))
            buf = BytesIO()
            init_img.save(buf, format="JPEG", quality=90)
            
            output = replicate.run(
                "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
                input={
                    "prompt": f"{prompt}, cinematic, masterpiece, 8k, highly detailed",
                    "image": buf,
                    "strength": 0.65, # How much to change the image (0.65 is high but preserves structure)
                    "negative_prompt": "blur, low quality, distortion, text, watermark"
                }
            )
            return download_asset(output[0])
        except Exception as e:
            log(f"Hallucination failed: {e}", "ERROR")
            return cinema_img

    def inpaint_ensemble(self, collage_img: Image.Image, mask_img: Image.Image, prompt: str) -> Image.Image:
        """Uses SDXL Inpainting to fill the background."""
        if not REPLICATE_API_TOKEN: return collage_img
        log(f"🎨 Inpainting background: '{prompt}'...", "GEN")
        
        try:
            # Prepare buffers
            img_buf = BytesIO()
            collage_img.save(img_buf, format="PNG")
            
            mask_buf = BytesIO()
            mask_img.save(mask_buf, format="PNG")
            
            output = replicate.run(
                "stability-ai/stable-diffusion-inpainting:95b7223104132402a9ae91cc677285bc5eb997834bd2349fa4868539071c7998",
                input={
                    "prompt": f"background of {prompt}, cinematic lighting, depth of field",
                    "image": img_buf,
                    "mask": mask_buf,
                    "num_inference_steps": 40
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
        # 1. AI Generation
        hallucinated = self.ai.hallucinate_building(cinema_img, visual_prompt)
        
        # 2. Layout
        canvas = ImageOps.fit(hallucinated, (self.W, self.H))
        
        # Overlay
        draw = ImageDraw.Draw(canvas)
        # Gradient at bottom for text
        grad = Image.new("L", (self.W, 600), 0)
        gdraw = ImageDraw.Draw(grad)
        for y in range(600):
            gdraw.line([(0,y), (self.W,y)], fill=int(y/600 * 200))
        canvas.paste(Image.new("RGB", (self.W, 600), "black"), (0, self.H-600), grad)
        
        # Text
        draw.text((60, self.H-250), title.upper(), font=self.fonts['h1'], fill=accent)
        draw.text((60, self.H-120), datetime.now(JST).strftime("%Y.%m.%d"), font=self.fonts['h2'], fill="white")
        
        return canvas

    def render_ensemble(self, film_datas, note, accent):
        # 1. Create blank canvas
        canvas = Image.new("RGBA", (self.W, self.H), (0,0,0,0))
        mask = Image.new("L", (self.W, self.H), 255) # White = Inpaint Area
        
        # 2. Place Characters (Cutouts)
        # We place them roughly center-bottom, staggering them
        positions = [(100, 400), (500, 350), (300, 500)] # Simple staggering
        
        for i, fdata in enumerate(film_datas[:3]):
            if not fdata.get('tmdb_poster_path'): continue
            
            poster = download_asset(f"https://image.tmdb.org/t/p/w780{fdata['tmdb_poster_path']}")
            if not poster: continue
            
            cutout = self.ai.rembg(poster)
            # Normalize size
            cutout = ImageOps.contain(cutout, (600, 900))
            
            # Paste onto canvas
            x_offset = (i * 250) - 50
            y_offset = self.H - cutout.height - 100
            
            canvas.paste(cutout, (x_offset, y_offset), cutout)
            
            # Update Mask (Black = Keep Area)
            # We use the alpha channel of cutout to draw black on mask
            cutout_alpha = cutout.split()[3]
            mask.paste(0, (x_offset, y_offset), cutout_alpha)

        # 3. AI Inpaint Background
        # We fill the 'White' area of mask with the prompt
        bg_prompt = "cinematic atmospheric background, smoke, neon lights, movie set"
        filled_bg = self.ai.inpaint_ensemble(canvas, mask, bg_prompt)
        
        # 4. Text Overlay
        draw = ImageDraw.Draw(filled_bg)
        draw.rectangle([(0,0), (self.W, 200)], fill="black")
        draw.text((50, 50), "FEATURED SELECTION", font=self.fonts['h2'], fill=accent)
        draw.text((50, 130), note, font=self.fonts['body'], fill="white")
        
        return filled_bg

    def render_cinematic_still(self, film_data, accent):
        # Use Backdrop (Horizontal)
        url = f"https://image.tmdb.org/t/p/original{film_data.get('tmdb_backdrop_path')}"
        img = download_asset(url)
        if not img: return None # Fail logic handles this
        
        canvas = ImageOps.fit(img, (self.W, self.H))
        
        # Letterbox effect
        draw = ImageDraw.Draw(canvas)
        draw.rectangle([(0,0), (self.W, 150)], fill="black")
        draw.rectangle([(0, self.H-300), (self.W, self.H)], fill="black")
        
        # Text
        title = film_data.get('clean_title_jp', film_data['movie_title'])
        draw.text((50, self.H-200), title, font=self.fonts['h1'], fill="white")
        draw.text((50, self.H-80), f"Dir. {film_data.get('director', 'Unknown')}", font=self.fonts['body'], fill=accent)
        
        return canvas

    def render_popout(self, film_data, accent):
        # ... (Same as V3 but ensuring Poster is used) ...
        poster_url = f"https://image.tmdb.org/t/p/original{film_data['tmdb_poster_path']}"
        poster = download_asset(poster_url)
        if not poster: return None

        bg = poster.copy()
        bg = ImageOps.fit(bg, (self.W, self.H))
        bg = bg.filter(ImageFilter.GaussianBlur(30))
        bg = ImageEnhance.Brightness(bg).enhance(0.4)
        
        draw = ImageDraw.Draw(bg)
        title = film_data.get('clean_title_jp', film_data['movie_title'])
        
        # Text Logic
        fsize = 130 if len(title) < 8 else 80
        font = self.fonts['h1'].font_variant(size=fsize)
        bbox = draw.textbbox((0,0), title, font=font)
        draw.text(((self.W - (bbox[2]-bbox[0]))//2, 300), title, font=font, fill="white")

        cutout = self.ai.rembg(poster)
        cutout = ImageOps.contain(cutout, (int(self.W*0.95), int(self.H*0.75)))
        bg.paste(cutout, ((self.W - cutout.width)//2, self.H - cutout.height), cutout)
        
        # Badge
        draw.rectangle([(0, self.H-100), (self.W, self.H)], fill=accent)
        draw.text((50, self.H-80), f"{film_data['showtime']} • {film_data.get('director')}", font=self.fonts['body'], fill="black")
        return bg

# --- MAIN WORKFLOW ---

def main():
    print("\n🎬 --- CINEMA SCRAPER V4.0 (GEN-ART) ---")
    check_environment()
    
    with open(SHOWTIMES_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    today_str = datetime.now(JST).strftime("%Y-%m-%d")
    todays_data = [x for x in data if x.get('date_text') == today_str]
    
    if not todays_data: return log("No shows today.", "WARN")

    target_cinema = select_target_cinema(todays_data)
    if not target_cinema: return log("No cinema selected.", "ERROR")
    
    cinema_films = [x for x in todays_data if x['cinema_name'] == target_cinema]
    
    # AI PLANNING
    director = CreativeDirector(GEMINI_API_KEY)
    plan = director.create_editorial_plan(target_cinema, cinema_films)
    
    print(f"\n📋 PLAN: {plan.get('editorial_title')} ({len(plan.get('slides',[]))} slides)")

    # RENDERING
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
                # Find film objects
                fdatas = [next((x for x in cinema_films if x['movie_title'] == t), None) for t in titles]
                fdatas = [x for x in fdatas if x] # Filter None
                img = compositor.render_ensemble(fdatas, slide.get('note', ''), accent)
                
            elif slide['type'] == 'POPOUT_POSTER':
                fname = slide.get('film_focus')
                fdata = next((x for x in cinema_films if x['movie_title'] == fname), None)
                if fdata: img = compositor.render_popout(fdata, accent)

            elif slide['type'] == 'CINEMATIC_STILL':
                fname = slide.get('film_focus')
                fdata = next((x for x in cinema_films if x['movie_title'] == fname), None)
                if fdata: img = compositor.render_cinematic_still(fdata, accent)

            # SAVE
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
