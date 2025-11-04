# bluestudio_module.py
# Robust scraper for Cinema Blue Studio (シネマブルースタジオ)
# - Layout-agnostic parsing
# - Hard CP932 (Shift_JIS) decoding to avoid mojibake
# - Duplicate title+range suppression
# - Improved director parsing
# - Adds date_dow and film_id fields to each record

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from calendar import day_name
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- Constants ---
CINEMA_NAME = "シネマブルースタジオ"
BASE_URL = "https://www.art-center.jp/tokyo/bluestudio/schedule.html"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BluestudioScraper/1.3)"}


# --- HTTP / Parsing Utilities ---
def _session() -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods={"GET"},
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.headers.update(HEADERS)
    return s


def _bs4_parse(text: str, prefer_html5lib: bool = True) -> BeautifulSoup:
    """
    Parse HTML text with BeautifulSoup. Prefer 'html5lib' if available;
    fallback to 'html.parser' so the script never crashes if html5lib is missing.
    """
    if prefer_html5lib:
        try:
            return BeautifulSoup(text, "html5lib")
        except Exception:
            return BeautifulSoup(text, "html.parser")
    return BeautifulSoup(text, "html.parser")


def fetch_soup(url: str) -> Optional[BeautifulSoup]:
    """
    Fetch URL and return BeautifulSoup, decoding the body as CP932 (Shift_JIS superset)
    regardless of HTTP headers to avoid mojibake that breaks Japanese label matching.
    """
    try:
        sess = _session()
        resp = sess.get(url, timeout=25)
        resp.raise_for_status()
        raw = resp.content  # bytes

        # Hard-decode as CP932; replace errors to avoid crashes.
        try:
            text = raw.decode("cp932", errors="replace")
        except Exception:
            text = raw.decode("utf-8", errors="replace")

        # If the page declares a different charset and it's not SJIS family, try to re-decode.
        m = re.search(r'<meta[^>]+charset=["\']?([\w\-]+)', text, flags=re.IGNORECASE)
        if m:
            meta_enc = m.group(1).lower()
            if meta_enc not in {"shift_jis", "shift-jis", "sjis", "cp932", "windows-31j"}:
                try:
                    text = raw.decode(meta_enc, errors="replace")
                except Exception:
                    pass  # keep cp932-decoded text

        soup = _bs4_parse(text, prefer_html5lib=True)
        # Safe parser reporting (HTML5TreeBuilder lacks `.name`)
        features = getattr(soup.builder, "features", set()) or set()
        parser_str = "html5lib" if ("html5lib" in features or "html5lib-treebuilder" in features) else "html.parser"
        print(
            f"DEBUG: HTTP {resp.status_code}, bytes={len(raw)}, chars={len(text)}, parser={parser_str}",
            file=sys.stderr,
        )
        return soup
    except requests.RequestException as e:
        print(f"ERROR: [{CINEMA_NAME}] Fetching/parsing failed: {e}", file=sys.stderr)
        return None


# --- Text normalization ---
_FW_DIGITS = "０１２３４５６７８９：／（）～－ー．．　⇒→"
_HW_DIGITS = "0123456789:/()~--..  ->"
_TRANS = str.maketrans(dict(zip(_FW_DIGITS, _HW_DIGITS)))


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    # Collapse digit-separated spaces (e.g., "19： 00")
    text = re.sub(r"(\d)\s+(\d)", r"\1\2", text)
    text = text.translate(_TRANS)
    # Normalize various arrows to '->'
    text = re.sub(r"(⇒|→|→|→)", "->", text)
    # Collapse whitespace
    return " ".join(text.strip().split())


