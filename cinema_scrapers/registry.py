"""Registry of cinema scrapers with lightweight adapters."""
from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Dict, List, Sequence

from .base import Normalizer, ScraperAdapter, ScraperMetadata, ScraperProtocol


@dataclass(frozen=True)
class ScraperSpec:
    module: str
    callable_name: str
    slug: str
    cinema_name: str
    normalizer: Normalizer | None = None


_DEF_NORMALIZERS: Dict[str, Normalizer] = {}


def _normalize_eurospace_schema(rows: Sequence[Dict[str, object]]) -> Sequence[Dict[str, object]]:
    normalized = []
    for show in rows:
        normalized.append(
            {
                "cinema_name": show.get("cinema"),
                "movie_title": show.get("title"),
                "date_text": show.get("date"),
                "showtime": show.get("time"),
                "detail_page_url": show.get("url"),
                "director": show.get("director"),
                "year": str(show.get("year", "") or ""),
                "country": show.get("country"),
                "runtime_min": str(show.get("runtime", "") or ""),
                "synopsis": show.get("synopsis", ""),
                "movie_title_en": show.get("movie_title_en", ""),
            }
        )
    return normalized


_DEF_NORMALIZERS["eurospace_module"] = _normalize_eurospace_schema


_SPECS: List[ScraperSpec] = [
    ScraperSpec("bunkamura_module", "scrape_bunkamura", "bunkamura", "Bunkamura ル・シネマ 渋谷宮下"),
    ScraperSpec("ks_cinema_module", "scrape_ks_cinema", "ks-cinema", "K's Cinema"),
    ScraperSpec("shin_bungeiza_module", "scrape_shin_bungeiza", "shin-bungeiza", "シネマヴェーラ渋谷"),
    ScraperSpec("shimotakaido_module", "scrape_shimotakaido", "shimotakaido", "下高井戸シネマ"),
    ScraperSpec("stranger_module", "scrape_stranger", "stranger", "Stranger"),
    ScraperSpec("meguro_cinema_module", "scrape_meguro_cinema", "meguro-cinema", "目黒シネマ"),
    ScraperSpec("image_forum_module", "scrape", "image-forum", "シアター・イメージフォーラム"),
    ScraperSpec("theatre_shinjuku_module", "scrape_theatre_shinjuku", "theatre-shinjuku", "テアトル新宿"),
    ScraperSpec("polepole_module", "scrape_polepole", "polepole", "ポレポレ東中野"),
    ScraperSpec("bluestudio_module", "scrape_bluestudio", "cinema-blue-studio", "シネマ・ブルースタジオ"),
    ScraperSpec("human_shibuya_module", "scrape_human_shibuya", "human-shibuya", "ヒューマントラストシネマ渋谷"),
    ScraperSpec("human_yurakucho_module", "scrape_human_yurakucho", "human-yurakucho", "ヒューマントラストシネマ有楽町"),
    ScraperSpec("laputa_asagaya_module", "scrape_laputa_asagaya", "laputa-asagaya", "ラピュタ阿佐ヶ谷"),
    ScraperSpec("musashino_kan_module", "scrape_musashino_kan", "musashino-kan", "新宿武蔵野館"),
    ScraperSpec("waseda_shochiku_module", "scrape_waseda_shochiku", "waseda-shochiku", "早稲田松竹"),
    ScraperSpec("nfaj_calendar_module", "scrape_nfaj_calendar", "nfaj", "国立映画アーカイブ"),
    ScraperSpec("eurospace_module", "scrape", "eurospace", "ユーロスペース", _DEF_NORMALIZERS["eurospace_module"]),
    ScraperSpec("cinemart_shinjuku_module", "scrape_cinemart_shinjuku", "cinemart-shinjuku", "シネマート新宿"),
    ScraperSpec("cinema_qualite_module", "scrape_cinema_qualite", "cinema-qualite", "シネマカリテ"),
    ScraperSpec("cine_quinto_module", "scrape_cine_quinto", "cine-quinto", "シネクイント"),
    ScraperSpec("yebisu_garden_module", "scrape_yebisu_garden_cinema", "yebisu-garden", "YEBISU GARDEN CINEMA"),
    ScraperSpec("k2_cinema_module", "scrape_k2_cinema", "k2-cinema", "K2シネマ"),
    ScraperSpec("cinema_rosa_module", "scrape_cinema_rosa", "cinema-rosa", "シネマ・ロサ"),
    ScraperSpec("chupki_module", "scrape_chupki", "chupki", "Kino Cinema Chupki"),
    ScraperSpec("cine_switch_ginza_module", "scrape_cine_switch_ginza", "cine-switch-ginza", "シネスイッチ銀座"),
]


def _create_adapter(spec: ScraperSpec) -> ScraperAdapter:
    module = import_module(f"cinema_scrapers.venues.{spec.module}")
    runner = getattr(module, spec.callable_name)
    description = (getattr(module, "__doc__", "") or "").strip().splitlines()[0] if getattr(module, "__doc__", None) else ""
    metadata = ScraperMetadata(
        slug=spec.slug,
        cinema_name=spec.cinema_name,
        module=spec.module,
        description=description,
    )
    return ScraperAdapter(metadata=metadata, runner=runner, normalizer=spec.normalizer)


def load_scrapers() -> List[ScraperProtocol]:
    return [_create_adapter(spec) for spec in _SPECS]
