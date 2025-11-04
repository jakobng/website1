from __future__ import annotations

import datetime as dt
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# --- Constants ---
CINEMA_NAME = "池袋シネマ・ロサ"
# Eigaland (for schedule)
EIGALAND_URL = "https://schedule.eigaland.com/schedule?webKey=c34cee0e-5a5e-4b99-8978-f04879a82299"


# Cinema Rosa site (for details)
ROSA_BASE_URL = "https://www.cinemarosa.net/"
ROSA_NOWSHOWING_URL = urljoin(ROSA_BASE_URL, "/nowshowing/")
ROSA_INDIES_URL = urljoin(ROSA_BASE_URL, "/indies/")

SAMPLE_DATA_DIR = Path(__file__).with_name("sample_data")
SAMPLE_EIGALAND_PAYLOAD = SAMPLE_DATA_DIR / "cinema_rosa_eigaland_payload.json"


def _clean_title_for_matching(text: Optional[str]) -> str:
    """A more aggressive cleaning function to create a reliable key for matching."""
    if not text:
        return ""
    text = unicodedata.normalize('NFKC', text)
    text = text.replace('映画 ', '').replace(' ', '')
    text = re.sub(r'[【『「《\(（].*?[】』」》\)）]', '', text)
    text = re.sub(r'[<【『「]', '', text)
    return text.strip()

def _clean_text(text: Optional[str]) -> str:
    """Normalizes whitespace for display text."""
    if not text: return ""
    return ' '.join(text.strip().split())

def _fetch_soup(url: str) -> Optional[BeautifulSoup]:
    """Fetches a static URL and returns a BeautifulSoup object."""
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
        response.raise_for_status()
        return BeautifulSoup(response.content, 'html.parser')
    except requests.RequestException as e:
        print(f"ERROR: [{CINEMA_NAME}] Could not fetch static page {url}: {e}", file=sys.stderr)
        return None

def _parse_date_from_eigaland(date_str: str, current_year: int) -> Optional[dt.date]:
    """Parses date strings like '6/23' from the Eigaland calendar."""
    if match := re.match(r"(\d{1,2})/(\d{1,2})", date_str):
        month, day = map(int, match.groups())
        try:
            year = current_year + 1 if month < dt.date.today().month else current_year
            return dt.date(year, month, day)
        except ValueError: return None
    return None

def _as_clean_text(value: Optional[object]) -> str:
    if value is None:
        return ""
    text = str(value)
    return ' '.join(text.strip().split())


