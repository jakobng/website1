"""
generate_post3.py
-----------------
Creates ONE AI-inpainted collage cover made from today's movie stills (TMDB backdrops).

Pipeline:
1. Load today's films from showtimes.json (same logic as generate_post2.py).
2. Download TMDB backdrops for selected films.
3. Chaotic collage layout on 1080x1350.
4. Build mask: black = stills, white = gaps, dilated for freedom.
5. Send (image, mask) -> FLUX-FILL-PRO with prompt "cinema still".
6. Paste original stills back on top with soft shadow.
7. Save as post_v2_image_00.png
"""

from __future__ import annotations

import os
import json
import random
import requests
from datetime import datetime
from pathlib import Path
from io import BytesIO

from PIL import Image, ImageFilter

# --- Replicate setup ---
try:
    import replicate
    REPLICATE_AVAILABLE = True
except ImportError:
    REPLICATE_AVAILABLE = False

REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")

# --- Paths / constants ---
BASE_DIR = Path(__file__).resolve().parent
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"
OUT_COVER_PATH = BASE_DIR / "cinema-scrapers" / "post_v2_image_00.png"

CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350
NUM_STILLS = 7  # number of films/stills to include in collage


# ---------------------------------------------------
# Helpers for showtimes & film selection
# ---------------------------------------------------

def get_today_str() -> str:
    """Return today's date in YYYY-MM-DD (matches date_text in showtimes.json)."""
    return datetime.now().strftime("%Y-%m-%d")


def load_showtimes() -> list[dict]:
    if not SHOWTIMES_PATH.exists():
        print(f"showtimes.json not found at {SHOWTIMES_PATH}")
        return []
    with open(SHOWTIMES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def select_films_for_today(showtimes: list[dict], max_films: int) -> list[dict]:
    """
    Mimics the film selection logic from the original generate_post2.py:
    - Only entries for today.
    - Only entries that have tmdb_backdrop_path.
    - Group by tmdb_id (or movie_title as fallback).
    - Then pick up to max_films films at random.
    """
    date_str = get_today_str()
    films_map: dict[str, dict] = {}

    for item in showtimes:
        if item.get("date_text") != date_str:
            continue
        if not item.get("tmdb_backdrop_path"):
            continue

        key = item.get("tmdb_id") or item.get("movie_title")
        if key not in films_map:
            films_map[key] = dict(item)
            films_map[key]["showings"] = {}
        # we don't actually need showtimes for the cover, but we keep the structure

    films = list(films_map.values())
    random.shuffle(films)
    return films[:max_films]


# ---------------------------------------------------
# Image download
# ---------------------------------------------------

def download_backdrop(path: str) -> Image.Image | None:
    """
    Downloads a TMDB backdrop given its path (e.g. '/abc123.jpg').
    Same logic as generate_post2's download_image(). :contentReference[oaicite:2]{index=2}
    """
    if not path:
        return None
    if path.startswith("http"):
        url = path
    else:
        url = f"https://image.tmdb.org/t/p/w1280{path}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            return Image.open(BytesIO(resp.content)).convert("RGB")
    except Exception as e:
        print("   ⚠️ Error downloading image:", e)
    return None


# ---------------------------------------------------
# 1. Create chaotic layout & mask
# ---------------------------------------------------

def create_layout_and_mask(images: list[Image.Image]) -> tuple[Image.Image, Image.Image, Image.Image]:
    """
    Build:
      - layout_rgba: transparent composition of stills
      - layout_rgb: same but flattened on black
      - mask: white = gaps, black = where stills are (dilated)
    """
    layout_rgba = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    layout_rgb = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0))
    mask = Image.new("L", (CANVAS_WIDTH, CANVAS_HEIGHT), 255)

    # Anchor positions, reasonably tight cluster
    anchors = [
        (CANVAS_WIDTH * 0.25, CANVAS_HEIGHT * 0.25),
        (CANVAS_WIDTH * 0.75, CANVAS_HEIGHT * 0.25),
        (CANVAS_WIDTH * 0.25, CANVAS_HEIGHT * 0.55),
        (CANVAS_WIDTH * 0.75, CANVAS_HEIGHT * 0.55),
        (CANVAS_WIDTH * 0.50, CANVAS_HEIGHT * 0.78),
        (CANVAS_WIDTH * 0.33, CANVAS_HEIGHT * 0.40),
        (CANVAS_WIDTH * 0.66, CANVAS_HEIGHT * 0.40),
    ]
    random.shuffle(anchors)

    for i, img in enumerate(images):
        img = img.convert("RGBA")

        # Resize to keep stills legible
        max_dim = random.randint(420, 620)
        w0, h0 = img.size
        if w0 >= h0:
            new_w = max_dim
            new_h = int(h0 * max_dim / w0)
        else:
            new_h = max_dim
            new_w = int(w0 * max_dim / h0)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        cx, cy = anchors[i % len(anchors)]
        x = int(cx + random.randint(-60, 60) - new_w / 2)
        y = int(cy + random.randint(-60, 60) - new_h / 2)

        # Paste into RGBA layout
        layout_rgba.alpha_composite(img, dest=(x, y))

        # Paste into RGB layout
        tmp = Image.new("RGB", (new_w, new_h), (0, 0, 0))
        tmp.paste(img, mask=img.split()[-1])
        layout_rgb.paste(tmp, (x, y))

        # Update mask (black area where stills are)
        alpha = img.split()[-1]
        m = Image.new("L", (new_w, new_h), 0)
        m.paste(alpha, (0, 0))
        mask.paste(0, (x, y), m)

    # Dilate mask so inpainting can smoothly blend seams
    mask = mask.filter(ImageFilter.MaxFilter(31))
    return layout_rgba, layout_rgb, mask


