"""
Generate Instagram-ready image carousel (V1 - "The Organic Mashup - Recognizable").
- Logic: 5 Cutouts -> Chaotic Layout -> Inpaint (Atmosphere) -> Paste Back with Shadow.
- Tweak: Reduced mask erosion and added drop shadow to keep cinemas recognizable.
"""
from __future__ import annotations

import json
import math
import random
import re
import textwrap
import os
import requests
import glob
import time
import colorsys
import difflib
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops, ImageOps

try:  
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

# --- API Setup ---
try:
    import replicate
    REPLICATE_AVAILABLE = True
except ImportError:
    print("⚠️ Replicate library not found. Run: pip install replicate")
    REPLICATE_AVAILABLE = False

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"
ASSETS_DIR = BASE_DIR / "cinema_assets"
BOLD_FONT_PATH = BASE_DIR / "NotoSansJP-Bold.ttf"
REGULAR_FONT_PATH = BASE_DIR / "NotoSansJP-Regular.ttf"
OUTPUT_CAPTION_PATH = BASE_DIR / "post_caption.txt"

# Secrets
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")

# Constants
MINIMUM_FILM_THRESHOLD = 3
INSTAGRAM_SLIDE_LIMIT = 10 
MAX_FEED_VERTICAL_SPACE = 750 
MAX_STORY_VERTICAL_SPACE = 1150
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350
STORY_CANVAS_HEIGHT = 1920
MARGIN = 60 
TITLE_WRAP_WIDTH = 30

# Inpainting backend configuration
INPAINT_BACKEND = "flux"        # "flux" or "stability"
INPAINT_MODE = "surreal"        # "surreal", "architectural", or "balanced"

# --- GLOBAL COLORS ---
SUNBURST_CENTER = (255, 210, 0) 
SUNBURST_OUTER = (255, 255, 255)
BLACK = (20, 20, 20)
GRAY = (30, 30, 30) 
WHITE = (255, 255, 255)

# --- Data Helpers (names, mappings, etc.) ---

CINEMA_LOCATIONS = {
    "ユーロスペース": "東京都渋谷区円山町1-5\n1-5 Maruyamacho, Shibuya-ku, Tokyo",
    "シアター・イメージフォーラム": "東京都渋谷区渋谷2-10-2\n2-10-2 Shibuya, Shibuya-ku, Tokyo",
    "ポレポレ東中野": "東京都中野区東中野4-4-1\n4-4-1 Higashi-Nakano, Nakano-ku, Tokyo",
    "ケイズシネマ": "東京都新宿区新宿3-35-13\n3-35-13 Shinjuku, Shinjuku-ku, Tokyo",
    "新宿シネマカリテ": "東京都新宿区新宿3-37-12\n3-37-12 Shinjuku, Shinjuku-ku, Tokyo",
    "テアトル新宿": "東京都新宿区新宿3-14-20\n3-14-20 Shinjuku, Shinjuku-ku, Tokyo",
    "新宿武蔵野館": "東京都新宿区新宿3-27-10\n3-27-10 Shinjuku, Shinjuku-ku, Tokyo",
    "シネマ・ジャック＆ベティ": "神奈川県横浜市中区若葉町3-51\n3-51 Wakabacho, Naka-ku, Yokohama",
    "アップリンク吉祥寺": "東京都武蔵野市吉祥寺本町1-5-1\n1-5-1 Kichijoji Honcho, Musashino-shi, Tokyo",
    "下高井戸シネマ": "東京都世田谷区松原3-27-26\n3-27-26 Matsubara, Setagaya-ku, Tokyo",
    "国立映画アーカイブ": "東京都中央区京橋3-7-6\n3-7-6 Kyobashi, Chuo-ku, Tokyo",
    "シネスイッチ銀座": "東京都中央区銀座4-4-5\n4-4-5 Ginza, Chuo-ku, Tokyo",
    "シネマヴェーラ渋谷": "東京都渋谷区円山町1-5\n1-5 Maruyamacho, Shibuya-ku, Tokyo",
    "ラピュタ阿佐ヶ谷": "東京都杉並区阿佐ヶ谷北2-12-21\n2-12-21 Asagayakita, Suginami-ku, Tokyo",
    "下高井戸シネマ": "東京都世田谷区松原3-30-15\n3-30-15 Matsubara, Setagaya-ku, Tokyo",
    "国立映画アーカイブ": "東京都中央区京橋3-7-6\n3-7-6 Kyobashi, Chuo-ku, Tokyo",
    "池袋シネマ・ロサ": "東京都豊島区西池袋1-37-12\n1-37-12 Nishi-Ikebukuro, Toshima-ku, Tokyo",
    "シネスイッチ銀座": "東京都中央区銀座4-4-5 3F\n3F, 4-4-5 Ginza, Chuo-ku, Tokyo",
    "シネマブルースタジオ": "東京都足立区千住3-92 2F\n2F, 3-92 Senju, Adachi-ku, Tokyo",
    "CINEMA Chupki TABATA": "東京都北区東田端2-14-4\n2-14-4 Higashitabata, Kita-ku, Tokyo",
    "シネクイント": "東京都渋谷区宇田川町20-11 8F\n8F, 20-11 Udagawacho, Shibuya-ku, Tokyo",
    "アップリンク吉祥寺": "東京都武蔵野市吉祥寺本町1-5-1 4F\n4F, 1-5-1 Kichijoji Honcho, Musashino-shi, Tokyo",
    "Tollywood": "東京都世田谷区代沢5-32-5 2F\n2F, 5-32-5 Daizawa, Setagaya-ku, Tokyo",
    "Morc阿佐ヶ谷": "東京都杉並区阿佐谷北2-12-19 B1F\nB1F, 2-12-19 Asagayakita, Suginami-ku, Tokyo"
}

