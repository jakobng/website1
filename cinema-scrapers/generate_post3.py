"""
Generate Post 3: The "Creative Director" Engine.
- Concept: AI-driven Curation. Gemini decides the layout based on the "Vibe" of the lineup.
- Tech: Google GenAI (Search Grounding) + Replicate (RemBG) + Pillow (Advanced Compositing).
"""

import os
import json
import random
import requests
import time
import textwrap
from io import BytesIO
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import List, Dict, Any, Optional

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageEnhance

# --- LIBRARIES ---
try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    print("⚠️ Google GenAI not found. Run: pip install google-genai")
    GEMINI_AVAILABLE = False

try:
    import replicate
    REPLICATE_AVAILABLE = True
except ImportError:
    print("⚠️ Replicate not found. Run: pip install replicate")
    REPLICATE_AVAILABLE = False

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "ig_posts"
CINEMA_ASSETS_DIR = BASE_DIR / "cinema_assets"
FONTS_DIR = BASE_DIR / "fonts"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CINEMA_ASSETS_DIR.mkdir(parents=True, exist_ok=True)

JST = ZoneInfo("Asia/Tokyo")

# API KEYS
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")

# --- CLASS: THE CREATIVE DIRECTOR ---

class CreativeDirector:
    """
    Uses Gemini 2.5 with Search Grounding to analyze the lineup and propose a visual plan.
    """
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.5-flash" 

    def analyze_lineup_and_direct(self, cinema_name: str, films: List[Dict]) -> Dict:
        """
        Returns a JSON 'Manifest' dictating the slide deck structure.
        """
        print(f"🧠 Director is analyzing lineup for {cinema_name}...")
        
        # 1. Prepare Data for LLM
        film_context = []
        for f in films:
            film_context.append({
                "title": f.get('movie_title'),
                "director": f.get('director'),
                "country": f.get('country'),
                "has_image": bool(f.get('tmdb_poster_path'))
            })
        
        # 2. Define the Schema (The Shot List)
        # We want Gemini to select from specific slide types.
        prompt = f"""
        You are the Art Director for a high-end cinema magazine. 
        We are featuring the cinema "{cinema_name}" and today's lineup:
        {json.dumps(film_context, ensure_ascii=False)}

        Analyze the lineup. Is there a theme? (e.g. "French New Wave", "Mads Mikkelsen Season", "Horror Marathon", "Indie Mix").
        If you don't know a film, use your Search tool to find its genre and vibe.

        Create a JSON plan for an Instagram Carousel (max 6 slides).
        Available Slide Types:
        1. "HERO_PORTAL": The cover. Must combine the cinema building with a film image.
        2. "POPOUT_SPOTLIGHT": Focus on ONE film. Requires high visual impact. Only choose if 'has_image' is true.
        3. "TIMELINE_STRIP": A visual schedule of the day. Good if there are many films.
        4. "EDITORIAL_QUOTE": Large typography with a critic's quote or tagline. Use this if 'has_image' is false or for variety.
        
        Output valid JSON only:
        {{
            "theme_title": "Short punchy title for the day (e.g. 'NEON NOIR')",
            "visual_style": "Describe colors and font vibe (e.g. 'Gritty, high contrast, red accent')",
            "accent_color_hex": "#RRGGBB",
            "slides": [
                {{ "type": "HERO_PORTAL", "focus_film": "Film Title" }},
                {{ "type": "POPOUT_SPOTLIGHT", "film": "Film Title", "reason": "Why this film?" }},
                {{ "type": "EDITORIAL_QUOTE", "film": "Film Title", "search_query": "search query to find a quote for this film" }},
                {{ "type": "TIMELINE_STRIP" }}
            ]
        }}
        """

        # 3. Configure Search Grounding
        grounding_tool = types.Tool(google_search=types.GoogleSearch())
        
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[grounding_tool],
                    response_mime_type="application/json",
                    temperature=0.4
                )
            )
            
            # Parse JSON
            plan = json.loads(response.text)
            
            # Enrich with Search Data for Quotes if needed
            # (Gemini usually does this in one pass if asked, but let's verify)
            if response.candidates[0].grounding_metadata:
                print("   🔍 Search Grounding was used to inform the direction.")
                
            return plan

        except Exception as e:
            print(f"❌ Director failed: {e}")
            # Fallback Plan
            return {
                "theme_title": f"{cinema_name} Daily",
                "accent_color_hex": "#FDB813",
                "slides": [{"type": "TIMELINE_STRIP"}]
            }

    def fetch_quote(self, film_title: str) -> str:
        """Helper to specifically find a quote if the plan requests it."""
        try:
            prompt = f"Find a short, famous, one-sentence review or tagline for the film '{film_title}'. Return JUST the text."
            grounding = types.Tool(google_search=types.GoogleSearch())
            resp = self.client.models.generate_content(
                model=self.model, contents=prompt, config=types.GenerateContentConfig(tools=[grounding])
            )
            return resp.text.strip().replace('"', '')
        except:
            return f"Now Showing: {film_title}"

