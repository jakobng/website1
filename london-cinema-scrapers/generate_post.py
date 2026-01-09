"""
Generate Instagram-ready carousel images + caption for London showtimes.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "ig_posts"

SHOWTIMES_PATH = DATA_DIR / "showtimes.json"
OUTPUT_CAPTION_PATH = OUTPUT_DIR / "post_caption.txt"

CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350
STORY_HEIGHT = 1920
MARGIN = 70
SLIDE_LIMIT = 8

LONDON_TZ = ZoneInfo("Europe/London")

FONT_REGULAR_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

WHITE = (255, 255, 255)
OFF_WHITE = (247, 247, 247)
CHARCOAL = (40, 40, 40)
MUTED = (90, 90, 90)
ACCENT = (203, 64, 74)


def load_font(path: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def parse_date(date_text: str) -> datetime | None:
    try:
        return datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        return None


def load_showtimes() -> list[dict]:
    with open(SHOWTIMES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def select_target_date(showtimes: Iterable[dict]) -> datetime:
    today = datetime.now(LONDON_TZ).date()
    dated = []
    for entry in showtimes:
        parsed = parse_date(entry.get("date_text", ""))
        if parsed:
            dated.append(parsed.date())
    if not dated:
        raise ValueError("No valid date_text entries found in showtimes.")
    if today in dated:
        return datetime.combine(today, datetime.min.time(), tzinfo=LONDON_TZ)
    earliest = min(dated)
    return datetime.combine(earliest, datetime.min.time(), tzinfo=LONDON_TZ)


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


def build_schedule(showtimes: Iterable[dict], target_date: datetime) -> dict[str, dict[str, list[str]]]:
    schedule: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    target_str = target_date.strftime("%Y-%m-%d")
    for entry in showtimes:
        if entry.get("date_text") != target_str:
            continue
        cinema = entry.get("cinema_name", "Unknown Cinema")
        title = entry.get("movie_title_en") or entry.get("movie_title") or "Untitled"
        time_str = entry.get("showtime") or "TBD"
        schedule[cinema][title].append(time_str)
    for cinema_titles in schedule.values():
        for times in cinema_titles.values():
            times.sort()
    return dict(schedule)


def cleanup_previous_outputs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for filename in OUTPUT_DIR.glob("post_image_*.png"):
        filename.unlink()
    for filename in OUTPUT_DIR.glob("story_image_*.png"):
        filename.unlink()
    for filename in OUTPUT_DIR.glob("post_caption.txt"):
        filename.unlink()


def render_cover_slide(target_date: datetime) -> Image.Image:
    img = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), OFF_WHITE)
    draw = ImageDraw.Draw(img)
    title_font = load_font(FONT_BOLD_PATH, 72)
    subtitle_font = load_font(FONT_REGULAR_PATH, 40)
    date_font = load_font(FONT_BOLD_PATH, 44)

    title = "London Cinema Showtimes"
    subtitle = "Independent & repertory screenings"
    date_line = target_date.strftime("%A %d %B %Y")

    draw.text((MARGIN, 220), title, font=title_font, fill=CHARCOAL)
    draw.text((MARGIN, 330), subtitle, font=subtitle_font, fill=MUTED)
    draw.line((MARGIN, 420, CANVAS_WIDTH - MARGIN, 420), fill=ACCENT, width=4)
    draw.text((MARGIN, 470), date_line, font=date_font, fill=ACCENT)
    draw.text((MARGIN, CANVAS_HEIGHT - 140), "Swipe for today’s listings", font=subtitle_font, fill=MUTED)
    return img


def render_cinema_slide(cinema_name: str, listings: dict[str, list[str]]) -> Image.Image:
    img = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), WHITE)
    draw = ImageDraw.Draw(img)
    header_font = load_font(FONT_BOLD_PATH, 56)
    film_font = load_font(FONT_BOLD_PATH, 34)
    time_font = load_font(FONT_REGULAR_PATH, 28)

    draw.text((MARGIN, 80), cinema_name, font=header_font, fill=CHARCOAL)
    draw.line((MARGIN, 160, CANVAS_WIDTH - MARGIN, 160), fill=ACCENT, width=3)

    y = 210
    max_width = CANVAS_WIDTH - 2 * MARGIN
    line_gap = 10
    block_gap = 24
    max_y = CANVAS_HEIGHT - 120

    for title, times in sorted(listings.items()):
        title_lines = wrap_text(draw, title, film_font, max_width)
        for line in title_lines:
            if y + 40 > max_y:
                draw.text((MARGIN, max_y - 40), "…", font=film_font, fill=MUTED)
                return img
            draw.text((MARGIN, y), line, font=film_font, fill=CHARCOAL)
            y += 40 + line_gap

        times_line = f"Times: {', '.join(times)}"
        time_lines = wrap_text(draw, times_line, time_font, max_width)
        for line in time_lines:
            if y + 32 > max_y:
                draw.text((MARGIN, max_y - 40), "…", font=film_font, fill=MUTED)
                return img
            draw.text((MARGIN, y), line, font=time_font, fill=MUTED)
            y += 32 + line_gap

        y += block_gap

    return img


def render_story_slide(target_date: datetime, cinema_names: list[str]) -> Image.Image:
    img = Image.new("RGB", (CANVAS_WIDTH, STORY_HEIGHT), OFF_WHITE)
    draw = ImageDraw.Draw(img)
    title_font = load_font(FONT_BOLD_PATH, 72)
    subtitle_font = load_font(FONT_REGULAR_PATH, 36)
    list_font = load_font(FONT_BOLD_PATH, 38)

    draw.text((MARGIN, 220), "London Showtimes", font=title_font, fill=CHARCOAL)
    draw.text((MARGIN, 320), target_date.strftime("%A %d %B"), font=subtitle_font, fill=ACCENT)

    y = 420
    for name in cinema_names[:6]:
        draw.text((MARGIN, y), f"• {name}", font=list_font, fill=CHARCOAL)
        y += 60

    draw.line((MARGIN, STORY_HEIGHT - 280, CANVAS_WIDTH - MARGIN, STORY_HEIGHT - 280), fill=ACCENT, width=4)
    draw.text((MARGIN, STORY_HEIGHT - 220), "Full schedule in bio", font=subtitle_font, fill=MUTED)
    return img


def build_caption(target_date: datetime, cinema_names: list[str]) -> str:
    header = f"London cinema showtimes for {target_date.strftime('%A %d %B %Y')}"
    cinemas = ", ".join(cinema_names)
    return "\n".join([
        header,
        "",
        "Cinemas in today’s roundup:",
        cinemas,
        "",
        "#LondonCinema #IndependentCinema #FilmListings",
    ])


def main() -> None:
    cleanup_previous_outputs()
    showtimes = load_showtimes()
    target_date = select_target_date(showtimes)
    schedule = build_schedule(showtimes, target_date)
    if not schedule:
        raise ValueError("No showtimes found for selected date.")

    cinema_names = sorted(schedule.keys())
    cover = render_cover_slide(target_date)
    cover.save(OUTPUT_DIR / "post_image_01.png")

    max_cinema_slides = SLIDE_LIMIT - 1
    for idx, cinema_name in enumerate(cinema_names[:max_cinema_slides], start=2):
        slide = render_cinema_slide(cinema_name, schedule[cinema_name])
        slide.save(OUTPUT_DIR / f"post_image_{idx:02d}.png")

    story = render_story_slide(target_date, cinema_names)
    story.save(OUTPUT_DIR / "story_image_01.png")

    caption = build_caption(target_date, cinema_names)
    OUTPUT_CAPTION_PATH.write_text(caption, encoding="utf-8")

    print(f"✅ Generated {min(len(cinema_names), max_cinema_slides) + 1} feed slides.")
    print("✅ Generated 1 story slide.")
    print(f"✅ Saved caption to {OUTPUT_CAPTION_PATH}")


if __name__ == "__main__":
    main()