CINEMA_ENGLISH_NAMES = {
    
    "ユーロスペース": "Eurospace",
    "シアター・イメージフォーラム": "Theatre Image Forum",
    "ポレポレ東中野": "Pole-Pole Higashinakano",
    "ケイズシネマ": "K's Cinema",
    "新宿シネマカリテ": "Shinjuku Cinema Qualite",
    "テアトル新宿": "Theatre Shinjuku",
    "新宿武蔵野館": "Shinjuku Musashinokan",
    "シネマ・ジャック＆ベティ": "Cinema Jack & Betty",
    "アップリンク吉祥寺": "Uplink Kichijoji",
    "下高井戸シネマ": "Shimo-Takaido Cinema",
    "国立映画アーカイブ": "National Film Archive of Japan",
    "シネスイッチ銀座": "Cine Switch Ginza",
    "シネマヴェーラ渋谷": "Cinema Vera Shibuya",
    "ラピュタ阿佐ヶ谷": "Laputa Asagaya",
    "池袋シネマ・ロサ": "Ikebukuro Cinema Rosa",
    "シネマブルースタジオ": "Cinema Blue Studio",
    "CINEMA Chupki TABATA": "Cinema Chupki Tabata",
    "シネクイント": "Cine Quint",
    "Tollywood": "Tollywood",
    "Morc阿佐ヶ谷": "Morc Asagaya"
}

# --- Utility Functions ---