# --- HELPER FUNCTIONS ---

def download_asset(url: str) -> Image.Image:
    if not url: return None
    try:
        resp = requests.get(url, timeout=10)
        img = Image.open(BytesIO(resp.content)).convert("RGBA")
        return img
    except Exception:
        return None

def remove_background_rembg(image: Image.Image) -> Image.Image:
    """Uses Replicate to remove background. Returns the CUTOUT."""
    if not REPLICATE_API_TOKEN:
        print("   ⚠️ No Replicate Token. Skipping RemBG.")
        return image
    
    print("   🎨 Sending to Replicate (RemBG)...")
    try:
        # Save temp file
        buf = BytesIO()
        image.save(buf, format="PNG")
        buf.seek(0)
        
        output = replicate.run(
            "cjwbw/rembg:fb8af171cfa1616ddcf1242c093f9c46bcada5ad4cf6f2fbe8b81b330ec5c003",
            input={"image": buf}
        )
        # Output is a URL
        return download_asset(output)
    except Exception as e:
        print(f"   ❌ RemBG failed: {e}")
        return image

def get_cinema_photo(cinema_name: str) -> Image.Image:
    # Basic mapping or fuzzy search in cinema_assets
    # For prototype, look for exact match or first file
    safe_name = cinema_name.replace(" ", "_").lower()
    matches = list(CINEMA_ASSETS_DIR.glob(f"*{safe_name}*"))
    if not matches:
        matches = list(CINEMA_ASSETS_DIR.glob("*.jpg")) # Fallback
    
    if matches:
        return Image.open(matches[0]).convert("RGBA")
    return Image.new("RGBA", (1080, 1350), (20, 20, 20))

# --- THE COMPOSITOR (RENDER ENGINE) ---

