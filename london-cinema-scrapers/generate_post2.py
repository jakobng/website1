"""
Generate Instagram-ready movie spotlight carousel + caption for London showtimes.
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
OUTPUT_CAPTION_PATH = OUTPUT_DIR / "post_v2_caption.txt"

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
ACCENT = (32, 82, 149)


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


def build_film_schedule(showtimes: Iterable[dict], target_date: datetime) -> dict[str, dict[str, list[str]]]:
    schedule: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    target_str = target_date.strftime("%Y-%m-%d")
    for entry in showtimes:
        if entry.get("date_text") != target_str:
            continue
        title = entry.get("movie_title_en") or entry.get("movie_title") or "Untitled"
        cinema = entry.get("cinema_name", "Unknown Cinema")
        time_str = entry.get("showtime") or "TBD"
        schedule[title][cinema].append(time_str)
    for cinema_map in schedule.values():
        for times in cinema_map.values():
            times.sort()
    return dict(schedule)


def cleanup_previous_outputs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for filename in OUTPUT_DIR.glob("post_v2_image_*.png"):
        filename.unlink()
    for filename in OUTPUT_DIR.glob("story_v2_image_*.png"):
        filename.unlink()
    for filename in OUTPUT_DIR.glob("post_v2_caption.txt"):
        filename.unlink()


def render_cover_slide(target_date: datetime) -> Image.Image:
    img = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), OFF_WHITE)
    draw = ImageDraw.Draw(img)
    title_font = load_font(FONT_BOLD_PATH, 72)
    subtitle_font = load_font(FONT_REGULAR_PATH, 40)
    date_font = load_font(FONT_BOLD_PATH, 44)

    title = "London Film Spotlights"
    subtitle = "Top films across the city"
    date_line = target_date.strftime("%A %d %B %Y")

    draw.text((MARGIN, 220), title, font=title_font, fill=CHARCOAL)
    draw.text((MARGIN, 330), subtitle, font=subtitle_font, fill=MUTED)
    draw.line((MARGIN, 420, CANVAS_WIDTH - MARGIN, 420), fill=ACCENT, width=4)
    draw.text((MARGIN, 470), date_line, font=date_font, fill=ACCENT)
    draw.text((MARGIN, CANVAS_HEIGHT - 140), "Swipe for film spotlights", font=subtitle_font, fill=MUTED)
    return img


def render_film_slide(title: str, cinema_map: dict[str, list[str]]) -> Image.Image:
    img = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), WHITE)
    draw = ImageDraw.Draw(img)
    header_font = load_font(FONT_BOLD_PATH, 56)
    cinema_font = load_font(FONT_BOLD_PATH, 32)
    time_font = load_font(FONT_REGULAR_PATH, 26)

    title_lines = wrap_text(draw, title, header_font, CANVAS_WIDTH - 2 * MARGIN)
    y = 80
    for line in title_lines:
        draw.text((MARGIN, y), line, font=header_font, fill=CHARCOAL)
        y += 64

    draw.line((MARGIN, y + 10, CANVAS_WIDTH - MARGIN, y + 10), fill=ACCENT, width=3)
    y += 50

    max_y = CANVAS_HEIGHT - 120
    for cinema, times in sorted(cinema_map.items()):
        cinema_lines = wrap_text(draw, cinema, cinema_font, CANVAS_WIDTH - 2 * MARGIN)
        for line in cinema_lines:
            if y + 36 > max_y:
                draw.text((MARGIN, max_y - 40), "…", font=cinema_font, fill=MUTED)
                return img
            draw.text((MARGIN, y), line, font=cinema_font, fill=CHARCOAL)
            y += 36

        times_line = f"Times: {', '.join(times)}"
        time_lines = wrap_text(draw, times_line, time_font, CANVAS_WIDTH - 2 * MARGIN)
        for line in time_lines:
            if y + 30 > max_y:
                draw.text((MARGIN, max_y - 40), "…", font=cinema_font, fill=MUTED)
                return img
            draw.text((MARGIN, y), line, font=time_font, fill=MUTED)
            y += 30

        y += 22

    return img


def render_story_slide(target_date: datetime, film_titles: list[str]) -> Image.Image:
    img = Image.new("RGB", (CANVAS_WIDTH, STORY_HEIGHT), OFF_WHITE)
    draw = ImageDraw.Draw(img)
    title_font = load_font(FONT_BOLD_PATH, 72)
    subtitle_font = load_font(FONT_REGULAR_PATH, 36)
    list_font = load_font(FONT_BOLD_PATH, 36)

    draw.text((MARGIN, 220), "Film Spotlights", font=title_font, fill=CHARCOAL)
    draw.text((MARGIN, 320), target_date.strftime("%A %d %B"), font=subtitle_font, fill=ACCENT)

    y = 420
    for title in film_titles[:6]:
        line = f"• {title}"
        draw.text((MARGIN, y), line, font=list_font, fill=CHARCOAL)
        y += 58

    draw.line((MARGIN, STORY_HEIGHT - 280, CANVAS_WIDTH - MARGIN, STORY_HEIGHT - 280), fill=ACCENT, width=4)
    draw.text((MARGIN, STORY_HEIGHT - 220), "Full listings in bio", font=subtitle_font, fill=MUTED)
    return img


def build_caption(target_date: datetime, film_titles: list[str]) -> str:
    header = f"London film spotlights for {target_date.strftime('%A %d %B %Y')}"
    films = ", ".join(film_titles)
    return "\n".join([
        header,
        "",
        "Featured films today:",
        films,
        "",
        "#LondonCinema #FilmSpotlight #IndieFilm",
    ])


def main() -> None:
    cleanup_previous_outputs()
    showtimes = load_showtimes()
    target_date = select_target_date(showtimes)
    schedule = build_film_schedule(showtimes, target_date)
    if not schedule:
        raise ValueError("No showtimes found for selected date.")

    film_titles = sorted(schedule.keys(), key=lambda title: sum(len(times) for times in schedule[title].values()), reverse=True)
    cover = render_cover_slide(target_date)
    cover.save(OUTPUT_DIR / "post_v2_image_01.png")

    max_film_slides = SLIDE_LIMIT - 1
    for idx, title in enumerate(film_titles[:max_film_slides], start=2):
        slide = render_film_slide(title, schedule[title])
        slide.save(OUTPUT_DIR / f"post_v2_image_{idx:02d}.png")

    story = render_story_slide(target_date, film_titles)
    story.save(OUTPUT_DIR / "story_v2_image_01.png")

    caption = build_caption(target_date, film_titles)
    OUTPUT_CAPTION_PATH.write_text(caption, encoding="utf-8")

    print(f"✅ Generated {min(len(film_titles), max_film_slides) + 1} feed slides.")
    print("✅ Generated 1 story slide.")
    print(f"✅ Saved caption to {OUTPUT_CAPTION_PATH}")


if __name__ == "__main__":
    main()