def load_showtimes() -> list[dict]:
    if not SHOWTIMES_PATH.exists():
        raise FileNotFoundError(f"Showtimes file not found: {SHOWTIMES_PATH}")
    with open(SHOWTIMES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

def get_tokyo_today():
    if ZoneInfo:
        tz = ZoneInfo("Asia/Tokyo")
        now = datetime.now(tz)
    else:
        now = datetime.utcnow()
    return now

def get_today_strs():
    now = get_tokyo_today()
    yyyy_mm_dd = now.strftime("%Y-%m-%d")
    date_label = now.strftime("%Y.%m.%d")
    weekday_short = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"][now.weekday()]
    return yyyy_mm_dd, f"{date_label} {weekday_short}"

def normalize_title(title: str | None) -> str | None:
    if not title:
        return None
    title = re.sub(r"\s+", " ", title).strip()
    title = re.sub(r"[【】\[\]（）\(\)]", "", title)
    return title

def best_english_title(showing: dict) -> str | None:
    candidates = []
    for key in ("movie_title_en", "title_en", "tmdb_title_en", "letterboxd_title_en"):
        if showing.get(key):
            candidates.append(showing[key])
    for c in candidates:
        if c and not re.search(r"[ぁ-んァ-ン一-龯]", c):
            return normalize_title(c)
    return normalize_title(showing.get("movie_title"))

def group_by_cinema(showtimes: list[dict]) -> dict[str, list[dict]]:
    grouped = defaultdict(list)
    for s in showtimes:
        cinema = s.get("cinema_name")
        if cinema:
            grouped[cinema].append(s)
    return grouped

def pick_cinemas_for_today(grouped_showtimes: dict[str, list[dict]]) -> list[str]:
    items = [(cinema, len(showings)) for cinema, showings in grouped_showtimes.items()]
    items = [x for x in items if x[1] >= MINIMUM_FILM_THRESHOLD]
    items.sort(key=lambda x: x[1], reverse=True)
    if len(items) <= INSTAGRAM_SLIDE_LIMIT:
        return [c for c, _ in items]
    return [c for c, _ in items[:INSTAGRAM_SLIDE_LIMIT]]

def load_cinema_assets() -> dict[str, list[Path]]:
    assets = defaultdict(list)
    if not ASSETS_DIR.exists():
        print(f"⚠️ Assets directory missing: {ASSETS_DIR}")
        return assets
    for img_path in ASSETS_DIR.glob("*.jpg"):
        name = img_path.stem
        cinema_name = name.split("__")[0]
        assets[cinema_name].append(img_path)
    return assets

def pick_assets_for_cover(cinemas_today: list[str], assets_by_cinema: dict[str, list[Path]]) -> list[Path]:
    chosen_paths = []
    used_cinemas = set()
    for cname in cinemas_today:
        if cname in assets_by_cinema and assets_by_cinema[cname]:
            img_path = random.choice(assets_by_cinema[cname])
            if img_path not in chosen_paths:
                chosen_paths.append(img_path)
                used_cinemas.add(cname)
                if len(chosen_paths) >= 5:
                    return chosen_paths
    all_asset_paths = [p for paths in assets_by_cinema.values() for p in paths]
    random.shuffle(all_asset_paths)
    for p in all_asset_paths:
        if p not in chosen_paths:
            chosen_paths.append(p)
            if len(chosen_paths) >= 5:
                break
    return chosen_paths[:5]

def remove_bg_via_replicate(pil_img: Image.Image) -> Image.Image:
    """Isolates the subject using the previous lucataco/remove-bg version."""
    if not REPLICATE_AVAILABLE or not REPLICATE_API_TOKEN:
        print("   ⚠️ Replicate not available or token missing. Skipping BG removal.")
        return pil_img.convert("RGBA")

    try:
        temp_in = BASE_DIR / "temp_rembg_in.png"
        pil_img.save(temp_in, format="PNG")

        # NOTE: this is the original pinned version that used to work
        output = replicate.run(
            "lucataco/remove-bg:95fcc2a26d3899cd6c2691c900465aaeff466285a65c14638cc5f36f34befaf1",
            input={"image": open(temp_in, "rb")}
        )

        if temp_in.exists():
            os.remove(temp_in)

        if output:
            resp = requests.get(str(output))
            if resp.status_code == 200:
                img = Image.open(BytesIO(resp.content)).convert("RGBA")
                # Safety check: if alpha is all zero, fall back to original
                extrema = img.getextrema()
                if extrema[3][1] == 0:
                    return pil_img.convert("RGBA")
                return img

    except Exception as e:
        print(f"   ⚠️ Rembg failed: {e}. Using original.")

    return pil_img.convert("RGBA")


def center_crop_to_content(img: Image.Image, max_pad: int = 20) -> Image.Image:
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    bbox = img.getbbox()
    if bbox is None:
        return img
    left, upper, right, lower = bbox
    left = max(0, left - max_pad)
    upper = max(0, upper - max_pad)
    right = min(img.width, right + max_pad)
    lower = min(img.height, lower + max_pad)
    return img.crop((left, upper, right, lower))

def create_layout_and_mask(asset_paths: list[Path]) -> tuple[Image.Image, Image.Image, Image.Image]:
    print("🧩 Building chaotic layout from cutouts...")
    layout_rgba = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    layout_rgb = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0))
    mask = Image.new("L", (CANVAS_WIDTH, CANVAS_HEIGHT), 255)

    anchor_positions = [
        (CANVAS_WIDTH * 0.25, CANVAS_HEIGHT * 0.25),
        (CANVAS_WIDTH * 0.75, CANVAS_HEIGHT * 0.25),
        (CANVAS_WIDTH * 0.25, CANVAS_HEIGHT * 0.55),
        (CANVAS_WIDTH * 0.75, CANVAS_HEIGHT * 0.55),
        (CANVAS_WIDTH * 0.5,  CANVAS_HEIGHT * 0.78),
    ]
    random.shuffle(anchor_positions)
    processed_cutouts = []

    for i, img_path in enumerate(asset_paths[:5]):
        try:
            print(f"   Loading asset: {img_path.name}")
            base_img = Image.open(img_path).convert("RGB")
        except Exception as e:
            print(f"   ⚠️ Error loading {img_path}: {e}")
            continue

        rgba = remove_bg_via_replicate(base_img)
        rgba = center_crop_to_content(rgba, max_pad=10)

        max_dim = int(550 * random.uniform(0.7, 1.2))
        w, h = rgba.size
        if w >= h:
            new_w = max_dim
            new_h = int(h * max_dim / w)
        else:
            new_h = max_dim
            new_w = int(w * max_dim / h)
        rgba = rgba.resize((new_w, new_h), Image.Resampling.LANCZOS)

        cx, cy = anchor_positions[i]
        jitter_x = random.randint(-100, 100)
        jitter_y = random.randint(-80, 80)
        x = int(cx + jitter_x - new_w / 2)
        y = int(cy + jitter_y - new_h / 2)

        layout_rgba.alpha_composite(rgba, dest=(x, y))
        base_tmp = Image.new("RGB", (new_w, new_h), (0, 0, 0))
        base_tmp.paste(rgba, mask=rgba.split()[-1])
        layout_rgb.paste(base_tmp, (x, y))

        cutout_mask = Image.new("L", (new_w, new_h), 0)
        cutout_mask.paste(rgba.split()[-1], (0, 0))
        mask.paste(0, (x, y), cutout_mask)
        processed_cutouts.append((rgba, (x, y)))

    mask = mask.filter(ImageFilter.MaxFilter(11))
    layout_rgb = layout_rgb.convert("RGB")
    return layout_rgba, layout_rgb, mask