class Compositor:
    def __init__(self, fonts_dir: Path):
        self.W = 1080
        self.H = 1350
        self.fonts = self._load_fonts(fonts_dir)

    def _load_fonts(self, d: Path):
        # Fallback to default if specific fonts missing
        return {
            "bold": ImageFont.truetype(str(d / "Manrope-Bold.ttf"), 120) if (d / "Manrope-Bold.ttf").exists() else ImageFont.load_default(),
            "medium": ImageFont.truetype(str(d / "Manrope-Regular.ttf"), 60) if (d / "Manrope-Regular.ttf").exists() else ImageFont.load_default(),
            "small": ImageFont.truetype(str(d / "Manrope-Regular.ttf"), 40) if (d / "Manrope-Regular.ttf").exists() else ImageFont.load_default(),
        }

    def render_hero_portal(self, cinema_img: Image.Image, film_img: Image.Image, title: str, accent_color: str) -> Image.Image:
        """
        Composites the film image INTO the cinema image (e.g. screen or door).
        For this prototype, we use a 'Soft Light' blend over the whole building + text.
        """
        canvas = cinema_img.copy()
        canvas = ImageOps.fit(canvas, (self.W, self.H))
        
        if film_img:
            film_layer = ImageOps.fit(film_img, (self.W, self.H))
            # Create a gradient mask
            mask = Image.new("L", (self.W, self.H), 0)
            draw = ImageDraw.Draw(mask)
            draw.rectangle([(0, self.H//2), (self.W, self.H)], fill=200) # Bottom half opaque
            canvas = Image.composite(film_layer, canvas, mask)
        
        # Overlay
        overlay = Image.new("RGBA", (self.W, self.H), (0,0,0,100))
        canvas = Image.alpha_composite(canvas, overlay)
        
        draw = ImageDraw.Draw(canvas)
        
        # Theme Title
        font_size = 100
        font = self.fonts['bold'].font_variant(size=font_size)
        
        # Text Logic
        margin = 60
        y_pos = 100
        
        # Draw Title
        draw.text((margin, y_pos), title.upper(), font=font, fill=accent_color)
        draw.text((margin, y_pos + font_size + 20), datetime.now().strftime("%B %d").upper(), font=self.fonts['medium'], fill="white")
        
        return canvas

    def render_popout_spotlight(self, film_data: Dict, accent: str) -> Image.Image:
        """
        1. Background: Original Poster (Blurred)
        2. Text: Big Title (Behind character)
        3. Foreground: Character Cutout
        """
        # Fetch high res
        poster_url = f"https://image.tmdb.org/t/p/original{film_data['tmdb_poster_path']}"
        full_poster = download_asset(poster_url)
        
        if not full_poster:
            return Image.new("RGB", (self.W, self.H), "black")

        # 1. Background
        bg = full_poster.copy()
        bg = ImageOps.fit(bg, (self.W, self.H))
        bg = bg.filter(ImageFilter.GaussianBlur(20))
        bg = ImageEnhance.Brightness(bg).enhance(0.5)

        # 2. Cutout
        cutout = remove_background_rembg(full_poster)
        cutout = ImageOps.contain(cutout, (int(self.W * 0.9), int(self.H * 0.8)))
        
        # 3. Composition
        # Draw Text FIRST (so it sits behind the cutout)
        draw = ImageDraw.Draw(bg)
        title = film_data.get('clean_title_jp') or film_data.get('movie_title')
        
        # Dynamic font scaling
        font_size = 150
        if len(title) > 8: font_size = 100
        if len(title) > 15: font_size = 80
        
        title_font = self.fonts['bold'].font_variant(size=font_size)
        
        # Center text
        bbox = draw.textbbox((0,0), title, font=title_font)
        text_w = bbox[2] - bbox[0]
        text_x = (self.W - text_w) // 2
        text_y = self.H // 3
        
        draw.text((text_x, text_y), title, font=title_font, fill="white", stroke_width=2, stroke_fill="black")
        
        # Place Cutout centered bottom
        cutout_x = (self.W - cutout.width) // 2
        cutout_y = self.H - cutout.height
        
        bg.paste(cutout, (cutout_x, cutout_y), cutout)
        
        # Info Badge
        draw.rectangle([(0, self.H - 150), (self.W, self.H)], fill=accent)
        info_text = f"{film_data['showtime']} • {film_data.get('director', '')}"
        draw.text((50, self.H - 110), info_text, font=self.fonts['medium'], fill="black")

        return bg

    def render_timeline(self, films: List[Dict], cinema_name: str, accent: str) -> Image.Image:
        """Visualizes time blocks."""
        img = Image.new("RGB", (self.W, self.H), "#F8F7F2")
        draw = ImageDraw.Draw(img)
        
        # Header
        draw.text((50, 50), "SCHEDULE", font=self.fonts['bold'], fill="black")
        draw.text((50, 180), cinema_name, font=self.fonts['medium'], fill="black")

        # Time Params (10:00 to 24:00)
        start_hour = 9
        end_hour = 24
        total_pixels = 900 # Height for chart
        px_per_hour = total_pixels / (end_hour - start_hour)
        chart_top = 300
        
        # Draw Axis
        draw.line([(150, chart_top), (150, chart_top + total_pixels)], fill="black", width=2)
        
        for film in films:
            try:
                # Parse Time "14:30"
                t_str = film['showtime']
                h, m = map(int, t_str.split(':'))
                minutes_from_start = (h - start_hour) * 60 + m
                duration = int(film.get('runtime_min', 90) or 90)
                
                y_start = chart_top + (minutes_from_start / 60 * px_per_hour)
                height = (duration / 60 * px_per_hour)
                
                # Draw Block
                draw.rectangle([(180, y_start), (self.W - 50, y_start + height)], fill=accent)
                
                # Label
                title = film.get('clean_title_jp', film['movie_title'])
                draw.text((200, y_start + 10), f"{t_str} {title}", font=self.fonts['small'], fill="black")
            except:
                continue
                
        return img

    def render_editorial(self, quote: str, film_title: str) -> Image.Image:
        """Text heavy slide."""
        img = Image.new("RGB", (self.W, self.H), "#111111")
        draw = ImageDraw.Draw(img)
        
        # Wrap text
        font = self.fonts['bold'].font_variant(size=80)
        lines = textwrap.wrap(quote, width=15)
        
        y = 300
        for line in lines:
            draw.text((50, y), line, font=font, fill="white")
            y += 100
            
        draw.text((50, self.H - 200), film_title, font=self.fonts['medium'], fill="gray")
        return img

# --- MAIN EXECUTION FLOW ---

def main():
    print("🎬 Starting Creative Director Engine (V3)...")
    
    # 1. Load Data
    if not SHOWTIMES_PATH.exists():
        print("❌ No showtimes.json found.")
        return
        
    with open(SHOWTIMES_PATH, 'r', encoding='utf-8') as f:
        all_showtimes = json.load(f)

    # Filter for Today
    today_str = datetime.now(JST).strftime("%Y-%m-%d")
    todays_films = [f for f in all_showtimes if f.get('date_text') == today_str]
    
    if not todays_films:
        print(f"⚠️ No films found for {today_str}. Exiting.")
        return

    # Select Random Cinema for Demo
    unique_cinemas = list(set(f['cinema_name'] for f in todays_films))
    target_cinema = random.choice(unique_cinemas)
    cinema_films = [f for f in todays_films if f['cinema_name'] == target_cinema]
    
    print(f"📍 Selected Cinema: {target_cinema} ({len(cinema_films)} films)")

    # 2. Initialize Agents
    director = CreativeDirector(api_key=GEMINI_API_KEY)
    compositor = Compositor(fonts_dir=FONTS_DIR)

    # 3. Get the "Shot List" (Plan)
    plan = director.analyze_lineup_and_direct(target_cinema, cinema_films)
    print(f"\n📜 Director's Plan: {plan.get('theme_title')}")
    print(json.dumps(plan, indent=2, ensure_ascii=False))

    # 4. Execution Loop
    accent_color = plan.get('accent_color_hex', "#FDB813")
    slides_created = 0
    
    caption_text = f"🎞️ {plan.get('theme_title')}\n🎨 Vibe: {plan.get('visual_style')}\n\n"

    for i, slide_req in enumerate(plan.get('slides', [])):
        print(f"\n🎨 Rendering Slide {i+1}: {slide_req['type']}")
        
        try:
            slide_img = None
            
            # --- HERO PORTAL ---
            if slide_req['type'] == 'HERO_PORTAL':
                cinema_pic = get_cinema_photo(target_cinema)
                # Find film image
                film_title = slide_req.get('focus_film')
                film_data = next((f for f in cinema_films if f['movie_title'] == film_title), cinema_films[0])
                
                poster_url = f"https://image.tmdb.org/t/p/w780{film_data['tmdb_poster_path']}" if film_data.get('tmdb_poster_path') else None
                film_pic = download_asset(poster_url)
                
                slide_img = compositor.render_hero_portal(cinema_pic, film_pic, plan.get('theme_title'), accent_color)
                
            # --- POPOUT SPOTLIGHT ---
            elif slide_req['type'] == 'POPOUT_SPOTLIGHT':
                film_title = slide_req.get('film')
                film_data = next((f for f in cinema_films if f['movie_title'] == film_title), None)
                if film_data and film_data.get('tmdb_poster_path'):
                    slide_img = compositor.render_popout_spotlight(film_data, accent_color)
                else:
                    print("   ⚠️ Missing image for Popout. Skipping.")
            
            # --- TIMELINE ---
            elif slide_req['type'] == 'TIMELINE_STRIP':
                slide_img = compositor.render_timeline(cinema_films, target_cinema, accent_color)
                
            # --- EDITORIAL QUOTE ---
            elif slide_req['type'] == 'EDITORIAL_QUOTE':
                film_title = slide_req.get('film')
                # Use Gemini to find quote if not provided
                quote = director.fetch_quote(film_title)
                slide_img = compositor.render_editorial(quote, film_title)

            # SAVE
            if slide_img:
                filename = f"post_v3_{i:02}.png"
                slide_img.save(OUTPUT_DIR / filename)
                
                # Story Version (Simple padding for now)
                story_bg = Image.new("RGB", (1080, 1920), "#111")
                story_bg.paste(slide_img, (0, (1920-1350)//2))
                story_bg.save(OUTPUT_DIR / f"story_v3_{i:02}.png")
                
                slides_created += 1

        except Exception as e:
            print(f"   ❌ Error rendering slide: {e}")
            import traceback
            traceback.print_exc()

    # Save Caption
    with open(OUTPUT_DIR / "post_v3_caption.txt", "w", encoding="utf-8") as f:
        f.write(caption_text + f"\n📍 {target_cinema}\n#TokyoCinema #JapanFilm")

    print(f"\n✅ Production Wrap. Generated {slides_created} slides.")

# --- PATH SETUP & EXECUTE ---
SHOWTIMES_PATH = DATA_DIR / "showtimes.json"

if __name__ == "__main__":
    main()
