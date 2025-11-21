"""
Generate Instagram-ready image carousel (V2 - Featured Films).
Design: Clean "Dark Mode" Cinematic Cards. No sunbursts.
Structure: 
  - Slide 0: Cover (Daily Digest Title)
  - Slides 1-9: Featured Films (Image Top, Info Bottom)
"""
from __future__ import annotations

import json
import random
import textwrap
import os
import glob
import requests
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"
BOLD_FONT_PATH = BASE_DIR / "NotoSansJP-Bold.ttf"
REGULAR_FONT_PATH = BASE_DIR / "NotoSansJP-Regular.ttf"
OUTPUT_CAPTION_PATH = BASE_DIR / "post_v2_caption.txt"

# Layout Dimensions (Instagram Portrait 4:5)
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350

# Ratios
IMAGE_HEIGHT = 750  # Top ~55%
TEXT_HEIGHT = 600   # Bottom ~45%

# Colors
COLOR_BG = (26, 26, 26)      # Dark Matte Grey/Black
COLOR_TEXT = (255, 255, 255) # White
COLOR_ACCENT = (255, 210, 0) # Your Brand Yellow
COLOR_SUBTEXT = (180, 180, 180) # Light Grey

# Padding
MARGIN = 60

# --- Data Loading & Processing ---

def get_today_str():
    """Returns YYYY-MM-DD for today (server local time)."""
    return datetime.now().strftime("%Y-%m-%d")

def load_todays_films():
    """
    Loads showtimes, filters for today, and groups them by Movie Title.
    ONLY includes films that have a 'tmdb_backdrop_path'.
    """
    target_date = get_today_str()
    
    if not SHOWTIMES_PATH.exists():
        print("showtimes.json not found.")
        return []

    with open(SHOWTIMES_PATH, 'r', encoding='utf-8') as f:
        all_data = json.load(f)

    # Group by Film Title
    grouped_films = {}
    
    for entry in all_data:
        # 1. Filter by Date
        if entry.get("date_text") != target_date:
            continue
            
        # 2. Filter: Must have an image
        if not entry.get("tmdb_backdrop_path"):
            continue

        title = entry.get("movie_title")
        if not title: continue

        if title not in grouped_films:
            grouped_films[title] = {
                "title": title,
                "en_title": entry.get("movie_title_en") or entry.get("tmdb_original_title"),
                "backdrop_path": entry.get("tmdb_backdrop_path"),
                "synopsis": entry.get("synopsis", ""),
                "showings": defaultdict(list) # { "Cinema Name": ["10:00", "12:00"] }
            }
        
        # Add showing info
        cinema = entry.get("cinema_name", "Unknown")
        time_str = entry.get("showtime")
        if time_str:
            grouped_films[title]["showings"][cinema].append(time_str)

    # Convert to list and sort times
    film_list = list(grouped_films.values())
    for film in film_list:
        for cinema in film["showings"]:
            film["showings"][cinema].sort()
            
    return film_list

# --- Image Processing Helpers ---

def download_image(backdrop_path):
    """Downloads image from TMDB and returns PIL Image."""
    url = f"https://image.tmdb.org/t/p/w1280{backdrop_path}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return Image.open(BytesIO(resp.content)).convert("RGB")
    except Exception as e:
        print(f"Error downloading {url}: {e}")
    return None