def build_inpaint_prompt(mode: str) -> str:
    """Builds text prompt for inpainting, with style modes."""
    base_constraints = (
        "no grid layout, no split screen, no frames, no borders, "
        "no collage panels, no text, no logo, no watermark"
    )

    if mode == "surreal":
        core = (
            "surreal multiplex interior built from fragments of Tokyo cinemas, "
            "floating awnings and marquees, overlapping balconies and corridors, "
            "impossible architecture, double exposure, ambient haze, "
            "light leaks, soft cinematic lighting, subtle film grain"
        )
    elif mode == "architectural":
        core = (
            "modern multi-screen cinema complex interior, unified architecture, "
            "concrete, brushed metal and glass, integrated cinema signage, "
            "wide atrium, escalators and skybridges, warm indirect lighting, "
            "highly detailed, photorealistic, ultra wide angle"
        )
    else:
        core = (
            "cinematic architectural montage, single unified cinema structure, "
            "fragments of Tokyo movie theaters assembled into one building, "
            "dreamlike but believable, atmospheric lighting, subtle haze, "
            "high detail, photo-real"
        )

    return f"{core}, {base_constraints}"


def inpaint_gaps(layout_img: Image.Image, mask_img: Image.Image) -> Image.Image:
    """Fill gaps between cinema cutouts using the selected inpaint model."""
    if not REPLICATE_AVAILABLE or not REPLICATE_API_TOKEN:
        print("   ⚠️ Replicate not available. Skipping Inpaint.")
        return layout_img

    prompt = build_inpaint_prompt(INPAINT_MODE)

    print(f"   🎨 Inpainting gaps (backend={INPAINT_BACKEND}, mode={INPAINT_MODE})...")
    # Save temporary files for Replicate
    temp_img_path = BASE_DIR / "temp_inpaint_img.png"
    temp_mask_path = BASE_DIR / "temp_inpaint_mask.png"
    layout_img.save(temp_img_path, format="PNG")
    mask_img.save(temp_mask_path, format="PNG")

    try:
        if INPAINT_BACKEND == "flux":
            # FLUX.1 Fill [pro]
            output = replicate.run(
                "black-forest-labs/flux-fill-pro",
                input={
                    "image": open(temp_img_path, "rb"),
                    "mask": open(temp_mask_path, "rb"),
                    "prompt": prompt,
                    "steps": 40,
                    "guidance": 50,
                    "output_format": "png",
                    "safety_tolerance": 2,
                    "prompt_upsampling": False,
                },
            )
        else:
            # Stability inpaint fallback (original behaviour)
            output = replicate.run(
                "stability-ai/stable-diffusion-inpainting:"
                "c28b92a7ecd66eee4aefcd8a94eb9e7f6c3805d5f06038165407fb5cb355ba67",
                input={
                    "image": open(temp_img_path, "rb"),
                    "mask": open(temp_mask_path, "rb"),
                    "prompt": prompt,
                    "negative_prompt": (
                        "grid, split screen, triptych, collage, frames, boundaries, "
                        "borders, multiple panels, text, watermark, logo"
                    ),
                    "num_inference_steps": 30,
                    "guidance_scale": 7.5,
                    "strength": 0.85,
                },
            )

        # Clean up temp files
        if temp_img_path.exists():
            os.remove(temp_img_path)
        if temp_mask_path.exists():
            os.remove(temp_mask_path)

        if output:
            url = output[0] if isinstance(output, list) else output
            resp = requests.get(url)
            if resp.status_code == 200:
                img = Image.open(BytesIO(resp.content)).convert("RGB")
                return img.resize(layout_img.size, Image.Resampling.LANCZOS)

        print("   ⚠️ Inpaint returned no image. Using raw layout.")
        return layout_img

    except Exception as e:
        print(f"   ⚠️ Inpainting failed: {e}. Using raw layout.")
        return layout_img

