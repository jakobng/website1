"""Utility helpers for normalising film metadata."""
from __future__ import annotations

import re
from typing import Optional

_TITLE_SUFFIXES = [
    r"\s*★トークショー付き",
    r"\s*35mmフィルム上映",
    r"\s*4Kレストア5\.1chヴァージョン",
    r"\s*4Kデジタルリマスター版",
    r"\s*4Kレストア版",
    r"\s*４Kレーザー上映",
    r"\s*４K版",
    r"\s*４K",
    r"\s*4K",
    r"\s*（字幕版）",
    r"\s*（字幕）",
    r"\s*（吹替版）",
    r"\s*（吹替）",
    r"\s*THE MOVIE$",
    r"\s*\[受賞感謝上映］",
    r"\s*★上映後トーク付",
    r"\s*トークイベント付き",
    r"\s*vol\.\s*\d+",
    r"\s*［[^］]+(?:ｲﾍﾞﾝﾄ|イベント)］",
    r"\s*ライブ音響上映",
    r"\s*特別音響上映",
    r"\s*字幕付き上映",
    r"\s*デジタルリマスター版",
    r"\s*【完成披露試写会】",
    r"\s*Blu-ray発売記念上映",
    r"\s*公開記念舞台挨拶",
    r"\s*上映後舞台挨拶",
    r"\s*初日舞台挨拶",
    r"\s*２日目舞台挨拶",
    r"\s*トークショー",
    r"\s*一挙上映",
]
_SUFFIX_RE = re.compile("|".join(f"(?:{pattern})" for pattern in _TITLE_SUFFIXES), re.IGNORECASE)
_BRACKET_RE = re.compile(r"^[\[\(（【][^\]\)）】]*[\]\)）】]")
_WHITESPACE_RE = re.compile(r"\s{2,}")
_RUNTIME_RE = re.compile(r"(\d+)\s*分")
_YEAR_RE = re.compile(r"(19\d{2}|20\d{2})")


def clean_title(raw_title: str) -> str:
    if not raw_title:
        return ""
    title = _BRACKET_RE.sub("", raw_title).strip()
    title = _SUFFIX_RE.sub("", title).strip()
    title = title.replace("：", ":").replace("　", " ")
    return _WHITESPACE_RE.sub(" ", title).strip()


def extract_runtime(text: str) -> Optional[str]:
    if not text:
        return None
    match = _RUNTIME_RE.search(text)
    return match.group(1) if match else None


def extract_year(text: str) -> Optional[str]:
    if not text:
        return None
    match = _YEAR_RE.search(text)
    return match.group(1) if match else None
