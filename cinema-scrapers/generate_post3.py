"""
Generate Instagram-ready carousel images + caption for Tokyo showtimes.
V3 Experimental: Uses London-style hero slide (clean PIL drawing, no AI).
"""
from __future__ import annotations

import json
import random
import re
import textwrap
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
FONTS_DIR = BASE_DIR / "fonts"
OUTPUT_DIR = BASE_DIR / "ig_posts"
ASSETS_DIR = BASE_DIR / "cinema_assets"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SHOWTIMES_PATH = DATA_DIR / "showtimes.json"
OUTPUT_CAPTION_PATH = OUTPUT_DIR / "post_caption.txt"

# Font paths
BOLD_FONT_PATH = FONTS_DIR / "NotoSansJP-Bold.ttf"
REGULAR_FONT_PATH = FONTS_DIR / "NotoSansJP-Regular.ttf"

# --- Constants ---
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350
STORY_HEIGHT = 1920
MARGIN = 70
SLIDE_LIMIT = 8
MINIMUM_FILM_THRESHOLD = 3
MAX_FEED_VERTICAL_SPACE = 750

# --- Timezone ---
JST = timezone(timedelta(hours=9))

def today_in_tokyo() -> datetime:
    """Returns JST datetime."""
    return datetime.now(timezone.utc).astimezone(JST)

# --- Colors ---
WHITE = (255, 255, 255)
OFF_WHITE = (247, 247, 247)
CHARCOAL = (40, 40, 40)
MUTED = (90, 90, 90)
ACCENT = (203, 64, 74)
LIGHT_GRAY = (230, 230, 230)
DARK_SHADOW = (0, 0, 0, 180)

# --- Cinema Databases ---
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


def load_font(path: Path, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.load_default()


def load_showtimes(today_str: str) -> list[dict]:
    try:
        with SHOWTIMES_PATH.open("r", encoding="utf-8") as f:
            all_showings = json.load(f)
    except FileNotFoundError:
        print(f"showtimes.json not found at {SHOWTIMES_PATH}")
        raise
    except json.JSONDecodeError as exc:
        print("Unable to decode showtimes.json")
        raise exc
    return [show for show in all_showings if show.get("date_text") == today_str]


def is_probably_not_japanese(text: str | None) -> bool:
    if not text:
        return False
    if not re.search(r'[a-zA-Z]', text):
        return False
    japanese_chars = re.findall(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', text)
    latin_chars = re.findall(r'[a-zA-Z]', text)
    if not japanese_chars:
        return True
    if latin_chars:
        if len(latin_chars) > len(japanese_chars) * 2:
            return True
        if len(japanese_chars) <= 2 and len(latin_chars) > len(japanese_chars):
            return True
    return False


def find_best_english_title(showing: dict) -> str | None:
    jp_title = showing.get('movie_title', '').lower()

    def get_clean_title(title_key: str) -> str | None:
        title = showing.get(title_key)
        if not is_probably_not_japanese(title):
            return None
        cleaned_title = title.split(' (')[0].strip()
        if cleaned_title.lower() in jp_title:
            return None
        return cleaned_title

    if en_title := get_clean_title('letterboxd_english_title'):
        return en_title
    if en_title := get_clean_title('tmdb_display_title'):
        return en_title
    if en_title := get_clean_title('movie_title_en'):
        return en_title
    return None


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
        if time_str:
            movies[(title, en_title)].append(time_str)

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


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test_line = f"{current} {word}".strip()
        if draw.textlength(test_line, font=font) <= max_width:
            current = test_line
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def cleanup_previous_outputs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for filename in OUTPUT_DIR.glob("post_image_*.png"):
        filename.unlink()
    for filename in OUTPUT_DIR.glob("story_image_*.png"):
        filename.unlink()
    for filename in OUTPUT_DIR.glob("post_caption.txt"):
        filename.unlink()


def render_cover_slide(target_date: datetime, cinema_names: list[str]) -> Image.Image:
    """London-style hero slide: clean programmatic PIL drawing, no AI."""
    img = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), OFF_WHITE)
    draw = ImageDraw.Draw(img)

    title_font = load_font(BOLD_FONT_PATH, 72)
    subtitle_font = load_font(REGULAR_FONT_PATH, 40)
    date_font = load_font(BOLD_FONT_PATH, 44)
    list_font = load_font(REGULAR_FONT_PATH, 32)

    title = "Tokyo Cinema Showtimes"
    subtitle = "Independent & repertory screenings"
    date_line = target_date.strftime("%A %d %B %Y")

    draw.text((MARGIN, 180), title, font=title_font, fill=CHARCOAL)
    draw.text((MARGIN, 290), subtitle, font=subtitle_font, fill=MUTED)
    draw.line((MARGIN, 380, CANVAS_WIDTH - MARGIN, 380), fill=ACCENT, width=4)
    draw.text((MARGIN, 420), date_line, font=date_font, fill=ACCENT)

    # List featured cinemas on the cover
    y = 520
    draw.text((MARGIN, y), "Featured cinemas:", font=subtitle_font, fill=MUTED)
    y += 60

    for name in cinema_names[:6]:
        cinema_en = CINEMA_ENGLISH_NAMES.get(name, name)
        draw.text((MARGIN + 20, y), f"• {cinema_en}", font=list_font, fill=CHARCOAL)
        y += 50

    draw.text((MARGIN, CANVAS_HEIGHT - 140), "Swipe for today's listings", font=subtitle_font, fill=MUTED)
    return img