# --- Date helpers ---
_WEEKDAY_JP = {"月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6}


def _extract_date_range(text: str) -> Optional[Tuple[dt.date, dt.date]]:
    """
    Extract (start_date, end_date) from blocks like:
    2025/8/27（水）～2025/9/9（火） or 2025/8/27（水）～9/9（火）
    """
    t = _normalize_text(text)

    # Start (YYYY/M/D)
    m_start = re.search(r"(\d{4})[./](\d{1,2})[./](\d{1,2})", t)
    if not m_start:
        return None
    y, mo, d = map(int, m_start.groups())
    start = dt.date(y, mo, d)

    # End (YYYY optional)
    tail = t[m_start.end():]
    m_end = re.search(r"[~〜\-\-ー―\s]+(?:(\d{4})[./])?(\d{1,2})[./](\d{1,2})", tail)
    if not m_end:
        return None
    y2_str, mo2_str, d2_str = m_end.groups()
    y2 = int(y2_str) if y2_str else y
    mo2 = int(mo2_str)
    d2 = int(d2_str)

    # Handle year roll-over if month goes far backwards (e.g., Dec -> Jan)
    if not y2_str and mo2 < start.month and (start.month - mo2) > 6:
        y2 = y + 1

    end = dt.date(y2, mo2, d2)
    if end < start:
        end = dt.date(y2 + 1, mo2, d2)
    return start, end


# --- Showtime extraction ---
_TIME_RE = r"\b(\d{1,2}):(\d{2})\b"


def _extract_times(text: str) -> List[str]:
    """
    Extract a cluster of showtimes from the line/segment following 「上映時間」.
    """
    t = _normalize_text(text)
    m = re.search(r"上映時間[^0-9]*([0-9:/・･ ,　／/]+)", t)
    if not m:
        return []
    seg = m.group(1)
    parts = re.split(r"[／/・･,\s]+", seg)
    times = []
    for p in parts:
        p = p.strip()
        if re.fullmatch(_TIME_RE, p):
            times.append(p)
    times = list(dict.fromkeys(times))
    return sorted(times)


# --- Details parsing ---
def _parse_details_from_text(text: str) -> Dict:
    details = {"director": None, "year": None, "runtime_min": None, "country": None, "synopsis": None}
    normalized_text = _normalize_text(text)

    # Director (tolerate colon, Japanese colon, or just whitespace; allow full-width spaces)
    # Examples: "監督: 黒沢清", "監督：黒沢 清", "監督  黒沢清", "監督・脚本：黒沢清"
    m = re.search(
        r"監督(?:・脚本)?\s*[:：]?\s*([^\s／/()]+(?:[・･\s　][^\s／/()]+)*)",
        normalized_text
    )
    if not m:
        # Fallback: handle cases where label and name are separated oddly
        m = re.search(r"監督(?:・脚本)?\s*[：: ]\s*([\w一-龥ぁ-んァ-ン・･　\s]+)", normalized_text)
    if m:
        details["director"] = re.sub(r"\s{2,}", " ", m.group(1)).strip()

    # Runtime
    m = re.search(r"\((\d{2,3})分\)", normalized_text)
    if m:
        details["runtime_min"] = m.group(1)

    # Year / Country (e.g., "2002年 日本")
    m = re.search(r"(\d{4})年\s*([^\s()]+)?", normalized_text)
    if m:
        details["year"] = m.group(1)
        country = (m.group(2) or "").strip()
        if country and not re.search(r"分$", country):
            details["country"] = country

    # Synopsis (optional)
    m = re.search(r"(?:あらすじ|ストーリー|解説)\s*[:：]?\s*(.+?)(?=(?:\(c\)|©|\(\d{2,3}分\)|$))", normalized_text)
    if m:
        details["synopsis"] = m.group(1).strip()

    return details


# --- Notes interpreter ---
def _interpret_notes_for_day(day: dt.date, base_times: List[str], notes: str) -> List[str]:
    """
    Apply weekly shifts and per-date cancellations/shifts.
    """
    times_for_day = list(base_times)
    n = _normalize_text(notes)

    # Weekly time shift: "毎週水曜・金曜は19:00->19:30に変更"
    m = re.search(r"毎週([月火水木金土日](?:・[月火水木金土日])*)曜?[^0-9]*?(\d{1,2}:\d{2})\s*->\s*(\d{1,2}:\d{2})", n)
    if m:
        days_jp, from_time, to_time = m.groups()
        selected = [_WEEKDAY_JP[d] for d in days_jp.split("・") if d in _WEEKDAY_JP]
        if day.weekday() in selected:
            times_for_day = [to_time if t == from_time else t for t in times_for_day]

    # Per-date cancellation like "9/9(火) 16:00 休映" or just "9/9(火) 休映"
    for m in re.finditer(r"(\d{1,2})/(\d{1,2})\s*（?.?）?\s*(\d{1,2}:\d{2})?.*?(休映|休演)", n):
        mo, dd, t_opt, _ = m.groups()
        if day.month == int(mo) and day.day == int(dd):
            if t_opt:
                times_for_day = [t for t in times_for_day if t != t_opt]
            else:
                times_for_day = []

    # Per-date one-off time shift: "9/9(火) 19:00 -> 19:30"
    for m in re.finditer(r"(\d{1,2})/(\d{1,2})\s*（?.?）?\s*(\d{1,2}:\d{2})\s*->\s*(\d{1,2}:\d{2})", n):
        mo, dd, from_time, to_time = m.groups()
        if day.month == int(mo) and day.day == int(dd):
            times_for_day = [to_time if t == from_time else t for t in times_for_day]

    return sorted(list(dict.fromkeys(times_for_day)))


# --- Nearby text utilities for fallback parsing ---
def _closest_title(node: Tag) -> str:
    """Find a plausible title near a given node (look for bold/header nearby)."""
    for cand in node.find_all_previous(["b", "strong", "h1", "h2", "h3"], limit=5):
        t = _normalize_text(cand.get_text())
        if t and len(t) >= 2 and "上映期間" not in t and "上映時間" not in t:
            return t
    sib = node.previous_sibling
    hops = 0
    while sib and hops < 5:
        if hasattr(sib, "get_text"):
            t = _normalize_text(sib.get_text())
            if t and len(t) >= 2 and "上映期間" not in t and "上映時間" not in t:
                return t.split("※")[0]
        sib = sib.previous_sibling
        hops += 1
    return ""


def _find_text_nearby(node: Tag, label: str) -> str:
    """Return text content of the first node near 'node' that contains 'label'."""
    t = node.get_text(" ", strip=True)
    if label in t:
        return t
    for sib in list(node.next_siblings)[:4] + list(node.previous_siblings)[:4]:
        if hasattr(sib, "get_text"):
            ts = sib.get_text(" ", strip=True)
            if label in ts:
                return ts
    if node.parent and hasattr(node.parent, "get_text"):
        tp = node.parent.get_text(" ", strip=True)
        if label in tp:
            return tp
    return ""


# --- Main Scraper ---
def scrape_bluestudio(max_days: int = 14, debug_dump: bool = False) -> List[Dict]:
    """Scrape all movie showings and details from Cinema Blue Studio."""
    print(f"INFO: [{CINEMA_NAME}] Starting scrape...", file=sys.stderr)

    soup = fetch_soup(BASE_URL)
    if not soup:
        return []

    if debug_dump:
        try:
            html = soup.decode() if hasattr(soup, "decode") else str(soup)
            Path("bluestudio_raw.html").write_text(html, encoding="utf-8")
            print("DEBUG: Wrote bluestudio_raw.html", file=sys.stderr)
        except Exception as e:
            print(f"DEBUG: Failed to write raw HTML: {e}", file=sys.stderr)

    all_showings: List[Dict] = []
    today = dt.date.today()
    cutoff = today + dt.timedelta(days=max_days)

    # ---------- Primary path: legacy table layout ----------
    schedule_tables: List[Tag] = []
    for tbl in soup.find_all("table"):
        txt = tbl.get_text(" ", strip=True)
        if "上映期間" in txt and "上映時間" in txt:
            schedule_tables.append(tbl)

    print(f"INFO: [{CINEMA_NAME}] Found {len(schedule_tables)} candidate schedule tables.", file=sys.stderr)

    # De-dupe identical title + date-range blocks
    seen_blocks = set()  # (title, start_date, end_date)

    def process_block(title: str, block_text: str):
        nonlocal all_showings, seen_blocks
        title = _normalize_text(title.split("※")[0])
        if not title:
            return

        date_range = _extract_date_range(block_text)
        if not date_range:
            print(f"WARN: [{CINEMA_NAME}] No date range for '{title}'. Skipping.", file=sys.stderr)
            return
        start_date, end_date = date_range

        key = (title, start_date, end_date)
        if key in seen_blocks:
            return
        seen_blocks.add(key)

        base_showtimes = _extract_times(block_text)
        if not base_showtimes:
            print(f"WARN: [{CINEMA_NAME}] No showtimes for '{title}'. Skipping.", file=sys.stderr)
            return

        notes_text = " ".join([_normalize_text(m.strip()) for m in re.findall(r"※\s*(.+)", block_text)])
        details = _parse_details_from_text(block_text)

        day = max(today, start_date)
        while day <= end_date and day < cutoff:
            times = _interpret_notes_for_day(day, base_showtimes, notes_text)
            for showtime in times:
                all_showings.append(
                    {
                        "cinema_name": CINEMA_NAME,
                        "movie_title": title,
                        "date_text": day.isoformat(),
                        "date_dow": day_name[day.weekday()],
                        "showtime": showtime,
                        "screen_name": None,
                        "detail_page_url": BASE_URL,
                        "film_id": re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-"),
                        **details,
                    }
                )
            day += dt.timedelta(days=1)

    # Process legacy tables if present
    for table in schedule_tables:
        table_text = table.get_text(separator="\n", strip=True)
        title_tag = (table.select_one("b, strong") or (table.find("td") if table.find("td") else None))
        title = _normalize_text(title_tag.get_text()) if title_tag else ""
        process_block(title, table_text)

    # ---------- Fallback path: label-driven scan (no tables) ----------
    if not all_showings:
        print(f"INFO: [{CINEMA_NAME}] Using fallback scanner (non-table layout).", file=sys.stderr)

        period_nodes: List[Tag] = []
        for el in soup.find_all(string=re.compile("上映期間")):
            node = el.parent if hasattr(el, "parent") else None
            if not node:
                continue
            period_nodes.append(node)

        print(f"INFO: [{CINEMA_NAME}] Found {len(period_nodes)} '上映期間' anchors.", file=sys.stderr)

        visited: set = set()
        for node in period_nodes:
            period_text = _find_text_nearby(node, "上映期間")
            time_text = _find_text_nearby(node, "上映時間")
            block_text = _normalize_text(f"{period_text} {time_text}".strip())

            if (period_text, time_text) in visited:
                continue
            visited.add((period_text, time_text))

            title = _closest_title(node)
            if not title:
                anc = node.parent
                hops = 0
                while anc and not title and hops < 3:
                    title = _closest_title(anc)
                    anc = anc.parent
                    hops += 1

            if not title:
                raw = node.get_text(" ", strip=True)
                title = raw.split("上映期間")[0].strip()

            if "上映期間" in block_text and "上映時間" in block_text:
                process_block(title, block_text)

    all_showings.sort(key=lambda x: (x.get("date_text", ""), x.get("showtime", "")))
    print(f"INFO: [{CINEMA_NAME}] Scrape complete. Found {len(all_showings)} showings.", file=sys.stderr)
    return all_showings


# --- CLI ---
def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Scrape showtimes from Cinema Blue Studio.")
    p.add_argument("--max-days", type=int, default=10, help="How many days ahead to include (default: 10).")
    p.add_argument(
        "--out",
        type=Path,
        default=Path("bluestudio_showtimes.json"),
        help="Output JSON path (default: bluestudio_showtimes.json).",
    )
    p.add_argument(
        "--debug",
        action="store_true",
        help="Dump fetched HTML to bluestudio_raw.html and add extra stderr logging.",
    )
    return p


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    args = _build_argparser().parse_args()
    showings = scrape_bluestudio(max_days=args.max_days, debug_dump=args.debug)

    if showings:
        with args.out.open("w", encoding="utf-8") as f:
            json.dump(showings, f, ensure_ascii=False, indent=2)
        print(
            f"\nINFO: Successfully created '{args.out}' with {len(showings)} records.",
            file=sys.stderr,
        )
    else:
        print(f"\nNo showings found for {CINEMA_NAME}.")
