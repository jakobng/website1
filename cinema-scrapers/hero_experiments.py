"""
Generate 5 experimental hero images using different collage approaches.
This is for comparing different methods to create surreal cinema architecture mashups.

Approaches:
1. img2img - Use collage as input, let SD reinterpret the whole image
2. Overlapping with gradient alpha - Cutouts overlap with feathered edges
3. Dense collage - Pack cutouts tightly, minimal gaps to fill
4. ControlNet edges - Use edge detection to guide generation
5. Two-pass - Generate base dream architecture, then overlay cutouts
"""
from __future__ import annotations

import json
import random
import re
import os
import requests
import difflib
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from io import BytesIO
import sys
import subprocess

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

# --- Robust Auto-Install for Google GenAI ---
try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Installing google-genai...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "google-genai"])
    from google import genai
    from google.genai import types

# --- API Setup ---
try:
    import replicate
    REPLICATE_AVAILABLE = True
except ImportError:
    print("Replicate not available")
    REPLICATE_AVAILABLE = False

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "ig_posts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SHOWTIMES_PATH = DATA_DIR / "showtimes.json"
ASSETS_DIR = BASE_DIR / "cinema_assets"
CUTOUTS_DIR = ASSETS_DIR / "cutouts"

REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350

JST = timezone(timedelta(hours=9))

def today_in_tokyo() -> datetime:
    return datetime.now(timezone.utc).astimezone(JST)

# --- Cinema Data ---
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
    "下北沢トリウッド": "Tollywood",
}

CINEMA_FILENAME_OVERRIDES = {
    "国立映画アーカイブ": "nfaj",
    "ポレポレ東中野": "polepole"
}

# --- Utility Functions ---
def normalize_name(s):
    s = str(s).lower()
    return re.sub(r'[^a-z0-9]', '', s)

def get_cinema_image_path(cinema_name: str) -> Path | None:
    if not ASSETS_DIR.exists(): return None
    if cinema_name in CINEMA_FILENAME_OVERRIDES:
        target = CINEMA_FILENAME_OVERRIDES[cinema_name]
    else:
        clean_name = CINEMA_ENGLISH_NAMES.get(cinema_name, "") or cinema_name
        target = normalize_name(clean_name).replace("cinema", "").replace("theatre", "").strip()
    if not target: return None
    candidates = list(ASSETS_DIR.glob("*"))
    matches = []
    for f in candidates:
        if f.suffix.lower() not in ['.jpg', '.jpeg', '.png']: continue
        f_name = normalize_name(f.stem)
        if target in f_name:
            matches.append(f)
        else:
            ratio = difflib.SequenceMatcher(None, target, f_name).ratio()
            if ratio > 0.6:
                matches.append(f)
    if matches:
        return random.choice(matches)
    return None

def get_cutout_path(cinema_name: str) -> Path | None:
    if not CUTOUTS_DIR.exists(): return None
    if cinema_name in CINEMA_FILENAME_OVERRIDES:
        target = CINEMA_FILENAME_OVERRIDES[cinema_name]
    else:
        clean_name = CINEMA_ENGLISH_NAMES.get(cinema_name, "") or cinema_name
        target = normalize_name(clean_name).replace("cinema", "").replace("theatre", "").strip()
    if not target: return None
    candidates = list(CUTOUTS_DIR.glob("*"))
    matches = []
    for f in candidates:
        if f.suffix.lower() not in ['.jpg', '.jpeg', '.png']: continue
        f_name = normalize_name(f.stem)
        if target in f_name:
            matches.append(f)
        else:
            ratio = difflib.SequenceMatcher(None, target, f_name).ratio()
            if ratio > 0.6:
                matches.append(f)
    if matches:
        return random.choice(matches)
    return None

def convert_white_to_transparent(img: Image.Image, threshold: int = 240) -> Image.Image:
    img = img.convert("RGBA")
    data = img.getdata()
    new_data = []
    for item in data:
        if item[0] > threshold and item[1] > threshold and item[2] > threshold:
            new_data.append((255, 255, 255, 0))
        else:
            new_data.append(item)
    img.putdata(new_data)
    return img

def load_showtimes(today_str: str) -> list[dict]:
    try:
        with SHOWTIMES_PATH.open("r", encoding="utf-8") as handle:
            all_showings = json.load(handle)
    except FileNotFoundError:
        return []
    todays_showings = [show for show in all_showings if show.get("date_text") == today_str]
    return todays_showings