def create_blurred_cinema_bg(cinema_name: str, width: int, height: int) -> Image.Image:
    """Create a blurred background from cinema asset if available."""
    base = Image.new("RGB", (width, height), (30, 30, 30))

    if not ASSETS_DIR.exists():
        return base

    # Try to find a matching asset
    safe_name = cinema_name.replace(" ", "_").lower()
    matches = list(ASSETS_DIR.glob(f"*{safe_name}*"))
    if not matches:
        # Try English name
        en_name = CINEMA_ENGLISH_NAMES.get(cinema_name, "")
        if en_name:
            safe_en = en_name.replace(" ", "_").lower()
            matches = list(ASSETS_DIR.glob(f"*{safe_en}*"))

    if not matches:
        return base

    try:
        img = Image.open(matches[0]).convert("RGB")
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
        # Dark overlay
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 120))
        img = img.convert("RGBA")
        img = Image.alpha_composite(img, overlay).convert("RGB")
        return img
    except Exception as e:
        print(f"Error creating background for {cinema_name}: {e}")
        return base


def draw_text_with_shadow(draw, xy, text, font, fill, shadow_color=(0, 0, 0, 180), offset=(3, 3), anchor=None):
    x, y = xy
    draw.text((x + offset[0], y + offset[1]), text, font=font, fill=shadow_color, anchor=anchor)
    draw.text((x, y), text, font=font, fill=fill, anchor=anchor)


