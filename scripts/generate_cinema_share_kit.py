#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "cinemas" / "share-kit"
OUTPUT_JSON = OUTPUT_DIR / "weekly-share-kit.json"
OUTPUT_MD = OUTPUT_DIR / "weekly-share-kit.md"


CITIES = {
    "tokyo": {
        "name": "Tokyo Mini-Theater",
        "page": "https://www.leonelki.com/tokyo-cinemas.html",
        "data": ROOT / "tokyo-cinema-scrapers" / "data" / "showtimes.json",
        "jp": "東京ミニシアター上映情報",
    },
    "london": {
        "name": "London Independent Cinema",
        "page": "https://www.leonelki.com/london-cinemas.html",
        "data": ROOT / "london-cinema-scrapers" / "data" / "showtimes.json",
        "jp": "ロンドンのインディペンデント映画館上映情報",
    },
    "manchester": {
        "name": "Manchester Cinema",
        "page": "https://www.leonelki.com/manchester-cinemas.html",
        "data": ROOT / "manchester_cinema_scrapers" / "data" / "showtimes.json",
        "jp": "マンチェスター映画館上映情報",
    },
    "taipei": {
        "name": "Taipei Independent Cinema",
        "page": "https://www.leonelki.com/taipei-cinemas.html",
        "data": ROOT / "taipei-cinema-scrapers" / "data" / "showtimes.json",
        "jp": "台北インディペンデント映画上映情報",
    },
}


def load_showtimes(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def title_for(item: dict) -> str:
    return (
        item.get("movie_title_en")
        or item.get("tmdb_title")
        or item.get("movie_title_jp")
        or item.get("movie_title")
        or "Untitled"
    )


def build_city_pack(city: str, config: dict) -> dict:
    today = date.today().isoformat()
    upcoming = [
        item for item in load_showtimes(config["data"])
        if str(item.get("date_text", "")) >= today
    ]
    cinema_count = len({item.get("cinema_name") for item in upcoming if item.get("cinema_name")})
    film_counter = Counter(title_for(item) for item in upcoming)
    top_films = [title for title, _ in film_counter.most_common(5)]
    dates = sorted({item.get("date_text") for item in upcoming if item.get("date_text")})
    date_range = ""
    if dates:
        date_range = dates[0] if dates[0] == dates[-1] else f"{dates[0]} to {dates[-1]}"

    en = (
        f"{config['name']} now has {len(upcoming)} upcoming showtimes "
        f"across {cinema_count} venues. Search by film, date, cinema, region, "
        f"or what is closest to you: {config['page']}"
    )
    ja = (
        f"{config['jp']}を更新しました。"
        f"現在 {cinema_count} 館、{len(upcoming)} 件の上映を検索できます。"
        f"作品名・日付・地域・現在地から探せます: {config['page']}"
    )

    return {
        "city": city,
        "name": config["name"],
        "page": config["page"],
        "upcoming_showtimes": len(upcoming),
        "cinemas": cinema_count,
        "date_range": date_range,
        "top_films": top_films,
        "copy": {
            "en": en,
            "ja": ja,
        },
    }


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    packs = [build_city_pack(city, config) for city, config in CITIES.items()]
    payload = {
        "generated_at": generated_at,
        "packs": packs,
    }
    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [f"# Weekly Cinema Share Kit", "", f"Generated: {generated_at}", ""]
    for pack in packs:
        lines.extend(
            [
                f"## {pack['name']}",
                "",
                f"- Page: {pack['page']}",
                f"- Upcoming showtimes: {pack['upcoming_showtimes']}",
                f"- Cinemas/venues: {pack['cinemas']}",
                f"- Date range: {pack['date_range'] or 'n/a'}",
                f"- Top films: {', '.join(pack['top_films']) if pack['top_films'] else 'n/a'}",
                "",
                "English:",
                pack["copy"]["en"],
                "",
                "Japanese:",
                pack["copy"]["ja"],
                "",
            ]
        )
    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUTPUT_JSON}")
    print(f"Wrote {OUTPUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
