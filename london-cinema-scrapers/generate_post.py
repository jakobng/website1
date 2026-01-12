"""
Generate Instagram-ready image carousel (Tokyo-style collages) for London showtimes.
"""
from __future__ import annotations

import json
import random
import re
import textwrap
import os
import requests
import difflib
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from io import BytesIO
import sys
import subprocess

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# --- Robust Auto-Install for Google GenAI ---
try:
    from google import genai
    from google.genai import types
except ImportError:
    print("📦 Library 'google-genai' not found. Installing...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "google-genai"])
        from google import genai
        from google.genai import types
    except Exception as e:
        print(f"⚠️ Critical: Failed to install 'google-genai'. Refinement will be skipped. Error: {e}")

# --- Timezone: London (UTC+0/+1 depending on DST) ---
LONDON_TZ = timezone(timedelta(hours=0))  # Will be handled by zoneinfo for DST

def today_in_london() -> datetime:
    """Returns London datetime."""
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("Europe/London"))

# --- API Setup ---
try:
    import replicate
    REPLICATE_AVAILABLE = True
except ImportError:
    print("⚠️ Replicate library not found. Run: pip install replicate")
    REPLICATE_AVAILABLE = False

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "ig_posts"
ASSETS_DIR = BASE_DIR / "cinema_assets"
CUTOUTS_DIR = ASSETS_DIR / "cutouts"  # Pre-cut cinema images with backgrounds removed

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SHOWTIMES_PATH = DATA_DIR / "showtimes.json"
OUTPUT_CAPTION_PATH = OUTPUT_DIR / "post_caption.txt"

# Font paths - use system fonts available on Ubuntu
BOLD_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
REGULAR_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# Secrets
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# --- Constants ---
MINIMUM_FILM_THRESHOLD = 3
INSTAGRAM_SLIDE_LIMIT = 8
MAX_FEED_VERTICAL_SPACE = 750
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350
MARGIN = 60
TITLE_WRAP_WIDTH = 30

# --- GLOBAL COLORS ---
WHITE = (255, 255, 255)
OFF_WHITE = (240, 240, 240)
LIGHT_GRAY = (230, 230, 230)
DARK_SHADOW = (0, 0, 0, 180)
CHARCOAL = (40, 40, 40)
ACCENT = (203, 64, 74)

# --- Database (London Cinemas) ---
CINEMA_ADDRESSES = {
    "BFI Southbank": "Belvedere Rd, London SE1 8XT",
    "Prince Charles Cinema": "7 Leicester Pl, London WC2H 7BY",
    "Rio Cinema": "107 Kingsland High St, London E8 2PB",
    "Genesis Cinema": "93-95 Mile End Rd, London E1 4UJ",
    "Barbican Cinema": "Silk St, London EC2Y 8DS",
    "Curzon Soho": "99 Shaftesbury Ave, London W1D 5DY",
    "Electric Cinema Portobello": "191 Portobello Rd, London W11 2ED",
    "Electric Cinema White City": "Television Centre, 101 Wood Ln, London W12 7FR",
    "ICA Cinema": "The Mall, St. James's, London SW1Y 5AH",
    "Ritzy Cinema": "Brixton Oval, Coldharbour Ln, London SW2 1JG",
    "Phoenix Cinema": "52 High Rd, London N2 9PJ",
    "Regent Street Cinema": "309 Regent St, London W1B 2UW",
    "Ciné Lumière": "17 Queensberry Pl, London SW7 2DT",
    "Close-Up Film Centre": "97 Sclater St, London E1 6HR",
    "Rich Mix": "35-47 Bethnal Green Rd, London E1 6LA",
    "The Castle Cinema": "64-66 Brooksby's Walk, London E9 6DA",
    "The Garden Cinema": "39-41 Parker St, London WC2B 5PQ",
    "The Lexi Cinema": "194B Chamberlayne Rd, London NW10 3JU",
    "ArtHouse Crouch End": "159A Tottenham Ln, London N8 9BT",
    "Chiswick Cinema": "2 Power Rd, London W4 5PY",
    "JW3 Cinema": "341-351 Finchley Rd, London NW3 6ET",
    "Bertha DocHouse": "Curzon Bloomsbury, Brunswick Centre, London WC1N 1AW",
    "David Lean Cinema": "Croydon Clocktower, Katharine St, Croydon CR9 1ET",
    "Sands Films Cinema Club": "82 St Marychurch St, London SE16 4HZ",
    "The Cinema in the Arches": "Cambridge Heath Rd, London E2 9PA",
    "The Nickel": "49 Greenwich High Rd, London SE10 8JL",
    "ActOne Cinema & Cafe": "1 Centre Way, Acton, London W3 7LH",
}