def render_cinema_slide(cinema_name: str, listings: list[dict[str, str | None]]) -> Image.Image:
    """Render a cinema slide with listings."""
    bg_img = create_blurred_cinema_bg(cinema_name, CANVAS_WIDTH, CANVAS_HEIGHT)
    draw = ImageDraw.Draw(bg_img)

    title_jp_font = load_font(BOLD_FONT_PATH, 55)
    title_en_font = load_font(BOLD_FONT_PATH, 32)
    regular_font = load_font(REGULAR_FONT_PATH, 34)
    en_movie_font = load_font(REGULAR_FONT_PATH, 28)
    small_font = load_font(REGULAR_FONT_PATH, 28)
    footer_font = load_font(REGULAR_FONT_PATH, 24)

    content_left = MARGIN + 20
    y_pos = MARGIN + 40

    draw_text_with_shadow(draw, (content_left, y_pos), cinema_name, title_jp_font, WHITE)
    y_pos += 70

    cinema_name_en = CINEMA_ENGLISH_NAMES.get(cinema_name, "")
    if cinema_name_en:
        draw_text_with_shadow(draw, (content_left, y_pos), cinema_name_en, title_en_font, LIGHT_GRAY)
        y_pos += 50
    else:
        y_pos += 20

    address = CINEMA_ADDRESSES.get(cinema_name, "")
    if address:
        jp_addr = address.split("\n")[0]
        draw_text_with_shadow(draw, (content_left, y_pos), f"📍 {jp_addr}", small_font, LIGHT_GRAY)
        y_pos += 60
    else:
        y_pos += 30

    draw.line([(MARGIN, y_pos), (CANVAS_WIDTH - MARGIN, y_pos)], fill=WHITE, width=3)
    y_pos += 40

    for listing in listings:
        wrapped_title = textwrap.wrap(f"■ {listing['title']}", width=30) or [f"■ {listing['title']}"]
        for line in wrapped_title:
            draw_text_with_shadow(draw, (content_left, y_pos), line, regular_font, WHITE)
            y_pos += 40
        if listing["en_title"]:
            wrapped_en = textwrap.wrap(f"({listing['en_title']})", width=35)
            for line in wrapped_en:
                draw_text_with_shadow(draw, (content_left + 10, y_pos), line, en_movie_font, LIGHT_GRAY)
                y_pos += 30
        if listing['times']:
            draw_text_with_shadow(draw, (content_left + 40, y_pos), listing["times"], regular_font, LIGHT_GRAY)
            y_pos += 55

    footer_text = "Details online: leonelki.com/cinemas"
    draw_text_with_shadow(draw, (CANVAS_WIDTH // 2, CANVAS_HEIGHT - MARGIN - 20), footer_text, footer_font, LIGHT_GRAY, anchor="mm")
    return bg_img


def render_story_slide(target_date: datetime, cinema_names: list[str]) -> Image.Image:
    """Render a story-format slide."""
    img = Image.new("RGB", (CANVAS_WIDTH, STORY_HEIGHT), OFF_WHITE)
    draw = ImageDraw.Draw(img)

    title_font = load_font(BOLD_FONT_PATH, 72)
    subtitle_font = load_font(REGULAR_FONT_PATH, 36)
    list_font = load_font(BOLD_FONT_PATH, 38)

    draw.text((MARGIN, 220), "Tokyo Showtimes", font=title_font, fill=CHARCOAL)
    draw.text((MARGIN, 320), target_date.strftime("%A %d %B"), font=subtitle_font, fill=ACCENT)

    y = 420
    for name in cinema_names[:6]:
        cinema_en = CINEMA_ENGLISH_NAMES.get(name, name)
        draw.text((MARGIN, y), f"• {cinema_en}", font=list_font, fill=CHARCOAL)
        y += 60

    draw.line((MARGIN, STORY_HEIGHT - 280, CANVAS_WIDTH - MARGIN, STORY_HEIGHT - 280), fill=ACCENT, width=4)
    draw.text((MARGIN, STORY_HEIGHT - 220), "Full schedule in bio", font=subtitle_font, fill=MUTED)
    return img


def segment_listings(listings: list[dict], max_height: int) -> list[list[dict]]:
    """Split listings into segments that fit on slides."""
    spacing = {'jp_line': 40, 'time_line': 55, 'en_line': 30}
    segments = []
    current_segment = []
    current_height = 0

    for listing in listings:
        required_height = spacing['jp_line'] + spacing['time_line']
        if listing.get('en_title'):
            required_height += spacing['en_line']
        if current_height + required_height > max_height:
            if current_segment:
                segments.append(current_segment)
                current_segment = [listing]
                current_height = required_height
            else:
                segments.append([listing])
                current_height = 0
        else:
            current_segment.append(listing)
            current_height += required_height

    if current_segment:
        segments.append(current_segment)
    return segments


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


def build_caption(target_date: datetime, all_featured_cinemas: list[dict]) -> str:
    date_str = target_date.strftime("%Y-%m-%d")
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
    return "\n".join(lines)


def main() -> None:
    print("🎬 Generate Post V3 - London-style Hero Slide (Experimental)")

    # Setup
    today = today_in_tokyo()
    today_str = today.date().isoformat()
    print(f"🕒 Generator Time (JST): {today.date()} (String: {today_str})")

    # Cleanup
    cleanup_previous_outputs()

    # Load showtimes
    try:
        todays_showings = load_showtimes(today_str)
    except Exception as e:
        print(f"❌ Error loading showtimes: {e}")
        return

    if not todays_showings:
        print(f"❌ No showings found for date: {today_str}")
        return

    print(f"✅ Found {len(todays_showings)} showings for {today_str}")

    # Group by cinema
    grouped: defaultdict[str, list[dict]] = defaultdict(list)
    for show in todays_showings:
        if show.get("cinema_name"):
            grouped[show["cinema_name"]].append(show)

    # Selection logic
    featured_names = get_recently_featured(OUTPUT_CAPTION_PATH)
    valid_cinemas = [c_name for c_name, shows in grouped.items() if len(shows) >= MINIMUM_FILM_THRESHOLD]

    candidates = [c for c in valid_cinemas if c not in featured_names]
    if not candidates:
        candidates = valid_cinemas

    random.shuffle(candidates)
    selected_cinemas = candidates[:SLIDE_LIMIT]

    if not selected_cinemas:
        print("❌ No cinemas met criteria.")
        return

    print(f"📍 Generating for: {selected_cinemas}")

    # Generate cover slide (London-style)
    cover = render_cover_slide(today, selected_cinemas)
    cover.save(OUTPUT_DIR / "post_image_01.png")
    print("✅ Generated cover slide (London-style)")

    # Generate cinema slides
    slide_counter = 1
    all_featured_for_caption = []

    for cinema_name in selected_cinemas:
        if slide_counter >= SLIDE_LIMIT:
            break

        shows = grouped[cinema_name]
        listings = format_listings(shows)
        segments = segment_listings(listings, MAX_FEED_VERTICAL_SPACE)

        all_featured_for_caption.append({
            'cinema_name': cinema_name,
            'listings': [l for sublist in segments for l in sublist]
        })

        for segment in segments:
            if slide_counter >= SLIDE_LIMIT:
                break
            slide_counter += 1
            slide_img = render_cinema_slide(cinema_name, segment)
            slide_img.save(OUTPUT_DIR / f"post_image_{slide_counter:02d}.png")

    # Generate story slide
    story = render_story_slide(today, selected_cinemas)
    story.save(OUTPUT_DIR / "story_image_01.png")

    # Generate caption
    caption = build_caption(today, all_featured_for_caption)
    OUTPUT_CAPTION_PATH.write_text(caption, encoding="utf-8")

    print(f"✅ Generated {slide_counter} feed slides.")
    print("✅ Generated 1 story slide.")
    print(f"✅ Saved caption to {OUTPUT_CAPTION_PATH}")


if __name__ == "__main__":
    main()