# ---------------------------------------------------
# 2. Inpainting via Flux-Fill-Pro
# ---------------------------------------------------

def inpaint_with_flux(layout_rgb: Image.Image, mask: Image.Image) -> Image.Image:
    if not REPLICATE_AVAILABLE or not REPLICATE_API_TOKEN:
        print("⚠️ Replicate not available or token missing. Skipping inpaint.")
        return layout_rgb

    print("🎨 Inpainting gaps with FLUX-FILL-PRO ...")

    temp_img = BASE_DIR / "temp_flux_img.png"
    temp_msk = BASE_DIR / "temp_flux_mask.png"
    layout_rgb.save(temp_img, format="PNG")
    mask.save(temp_msk, format="PNG")

    try:
        output = replicate.run(
            "black-forest-labs/flux-fill-pro",
            input={
                "image": open(temp_img, "rb"),
                "mask": open(temp_msk, "rb"),
                "prompt": "cinema still",
                "steps": 45,
                "guidance": 18,
                "output_format": "png",
                "prompt_upsampling": False,
                "safety_tolerance": 2,
            },
        )

        if temp_img.exists():
            temp_img.unlink()
        if temp_msk.exists():
            temp_msk.unlink()

        if output:
            url = output[0] if isinstance(output, list) else output
            r = requests.get(url)
            if r.status_code == 200:
                out = Image.open(BytesIO(r.content)).convert("RGB")
                return out.resize((CANVAS_WIDTH, CANVAS_HEIGHT), Image.Resampling.LANCZOS)

        print("⚠️ Flux returned no image, using original layout.")
        return layout_rgb

    except Exception as e:
        print("⚠️ Flux error:", e)
        return layout_rgb


# ---------------------------------------------------
# 3. Paste-back and save
# ---------------------------------------------------

def build_final_image(inpainted_bg: Image.Image, layout_rgba: Image.Image) -> Image.Image:
    print("🧱 Compositing final cover...")
    base = inpainted_bg.convert("RGBA")

    # Soft shadow from alpha
    alpha = layout_rgba.split()[-1]
    shadow_mask = alpha.filter(ImageFilter.GaussianBlur(14))
    shadow_layer = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 160))
    base = Image.alpha_composite(
        base,
        Image.composite(shadow_layer, Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT)), shadow_mask),
    )

    # Paste original crisp stills
    out = Image.alpha_composite(base, layout_rgba)
    return out.convert("RGB")


# ---------------------------------------------------
# MAIN
# ---------------------------------------------------

def main():
    showtimes = load_showtimes()
    if not showtimes:
        return

    films = select_films_for_today(showtimes, NUM_STILLS)
    if not films:
        print("No films found for today with tmdb_backdrop_path.")
        return

    images = []
    print(f"Selected {len(films)} films for collage.")
    for f in films:
        path = f.get("tmdb_backdrop_path")
        img = download_backdrop(path)
        if img:
            images.append(img)

    if not images:
        print("No backdrops could be downloaded.")
        return

    layout_rgba, layout_rgb, mask = create_layout_and_mask(images)
    inpainted = inpaint_with_flux(layout_rgb, mask)
    final_img = build_final_image(inpainted, layout_rgba)
    final_img.save(OUT_COVER_PATH, format="PNG")
    print("✅ Saved cover:", OUT_COVER_PATH)


if __name__ == "__main__":
    main()