CINEMA_FILENAME_OVERRIDES = {
    "BFI Southbank": "bfi",
    "Prince Charles Cinema": "princecharles",
    "Rio Cinema": "rio",
    "Genesis Cinema": "genesis",
    "Barbican Cinema": "barbican",
    "Curzon Soho": "curzon",
    "Electric Cinema Portobello": "electric",
    "Electric Cinema White City": "electricwhitecity",
    "ICA Cinema": "ica",
    "Ritzy Cinema": "ritzy",
    "Phoenix Cinema": "phoenix",
    "Regent Street Cinema": "regentstreet",
    "Ciné Lumière": "cinelumiere",
    "Close-Up Film Centre": "closeup",
    "Rich Mix": "richmix",
    "The Castle Cinema": "castle",
    "The Garden Cinema": "garden",
    "The Lexi Cinema": "lexi",
    "ArtHouse Crouch End": "arthouse",
    "Chiswick Cinema": "chiswick",
    "JW3 Cinema": "jw3",
    "Bertha DocHouse": "dochouse",
    "David Lean Cinema": "davidlean",
    "Sands Films Cinema Club": "sands",
    "The Cinema in the Arches": "arches",
    "The Nickel": "nickel",
    "ActOne Cinema & Cafe": "actone",
}


# --- Utility Functions ---
def load_font(path: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def load_showtimes(today_str: str) -> list[dict]:
    try:
        with SHOWTIMES_PATH.open("r", encoding="utf-8") as handle:
            all_showings = json.load(handle)
    except FileNotFoundError:
        print(f"showtimes.json not found at {SHOWTIMES_PATH}")
        raise
    except json.JSONDecodeError as exc:
        print("Unable to decode showtimes.json")
        raise exc
    todays_showings = [show for show in all_showings if show.get("date_text") == today_str]
    return todays_showings


def format_listings(showings: list[dict]) -> list[dict[str, str | None]]:
    movies: defaultdict[str, list[str]] = defaultdict(list)
    for show in showings:
        title = show.get("movie_title_en") or show.get("movie_title") or "Untitled"
        time_str = show.get("showtime") or ""
        if time_str:
            movies[title].append(time_str)

    formatted = []
    for title, times in movies.items():
        times.sort()
        formatted.append({
            "title": title,
            "times": ", ".join(times),
            "first_showtime": times[0] if times else "23:59"
        })

    formatted.sort(key=lambda x: x['first_showtime'])
    return formatted


def segment_listings(listings: list[dict], max_height: int, spacing: dict[str, int]) -> list[list[dict]]:
    segmented_lists = []
    current_segment = []
    current_height = 0
    for listing in listings:
        required_height = spacing['title_line'] + spacing['time_line']
        if current_height + required_height > max_height:
            if current_segment:
                segmented_lists.append(current_segment)
                current_segment = [listing]
                current_height = required_height
            else:
                segmented_lists.append([listing])
                current_height = 0
        else:
            current_segment.append(listing)
            current_height += required_height
    if current_segment:
        segmented_lists.append(current_segment)
    return segmented_lists


def get_recently_featured(caption_path: Path) -> list[str]:
    if not caption_path.exists():
        return []
    try:
        content = caption_path.read_text(encoding="utf-8")
        names = re.findall(r"--- 【(.*?)】 ---", content)
        return names
    except Exception as e:
        print(f"   [WARN] Could not read previous caption: {e}")
        return []


# --- ASSET & REPLICATE LOGIC ---
def normalize_name(s):
    s = str(s).lower()
    return re.sub(r'[^a-z0-9]', '', s)


def get_cinema_image_path(cinema_name: str, use_cutouts: bool = True) -> Path | None:
    """
    Find cinema image path. If use_cutouts=True, prioritizes pre-cut images
    from cinema_assets/cutouts/ folder (with backgrounds already removed).
    """
    if cinema_name in CINEMA_FILENAME_OVERRIDES:
        target = CINEMA_FILENAME_OVERRIDES[cinema_name]
    else:
        target = normalize_name(cinema_name)

    if not target:
        return None

    # Try cutouts folder first if requested
    search_dirs = []
    if use_cutouts and CUTOUTS_DIR.exists():
        search_dirs.append(CUTOUTS_DIR)
    if ASSETS_DIR.exists():
        search_dirs.append(ASSETS_DIR)

    if not search_dirs:
        return None

    for search_dir in search_dirs:
        candidates = [f for f in search_dir.glob("*") if f.is_file()]
        exact_matches = []
        substring_matches = []
        fuzzy_matches = []

        for f in candidates:
            if f.suffix.lower() not in ['.jpg', '.jpeg', '.png']:
                continue
            f_name = normalize_name(f.stem)

            # Prioritize exact matches
            if f_name == target:
                exact_matches.append(f)
            # Then substring matches
            elif target in f_name or f_name in target:
                substring_matches.append(f)
            # Finally fuzzy matches
            else:
                ratio = difflib.SequenceMatcher(None, target, f_name).ratio()
                if ratio > 0.6:
                    fuzzy_matches.append(f)

        # Return in order of priority
        if exact_matches:
            return random.choice(exact_matches)
        elif substring_matches:
            return random.choice(substring_matches)
        elif fuzzy_matches:
            return random.choice(fuzzy_matches)

    return None


def convert_white_to_transparent(img: Image.Image, threshold: int = 240) -> Image.Image:
    """Convert white/near-white pixels to transparent for cutouts with white backgrounds."""
    img = img.convert("RGBA")
    data = img.getdata()
    new_data = []
    for item in data:
        # If pixel is white-ish (all RGB values above threshold), make transparent
        if item[0] > threshold and item[1] > threshold and item[2] > threshold:
            new_data.append((255, 255, 255, 0))
        else:
            new_data.append(item)
    img.putdata(new_data)
    return img


def create_layout_and_mask(cinemas: list[tuple[str, Path]], target_width: int, target_height: int) -> tuple[Image.Image, Image.Image, Image.Image]:
    width = target_width
    height = target_height
    layout_rgba = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    layout_rgb = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    mask = Image.new("L", (width, height), 255) # White = Inpaint

    imgs_to_process = cinemas[:4]
    if len(imgs_to_process) < 4:
        imgs_to_process = (imgs_to_process * 4)[:4]
    random.shuffle(imgs_to_process)

    anchors = [
        (random.randint(int(width * 0.15), int(width * 0.85)),
         random.randint(int(height * 0.15), int(height * 0.85)))
        for _ in range(4)
    ]

    for i, (name, path) in enumerate(imgs_to_process):
        try:
            raw = Image.open(path).convert("RGBA")
            cutout = convert_white_to_transparent(raw)
            bbox = cutout.getbbox()
            if bbox: cutout = cutout.crop(bbox)

            scale_variance = random.uniform(0.8, 1.1)
            max_dim = int(600 * scale_variance)
            cutout.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

            cx, cy = anchors[i]
            cx += random.randint(-50, 50)
            cy += random.randint(-50, 50)
            x = cx - (cutout.width // 2)
            y = cy - (cutout.height // 2)

            layout_rgba.paste(cutout, (x, y), mask=cutout)
            layout_rgb.paste(cutout, (x, y), mask=cutout)
            
            # Protect the image area
            alpha = cutout.split()[3]
            mask.paste(0, (x, y), mask=alpha)
            
        except Exception as e:
            print(f"Error processing cutout {name}: {e}")

    # Soften edges to encourage blending
    mask = mask.filter(ImageFilter.MaxFilter(9))
    mask = mask.filter(ImageFilter.GaussianBlur(15))
    
    return layout_rgba, layout_rgb.convert("RGB"), mask
def refine_hero_with_ai(pil_image, date_text, cinema_names=[]):
    print("   ✨ Refining Hero Collage (Gemini + Text Rendering)...")
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("   ⚠️ GEMINI_API_KEY not found. Skipping.")
            return pil_image

        client = genai.Client(api_key=api_key)
        prompt_text = (
            f"Refine this collage into a unified image. "
            f"Strictly preserve the layout, composition, and structures of the input image. "
            f"Do not add new buildings, objects, or architectural elements that are not present in the collage. "
            f"Your task is only to blend the edges and unify the lighting and textures so the cutouts look like a cohesive scene. "
            f"The image MUST include the title 'LONDON CINEMA' and the date '{date_text}'."
        )
        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=[prompt_text, pil_image],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            )
        )
        for part in response.parts:
            if part.inline_data:
                return Image.open(BytesIO(part.inline_data.data)).convert("RGB").resize(pil_image.size, Image.Resampling.LANCZOS)
        print("   ⚠️ No image returned from Gemini.")
        return pil_image
    except Exception as e:
        print(f"   ⚠️ Gemini Refinement Failed: {e}")
        return pil_image


def inpaint_gaps(layout_img: Image.Image, mask_img: Image.Image) -> Image.Image:
    if not REPLICATE_AVAILABLE or not REPLICATE_API_TOKEN:
        return layout_img

    print("   🎨 Inpainting gaps (Classic SD 1.5)...")
    try:
        # SD 1.5 works best at 512x768-ish. If we send 1080p, it gets confused.
        # We shrink it for the "Dreaming" phase, then upscale later.
        processing_size = (512, 640) # Aspect ratio roughly matches 1080x1350
        
        orig_size = layout_img.size
        small_layout = layout_img.resize(processing_size, Image.Resampling.LANCZOS)
        small_mask = mask_img.resize(processing_size, Image.Resampling.LANCZOS)

        temp_img_path = BASE_DIR / "temp_inpaint_img.png"
        temp_mask_path = BASE_DIR / "temp_inpaint_mask.png"
        small_layout.save(temp_img_path, format="PNG")
        small_mask.save(temp_mask_path, format="PNG")

        output = replicate.run(
            "stability-ai/stable-diffusion-inpainting:c28b92a7ecd66eee4aefcd8a94eb9e7f6c3805d5f06038165407fb5cb355ba67",
            input={
                "image": open(temp_img_path, "rb"),
                "mask": open(temp_mask_path, "rb"),
                "prompt": "surreal architectural mashup, unified dream structure, london cinema, seamless cinematic wide angle, fog, dramatic lighting, detailed",
                "negative_prompt": "white edges, collage, text, watermark, blurry, low res",
                "num_inference_steps": 40,
                "guidance_scale": 7.5,
                "strength": 1.0 
            }
        )
        
        if temp_img_path.exists(): os.remove(temp_img_path)
        if temp_mask_path.exists(): os.remove(temp_mask_path)
            
        if output:
            url = output[0] if isinstance(output, list) else output
            resp = requests.get(url)
            if resp.status_code == 200:
                img = Image.open(BytesIO(resp.content)).convert("RGB")
                # We return the small AI image. The main function will upscale it.
                return img
    except Exception as e:
        print(f"   ⚠️ Inpainting failed: {e}")
        
    return layout_img

def upscale_image(img: Image.Image) -> Image.Image:
    if not REPLICATE_AVAILABLE or not REPLICATE_API_TOKEN:
        return img
    
    print("   🚀 Upscaling (RealESRGAN)...")
    try:
        temp_path = BASE_DIR / "temp_to_upscale.png"
        img.save(temp_path, format="PNG")
        
        output = replicate.run(
            "nightmareai/real-esrgan:42fed1c4974146d4d2414e2be2c5277c7fcf05fcc3a73ab415c722d379caa961",
            input={
                "image": open(temp_path, "rb"),
                "scale": 2,
                "face_enhance": False
            }
        )
        
        if temp_path.exists():
            os.remove(temp_path)
            
        if output:
            url = output if isinstance(output, str) else output[0]
            resp = requests.get(url)
            if resp.status_code == 200:
                return Image.open(BytesIO(resp.content)).convert("RGB")
                
    except Exception as e:
        print(f"   ⚠️ Upscale failed: {e}")
    
    return img

def create_blurred_cinema_bg(cinema_name: str, width: int, height: int) -> Image.Image:
    # Use full images for backgrounds, not cutouts
    full_path = get_cinema_image_path(cinema_name, use_cutouts=False)
    base = Image.new("RGB", (width, height), (30, 30, 30))
    if not full_path or not full_path.exists():
        return base
    try:
        img = Image.open(full_path).convert("RGB")
        target_ratio = width / height
        img_ratio = img.width / img.height
        if img_ratio > target_ratio:
            new_width = int(img.height * target_ratio)
            left = (img.width - new_width) // 2
            img = img.crop((left, 0, left + new_width, img.height))
        else:
            new_height = int(img.width / target_ratio)
            top = (img.height - new_height) // 2
            img = img.crop((0, top, img.width, top + new_height))
        img = img.resize((width, height), Image.Resampling.LANCZOS)
        img = img.filter(ImageFilter.GaussianBlur(8))
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 120))
        img = img.convert("RGBA")
        img = Image.alpha_composite(img, overlay).convert("RGB")
        return img
    except Exception as e:
        print(f"Error creating background for {cinema_name}: {e}")
        return base


