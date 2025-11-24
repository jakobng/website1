"""
generate_post3.py (Shortened Version)
-------------------------------------
Creates ONE AI-inpainted collage cover made from today's movie stills.

Pipeline:
1. Select N movie stills
2. Chaotic collage layout (no rotation, random jitter)
3. Build mask: black = stills, white = gaps
4. Send (image, mask) → Flux-Fill-Pro with prompt "cinema still"
5. Paste original stills back with soft drop shadow
6. Output: post_v2_image_00.png
"""

from __future__ import annotations
import os
import json
import random
import requests
from datetime import datetime
from pathlib import Path
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Replicate
try:
    import replicate
    REPLICATE_AVAILABLE = True
except ImportError:
    REPLICATE_AVAILABLE = False

BASE_DIR = Path(__file__).resolve().parent
STILLS_DIR = BASE_DIR / "stills"              # directory where your stills are placed
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"  # same data source as original

# Output
OUT_COVER_PATH = BASE_DIR / "post_v2_image_00.png"

# Canvas
W, H = 1080, 1350

# How many stills to use
NUM_STILLS = 7


# ---------------------------------------------------
# Helpers
# ---------------------------------------------------

def load_showtimes():
    with open(SHOWTIMES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def get_today_str():
    now = datetime.now()
    return now.strftime("%Y-%m-%d")

def pick_stills_for_today(showtimes):
    """
    Select up to NUM_STILLS stills using the same logic
    as your old generate_post2.py file.
    """
    candidates = []

    for s in showtimes:
        # 1. First preference: local downloaded image path
        local = s.get("image_local_path")
        if local:
            p = BASE_DIR / local
            if p.exists():
                candidates.append(p)
                continue

        # 2. Second: s.get("still") (older naming)
        still = s.get("still")
        if still:
            p = STILLS_DIR / still
            if p.exists():
                candidates.append(p)
                continue

        # 3. Third: s.get("still_path") (rare)
        still2 = s.get("still_path")
        if still2:
            p = STILLS_DIR / still2
            if p.exists():
                candidates.append(p)
                continue

    random.shuffle(candidates)
    return candidates[:NUM_STILLS]


# ---------------------------------------------------
# 1. Create chaotic layout & mask
# ---------------------------------------------------

def create_layout_and_mask(still_paths):
    layout_rgba = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    layout_rgb  = Image.new("RGB",  (W, H), (0, 0, 0))
    mask        = Image.new("L",    (W, H), 255)

    # Anchor points (compact)
    anchors = [
        (W*0.25, H*0.25),
        (W*0.75, H*0.25),
        (W*0.25, H*0.55),
        (W*0.75, H*0.55),
        (W*0.50, H*0.75),
        (W*0.33, H*0.40),
        (W*0.66, H*0.40),
    ]
    random.shuffle(anchors)

    for i, path in enumerate(still_paths):
        img = Image.open(path).convert("RGBA")

        # Resize keeping recognisability
        max_dim = random.randint(420, 620)
        w0, h0 = img.size
        if w0 >= h0:
            new_w = max_dim
            new_h = int(h0 * max_dim / w0)
        else:
            new_h = max_dim
            new_w = int(w0 * max_dim / h0)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # Position
        cx, cy = anchors[i % len(anchors)]
        x = int(cx + random.randint(-60, 60) - new_w/2)
        y = int(cy + random.randint(-60, 60) - new_h/2)

        # Paste into layout
        layout_rgba.alpha_composite(img, dest=(x, y))

        tmp = Image.new("RGB", (new_w, new_h), (0,0,0))
        tmp.paste(img, mask=img.split()[-1])
        layout_rgb.paste(tmp, (x, y))

        # Update mask (black = still)
        m = Image.new("L", (new_w, new_h), 0)
        m.paste(img.split()[-1], (0,0))
        mask.paste(0, (x, y), m)

    # Expand mask for inpainting freedom
    mask = mask.filter(ImageFilter.MaxFilter(31))

    return layout_rgba, layout_rgb, mask


# ---------------------------------------------------
# 2. Inpainting via Flux-Fill-Pro
# ---------------------------------------------------

def inpaint_with_flux(layout_rgb: Image.Image, mask: Image.Image) -> Image.Image:
    if not REPLICATE_AVAILABLE or not os.getenv("REPLICATE_API_TOKEN"):
        print("⚠️ No Replicate token or library. Skipping inpaint.")
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
                "mask":  open(temp_msk, "rb"),
                "prompt": "cinema still",
                "steps": 45,
                "guidance": 18,
                "output_format": "png",
                "prompt_upsampling": False,
                "safety_tolerance": 2,
            }
        )

        if temp_img.exists(): temp_img.unlink()
        if temp_msk.exists(): temp_msk.unlink()

        if output:
            url = output[0] if isinstance(output, list) else output
            r = requests.get(url)
            if r.status_code == 200:
                out = Image.open(BytesIO(r.content)).convert("RGB")
                return out.resize((W, H), Image.Resampling.LANCZOS)

    except Exception as e:
        print("⚠️ Flux error:", e)

    return layout_rgb


# ---------------------------------------------------
# 3. Paste-back + save
# ---------------------------------------------------

def build_final_image(inpainted_bg: Image.Image, layout_rgba: Image.Image):
    print("🧱 Compositing final cover...")
    base = inpainted_bg.convert("RGBA")

    # Soft shadow
    alpha = layout_rgba.split()[-1]
    shadow = alpha.filter(ImageFilter.GaussianBlur(14))
    sh = Image.new("RGBA", (W, H), (0,0,0,160))
    base = Image.alpha_composite(base, Image.composite(sh, Image.new("RGBA",(W,H)), shadow))

    # Paste original crisp stills
    out = Image.alpha_composite(base, layout_rgba)
    return out.convert("RGB")


# ---------------------------------------------------
# MAIN
# ---------------------------------------------------

def main():
    show = load_showtimes()
    stills = pick_stills_for_today(show)

    if not stills:
        print("No stills available.")
        return

    layout_rgba, layout_rgb, mask = create_layout_and_mask(stills)
    inpainted = inpaint_with_flux(layout_rgb, mask)
    final_img = build_final_image(inpainted, layout_rgba)

    final_img.save(OUT_COVER_PATH, format="PNG")
    print("✅ Saved:", OUT_COVER_PATH)


if __name__ == "__main__":
    main()
