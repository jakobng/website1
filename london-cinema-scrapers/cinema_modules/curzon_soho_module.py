#!/usr/bin/env python3
# curzon_soho_module.py
# Scraper for Curzon Soho cinema
# https://www.curzon.com/venues/soho/
#
# Structure: JavaScript-rendered page using Vista WebClient
# Uses Playwright to render the page and extract showtimes

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from typing import Dict, List, Optional

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

BASE_URL = "https://www.curzon.com"
VENUE_URL = f"{BASE_URL}/venues/soho/"
CINEMA_NAME = "Curzon Soho"

TODAY = dt.date.today()
WINDOW_DAYS = 14


def _clean(text: str) -> str:
    """Clean whitespace and normalize text."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip())


def _parse_runtime(runtime_str: str) -> str:
    """
    Parse runtime string like "2h 6m" or "2h 29m" to minutes.
    Returns string of minutes or empty string.
    """
    if not runtime_str:
        return ""

    runtime_str = runtime_str.strip()
    hours = 0
    minutes = 0

    # Match "2h 6m" or "2h" or "90m" patterns
    hour_match = re.search(r"(\d+)\s*h", runtime_str, re.I)
    min_match = re.search(r"(\d+)\s*m", runtime_str, re.I)

    if hour_match:
        hours = int(hour_match.group(1))
    if min_match:
        minutes = int(min_match.group(1))

    total_minutes = hours * 60 + minutes
    return str(total_minutes) if total_minutes > 0 else ""


def _parse_date_from_picker(day_str: str, day_num: str, month_str: str) -> Optional[dt.date]:
    """
    Parse date from the date picker elements.
    day_str: "Sat", "Sun", etc or "Today"
    day_num: "10", "11", etc
    month_str: "Jan", "Feb", etc
    """
    if day_str.lower() == "today":
        return TODAY

    try:
        day = int(day_num)
        current_year = TODAY.year

        # Parse month
        month_map = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4,
            "may": 5, "jun": 6, "jul": 7, "aug": 8,
            "sep": 9, "oct": 10, "nov": 11, "dec": 12
        }
        month = month_map.get(month_str.lower()[:3])
        if not month:
            return None

        # Construct date
        try:
            parsed_date = dt.date(current_year, month, day)
        except ValueError:
            return None

        # If date is far in the past, assume next year
        if parsed_date < TODAY - dt.timedelta(days=30):
            parsed_date = dt.date(current_year + 1, month, day)

        return parsed_date
    except (ValueError, AttributeError):
        return None


def _parse_iso_datetime(iso_str: str) -> Optional[dt.datetime]:
    """
    Parse ISO datetime string like "2026-01-09T12:00:00.000Z"
    Returns datetime object or None.
    """
    if not iso_str:
        return None

    try:
        # Handle various ISO formats
        iso_str = iso_str.replace("Z", "+00:00")
        if "." in iso_str:
            # Remove milliseconds for simpler parsing
            iso_str = re.sub(r"\.\d+", "", iso_str)
        return dt.datetime.fromisoformat(iso_str)
    except ValueError:
        return None


def _dismiss_yie_overlay(page) -> None:
    """Hide Yieldify overlay/backdrop if present."""
    try:
        if not page.query_selector("[id^='yie-overlay-'], [id^='yie-backdrop-']"):
            return
        page.add_style_tag(
            content="[id^='yie-overlay-'], [id^='yie-backdrop-'] { display: none !important; }"
        )
        page.evaluate(
            "() => {"
            "document.querySelectorAll('[id^=\"yie-overlay-\"], [id^=\"yie-backdrop-\"]')"
            ".forEach(el => el.remove());"
            "}"
        )
        page.wait_for_timeout(100)
    except Exception as exc:
        print(f"[{CINEMA_NAME}] Overlay dismissal failed: {exc}", file=sys.stderr)


def scrape_curzon_soho() -> List[Dict]:
    """
    Scrape Curzon Soho showtimes using Playwright.

    Returns a list of showtime records with standard schema.
    """
    shows = []

    print(f"[{CINEMA_NAME}] Starting Playwright scraper...", file=sys.stderr)

    try:
        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            # Navigate to venue page
            print(f"[{CINEMA_NAME}] Loading {VENUE_URL}", file=sys.stderr)
            page.goto(VENUE_URL, wait_until="networkidle", timeout=60000)

            # Wait for film list to load
            try:
                page.wait_for_selector(".v-showtime-picker-film-list", timeout=30000)
            except PlaywrightTimeout:
                print(f"[{CINEMA_NAME}] Timeout waiting for film list", file=sys.stderr)
                browser.close()
                return []

            _dismiss_yie_overlay(page)

            # Get all available dates from the date picker
            date_elements = page.query_selector_all(".v-date-picker-date")
            dates_to_scrape = []

            for date_elem in date_elements:
                # Check if date is inactive (no showings)
                button = date_elem.query_selector(".v-date-picker-date__button")
                if button and "v-date-picker-date__button--inactive" in (button.get_attribute("class") or ""):
                    continue

                # Extract date parts
                spans = date_elem.query_selector_all(".v-display-text-part")
                if len(spans) >= 1:
                    if len(spans) == 1:
                        # "Today"
                        day_str = spans[0].inner_text().strip()
                        if day_str.lower() == "today":
                            dates_to_scrape.append((TODAY, date_elem))
                    elif len(spans) >= 3:
                        # "Sat", "10", "Jan"
                        day_str = spans[0].inner_text().strip()
                        day_num = spans[1].inner_text().strip()
                        month_str = spans[2].inner_text().strip()
                        parsed_date = _parse_date_from_picker(day_str, day_num, month_str)
                        if parsed_date and TODAY <= parsed_date < TODAY + dt.timedelta(days=WINDOW_DAYS):
                            dates_to_scrape.append((parsed_date, date_elem))

            print(f"[{CINEMA_NAME}] Found {len(dates_to_scrape)} dates to scrape", file=sys.stderr)

            # Scrape each date
            for show_date, date_elem in dates_to_scrape:
                # Click on date to load its showtimes
                button = date_elem.query_selector(".v-date-picker-date__button")
                if button:
                    _dismiss_yie_overlay(page)
                    button.click()
                    # Wait for content to update
                    page.wait_for_timeout(1500)

                # Extract films for this date
                film_items = page.query_selector_all(".v-showtime-picker-film-list__item")

                for film_item in film_items:
                    # Extract film title
                    title_elem = film_item.query_selector(".v-film-title__text")
                    if not title_elem:
                        continue

                    film_title = _clean(title_elem.inner_text())
                    if not film_title:
                        continue

                    # Extract detail page URL
                    detail_link = film_item.query_selector(".v-showtime-picker-film-details__film-link")
                    detail_url = ""
                    if detail_link:
                        href = detail_link.get_attribute("href")
                        if href:
                            detail_url = BASE_URL + href if href.startswith("/") else href

                    # Extract synopsis
                    synopsis_elem = film_item.query_selector(".v-film-synopsis .v-detail__content")
                    synopsis = _clean(synopsis_elem.inner_text()) if synopsis_elem else ""

                    # Extract runtime
                    runtime_elem = film_item.query_selector(".v-film-runtime .v-detail__content")
                    runtime_str = _clean(runtime_elem.inner_text()) if runtime_elem else ""
                    runtime_min = _parse_runtime(runtime_str)

                    # Extract showtimes
                    showtime_buttons = film_item.query_selector_all(".v-showtime-button")

                    for st_btn in showtime_buttons:
                        # Get time from datetime attribute
                        time_elem = st_btn.query_selector("time.v-showtime-button__detail-start-time")
                        if not time_elem:
                            continue

                        datetime_attr = time_elem.get_attribute("datetime")
                        parsed_dt = _parse_iso_datetime(datetime_attr)

                        if not parsed_dt:
                            continue

                        # Convert UTC to local UK time (simplified - assumes GMT)
                        showtime = parsed_dt.strftime("%H:%M")

                        # Get booking URL
                        booking_url = ""
                        href = st_btn.get_attribute("href")
                        if href:
                            booking_url = BASE_URL + href if href.startswith("/") else href

                        # Extract format tags (e.g., Open Captioned)
                        format_tags = []
                        attr_icons = st_btn.query_selector_all(".v-attribute__img img")
                        for icon in attr_icons:
                            alt_text = icon.get_attribute("alt")
                            if alt_text:
                                format_tags.append(alt_text)

                        shows.append({
                            "cinema_name": CINEMA_NAME,
                            "movie_title": film_title,
                            "movie_title_en": film_title,
                            "date_text": show_date.isoformat(),
                            "showtime": showtime,
                            "detail_page_url": detail_url,
                            "booking_url": booking_url,
                            "director": "",
                            "year": "",
                            "country": "",
                            "runtime_min": runtime_min,
                            "synopsis": synopsis[:500] if synopsis else "",
                            "format_tags": format_tags,
                        })

            browser.close()

        print(f"[{CINEMA_NAME}] Found {len(shows)} total showings", file=sys.stderr)

    except Exception as e:
        print(f"[{CINEMA_NAME}] Error: {e}", file=sys.stderr)
        raise

    # Deduplicate
    seen = set()
    unique_shows = []
    for s in shows:
        key = (s["movie_title"], s["date_text"], s["showtime"])
        if key not in seen:
            seen.add(key)
            unique_shows.append(s)

    return sorted(unique_shows, key=lambda x: (x["date_text"], x["showtime"], x["movie_title"]))


if __name__ == "__main__":
    data = scrape_curzon_soho()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"\n[INFO] Total: {len(data)} showings", file=sys.stderr)