def draw_text_with_shadow(draw, xy, text, font, fill, shadow_color=DARK_SHADOW, offset=(3, 3), anchor=None):
    x, y = xy
    draw.text((x + offset[0], y + offset[1]), text, font=font, fill=shadow_color, anchor=anchor)
    draw.text((x, y), text, font=font, fill=fill, anchor=anchor)


def draw_cinema_slide(cinema_name: str, listings: list[dict], bg_template: Image.Image) -> Image.Image:
    img = bg_template.copy()
    draw = ImageDraw.Draw(img)
    try:
        title_font = load_font(BOLD_FONT_PATH, 55)
        regular_font = load_font(REGULAR_FONT_PATH, 34)
        small_font = load_font(REGULAR_FONT_PATH, 28)
        footer_font = load_font(REGULAR_FONT_PATH, 24)
    except Exception:
        raise

    content_left = MARGIN + 20
    y_pos = MARGIN + 40

    draw_text_with_shadow(draw, (content_left, y_pos), cinema_name, title_font, WHITE)
    y_pos += 70

    address = CINEMA_ADDRESSES.get(cinema_name, "")
    if address:
        draw_text_with_shadow(draw, (content_left, y_pos), f"📍 {address}", small_font, LIGHT_GRAY)
        y_pos += 60
    else:
        y_pos += 30

    draw.line([(MARGIN, y_pos), (CANVAS_WIDTH - MARGIN, y_pos)], fill=WHITE, width=3)
    y_pos += 40

    for listing in listings:
        wrapped_title = textwrap.wrap(f"■ {listing['title']}", width=TITLE_WRAP_WIDTH) or [f"■ {listing['title']}"]
        for line in wrapped_title:
            draw_text_with_shadow(draw, (content_left, y_pos), line, regular_font, WHITE)
            y_pos += 40
        if listing['times']:
            draw_text_with_shadow(draw, (content_left + 40, y_pos), listing["times"], regular_font, LIGHT_GRAY)
            y_pos += 55

    footer_text = "Full schedule online"
    draw_text_with_shadow(draw, (CANVAS_WIDTH // 2, CANVAS_HEIGHT - MARGIN - 20), footer_text, footer_font, LIGHT_GRAY, anchor="mm")
    return img


def render_simple_cover(target_date: datetime) -> Image.Image:
    """Fallback cover when no cinema images are available."""
    img = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), OFF_WHITE)
    draw = ImageDraw.Draw(img)
    title_font = load_font(BOLD_FONT_PATH, 72)
    subtitle_font = load_font(REGULAR_FONT_PATH, 40)
    date_font = load_font(BOLD_FONT_PATH, 44)

    title = "London Cinema Showtimes"
    subtitle = "Independent & repertory screenings"
    date_line = target_date.strftime("%A %d %B %Y")

    draw.text((MARGIN, 220), title, font=title_font, fill=CHARCOAL)
    draw.text((MARGIN, 330), subtitle, font=subtitle_font, fill=(90, 90, 90))
    draw.line((MARGIN, 420, CANVAS_WIDTH - MARGIN, 420), fill=ACCENT, width=4)
    draw.text((MARGIN, 470), date_line, font=date_font, fill=ACCENT)
    draw.text((MARGIN, CANVAS_HEIGHT - 140), "Swipe for today's listings", font=subtitle_font, fill=(90, 90, 90))
    return img


