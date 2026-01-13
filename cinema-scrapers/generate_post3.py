"""
Generate Instagram-ready image carousel (V2.2 - "Proportional Story Cover").
REPLACES V28/V61.
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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from io import BytesIO
import sys
import subprocess

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops, ImageOps

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

# --- API Setup ---
try:
    import replicate
    REPLICATE_AVAILABLE = True
except ImportError:
    print("⚠️ Replicate library not found. Run: pip install replicate")
    REPLICATE_AVAILABLE = False



# --- ⚡ FIX: Force JST (UTC+9) explicitly ---
JST = timezone(timedelta(hours=9))

def today_in_tokyo() -> datetime:
    return datetime.now(timezone.utc).astimezone(JST)



# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
FONTS_DIR = BASE_DIR / "fonts"
OUTPUT_DIR = BASE_DIR / "ig_posts"

# Ensure output directory exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Path Updates
SHOWTIMES_PATH = DATA_DIR / "showtimes.json"
ASSETS_DIR = BASE_DIR / "cinema_assets"
CUTOUTS_DIR = ASSETS_DIR / "cutouts"
OUTPUT_CAPTION_PATH = OUTPUT_DIR / "post_caption.txt"

# Font Updates
BOLD_FONT_PATH = FONTS_DIR / "NotoSansJP-Bold.ttf"
REGULAR_FONT_PATH = FONTS_DIR / "NotoSansJP-Regular.ttf"

# Secrets
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# --- CONSTANTS ---
MINIMUM_FILM_THRESHOLD = 3
INSTAGRAM_SLIDE_LIMIT = 8 
MAX_FEED_VERTICAL_SPACE = 750 
MAX_STORY_VERTICAL_SPACE = 1150
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350
STORY_CANVAS_HEIGHT = 1920
MARGIN = 60 
TITLE_WRAP_WIDTH = 30

# --- HERO GENERATION STRATEGIES ---
HERO_STRATEGIES = [
    {
        "name": "Raw VQ-GAN Latent Mashup",
        "sd_prompt": "early AI vq-gan+clip style, surreal architectural mashup of Tokyo cinema buildings, latent space bleeding, glitched transitions, surprising structural connections, vibrant and messy dreamscape, artifact-heavy, kaleidoscopic cinema facades",
        "use_gemini": False
    },
    {
        "name": "Surreal Cinema Dreamscape",
        "sd_prompt": "dream-like architectural collage connecting movie theaters, impossible non-euclidean geometry, atmospheric neon lighting, early AI aesthetic, surprising organic-architectural hybrids",
        "use_gemini": True,
        "gemini_prompt": "Refine this architectural mashup. Maintain the surprising, surreal 'early AI' connections but elevate the final quality. Make the lighting and textures feel like a coherent, high-quality 35mm film still. The mashup should feel weird and surprising but intentional. Subtly integrate 'TOKYO CINEMA' and the date '{date_text}' into the scene."
    },
    {
        "name": "Abstract Marquee Glitch",
        "sd_prompt": "glitched and overlapping cinema marquees and neon signs, kaleidoscopic architectural mashup, vibrant liquid-like bleeding colors, early AI artifacts, dream-like structural incoherence",
        "use_gemini": False
    }
]

# --- GLOBAL COLORS ---
WHITE = (255, 255, 255)
OFF_WHITE = (240, 240, 240)
LIGHT_GRAY = (230, 230, 230) 
DARK_SHADOW = (0, 0, 0, 180) 

# --- Database (Cinemas) ---
CINEMA_ADDRESSES = {
    "Bunkamura ル・シネマ 渋谷宮下": "東京都渋谷区渋谷1-23-16 6F",
    "K's Cinema (ケイズシネマ)": "東京都新宿区新宿3-35-13 3F",
    "シネマート新宿": "東京都新宿区新宿3-13-3 6F",
    "新宿シネマカリテ": "東京都新宿区新宿3-37-12 5F",
    "新宿武蔵野館": "東京都新宿区新宿3-27-10 3F",
    "テアトル新宿": "東京都新宿区新宿3-14-20 7F",
    "早稲田松竹": "東京都新宿区高田馬場1-5-16",
    "YEBISU GARDEN CINEMA": "東京都渋谷区恵比寿4-20-2",
    "シアター・イメージフォーラム": "東京都渋谷区渋谷2-10-2",
    "ユーロスペース": "東京都渋谷区円山町1-5 3F",
    "ヒューマントラストシネマ渋谷": "東京都渋谷区渋谷1-23-16 7F",
    "Stranger (ストレンジャー)": "東京都墨田区菊川3-7-1 1F",
    "新文芸坐": "東京都豊島区東池袋1-43-5 3F",
    "目黒シネマ": "東京都品川区上大崎2-24-15",
    "ポレポレ東中野": "東京都中野区東中野4-4-1 1F",
    "K2 Cinema": "東京都世田谷区北沢2-21-22 2F",
    "ヒューマントラストシネマ有楽町": "東京都千代田区有楽町2-7-1 8F",
    "ラピュタ阿佐ヶ谷": "東京都杉並区阿佐ヶ谷北2-12-21",
    "下高井戸シネマ": "東京都世田谷区松原3-30-15",
    "国立映画アーカイブ": "東京都中央区京橋3-7-6",
    "池袋シネマ・ロサ": "東京都豊島区西池袋1-37-12",
    "シネスイッチ銀座": "東京都中央区銀座4-4-5 3F",
    "シネマブルースタジオ": "東京都足立区千住3-92 2F",
    "CINEMA Chupki TABATA": "東京都北区東田端2-14-4",
    "シネクイント": "東京都渋谷区宇田川町20-11 8F",
    "アップリンク吉祥寺": "東京都武蔵野市吉祥寺本町1-5-1 4F",
    "下北沢トリウッド": "東京都世田谷区代沢5-32-5 2F",
    "Morc阿佐ヶ谷": "東京都杉並区阿佐谷北2-12-19 B1F",
    "シネマリス": "東京都新宿区新宿3-29-6"
}

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
    "シネマリス": "CineMalice"
}

CINEMA_FILENAME_OVERRIDES = {
    "国立映画アーカイブ": "nfaj",
    "シネマリス": "cinemalice",
    "ポレポレ東中野": "polepole",
    "新宿武蔵野館": "musashino_kan",
    "新宿シネマカリテ": "qualite",
    "池袋シネマ・ロサ": "rosa",
    "シアター・イメージフォーラム": "image_forum",
    "シネマブルースタジオ": "blue_studio",
    "ヒューマントラストシネマ渋谷": "human_shibuya",
    "ヒューマントラストシネマ有楽町": "human_yurakucho",
    "アップリンク吉祥寺": "uplink",
    "新文芸坐": "shin_bungeiza",
    "早稲田松竹": "waseda_shochiku"
}

# --- Utility Functions ---
def is_probably_not_japanese(text: str | None) -> bool:
    if not text: return False
    if not re.search(r'[a-zA-Z]', text): return False 
    japanese_chars = re.findall(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', text)
    latin_chars = re.findall(r'[a-zA-Z]', text)
    if not japanese_chars: return True
    if latin_chars:
        if len(latin_chars) > len(japanese_chars) * 2: return True
        if len(japanese_chars) <= 2 and len(latin_chars) > len(japanese_chars): return True
    return False

def clean_search_title(title: str) -> str:
    if not title: return ""
    title = re.sub(r'[\(（].*?[\)）]', '', title)
    title = re.sub(r'[\\\[\u3010].*?[\\\]\u3011]', '', title)
    keywords = ["4K", "2K", "3D", "IMAX", "Dolby", "Atmos", "レストア", "デジタル", "リマスター", "完全版", "ディレクターズカット", "劇場版", "特別上映", "特集", "上映後トーク", "舞台挨拶"]
    for kw in keywords:
        title = title.replace(kw, "")
    return title.strip()

def find_best_english_title(showing: dict) -> str | None:
    jp_title = showing.get('movie_title', '').lower()
    def get_clean_title(title_key: str) -> str | None:
        title = showing.get(title_key)
        if not is_probably_not_japanese(title): return None
        cleaned_title = title.split(' (')[0].strip()
        if cleaned_title.lower() in jp_title: return None
        return cleaned_title
    if en_title := get_clean_title('letterboxd_english_title'): return en_title
    if en_title := get_clean_title('tmdb_display_title'): return en_title
    if en_title := get_clean_title('movie_title_en'): return en_title
    return None

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
    movies: defaultdict[tuple[str, str | None], list[str]] = defaultdict(list)
    title_map: dict[str, str | None] = {}
    for show in showings:
        title = show.get("movie_title") or "タイトル未定"
        if title not in title_map:
            title_map[title] = find_best_english_title(show)
    for show in showings:
        title = show.get("movie_title") or "タイトル未定"
        en_title = title_map[title]
        time_str = show.get("showtime") or ""
        if time_str: movies[(title, en_title)].append(time_str)
    
    formatted = []
    for (title, en_title), times in movies.items():
        times.sort()
        formatted.append({
            "title": title, 
            "en_title": en_title, 
            "times": ", ".join(times),
            "first_showtime": times[0] if times else "23:59"
        })
    
    formatted.sort(key=lambda x: x['first_showtime'])
    return formatted

def segment_listings(listings: list[dict[str, str | None]], max_height: int, spacing: dict[str, int]) -> list[list[dict]]:
    SEGMENTED_LISTS = []
    current_segment = []
    current_height = 0
    for listing in listings:
        required_height = spacing['jp_line'] + spacing['time_line']
        if listing.get('en_title'):
             required_height += spacing['en_line']
        if current_height + required_height > max_height:
            if current_segment:
                SEGMENTED_LISTS.append(current_segment)
                current_segment = [listing]
                current_height = required_height
            else:
                 SEGMENTED_LISTS.append([listing])
                 current_height = 0
        else:
            current_segment.append(listing)
            current_height += required_height
    if current_segment:
        SEGMENTED_LISTS.append(current_segment)
    return SEGMENTED_LISTS

def get_recently_featured(caption_path: Path) -> list[str]:
    if not caption_path.exists(): return []
    try:
        content = caption_path.read_text(encoding="utf-8")
        names = re.findall(r"---\s\[(.*?)(\s*)\]\s---", content)
        return [name[0] for name in names]
    except Exception as e:
        print(f"   [WARN] Could not read previous caption: {e}")
        return []

# --- ASSET & REPLICATE LOGIC ---

def normalize_name(s):
    s = str(s).lower()
    return re.sub(r'[^a-z0-9]', '', s)

def get_cinema_image_path(cinema_name: str) -> Path | None:
    if not ASSETS_DIR.exists(): return None
    
    # Priority 1: Overrides
    if cinema_name in CINEMA_FILENAME_OVERRIDES:
        target = CINEMA_FILENAME_OVERRIDES[cinema_name]
    else:
        # Priority 2: English Name normalized
        en_name = CINEMA_ENGLISH_NAMES.get(cinema_name, "")
        if en_name:
            target = normalize_name(en_name).replace("cinema", "").replace("theatre", "").strip()
        else:
            # Priority 3: Original name normalized
            target = normalize_name(cinema_name)

    candidates = list(ASSETS_DIR.glob("**/*"))
    matches = []
    for f in candidates:
        if f.suffix.lower() not in ['.jpg', '.jpeg', '.png']: continue
        f_name_norm = normalize_name(f.stem)
        
        if target == f_name_norm: return f # Exact match
        if target in f_name_norm or f_name_norm in target:
            matches.append(f)
        else:
            ratio = difflib.SequenceMatcher(None, target, f_name_norm).ratio()
            if ratio > 0.6:
                matches.append(f)

    if matches:
        return random.choice(matches)
    return None

def get_cutout_path(cinema_name: str) -> Path | None:
    if not CUTOUTS_DIR.exists(): return None
    
    # Priority 1: Overrides
    if cinema_name in CINEMA_FILENAME_OVERRIDES:
        target = CINEMA_FILENAME_OVERRIDES[cinema_name]
    else:
        en_name = CINEMA_ENGLISH_NAMES.get(cinema_name, "")
        if en_name:
            target = normalize_name(en_name).replace("cinema", "").replace("theatre", "").strip()
        else:
            target = normalize_name(cinema_name)

    candidates = list(CUTOUTS_DIR.glob("*"))
    matches = []
    for f in candidates:
        if f.suffix.lower() not in ['.jpg', '.jpeg', '.png']: continue
        f_name_norm = normalize_name(f.stem)
        
        if target == f_name_norm: return f # Exact match
        if target in f_name_norm or f_name_norm in target:
            matches.append(f)
        else:
            ratio = difflib.SequenceMatcher(None, target, f_name_norm).ratio()
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

def remove_background_replicate(pil_img: Image.Image) -> Image.Image:
    if not REPLICATE_AVAILABLE or not REPLICATE_API_TOKEN: 
        return pil_img.convert("RGBA")
    
    # List of reliable background removal models to try in order
    REMBG_MODELS = [
        "851-labs/background-remover:a029dff38972b5fda4ec5d75d7d1cd25aeff621d2cf4946a41055d7db66b80bc",
        "lucataco/remove-bg:95fcc2a26d3899cd6c2691c900465aaeff466285a65c14638cc5f36f34befaf1",
        "afiaka87/remove-bg:69680da395048d086202525f053229b1613589b9f36f982d1378f8b09062325c"
    ]
    
    try:
        temp_in = BASE_DIR / f"temp_rembg_{random.randint(0,999)}.png"
        pil_img.save(temp_in, format="PNG")
        
        output = None
        for model_id in REMBG_MODELS:
            try:
                print(f"      📡 Trying Rembg: {model_id.split(':')[0]}...")
                output = replicate.run(model_id, input={"image": open(temp_in, "rb")})
                if output: break
            except Exception as e:
                print(f"      ⚠️ Model {model_id.split(':')[0]} failed: {str(e)[:100]}")
        
        if temp_in.exists(): os.remove(temp_in)
        
        if output:
            print(f"      ✅ Rembg successful")
            # Handle both string and list output
            url = output[0] if isinstance(output, list) else str(output)
            resp = requests.get(url)
            if resp.status_code == 200:
                return Image.open(BytesIO(resp.content)).convert("RGBA")
    except Exception as e:
        print(f"   ⚠️ Rembg process failed: {e}")
    return pil_img.convert("RGBA")

def feather_cutout(img: Image.Image, erosion: int = 2, blur: int = 5) -> Image.Image:
    if img.mode != 'RGBA': img = img.convert('RGBA')
    alpha = img.split()[3]
    # Smaller filter to avoid 'bad filter size' on small images
    alpha = alpha.filter(ImageFilter.MinFilter(3))
    alpha = alpha.filter(ImageFilter.GaussianBlur(blur))
    img.putalpha(alpha)
    return img

def create_layout_and_mask(cinemas: list[tuple[str, Path]], target_width: int, target_height: int) -> tuple[Image.Image, Image.Image, Image.Image]:
    width, height = target_width, target_height
    layout_rgba = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    # Neutral gray background
    layout_rgb = Image.new("RGB", (width, height), (60, 60, 60))
    mask = Image.new("L", (width, height), 255)

    imgs_to_process = cinemas[:4]
    if len(imgs_to_process) < 4: imgs_to_process = (imgs_to_process * 4)[:4]
    random.shuffle(imgs_to_process)

    anchors = [
        (random.randint(int(width*0.1), int(width*0.4)), random.randint(int(height*0.1), int(height*0.4))),
        (random.randint(int(width*0.6), int(width*0.9)), random.randint(int(height*0.1), int(height*0.4))),
        (random.randint(int(width*0.1), int(width*0.4)), random.randint(int(height*0.6), int(height*0.9))),
        (random.randint(int(width*0.6), int(width*0.9)), random.randint(int(height*0.6), int(height*0.9)))
    ]

    for i, (name, path) in enumerate(imgs_to_process):
        try:
            print(f"   ✂️ Processing: {name} ({path.name})")
            raw = Image.open(path).convert("RGBA")
            
            # If it's in the cutouts folder, we assume it's a subject on a white background
            if "cutouts" in str(path).lower():
                print(f"      ✨ Applying white-to-transparent conversion")
                cutout = convert_white_to_transparent(raw, threshold=235)
            else:
                # Only use Replicate if it's not a pre-made cutout
                cutout = remove_background_replicate(raw)
            
            bbox = cutout.getbbox()
            if bbox: cutout = cutout.crop(bbox)
            cutout = feather_cutout(cutout, erosion=1, blur=3)

            scale = random.uniform(0.8, 1.1)
            max_dim = int(800 * scale)
            cutout.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

            cx, cy = anchors[i]
            x, y = cx - (cutout.width // 2), cy - (cutout.height // 2)

            # Paste into layout_rgba (the actual collage)
            layout_rgba.paste(cutout, (x, y), mask=cutout)
            
            # Mask logic: 0 = KEEP (the building), 255 = CHANGE (the gaps)
            alpha = cutout.split()[3]
            core_mask = alpha.filter(ImageFilter.MinFilter(3))
            mask.paste(0, (x, y), mask=core_mask)
        except Exception as e:
            print(f"Error processing {name}: {e}")

    # Re-composite layout_rgb correctly
    final_layout_rgb = Image.new("RGB", (width, height), (60, 60, 60))
    final_layout_rgb.paste(layout_rgba, (0,0), mask=layout_rgba)

    return layout_rgba, final_layout_rgb, mask

def refine_hero_with_ai(pil_image, date_text, strategy, cinema_names=[]):
    if not strategy.get("use_gemini"):
        print("   ⏩ Skipping Gemini refinement (as per strategy).")
        return pil_image
    
    print(f"   ✨ Refining Hero Collage (Gemini) - Strategy: {strategy['name']}...")
    try:
        if not GEMINI_API_KEY: return pil_image
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        prompt = strategy["gemini_prompt"].format(date_text=date_text)
        prompt += f"\nContext Cinemas: {', '.join(cinema_names[:4])}."

        print(f"   📝 Gemini Prompt: {prompt}")
        
        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=[prompt, pil_image],
            config=types.GenerateContentConfig(response_modalities=["IMAGE"])
        )
        for part in response.parts:
            if part.inline_data:
                return Image.open(BytesIO(part.inline_data.data)).convert("RGB").resize(pil_image.size, Image.Resampling.LANCZOS)
    except Exception as e:
        print(f"   ⚠️ Gemini Failed: {e}")
    return pil_image

def inpaint_gaps(layout_img: Image.Image, mask_img: Image.Image, strategy) -> Image.Image:
    if not REPLICATE_AVAILABLE or not REPLICATE_API_TOKEN: 
        return layout_img
    
    prompt = strategy["sd_prompt"]
    print(f"   🎨 Inpainting gaps (SDXL) - Strategy: {strategy['name']}...")
    
    # Verified working version of SDXL from your Replicate dashboard
    SDXL_VERSION = "stability-ai/sdxl:7762fd07cf82c948538e41f63f77d685e02b063e37e496e96eefd46c929f9bdc"
    
    try:
        temp_img, temp_mask = BASE_DIR / "temp_in_img.png", BASE_DIR / "temp_in_mask.png"
        layout_img.save(temp_img); mask_img.save(temp_mask)
        
        # DEBUG IMAGES
        debug_dir = OUTPUT_DIR / "debug"
        debug_dir.mkdir(exist_ok=True)
        layout_img.save(debug_dir / f"layout_{strategy['name'].replace(' ', '_')}.png")
        mask_img.save(debug_dir / f"mask_{strategy['name'].replace(' ', '_')}.png")
        
        print(f"      📡 Calling Replicate (SDXL verified)...")
        output = replicate.run(
            SDXL_VERSION,
            input={
                "image": open(temp_img, "rb"), 
                "mask": open(temp_mask, "rb"),
                "prompt": f"{prompt}, seamless surreal integration, cinematic lighting, high quality",
                "negative_prompt": "white background, empty space, floating objects, borders, frames, text, watermark, bad quality, blurry",
                "strength": 0.85, # Allows for significant mashup while keeping cinema structure
                "num_inference_steps": 30,
                "guidance_scale": 7.5,
                "apply_watermark": False
            }
        )
        
        if temp_img.exists(): os.remove(temp_img)
        if temp_mask.exists(): os.remove(temp_mask)
        
        if output:
            # The SDXL model usually returns a list of file outputs
            url = output[0] if isinstance(output, list) else str(output)
            print(f"      ✅ Inpainting successful: {url}")
            resp = requests.get(url)
            return Image.open(BytesIO(resp.content)).convert("RGB").resize(layout_img.size, Image.Resampling.LANCZOS)
        else:
            print("   ⚠️ SDXL returned no output.")
    except Exception as e:
        print(f"   ⚠️ SDXL process failed: {e}")
    return layout_img

def create_blurred_cinema_bg(cinema_name: str, width: int, height: int) -> Image.Image:
    full_path = get_cinema_image_path(cinema_name)
    base = Image.new("RGB", (width, height), (30, 30, 30))
    if not full_path: return base
    try:
        img = Image.open(full_path).convert("RGB")
        img = ImageOps.fit(img, (width, height), method=Image.Resampling.LANCZOS)
        img = img.filter(ImageFilter.GaussianBlur(10))
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 140))
        return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    except: return base

def draw_text_with_shadow(draw, xy, text, font, fill, shadow_color=DARK_SHADOW, offset=(3,3), anchor=None):
    draw.text((xy[0]+offset[0], xy[1]+offset[1]), text, font=font, fill=shadow_color, anchor=anchor)
    draw.text(xy, text, font=font, fill=fill, anchor=anchor)

def draw_cinema_slide(cinema_name: str, cinema_name_en: str, listings: list[dict], bg_template: Image.Image) -> Image.Image:
    img = bg_template.copy(); draw = ImageDraw.Draw(img)
    title_jp_f = ImageFont.truetype(str(BOLD_FONT_PATH), 55)
    title_en_f = ImageFont.truetype(str(BOLD_FONT_PATH), 32)
    reg_f = ImageFont.truetype(str(REGULAR_FONT_PATH), 34)
    en_f = ImageFont.truetype(str(REGULAR_FONT_PATH), 28)
    
    y = MARGIN + 40
    draw_text_with_shadow(draw, (MARGIN+20, y), cinema_name, title_jp_f, WHITE); y += 70
    if cinema_name_en or CINEMA_ENGLISH_NAMES.get(cinema_name):
        draw_text_with_shadow(draw, (MARGIN+20, y), cinema_name_en or CINEMA_ENGLISH_NAMES[cinema_name], title_en_f, LIGHT_GRAY); y += 55
    
    draw.line([(MARGIN, y), (CANVAS_WIDTH-MARGIN, y)], fill=WHITE, width=2); y += 40
    for l in listings:
        for line in textwrap.wrap(f"■ {l['title']}", width=TITLE_WRAP_WIDTH):
            draw_text_with_shadow(draw, (MARGIN+20, y), line, reg_f, WHITE); y += 42
        if l['en_title']:
            for line in textwrap.wrap(f"({l['en_title']})", width=38):
                draw_text_with_shadow(draw, (MARGIN+30, y), line, en_f, LIGHT_GRAY); y += 32
        if l['times']:
            draw_text_with_shadow(draw, (MARGIN+60, y), l['times'], reg_f, LIGHT_GRAY); y += 60
    return img

def write_caption_for_multiple_cinemas(date_str: str, all_featured_cinemas: list[dict]) -> None:
    header = f"🗓️ 本日の東京ミニシアター上映情報 / Today's Featured Showtimes ({date_str})\n"
    lines = [header]
    for item in all_featured_cinemas:
        cinema_name = item['cinema_name']
        address = CINEMA_ADDRESSES.get(cinema_name, "")
        lines.append(f"\n--- 【{cinema_name}】 ---")
        if address:
            jp_address = address.split("\n")[0]
            lines.append(f"📍 {jp_address}") 
        for listing in item['listings']:
            lines.append(f"• {listing['title']}")
    dynamic_hashtag = "IndieCinema"
    if all_featured_cinemas:
         first_cinema_name = all_featured_cinemas[0]['cinema_name']
         dynamic_hashtag = "".join(ch for ch in first_cinema_name if ch.isalnum() or "\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff")

    footer = f"""