def get_selected_cinemas(today_str: str) -> list[str]:
    """Get list of cinemas with showings today."""
    showings = load_showtimes(today_str)
    grouped = defaultdict(list)
    for show in showings:
        if show.get("cinema_name"):
            grouped[show.get("cinema_name")].append(show)
    valid = [c for c, shows in grouped.items() if len(shows) >= 3]
    random.shuffle(valid)
    return valid[:8]

def get_cinema_images(cinemas: list[str]) -> list[tuple[str, Path]]:
    """Get image paths for cinemas, preferring cutouts."""
    result = []
    for c in cinemas:
        if path := get_cutout_path(c):
            result.append((c, path))
        elif path := get_cinema_image_path(c):
            result.append((c, path))
    return result

# --- Approach 1: img2img (reinterpret whole collage) ---
def create_basic_collage(cinemas: list[tuple[str, Path]], width: int, height: int) -> Image.Image:
    """Create a basic collage with random placement."""
    canvas = Image.new("RGB", (width, height), (240, 240, 240))
    imgs = cinemas[:4]
    if len(imgs) < 4:
        imgs = (imgs * 4)[:4]
    random.shuffle(imgs)

    for i, (name, path) in enumerate(imgs):
        try:
            raw = Image.open(path).convert("RGBA")
            cutout = convert_white_to_transparent(raw)
            bbox = cutout.getbbox()
            if bbox: cutout = cutout.crop(bbox)

            max_dim = int(550 * random.uniform(0.8, 1.1))
            cutout.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

            x = random.randint(int(width * 0.1), int(width * 0.9) - cutout.width)
            y = random.randint(int(height * 0.1), int(height * 0.9) - cutout.height)

            canvas.paste(cutout, (x, y), mask=cutout)
        except Exception as e:
            print(f"Error: {e}")
    return canvas

def approach_1_img2img(cinemas: list[tuple[str, Path]], width: int, height: int) -> Image.Image:
    """Use img2img to reinterpret the entire collage."""
    print("   [1/5] img2img approach...")
    collage = create_basic_collage(cinemas, width, height)

    if not REPLICATE_AVAILABLE or not REPLICATE_API_TOKEN:
        print("   Replicate not available, returning raw collage")
        return collage

    try:
        temp_path = BASE_DIR / "temp_img2img.png"
        collage.save(temp_path, format="PNG")

        output = replicate.run(
            "stability-ai/sdxl:7762fd07cf82c948538e41f63f77d685e02b063e37e496e96eefd46c929f9bdc",
            input={
                "image": open(temp_path, "rb"),
                "prompt": "surreal dream architecture, impossible cinema building, unified architectural monument, blend of art deco and brutalist styles, single cohesive structure, dramatic lighting, wide angle, 8k detailed",
                "negative_prompt": "collage, multiple buildings, split, divided, separate structures, text, watermark",
                "prompt_strength": 0.55,  # Lower = more faithful to input
                "num_inference_steps": 30,
                "guidance_scale": 7.5,
            }
        )
        if temp_path.exists(): os.remove(temp_path)

        if output:
            url = output[0] if isinstance(output, list) else output
            resp = requests.get(url)
            if resp.status_code == 200:
                return Image.open(BytesIO(resp.content)).convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
    except Exception as e:
        print(f"   img2img failed: {e}")

    return collage

# --- Approach 2: Overlapping cutouts with gradient alpha ---
def create_radial_gradient_mask(size: tuple[int, int]) -> Image.Image:
    """Create a radial gradient mask for feathered edges."""
    w, h = size
    mask = Image.new("L", (w, h), 0)
    center_x, center_y = w // 2, h // 2
    max_dist = ((w/2)**2 + (h/2)**2) ** 0.5

    for y in range(h):
        for x in range(w):
            dist = ((x - center_x)**2 + (y - center_y)**2) ** 0.5
            # Fade from 255 (center) to 0 (edges)
            alpha = int(255 * max(0, 1 - (dist / max_dist) ** 0.7))
            mask.putpixel((x, y), alpha)
    return mask