# --- IMAGE GENERATORS ---

def create_sunburst_background(width: int, height: int) -> Image.Image:
    center_x = width / 2
    center_y = height * 0.25
    num_rays = 40

    base = Image.new("RGB", (width, height), SUNBURST_OUTER)
    draw = ImageDraw.Draw(base)

    for i in range(num_rays):
        angle = (i / num_rays) * 2 * math.pi
        ray_length = height
        end_x = int(center_x + math.cos(angle) * ray_length)
        end_y = int(center_y + math.sin(angle) * ray_length)
        alpha = int(80 + 80 * math.sin(i / num_rays * math.pi))
        ray_color = (SUNBURST_CENTER[0], SUNBURST_CENTER[1], SUNBURST_CENTER[2], alpha)

        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        ray_draw = ImageDraw.Draw(overlay)
        ray_draw.polygon(
            [(center_x, center_y), (end_x, end_y), (center_x, center_y)],
            fill=ray_color,
        )
        base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")

    vignette = Image.new("L", (width, height), 255)
    vignette_draw = ImageDraw.Draw(vignette)
    vignette_radius = min(width, height) * 0.9
    vignette_draw.ellipse(
        [
            (center_x - vignette_radius, center_y - vignette_radius),
            (center_x + vignette_radius, center_y + vignette_radius),
        ],
        fill=0,
    )
    vignette = vignette.filter(ImageFilter.GaussianBlur(80))

    base = ImageChops.multiply(base, ImageOps.colorize(vignette, (0, 0, 0), (255, 255, 255)))
    return base

