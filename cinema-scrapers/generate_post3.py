"""
generate_post3.py
The "Infinite Cinemascape" Protocol (Single File Edition).

Features:
1. Art Director: Uses Gemini 2.0 Flash to hallucinate a visual theme based on the movie plot.
2. Grid Memory: Remembers where yesterday's visual "line" ended to ensure continuity.
3. The Painter: Uses Stable Diffusion XL (SDXL) via Replicate to "inpaint" a world around the posters.
4. Typography: Overlays clean, minimalist text for showtimes.
"""

import os
import sys
import json
import time
import random
import requests
from pathlib import Path
from datetime import datetime
from io import BytesIO
from typing import Dict, List, Tuple

# --- LIBRARIES ---
try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
except ImportError:
    print("❌ PIL (Pillow) not found. Run: pip install Pillow")
    sys.exit(1)

try:
    import replicate
except ImportError:
    print("❌ Replicate not found. Run: pip install replicate")
    sys.exit(1)

try:
    # We use the NEW Google Gen AI SDK (v0.1+)
    from google import genai
    from google.genai import types
except ImportError:
    print("❌ Google GenAI not found. Run: pip install google-genai")
    sys.exit(1)

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "cinema_assets"
OUTPUT_DIR = BASE_DIR
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"
STATE_FILE = BASE_DIR / "cinemascape_state.json"
FONT_PATH = BASE_DIR / "NotoSansJP-Bold.ttf" # Ensure this font exists!

# SECRETS
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Create dirs if missing
ASSETS_DIR.mkdir(exist_ok=True)

# --- CLASS 1: THE ART DIRECTOR (GEMINI) ---
class ArtDirector:
    """
    Acts as the creative lead. Reads the synopsis and dreams up a scene.
    """
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("⚠️ GEMINI_API_KEY is missing!")
        self.client = genai.Client(api_key=api_key)

    def dream_scene(self, film_title: str, synopsis: str) -> Dict:
        print(f"🧠 Art Director is reading script for: {film_title}...")
        
        prompt = f"""
        You are a Visual Futurist and Art Director for a high-end cinema magazine.
        WE ARE DESIGNING A BACKGROUND FOR: "{film_title}"
        SYNOPSIS: "{synopsis}"

        Your goal: Describe a VISUAL BACKGROUND that represents the *mood* of this film.
        RULES:
        1. OUTPUT A SINGLE JSON OBJECT.
        2. "visual_prompt": Descriptive prompt for SDXL (texture, lighting, style).
        3. "connection_element": A specific object that forms a vertical line (wire, beam, vine).
        """
        
        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            data = json.loads(response.text)
            
            # --- FIX: Handle List Output ---
            if isinstance(data, list):
                data = data[0] if len(data) > 0 else {}
                
            return data
        except Exception as e:
            print(f"❌ Art Director hallucination failed: {e}")
            return {
                "visual_prompt": "Cinematic atmosphere, soft dramatic lighting, photorealistic",
                "connection_element": "A steel wire"
            }

# --- CLASS 2: THE GRID MANAGER (MEMORY) ---
class GridManager:
    """
    Manages the 'Infinite Scroll' continuity.
    """
    def __init__(self):
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        if STATE_FILE.exists():
            try:
                text = STATE_FILE.read_text()
                if text.strip():
                    return json.loads(text)
            except:
                pass
        return {
            "last_exit_x_percent": 0.5, 
            "history": []
        }

    def get_entry_point(self) -> float:
        """Where should the line start at the TOP? (Matches yesterday's bottom)"""
        return self.state.get("last_exit_x_percent", 0.5)

    def save_state(self, exit_x_percent: float, film_title: str):
        """Saves today's exit point for tomorrow."""
        self.state["last_exit_x_percent"] = exit_x_percent
        self.state["history"].append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "film": film_title,
            "exit_x": exit_x_percent
        })
        if len(self.state["history"]) > 10:
            self.state["history"].pop(0)
        STATE_FILE.write_text(json.dumps(self.state, indent=2))

# --- HELPER FUNCTIONS ---

def download_poster(tmdb_id: int) -> Path:
    """Downloads poster from TMDB if not exists."""
    file_path = ASSETS_DIR / f"{tmdb_id}.jpg"
    if file_path.exists():
        return file_path
    
    # In a real run, we would fetch from TMDB API here.
    # For now, we assume assets are pre-fetched or we skip.
    print(f"⚠️ Poster {tmdb_id} not found locally.")
    return None

def remove_background(input_path: Path) -> Image.Image:
    """Uses Replicate (lucataco/remove-bg) to get a cutout."""
    print(f"✂️ Removing background for {input_path.name}...")
    try:
        output = replicate.run(
            "lucataco/remove-bg:95fcc2a26d3899cd6c2691c900465aaeff466285a65c14638cc5f36f34befaf1",
            input={"image": open(input_path, "rb")}
        )
        response = requests.get(output)
        return Image.open(BytesIO(response.content)).convert("RGBA")
    except Exception as e:
        print(f"❌ BG Removal failed: {e}")
        return Image.open(input_path).convert("RGBA") # Fallback