def approach_2_gradient_overlap(cinemas: list[tuple[str, Path]], width: int, height: int) -> Image.Image:
    """Overlapping cutouts with gradient alpha blending."""
    print("   [2/5] Gradient overlap approach...")
    canvas = Image.new("RGBA", (width, height), (200, 200, 200, 255))

    imgs = cinemas[:5]
    if len(imgs) < 5:
        imgs = (imgs * 5)[:5]
    random.shuffle(imgs)

    for i, (name, path) in enumerate(imgs):
        try:
            raw = Image.open(path).convert("RGBA")
            cutout = convert_white_to_transparent(raw)
            bbox = cutout.getbbox()
            if bbox: cutout = cutout.crop(bbox)

            # Larger size for more overlap
            max_dim = int(700 * random.uniform(0.9, 1.2))
            cutout.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

            # Create gradient mask and apply to alpha
            gradient = create_radial_gradient_mask(cutout.size)
            r, g, b, a = cutout.split()
            # Combine original alpha with gradient
            combined_alpha = Image.composite(a, Image.new("L", a.size, 0), gradient)
            cutout = Image.merge("RGBA", (r, g, b, combined_alpha))

            # Center-biased placement for more overlap
            x = random.randint(int(width * 0.15), int(width * 0.65))
            y = random.randint(int(height * 0.15), int(height * 0.65))

            canvas.paste(cutout, (x, y), mask=cutout)
        except Exception as e:
            print(f"Error: {e}")

    # Convert to RGB and run through SD for unification
    result = canvas.convert("RGB")

    if REPLICATE_AVAILABLE and REPLICATE_API_TOKEN:
        try:
            temp_path = BASE_DIR / "temp_gradient.png"
            result.save(temp_path, format="PNG")
            output = replicate.run(
                "stability-ai/sdxl:7762fd07cf82c948538e41f63f77d685e02b063e37e496e96eefd46c929f9bdc",
                input={
                    "image": open(temp_path, "rb"),
                    "prompt": "unified dream cinema architecture, single impossible building, art deco brutalist fusion, dramatic lighting",
                    "negative_prompt": "collage, separate buildings, divided, text",
                    "prompt_strength": 0.45,
                    "num_inference_steps": 25,
                }
            )
            if temp_path.exists(): os.remove(temp_path)
            if output:
                url = output[0] if isinstance(output, list) else output
                resp = requests.get(url)
                if resp.status_code == 200:
                    return Image.open(BytesIO(resp.content)).convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
        except Exception as e:
            print(f"   Gradient approach SD failed: {e}")

    return result

# --- Approach 3: Dense collage, minimal gaps ---
def approach_3_dense_collage(cinemas: list[tuple[str, Path]], width: int, height: int) -> Image.Image:
    """Pack cutouts densely with lots of overlap, minimal gaps."""
    print("   [3/5] Dense collage approach...")
    canvas = Image.new("RGBA", (width, height), (180, 180, 180, 255))

    imgs = cinemas[:6]
    if len(imgs) < 6:
        imgs = (imgs * 6)[:6]
    random.shuffle(imgs)

    # Grid-ish placement with heavy overlap
    positions = [
        (0.2, 0.2), (0.5, 0.15), (0.8, 0.25),
        (0.15, 0.6), (0.5, 0.55), (0.85, 0.65),
    ]

    for i, (name, path) in enumerate(imgs):
        try:
            raw = Image.open(path).convert("RGBA")
            cutout = convert_white_to_transparent(raw)
            bbox = cutout.getbbox()
            if bbox: cutout = cutout.crop(bbox)

            # Large cutouts for maximum coverage
            max_dim = int(650 * random.uniform(1.0, 1.3))
            cutout.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

            px, py = positions[i]
            x = int(width * px) - cutout.width // 2 + random.randint(-30, 30)
            y = int(height * py) - cutout.height // 2 + random.randint(-30, 30)

            canvas.paste(cutout, (x, y), mask=cutout)
        except Exception as e:
            print(f"Error: {e}")

    result = canvas.convert("RGB")

    # Light SD pass to smooth seams only
    if REPLICATE_AVAILABLE and REPLICATE_API_TOKEN:
        try:
            temp_path = BASE_DIR / "temp_dense.png"
            result.save(temp_path, format="PNG")
            output = replicate.run(
                "stability-ai/sdxl:7762fd07cf82c948538e41f63f77d685e02b063e37e496e96eefd46c929f9bdc",
                input={
                    "image": open(temp_path, "rb"),
                    "prompt": "seamless cinema architecture, unified building facade, smooth transitions, coherent style",
                    "negative_prompt": "collage edges, seams, separate pieces",
                    "prompt_strength": 0.35,  # Very light touch
                    "num_inference_steps": 20,
                }
            )
            if temp_path.exists(): os.remove(temp_path)
            if output:
                url = output[0] if isinstance(output, list) else output
                resp = requests.get(url)
                if resp.status_code == 200:
                    return Image.open(BytesIO(resp.content)).convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
        except Exception as e:
            print(f"   Dense approach SD failed: {e}")

    return result