def composite_cover(inpainted_bg: Image.Image, layout_rgba: Image.Image, date_label: str) -> Image.Image:
    print("🧱 Compositing final cover with paste-back and shadow...")

    img = inpainted_bg.convert("RGBA")

    # Drop shadow based on cinema cutouts
    shadow_offset = (10, 10)
    shadow = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    alpha = layout_rgba.split()[-1]
    shadow_mask = alpha.filter(ImageFilter.GaussianBlur(15))
    shadow.paste((0, 0, 0, 180), (shadow_offset[0], shadow_offset[1]), shadow_mask)

    img = Image.alpha_composite(img, shadow)
    img = Image.alpha_composite(img, layout_rgba)

    # Date pill overlay
    overlay = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    try:
        date_font = ImageFont.truetype(str(BOLD_FONT_PATH), 46)
    except Exception:
        date_font = ImageFont.load_default()

    pill_x, pill_y = 40, 40
    pill_padding = 18

    # Pillow ≥10: use font.getbbox instead of draw.textsize
    bbox = date_font.getbbox(date_label)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    pill_w = text_w + pill_padding * 2
    pill_h = text_h + pill_padding

    draw.rectangle(
        [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
        fill=(0, 0, 0, 230),
        outline=None,
    )
    draw.text(
        (pill_x + pill_padding, pill_y + pill_padding / 2),
        date_label,
        font=date_font,
        fill=(255, 255, 255),
    )

    return Image.alpha_composite(img, overlay).convert("RGB")


# --- SLIDES (UNCHANGED) ---

def draw_story_slide(cinema_name: str, cinema_name_en: str, listings: list[dict[str, str | None]], bg_template: Image.Image) -> Image.Image:
    img = bg_template.copy()
    draw = ImageDraw.Draw(img)
    try:
        header_font = ImageFont.truetype(str(BOLD_FONT_PATH), 70)
        subhead_font = ImageFont.truetype(str(BOLD_FONT_PATH), 40)
        movie_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 42)
        en_movie_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 30)
        time_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 34)
    except Exception:
        header_font = subhead_font = movie_font = en_movie_font = time_font = ImageFont.load_default()

    top_margin = 120
    x = MARGIN
    y = top_margin

    draw.text((x, y), cinema_name, font=header_font, fill=BLACK)
    y += header_font.getbbox(cinema_name)[3] + 10

    if cinema_name_en:
        draw.text((x, y), cinema_name_en, font=subhead_font, fill=BLACK)
        y += subhead_font.getbbox(cinema_name_en)[3] + 40
    else:
        y += 20

    max_lines = 9
    line_count = 0

    for listing in listings:
        if line_count >= max_lines:
            break

        movie_title = listing.get("movie_title") or ""
        en_title = best_english_title(listing) or ""

        times = listing.get("all_showtimes") or listing.get("showtime") or ""
        if isinstance(times, list):
            times_str = ", ".join(times)
        else:
            times_str = times

        wrapped = textwrap.wrap(movie_title, width=18)
        for line in wrapped:
            if line_count >= max_lines:
                break
            draw.text((x, y), line, font=movie_font, fill=BLACK)
            y += movie_font.getbbox(line)[3] + 4
            line_count += 1

        if line_count >= max_lines:
            break

        if en_title:
            draw.text((x + 10, y), en_title, font=en_movie_font, fill=(60, 60, 60))
            y += en_movie_font.getbbox(en_title)[3] + 4
            line_count += 1

        if line_count >= max_lines:
            break

        time_label = f"🎬 {times_str}"
        draw.text((x + 10, y), time_label, font=time_font, fill=(40, 40, 40))
        y += time_font.getbbox(time_label)[3] + 18
        line_count += 1

    location = CINEMA_LOCATIONS.get(cinema_name)
    if location:
        y = img.height - 180
        location_lines = location.split("\n")
        loc_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 30) if REGULAR_FONT_PATH.exists() else ImageFont.load_default()
        for line in location_lines:
            draw.text((x, y), line, font=loc_font, fill=(80, 80, 80))
            y += loc_font.getbbox(line)[3] + 4

    return img