def crop_center(pil_img, crop_width, crop_height):
    """Crops the center of the image to fit dimensions."""
    img_width, img_height = pil_img.size
    return pil_img.crop(((img_width - crop_width) // 2,
                         (img_height - crop_height) // 2,
                         (img_width + crop_width) // 2,
                         (img_height + crop_height) // 2))

def resize_for_header(pil_img):
    """Resizes image to fill the width (1080) and height (750)."""
    img_ratio = pil_img.width / pil_img.height
    target_ratio = CANVAS_WIDTH / IMAGE_HEIGHT

    if img_ratio > target_ratio:
        # Image is wider than target: resize by height, crop width
        new_height = IMAGE_HEIGHT
        new_width = int(new_height * img_ratio)
    else:
        # Image is taller than target: resize by width, crop height
        new_width = CANVAS_WIDTH
        new_height = int(new_width / img_ratio)

    pil_img = pil_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    return crop_center(pil_img, CANVAS_WIDTH, IMAGE_HEIGHT)

# --- Drawing Functions ---

def get_fonts():
    """Returns dictionary of fonts."""
    try:
        return {
            "header": ImageFont.truetype(str(BOLD_FONT_PATH), 80),
            "title": ImageFont.truetype(str(BOLD_FONT_PATH), 55),
            "sub_title": ImageFont.truetype(str(REGULAR_FONT_PATH), 30),
            "synopsis": ImageFont.truetype(str(REGULAR_FONT_PATH), 28),
            "cinema_bold": ImageFont.truetype(str(BOLD_FONT_PATH), 32),
            "time_reg": ImageFont.truetype(str(REGULAR_FONT_PATH), 32),
            "date": ImageFont.truetype(str(BOLD_FONT_PATH), 40),
        }
    except:
        # Fallback if custom fonts missing
        default = ImageFont.load_default()
        return {k: default for k in ["header", "title", "sub_title", "synopsis", "cinema_bold", "time_reg", "date"]}

def draw_film_card(film_data, fonts, image_obj, is_cover=False):
    """Draws a single slide."""
    
    # 1. Setup Canvas
    canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), COLOR_BG)
    draw = ImageDraw.Draw(canvas)

    # 2. Place Image (Top Section)
    if image_obj:
        header_img = resize_for_header(image_obj)
        canvas.paste(header_img, (0, 0))

    # 3. Draw Text (Bottom Section)
    # Start Y position for text
    cursor_y = IMAGE_HEIGHT + 50 
    left_x = MARGIN
    
    if is_cover:
        # --- COVER SLIDE DESIGN ---
        # Darken the image for cover text visibility
        overlay = Image.new("RGBA", (CANVAS_WIDTH, IMAGE_HEIGHT), (0,0,0,120))
        canvas.paste(overlay, (0,0), overlay)
        draw = ImageDraw.Draw(canvas) # Re-init draw after paste

        # Big Title over Image
        cx = CANVAS_WIDTH // 2
        cy = IMAGE_HEIGHT // 2
        draw.text((cx, cy - 60), "TOKYO\nMINI THEATERS", font=fonts["header"], fill=COLOR_TEXT, anchor="mm", align="center")
        
        # Bottom info
        today_disp = datetime.now().strftime("%Y.%m.%d")
        draw.text((left_x, cursor_y), "TODAY'S SELECTION", font=fonts["sub_title"], fill=COLOR_ACCENT)
        draw.text((left_x, cursor_y + 50), f"{today_disp} の上映作品", font=fonts["header"], fill=COLOR_TEXT)
        draw.text((left_x, cursor_y + 160), "厳選9作品をチェック →", font=fonts["title"], fill=COLOR_SUBTEXT)

    else:
        # --- FILM SLIDE DESIGN ---
        
        # A. Yellow Accent Bar
        draw.rectangle([(left_x, cursor_y + 5), (left_x + 8, cursor_y + 65)], fill=COLOR_ACCENT)
        text_indent = 30

        # B. Title (Wrap if needed)
        title_text = film_data["title"]
        wrapped_title = textwrap.wrap(title_text, width=19) # Adjust width based on font
        for line in wrapped_title:
            draw.text((left_x + text_indent, cursor_y), line, font=fonts["title"], fill=COLOR_TEXT)
            cursor_y += 70
        
        # C. English Title (Optional)
        en_title = film_data.get("en_title")
        if en_title and en_title != "None":
            cursor_y += 5
            draw.text((left_x + text_indent, cursor_y), en_title, font=fonts["sub_title"], fill=COLOR_SUBTEXT)
            cursor_y += 45

        # D. Synopsis (Truncated)
        cursor_y += 20
        synopsis = film_data.get("synopsis", "")
        if synopsis:
            if len(synopsis) > 70: synopsis = synopsis[:70] + "..."
            wrapped_syn = textwrap.wrap(synopsis, width=40)
            for line in wrapped_syn:
                draw.text((left_x, cursor_y), line, font=fonts["synopsis"], fill=COLOR_SUBTEXT)
                cursor_y += 40

        # E. Divider
        cursor_y += 20
        draw.line([(left_x, cursor_y), (CANVAS_WIDTH - MARGIN, cursor_y)], fill=(60, 60, 60), width=2)
        cursor_y += 30

        # F. Showtimes
        for cinema, times in film_data["showings"].items():
            # Check if we are running out of space
            if cursor_y > CANVAS_HEIGHT - 80:
                break
                
            draw.text((left_x, cursor_y), f"📍 {cinema}", font=fonts["cinema_bold"], fill=COLOR_TEXT)
            
            # Show times below cinema name
            times_str = " / ".join(times)
            draw.text((left_x + 40, cursor_y + 45), times_str, font=fonts["time_reg"], fill=COLOR_ACCENT)
            
            cursor_y += 100 # Spacing for next cinema

    return canvas

# --- Main Execution ---

def main():
    print("--- Starting V2 Post Generation (Simple Dark Mode) ---")
    
    # 1. Cleanup old files
    for f in glob.glob(str(BASE_DIR / "post_v2_*.png")): os.remove(f)

    # 2. Load Data
    films = load_todays_films()
    print(f"Found {len(films)} films with images for today.")

    if len(films) < 1:
        print("No films found. Exiting.")
        return

    # 3. Select Random 9
    random.shuffle(films)
    selected_films = films[:9]
    
    fonts = get_fonts()

    # 4. Generate Slides
    caption_text = f"🎥 {get_today_str()} Tokyo Mini-Theater Selection\n\n"

    # Slide 0: Cover (Using the image of the first film as background)
    print("Generating Cover Slide...")
    cover_img_data = download_image(selected_films[0]["backdrop_path"])
    if cover_img_data:
        cover_slide = draw_film_card(None, fonts, cover_img_data, is_cover=True)
        cover_slide.save(BASE_DIR / "post_v2_image_00.png")
    
    # Slides 1-9: Films
    for i, film in enumerate(selected_films):
        print(f"Generating Slide {i+1}: {film['title']}")
        
        # Download Image
        img_data = download_image(film["backdrop_path"])
        if not img_data:
            print("  -> Image download failed, skipping.")
            continue

        # Draw
        slide = draw_film_card(film, fonts, img_data, is_cover=False)
        slide.save(BASE_DIR / f"post_v2_image_{i+1:02}.png")

        # Append to Caption
        caption_text += f"🎬 {film['title']}\n"
        for cinema, times in film['showings'].items():
            caption_text += f"📍 {cinema} ({', '.join(times)})\n"
        caption_text += "\n"

    # 5. Save Caption
    caption_text += "詳細はプロフィールリンクから / Check Link in Bio for more.\n#東京ミニシアター #映画 #tokyocinema"
    with open(OUTPUT_CAPTION_PATH, "w", encoding="utf-8") as f:
        f.write(caption_text)

    print("Done! Created post_v2 images and caption.")

if __name__ == "__main__":
    main()