# --- Approach 4: ControlNet with edge guidance ---
def extract_edges(img: Image.Image) -> Image.Image:
    """Extract edges from image for ControlNet guidance."""
    gray = img.convert("L")
    # Simple edge detection using PIL filters
    edges = gray.filter(ImageFilter.FIND_EDGES)
    # Enhance edges
    edges = edges.point(lambda x: 255 if x > 30 else 0)
    return edges

def approach_4_controlnet_edges(cinemas: list[tuple[str, Path]], width: int, height: int) -> Image.Image:
    """Use edge detection to guide generation of new architecture."""
    print("   [4/5] ControlNet edges approach...")

    # First create a collage
    collage = create_basic_collage(cinemas, width, height)
    edges = extract_edges(collage)

    if not REPLICATE_AVAILABLE or not REPLICATE_API_TOKEN:
        print("   Replicate not available")
        return collage

    try:
        temp_edges = BASE_DIR / "temp_edges.png"
        edges.save(temp_edges, format="PNG")

        # Use ControlNet with canny edges
        output = replicate.run(
            "jagilley/controlnet-canny:aff48af9c68d162388d230a2ab003f68d2638d88307bdaf1c2f1ac95079c9613",
            input={
                "image": open(temp_edges, "rb"),
                "prompt": "surreal dream cinema building, impossible architecture monument, art deco meets brutalism, unified single structure, dramatic cinematic lighting, architectural photography, 8k",
                "negative_prompt": "collage, multiple buildings, divided, split screen, text, watermark, low quality",
                "num_inference_steps": 30,
                "guidance_scale": 9,
            }
        )
        if temp_edges.exists(): os.remove(temp_edges)

        if output:
            url = output[0] if isinstance(output, list) else output
            resp = requests.get(url)
            if resp.status_code == 200:
                return Image.open(BytesIO(resp.content)).convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
    except Exception as e:
        print(f"   ControlNet failed: {e}")

    return collage

# --- Approach 5: Two-pass (base + overlay) ---
def approach_5_two_pass(cinemas: list[tuple[str, Path]], width: int, height: int) -> Image.Image:
    """Generate base dream architecture, then overlay cutouts with blending."""
    print("   [5/5] Two-pass approach...")

    cinema_names = [c[0] for c in cinemas[:4]]
    names_str = ", ".join([CINEMA_ENGLISH_NAMES.get(n, n) for n in cinema_names])

    # Pass 1: Generate base dream architecture from scratch
    base = Image.new("RGB", (width, height), (200, 200, 200))

    if REPLICATE_AVAILABLE and REPLICATE_API_TOKEN:
        try:
            output = replicate.run(
                "stability-ai/sdxl:7762fd07cf82c948538e41f63f77d685e02b063e37e496e96eefd46c929f9bdc",
                input={
                    "prompt": f"surreal impossible cinema building exterior, dream architecture monument to film, art deco and brutalist fusion, dramatic wide angle, cinematic lighting, inspired by Tokyo independent cinemas, 8k architectural photography",
                    "negative_prompt": "text, people, cars, realistic, multiple buildings",
                    "width": width,
                    "height": height,
                    "num_inference_steps": 30,
                    "guidance_scale": 8,
                }
            )
            if output:
                url = output[0] if isinstance(output, list) else output
                resp = requests.get(url)
                if resp.status_code == 200:
                    base = Image.open(BytesIO(resp.content)).convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
        except Exception as e:
            print(f"   Base generation failed: {e}")

    # Pass 2: Overlay cutouts with transparency blending
    canvas = base.convert("RGBA")

    imgs = cinemas[:3]
    if len(imgs) < 3:
        imgs = (imgs * 3)[:3]

    for i, (name, path) in enumerate(imgs):
        try:
            raw = Image.open(path).convert("RGBA")
            cutout = convert_white_to_transparent(raw)
            bbox = cutout.getbbox()
            if bbox: cutout = cutout.crop(bbox)

            max_dim = int(400 * random.uniform(0.8, 1.0))
            cutout.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

            # Add transparency to cutout for blending
            r, g, b, a = cutout.split()
            a = a.point(lambda x: int(x * 0.7))  # 70% opacity
            cutout = Image.merge("RGBA", (r, g, b, a))

            # Feather edges
            gradient = create_radial_gradient_mask(cutout.size)
            r, g, b, a = cutout.split()
            combined_alpha = Image.composite(a, Image.new("L", a.size, 0), gradient)
            cutout = Image.merge("RGBA", (r, g, b, combined_alpha))

            x = random.randint(int(width * 0.1), int(width * 0.7))
            y = random.randint(int(height * 0.1), int(height * 0.7))

            canvas.paste(cutout, (x, y), mask=cutout)
        except Exception as e:
            print(f"Error: {e}")

    result = canvas.convert("RGB")

    # Light unification pass
    if REPLICATE_AVAILABLE and REPLICATE_API_TOKEN:
        try:
            temp_path = BASE_DIR / "temp_twopass.png"
            result.save(temp_path, format="PNG")
            output = replicate.run(
                "stability-ai/sdxl:7762fd07cf82c948538e41f63f77d685e02b063e37e496e96eefd46c929f9bdc",
                input={
                    "image": open(temp_path, "rb"),
                    "prompt": "unified dream cinema architecture, cohesive lighting and style, single building",
                    "negative_prompt": "collage, separate pieces",
                    "prompt_strength": 0.25,  # Very light
                    "num_inference_steps": 15,
                }
            )
            if temp_path.exists(): os.remove(temp_path)
            if output:
                url = output[0] if isinstance(output, list) else output
                resp = requests.get(url)
                if resp.status_code == 200:
                    return Image.open(BytesIO(resp.content)).convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
        except Exception as e:
            print(f"   Two-pass unification failed: {e}")

    return result