def create_story_bg() -> Image.Image:
    bg = Image.new("RGB", (CANVAS_WIDTH, STORY_CANVAS_HEIGHT), (245, 245, 245))
    draw = ImageDraw.Draw(bg)
    for i in range(0, STORY_CANVAS_HEIGHT, 40):
        alpha = int(40 + 40 * math.sin(i / STORY_CANVAS_HEIGHT * math.pi))
        line_color = (230, 230, 230)
        draw.line([(0, i), (CANVAS_WIDTH, i)], fill=line_color, width=1)
    return bg

def build_caption(cinemas_today: list[str], grouped_showtimes: dict[str, list[dict]]) -> str:
    yyyy_mm_dd, date_label = get_today_strs()
    lines = []
    lines.append("Tokyo Mini Theatre Showtimes 🎬")
    lines.append(f"{date_label}")
    lines.append("")
    lines.append("Today's featured cinemas:")
    for c in cinemas_today:
        en = CINEMA_ENGLISH_NAMES.get(c, "")
        if en:
            lines.append(f"・{c} / {en}")
        else:
            lines.append(f"・{c}")
    lines.append("")
    lines.append("Full listings and tickets → link in bio")
    return "\n".join(lines)

def main():
    if REPLICATE_API_TOKEN:
        os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

    showtimes = load_showtimes()
    grouped = group_by_cinema(showtimes)
    cinemas_today = pick_cinemas_for_today(grouped)
    if not cinemas_today:
        print("No cinemas meet the minimum film threshold for today.")
        return

    assets_by_cinema = load_cinema_assets()
    cover_assets = pick_assets_for_cover(cinemas_today, assets_by_cinema)

    layout_rgba, layout_rgb, mask = create_layout_and_mask(cover_assets)
    inpainted_bg = inpaint_gaps(layout_rgb, mask)
    _, date_label = get_today_strs()
    cover_img = composite_cover(inpainted_bg, layout_rgba, date_label)
    cover_img = cover_img.resize((CANVAS_WIDTH, CANVAS_HEIGHT), Image.Resampling.LANCZOS)
    cover_img.save(BASE_DIR / "post_image_00.png", format="PNG")

    story_bg = create_story_bg()
    sorted_cinemas = cinemas_today[:INSTAGRAM_SLIDE_LIMIT]
    slide_index = 1
    for cinema_name in sorted_cinemas:
        listings = grouped[cinema_name]
        listings.sort(key=lambda s: (s.get("movie_title") or "", s.get("showtime") or ""))
        cinema_name_en = CINEMA_ENGLISH_NAMES.get(cinema_name, "")
        story_img = draw_story_slide(cinema_name, cinema_name_en, listings, story_bg)
        story_img = story_img.resize((CANVAS_WIDTH, STORY_CANVAS_HEIGHT), Image.Resampling.LANCZOS)
        fname = BASE_DIR / f"story_image_{slide_index:02d}.png"
        story_img.save(fname, format="PNG")
        slide_index += 1
        if slide_index > INSTAGRAM_SLIDE_LIMIT:
            break

    caption_text = build_caption(cinemas_today, grouped)
    with open(OUTPUT_CAPTION_PATH, "w", encoding="utf-8") as f:
        f.write(caption_text)

    print("✅ Instagram assets generated:")
    print(f" - Cover: post_image_00.png")
    print(f" - Story slides: story_image_01.png ... story_image_{slide_index-1:02d}.png")
    print(f" - Caption: {OUTPUT_CAPTION_PATH.name}")

if __name__ == "__main__":
    main()
