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
        print(f"⚠️ Assets directory missing: {ASSETS_DIR}")_