# --- Gemini Refinement (optional final pass) ---
def refine_with_gemini(img: Image.Image, date_text: str, approach_name: str) -> Image.Image:
    """Optional Gemini refinement for text overlay."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return img

    try:
        client = genai.Client(api_key=api_key)
        prompt = (
            f"Refine this dream cinema architecture image. "
            f"Add the title 'TODAY'S CINEMA SELECTION' and date '{date_text}' elegantly. "
            f"Approach: {approach_name}. Unify lighting and make it cohesive."
        )
        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=[prompt, img],
            config=types.GenerateContentConfig(response_modalities=["IMAGE"])
        )
        for part in response.parts:
            if part.inline_data:
                return Image.open(BytesIO(part.inline_data.data)).convert("RGB").resize(img.size, Image.Resampling.LANCZOS)
    except Exception as e:
        print(f"   Gemini refinement failed: {e}")
    return img


def main():
    print("=" * 60)
    print("EXPERIMENTAL HERO IMAGE GENERATOR - 5 APPROACHES")
    print("=" * 60)

    today = today_in_tokyo().date()
    today_str = today.isoformat()
    date_display = f"{today.strftime('%Y.%m.%d')} {today.strftime('%a').upper()}"

    print(f"Date: {today_str}")

    # Get cinemas
    cinemas = get_selected_cinemas(today_str)
    if not cinemas:
        print("No cinemas found, using fallback images from assets")
        # Fallback: just use whatever images we have
        all_images = list(ASSETS_DIR.glob("*.jpg")) + list(ASSETS_DIR.glob("*.png"))
        cinemas = [(f.stem, f) for f in all_images[:8]]
    else:
        cinemas = get_cinema_images(cinemas)

    print(f"Using {len(cinemas)} cinema images")

    if len(cinemas) < 2:
        print("Not enough images to create collage")
        return

    # Generate all 5 approaches
    approaches = [
        ("01_img2img", approach_1_img2img),
        ("02_gradient_overlap", approach_2_gradient_overlap),
        ("03_dense_collage", approach_3_dense_collage),
        ("04_controlnet_edges", approach_4_controlnet_edges),
        ("05_two_pass", approach_5_two_pass),
    ]

    for name, func in approaches:
        print(f"\nGenerating: {name}")
        try:
            result = func(cinemas, CANVAS_WIDTH, CANVAS_HEIGHT)

            # Optional: Gemini refinement
            # result = refine_with_gemini(result, date_display, name)

            output_path = OUTPUT_DIR / f"hero_{name}.png"
            result.save(output_path)
            print(f"   Saved: {output_path}")
        except Exception as e:
            print(f"   FAILED: {e}")

    print("\n" + "=" * 60)
    print("DONE - Compare the 5 hero images in ig_posts/")
    print("=" * 60)


if __name__ == "__main__":
    main()