#TokyoIndieCinema #{dynamic_hashtag} #MiniTheater #MovieLog
Check Bio for Full Schedule / 詳細はリンクへ
"""
    lines.append(footer)
    with OUTPUT_CAPTION_PATH.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def main():
    today = today_in_tokyo().date()
    today_str = today.isoformat()
    bilingual_date = f"{today.strftime('%Y.%m.%d')} {today.strftime('%a').upper()}"
    
    print(f"🕒 Today: {today_str}")
    if OUTPUT_DIR.exists():
        for f in OUTPUT_DIR.glob("*.png"): os.remove(f)

    showings = load_showtimes(today_str)
    if not showings: 
        print("❌ No showings."); return
    print(f"✅ Found {len(showings)} showings.")

    grouped = defaultdict(list)
    for s in showings: grouped[s['cinema_name']].append(s)
            
    valid = [c for c, s in grouped.items() if len(s) >= MINIMUM_FILM_THRESHOLD]
    random.shuffle(valid)
    selected = valid[:INSTAGRAM_SLIDE_LIMIT]
    if not selected: return

    # --- HERO GENERATION ---
    cinema_images = []
    for c in selected:
        # Prefer pre-made cutouts if they exist
        path = get_cutout_path(c) or get_cinema_image_path(c)
        if path:
            cinema_images.append((c, path))
    
    if cinema_images:
        print(f"   🎨 Found {len(cinema_images)} images for collage. Generating {len(HERO_STRATEGIES)} hero options...")
        layout_rgba, layout_rgb, mask = create_layout_and_mask(cinema_images, CANVAS_WIDTH, CANVAS_HEIGHT)
        
        for i, strategy in enumerate(HERO_STRATEGIES):
            print(f"\n   🚀 Generating Option {i+1}: {strategy['name']}")
            cover_bg = inpaint_gaps(layout_rgb, mask, strategy)
            final_cover = refine_hero_with_ai(cover_bg, bilingual_date, strategy, [c[0] for c in cinema_images])
            
            # Save individual options
            opt_path = OUTPUT_DIR / f"hero_option_{i:02}.png"
            final_cover.save(opt_path)
            final_cover.resize((CANVAS_WIDTH, STORY_CANVAS_HEIGHT), Image.Resampling.LANCZOS).save(OUTPUT_DIR / f"story_option_{i:02}.png")
            
            # Set the first one as the default post_image_00.png
            if i == 0:
                final_cover.save(OUTPUT_DIR / "post_image_00.png")
                final_cover.resize((CANVAS_WIDTH, STORY_CANVAS_HEIGHT), Image.Resampling.LANCZOS).save(OUTPUT_DIR / "story_image_00.png")
            
            print(f"   ✅ Saved {strategy['name']} to {opt_path.name}")
    else:
        print("   ⚠️ No images found for Hero Collage.")

    # --- SLIDES ---
    slide_idx = 0
    all_featured = []
    for c_name in selected:
        if slide_idx >= 9: break
        listings = format_listings(grouped[c_name])
        segmented = segment_listings(listings, MAX_FEED_VERTICAL_SPACE, {'jp_line': 40, 'time_line': 55, 'en_line': 30})
        bg = create_blurred_cinema_bg(c_name, CANVAS_WIDTH, CANVAS_HEIGHT)
        all_featured.append({'cinema_name': c_name, 'listings': [l for sub in segmented for l in sub]})
        for seg in segmented:
            slide_idx += 1
            if slide_idx >= 10: break
            draw_cinema_slide(c_name, "", seg, bg).save(OUTPUT_DIR / f"post_image_{slide_idx:02}.png")
            
    write_caption_for_multiple_cinemas(today_str, all_featured)
    print(f"✅ Done. Generated {slide_idx} slides.")

if __name__ == "__main__":
    main()
