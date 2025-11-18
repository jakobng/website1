"""Generate Instagram-ready image and caption for today's cinema showings.

This script reads ``showtimes.json`` produced by ``main_scraper.py`` and creates
``post_image.png`` and ``post_caption.txt`` using a provided template image and
fonts. The logic follows the specification described in the project brief so
that it can be executed automatically inside a GitHub Action.
"""
from __future__ import annotations

import json
import random
import textwrap
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFont

try:  # Python 3.9+
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - fallback for older versions
    ZoneInfo = None  # type: ignore


BASE_DIR = Path(__file__).resolve().parent
SHOWTIMES_PATH = BASE_DIR / "showtimes.json"
TEMPLATE_PATH = BASE_DIR / "template.png"
BOLD_FONT_PATH = BASE_DIR / "NotoSansJP-Bold.ttf"
REGULAR_FONT_PATH = BASE_DIR / "NotoSansJP-Regular.ttf"
OUTPUT_IMAGE_PATH = BASE_DIR / "post_image.png"
OUTPUT_CAPTION_PATH = BASE_DIR / "post_caption.txt"

LEFT_MARGIN = 60
TOP_MARGIN = 70
MAX_DRAW_Y = 950
FOOTER_Y = 1020
TITLE_WRAP_WIDTH = 28

BLACK = (0, 0, 0)
GRAY = (96, 96, 96)


def today_in_tokyo() -> datetime:
    """Return the current datetime in the Asia/Tokyo timezone if available."""
    if ZoneInfo is not None:
        return datetime.now(ZoneInfo("Asia/Tokyo"))
    return datetime.now()


def load_showtimes(today_str: str) -> List[Dict]:
    """Load today's showtimes from the JSON file."""
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


def choose_cinema(showings: List[Dict]) -> Tuple[str, List[Dict]]:
    """Group showings by cinema and pick one cinema at random."""
    grouped: Dict[str, List[Dict]] = defaultdict(list)
    for show in showings:
        cinema_name = show.get("cinema_name")
        if cinema_name:
            grouped[cinema_name].append(show)

    if not grouped:
        return "", []

    cinema_name = random.choice(list(grouped.keys()))
    return cinema_name, grouped[cinema_name]


def format_listings(showings: List[Dict]) -> List[Dict[str, str]]:
    """Format the showings into a sorted list of movie title/time strings."""
    movies: Dict[str, List[str]] = defaultdict(list)
    for show in showings:
        title = show.get("movie_title") or "タイトル未定"
        time_str = show.get("showtime") or ""
        if time_str:
            movies[title].append(time_str)

    formatted = []
    for title in sorted(movies.keys()):
        times_sorted = sorted(movies[title], key=lambda t: t)
        times_text = ", ".join(times_sorted)
        formatted.append({"title": title, "times": times_text})

    return formatted


def draw_image(cinema_name: str, date_jp: str, listings: List[Dict[str, str]]) -> None:
    """Create the Instagram image using the provided template and fonts."""
    try:
        template = Image.open(TEMPLATE_PATH).convert("RGBA")
    except FileNotFoundError:
        print(f"template.png not found at {TEMPLATE_PATH}")
        raise

    try:
        title_font = ImageFont.truetype(str(BOLD_FONT_PATH), 65)
        regular_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 40)
        small_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 30)
    except FileNotFoundError as exc:
        print("Font file missing:", exc)
        raise
    except OSError as exc:
        print("Unable to load font:", exc)
        raise

    draw = ImageDraw.Draw(template)

    y_pos = TOP_MARGIN
    draw.text((LEFT_MARGIN, y_pos), cinema_name, font=title_font, fill=BLACK)
    draw.text((LEFT_MARGIN, y_pos + 80), date_jp, font=small_font, fill=GRAY)
    y_pos += 150

    for listing in listings:
        if y_pos > MAX_DRAW_Y:
            break

        wrapped_title = textwrap.wrap(listing["title"], width=TITLE_WRAP_WIDTH) or [listing["title"]]
        for idx, line in enumerate(wrapped_title):
            draw.text((LEFT_MARGIN, y_pos), line, font=regular_font, fill=BLACK)
            y_pos += 50
        draw.text((LEFT_MARGIN + 30, y_pos), listing["times"], font=small_font, fill=GRAY)
        y_pos += 60

    draw.text((LEFT_MARGIN, FOOTER_Y), "詳細は leonelki.com/cinema-scrapers/ で", font=small_font, fill=GRAY)
    template.save(OUTPUT_IMAGE_PATH)


def build_hashtag(cinema_name: str) -> str:
    """Create a hashtag-friendly token from the cinema name."""
    cleaned = "".join(ch for ch in cinema_name if ch.isalnum() or "\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff")
    return cleaned or "cinema"


def write_caption(cinema_name: str, date_jp: str, listings: List[Dict[str, str]]) -> None:
    """Write the Instagram caption to a UTF-8 text file."""
    lines = [
        f"【{cinema_name}】",
        f"本日（{date_jp}）の上映情報です。",
        "",
    ]

    for listing in listings:
        lines.append(f"■ {listing['title']}")
        lines.append(listing["times"])
        lines.append("")

    hashtag = build_hashtag(cinema_name)
    lines.extend(
        [
            "詳細はプロフィールのリンクから！ leonelki.com/cinema-scrapers/",
            "#東京 #ミニシアター #映画 #映画館 #上映情報 #" + hashtag,
        ]
    )

    caption = "\n".join(lines).strip() + "\n"
    OUTPUT_CAPTION_PATH.write_text(caption, encoding="utf-8")


def main() -> None:
    today = today_in_tokyo().date()
    today_str = today.isoformat()
    date_jp = today.strftime("%Y年%m月%d日")

    todays_showings = load_showtimes(today_str)
    if not todays_showings:
        print("No showings for today.")
        return

    cinema_name, cinema_showings = choose_cinema(todays_showings)
    if not cinema_showings:
        print("No cinemas with showings today.")
        return

    listings = format_listings(cinema_showings)
    if not listings:
        print("Selected cinema has no valid listings.")
        return

    draw_image(cinema_name, date_jp, listings)
    write_caption(cinema_name, date_jp, listings)
    print(f"Generated post for {cinema_name} on {date_jp}.")


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError:
        pass
    except json.JSONDecodeError:
        pass