def draw_text_overlay(base_img: Image.Image, film: Dict, showtimes: List[Dict]) -> Image.Image:
    """Draws the minimalist showtime info on top of the art."""
    draw = ImageDraw.Draw(base_img)
    width, height = base_img.size
    
    # Load Font
    try:
        # Use a large size for title
        font_title = ImageFont.truetype(str(FONT_PATH), 60)
        font_info = ImageFont.truetype(str(FONT_PATH), 30)
    except:
        font_title = ImageFont.load_default()
        font_info = ImageFont.load_default()

    # Draw Title (Bottom Left)
    title = film.get('movie_title', 'Unknown Film')
    draw.text((50, height - 200), title, font=font_title, fill="white", stroke_width=2, stroke_fill="black")
    
    # Draw Showtimes (Bottom Left, below title)
    y_cursor = height - 130
    for s in showtimes[:3]: # Limit to 3 lines
        text = f"{s['cinema_name']}: {s['showtime']}"
        draw.text((50, y_cursor), text, font=font_info, fill="white", stroke_width=1, stroke_fill="black")
        y_cursor += 40

    return base_img

# --- MAIN GENERATOR LOGIC ---

def main():
    print("🎬 Starting Infinite Cinemascape Generator (SDXL Edition)...")

    # 1. Load Data
    if not SHOWTIMES_PATH.exists():
        print("❌ showtimes.json not found!")
        return

    with open(SHOWTIMES_PATH, 'r') as f:
        data = json.load(f)
    
    # Group showtimes by movie to find the "Anchor Film"
    anchor_film = next((f for f in data if f.get('synopsis')), data[0])
    print(f"🎥 Anchor Film: {anchor_film['movie_title']}")
    
    # 2. Art Direction
    director = ArtDirector(GEMINI_API_KEY)
    vision = director.dream_scene(
        anchor_film['movie_title'], 
        anchor_film.get('synopsis', 'A film in Tokyo.')
    )
    print(f"🎨 Visual Prompt: {vision['visual_prompt']}")
    
    # 3. Grid Calculation
    grid = GridManager()
    entry_x = grid.get_entry_point()
    exit_x = random.uniform(0.2, 0.8)
    print(f"🔗 Grid Line: Start {entry_x:.2f} -> End {exit_x:.2f}")

    # 4. Prepare Canvas & Mask
    W, H = 1080, 1350 # IG Portrait
    canvas = Image.new("RGB", (W, H), (0, 0, 0)) # Black base
    mask = Image.new("L", (W, H), 255) # White (255) = Inpaint Area
    
    # 5. Place Asset (Using HORIZONTAL Backdrop)
    tmdb_id = anchor_film.get('tmdb_id')
    # --- CHANGE: Use Backdrop Path instead of Poster ---
    asset_suffix = anchor_film.get('tmdb_backdrop_path') 
    
    poster_placed = False
    
    if tmdb_id and asset_suffix:
        # Reuse download function (it works for backdrops too)
        asset_path = download_poster(tmdb_id, asset_suffix) 
        if asset_path:
            asset_img = remove_background(asset_path)
            
            # --- CHANGE: Wider Scaling for Horizontal Images ---
            # 16:9 image needs to be wider to make an impact. 
            # Let's use 95% of the canvas width.
            scale_factor = (W * 0.95) / asset_img.width
            new_size = (int(asset_img.width * scale_factor), int(asset_img.height * scale_factor))
            asset_img = asset_img.resize(new_size, Image.Resampling.LANCZOS)
            
            pos_x = (W - new_size[0]) // 2
            pos_y = (H - new_size[1]) // 2
            
            # Paste onto Canvas
            canvas.paste(asset_img, (pos_x, pos_y), asset_img)
            
            # Update Mask
            mask_draw = ImageDraw.Draw(mask)
            asset_alpha = asset_img.split()[3]
            protection_mask = ImageOps.invert(asset_alpha)
            mask.paste(protection_mask, (pos_x, pos_y), asset_alpha)
            poster_placed = True
            
    if not poster_placed:
        print("⚠️ Proceeding without asset cutout.")

    # 6. GENERATE (Inpainting)
    temp_canvas_path = "temp_canvas.png"
    temp_mask_path = "temp_mask.png"
    canvas.save(temp_canvas_path)
    mask.save(temp_mask_path)
    
    print("🚀 Sending to Stability AI (SDXL)...")
    try:
        output = replicate.run(
            "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
            input={
                "prompt": f"{vision['visual_prompt']}. A {vision['connection_element']} runs vertically through the composition from top to bottom. High quality, 8k.",
                "negative_prompt": "text, watermark, low quality, distorted, ugly, blurry text",
                "image": open(temp_canvas_path, "rb"),
                "mask": open(temp_mask_path, "rb"),
                "prompt_strength": 0.95, 
                "num_inference_steps": 40
            }
        )
        bg_url = output[0]
        print(f"✨ Background Generated: {bg_url}")
        
        # Download Result
        resp = requests.get(bg_url)
        final_img = Image.open(BytesIO(resp.content)).convert("RGB")
        
        # 8. Text Overlay
        final_img = draw_text_overlay(final_img, anchor_film, [anchor_film])
        
        # 9. Save Output
        output_filename = f"post_v3_image_01.png"
        final_img.save(OUTPUT_DIR / output_filename)
        print(f"💾 Saved final post to {output_filename}")
        
        # 10. Save Grid State
        grid.save_state(exit_x, anchor_film['movie_title'])
        print("✅ Grid State updated.")

    except Exception as e:
        print(f"❌ Generation failed: {e}")

if __name__ == "__main__":
    if not REPLICATE_API_TOKEN or not GEMINI_API_KEY:
        print("⚠️ Please set REPLICATE_API_TOKEN and GEMINI_API_KEY environment variables.")
    else:
        main()