def _coerce_nuxt_like_json(text: str) -> Optional[str]:
    if not text:
        return None
    replacements = {
        ':undefined': ':null',
        'undefined': 'null',
        '!0': 'true',
        '!1': 'false',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _parse_eigaland_html_payload(html: str) -> Optional[dict]:
    if not html:
        return None
    soup = BeautifulSoup(html, 'html.parser')
    script_tag = soup.select_one('script#__NUXT_DATA__')
    if script_tag and script_tag.string:
        try:
            return json.loads(script_tag.string)
        except json.JSONDecodeError:
            pass

    script_tag = soup.select_one('script#__NUXT__')
    if script_tag and script_tag.string:
        coerced = _coerce_nuxt_like_json(script_tag.string)
        if coerced:
            try:
                return json.loads(coerced)
            except json.JSONDecodeError:
                pass

    match = re.search(r'window\.__NUXT__\s*=\s*({.*?})\s*;</script>', html, re.S)
    if not match:
        match = re.search(r'window\.__NUXT__\s*=\s*({.*?})\s*;', html, re.S)
    if match:
        coerced = _coerce_nuxt_like_json(match.group(1))
        if coerced:
            try:
                return json.loads(coerced)
            except json.JSONDecodeError:
                pass
    return None


def _fetch_eigaland_payload() -> Optional[dict]:
    try:
        response = requests.get(EIGALAND_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        response.raise_for_status()
        payload = _parse_eigaland_html_payload(response.text)
        if payload:
            return payload
        print(f"WARN: [{CINEMA_NAME}] Unable to parse Eigaland payload from HTML.", file=sys.stderr)
    except requests.RequestException as e:
        print(f"ERROR: [{CINEMA_NAME}] Could not fetch Eigaland schedule: {e}", file=sys.stderr)

    if SAMPLE_EIGALAND_PAYLOAD.exists():
        try:
            print(f"INFO: [{CINEMA_NAME}] Falling back to local Eigaland payload sample.", file=sys.stderr)
            return json.loads(SAMPLE_EIGALAND_PAYLOAD.read_text(encoding='utf-8'))
        except Exception as read_err:
            print(f"ERROR: [{CINEMA_NAME}] Failed reading fallback payload: {read_err}", file=sys.stderr)
    return None


def _normalize_date_value(raw_date: Optional[object]) -> Optional[str]:
    text = _as_clean_text(raw_date)
    if not text:
        return None
    if re.match(r"\d{4}-\d{2}-\d{2}", text):
        return text[:10]
    if re.match(r"\d{4}/\d{2}/\d{2}", text):
        parts = text.split('/')
        return f"{parts[0]}-{parts[1]}-{parts[2]}"
    if re.match(r"\d{1,2}/\d{1,2}", text):
        parsed = _parse_date_from_eigaland(text, dt.date.today().year)
        if parsed:
            return parsed.isoformat()
    return None


def _extract_schedule_from_payload(payload: object) -> List[Dict[str, str]]:
    showings: List[Dict[str, str]] = []
    seen: set[Tuple[str, str, str, Optional[str]]] = set()

    def traverse(node: object, context: Dict[str, Optional[str]]) -> None:
        if isinstance(node, dict):
            local_ctx = dict(context)

            for date_key in ('date', 'playDate', 'showDate', 'screeningDate', 'play_date', 'show_date'):
                if date_key in node:
                    normalized = _normalize_date_value(node.get(date_key))
                    if normalized:
                        local_ctx['date'] = normalized
                        break

            movie_dict = node.get('movie') if isinstance(node.get('movie'), dict) else None
            possible_titles: List[str] = []
            if movie_dict:
                for key in ('movieTitle', 'title', 'name'):
                    if movie_dict.get(key):
                        possible_titles.append(_as_clean_text(movie_dict.get(key)))
            for key in ('movieTitle', 'movieName', 'title'):
                if node.get(key):
                    possible_titles.append(_as_clean_text(node.get(key)))

            for candidate in possible_titles:
                if candidate and candidate != CINEMA_NAME:
                    local_ctx['title'] = candidate
                    break

            screen_candidate: Optional[str] = None
            if isinstance(node.get('screen'), dict):
                screen_candidate = _as_clean_text(node['screen'].get('name') or node['screen'].get('screenName'))
            elif isinstance(node.get('screen'), str):
                screen_candidate = _as_clean_text(node['screen'])
            elif node.get('screenName'):
                screen_candidate = _as_clean_text(node.get('screenName'))
            if screen_candidate:
                local_ctx['screen'] = screen_candidate

            booking_candidate = node.get('bookingUrl') or node.get('booking_url') or node.get('purchaseUrl') or node.get('purchase_url')
            if not booking_candidate and node.get('scheduleId'):
                schedule_id = _as_clean_text(node.get('scheduleId'))
                if schedule_id:
                    booking_candidate = f"https://app.eigaland.com/booking?&scheduleId={schedule_id}"
            if booking_candidate:
                local_ctx['booking_url'] = booking_candidate

            detail_candidate = node.get('detailUrl') or node.get('detail_url')
            if detail_candidate:
                local_ctx['detail_url'] = _as_clean_text(detail_candidate)

            start_time: Optional[str] = None
            for key in ('startTime', 'start_time', 'showTime', 'time'):
                if node.get(key):
                    start_time = _as_clean_text(node.get(key))
                    break

            if start_time and local_ctx.get('title') and local_ctx.get('date'):
                dedupe_key = (local_ctx['date'], local_ctx['title'], start_time, local_ctx.get('screen'))
                if dedupe_key not in seen:
                    seen.add(dedupe_key)
                    showings.append({
                        "movie_title": local_ctx['title'],
                        "date_text": local_ctx['date'],
                        "showtime": start_time,
                        "screen_name": local_ctx.get('screen'),
                        "purchase_url": local_ctx.get('booking_url'),
                        "detail_page_url": local_ctx.get('detail_url'),
                    })

            for child in node.values():
                traverse(child, local_ctx)

        elif isinstance(node, list):
            for item in node:
                traverse(item, context)

    traverse(payload, {})
    return showings


def _load_eigaland_schedule() -> List[Dict[str, str]]:
    payload = _fetch_eigaland_payload()
    if not payload:
        return []
    return _extract_schedule_from_payload(payload)


def _parse_rosa_detail_page(soup: BeautifulSoup) -> Dict[str, Optional[str]]:
    """Parses a movie detail page from cinemarosa.net."""
    details = {"director": None, "year": None, "runtime_min": None, "country": None, "synopsis": None}
    if info_p := soup.select_one("p.film_info"):
        film_info_text = ' '.join(info_p.get_text(separator=' ').split())
        if match := re.search(r"(\d{4})\s*/", film_info_text): details["year"] = match.group(1)
        if match := re.search(r"(\d+時間)?\s*(\d+)分", film_info_text):
            h = int(re.sub(r'\D', '', match.group(1))) if match.group(1) else 0
            m = int(match.group(2))
            details["runtime_min"] = str(h * 60 + m)
        if parts := [p.strip() for p in film_info_text.split('/') if p]:
            if len(parts) > 1 and details["year"]: details["country"] = parts[1].strip()
    if film_txt_div := soup.select_one("div.film_txt"):
        for p_tag in film_txt_div.find_all('p'):
            if "監督" in p_tag.text:
                details["director"] = _clean_text(p_tag.text).replace("監督", "").lstrip(":： ").split(' ')[0]
                break
    if synopsis_div := soup.select_one("div.free_area"): details["synopsis"] = _clean_text(synopsis_div.text)
    return details

# --- Main Scraping Logic ---

def scrape_cinema_rosa() -> List[Dict[str, str]]:
    details_cache: Dict[str, Dict] = {}
    for start_url in [ROSA_NOWSHOWING_URL, ROSA_INDIES_URL]:
        print(f"INFO: [{CINEMA_NAME}] Fetching movie list from {start_url}", file=sys.stderr)
        soup = _fetch_soup(start_url)
        if not soup:
            continue
        for link in soup.select(".show_box a"):
            title_node = link.select_one(".show_title")
            if not title_node:
                continue
            raw_title = _clean_text(title_node.text)
            title_key = _clean_title_for_matching(raw_title)
            if title_key in details_cache:
                continue
            detail_url = urljoin(ROSA_BASE_URL, link.get('href', ''))
            detail_soup = _fetch_soup(detail_url) if detail_url else None
            if detail_soup:
                print(f"  Scraping details for '{raw_title}'...", file=sys.stderr)
                details = _parse_rosa_detail_page(detail_soup)
                details["detail_page_url"] = detail_url
                details_cache[title_key] = details
    print(f"INFO: [{CINEMA_NAME}] Built cache for {len(details_cache)} movies.", file=sys.stderr)

    eigaland_showings = _load_eigaland_schedule()
    showings: List[Dict[str, Optional[str]]] = []
    unmatched_titles = set()

    for entry in eigaland_showings:
        raw_title = _clean_text(entry.get("movie_title"))
        if not raw_title:
            continue
        title_key = _clean_title_for_matching(raw_title)
        details = details_cache.get(title_key, {})
        if not details:
            unmatched_titles.add(raw_title)
        record = {
            "cinema_name": CINEMA_NAME,
            "movie_title": raw_title,
            "date_text": entry.get("date_text"),
            "showtime": entry.get("showtime"),
            "screen_name": entry.get("screen_name"),
            "purchase_url": entry.get("purchase_url"),
        }
        record.update({
            "director": details.get("director"),
            "year": details.get("year"),
            "country": details.get("country"),
            "runtime_min": details.get("runtime_min"),
            "synopsis": details.get("synopsis"),
            "detail_page_url": details.get("detail_page_url") or entry.get("detail_page_url"),
        })
        showings.append(record)

    if unmatched_titles:
        print(f"WARN: [{CINEMA_NAME}] Missing detailed info for: {', '.join(sorted(unmatched_titles))}", file=sys.stderr)

    unique = {(s.get("date_text"), s.get("movie_title"), s.get("showtime"), s.get("screen_name")): s for s in showings}
    final_list = sorted(unique.values(), key=lambda r: (r.get("date_text", ""), r.get("showtime", ""), r.get("movie_title", "")))
    print(f"INFO: [{CINEMA_NAME}] Collected {len(final_list)} unique showings.")
    return final_list

if __name__ == '__main__':
    if sys.platform == "win32": sys.stdout.reconfigure(encoding='utf-8')
    showings = scrape_cinema_rosa()
    if showings:
        output_filename = "cinema_rosa_showtimes.json"
        print(f"\nINFO: Writing {len(showings)} records to {output_filename}...")
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(showings, f, ensure_ascii=False, indent=2)
        print(f"INFO: Successfully created {output_filename}.")
        print("\n--- Sample of First Showing ---")
        from pprint import pprint
        pprint(showings[0])
    else:
        print(f"\nNo showings found for {CINEMA_NAME}.")