def write_caption_for_multiple_cinemas(date_str: str, all_featured_cinemas: list[dict]) -> None:
    header = f"🎬 London Cinema Showtimes ({date_str})\n"
    lines = [header]
    for item in all_featured_cinemas:
        cinema_name = item['cinema_name']
        address = CINEMA_ADDRESSES.get(cinema_name, "")
        lines.append(f"\n--- 【{cinema_name}】 ---")
        if address:
            lines.append(f"📍 {address}")
        for listing in item['listings']:
            lines.append(f"• {listing['title']}")

    footer = """
#LondonCinema #IndependentCinema #RepertoryCinema #FilmListings
Full schedule: link in bio
"""
    lines.append(footer)
    with OUTPUT_CAPTION_PATH.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> None:
    # 1. Setup
    today = today_in_london().date()
    today_str = today.isoformat()

    date_display = today.strftime("%d.%m.%Y")
    date_day = today.strftime("%a").upper()
    bilingual_date_str = f"{date_display} {date_day}"

    print(f"🕒 Generator Time (London): {today} (String: {today_str})")

    # Cleanup old images
    print("🧹 Cleaning old images...")
    if OUTPUT_DIR.exists():
        for f in OUTPUT_DIR.glob("post_image_*.png"):
            try:
                os.remove(f)
            except:
                pass
        for f in OUTPUT_DIR.glob("story_image_*.png"):
            try:
                os.remove(f)
            except:
                pass

    try:
        todays_showings = load_showtimes(today_str)
    except Exception as e:
        print(f"❌ Error loading showtimes: {e}")
        todays_showings = []

    if not todays_showings:
        print(f"❌ No showings found for date: {today_str}")
        return
    else:
        print(f"✅ Found {len(todays_showings)} showings for {today_str}")

    # 2. Group by Cinema
    grouped: defaultdict[str, list[dict]] = defaultdict(list)
    for show in todays_showings:
        if show.get("cinema_name"):
            grouped[show.get("cinema_name")].append(show)

    # 3. Selection Logic
    featured_names = get_recently_featured(OUTPUT_CAPTION_PATH)
    valid_cinemas = []
    for c_name, shows in grouped.items():
        if len(shows) >= MINIMUM_FILM_THRESHOLD:
            valid_cinemas.append(c_name)
    candidates = [c for c in valid_cinemas if c not in featured_names]
    if not candidates:
        candidates = valid_cinemas

    random.shuffle(candidates)
    selected_cinemas = candidates[:INSTAGRAM_SLIDE_LIMIT]

    if not selected_cinemas:
        print("No cinemas met criteria.")
        return

    # 4. Generate Images
    print(f"Generating for: {selected_cinemas}")

    # COVER - try collage first, fallback to simple
    cinema_images = []
    for c in selected_cinemas:
        if path := get_cinema_image_path(c):
            cinema_images.append((c, path))

    if cinema_images and len(cinema_images) >= 2:
        print("   🎨 Building Hero Collage...")
        layout_rgba, layout_rgb, mask = create_layout_and_mask(cinema_images, CANVAS_WIDTH, CANVAS_HEIGHT)
        
        # 1. Inpaint (Returns a smaller, creative SD 1.5 image)
        inpainted_small = inpaint_gaps(layout_rgb, mask) 
        
        # 2. Upscale (Makes it sharp and big)
        print("   🔍 Upscaling to high res...")
        upscaled_bg = upscale_image(inpainted_small)
        
        # Resize to fit exactly our canvas (Upscale might be slightly different size)
        final_bg = upscaled_bg.resize((CANVAS_WIDTH, CANVAS_HEIGHT), Image.Resampling.LANCZOS)

        # 3. Add Text
        print("   🔤 Applying text overlay...")
        final_cover = draw_hero_text_overlay(final_bg, bilingual_date_str)
        
        final_cover.save(OUTPUT_DIR / "post_image_00.png")

    # SLIDES
    slide_counter = 0
    all_featured_for_caption = []

    for cinema_name in selected_cinemas:
        if slide_counter >= 9:
            break

        shows = grouped[cinema_name]
        listings = format_listings(shows)
        segmented = segment_listings(listings, MAX_FEED_VERTICAL_SPACE, spacing={'title_line': 40, 'time_line': 55})
        bg_img = create_blurred_cinema_bg(cinema_name, CANVAS_WIDTH, CANVAS_HEIGHT)

        all_featured_for_caption.append({
            'cinema_name': cinema_name,
            'listings': [l for sublist in segmented for l in sublist]
        })

        for segment in segmented:
            if slide_counter >= 9:
                break
            slide_counter += 1
            slide_img = draw_cinema_slide(cinema_name, segment, bg_img)
            slide_img.save(OUTPUT_DIR / f"post_image_{slide_counter:02}.png")

    write_caption_for_multiple_cinemas(today_str, all_featured_for_caption)
    print(f"✅ Done. Generated {slide_counter + 1} slides.")


if __name__ == "__main__":
    main()
