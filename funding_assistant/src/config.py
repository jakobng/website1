from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def _get_int(key: str, default: int) -> int:
    """Get an environment variable as int, handling empty strings."""
    val = os.getenv(key, "")
    if val.strip() == "":
        return default
    return int(val)


@dataclass
class AppConfig:
    base_dir: Path = Path(__file__).resolve().parents[1]
    data_dir: Path = Path(os.getenv("DATA_DIR", base_dir / "data"))
    projects_path: Path = Path(os.getenv("PROJECTS_PATH", data_dir / "projects.yml"))
    sources_path: Path = Path(os.getenv("SOURCES_PATH", data_dir / "sources.yml"))
    db_path: Path = Path(os.getenv("DB_PATH", data_dir / "results.db"))

    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    search_provider: str = os.getenv("SEARCH_PROVIDER", "gemini_grounded")
    query_strategy: str = os.getenv("QUERY_STRATEGY", "broad")

    brave_api_key: str | None = os.getenv("BRAVE_API_KEY")
    serpapi_api_key: str | None = os.getenv("SERPAPI_API_KEY")
    bing_api_key: str | None = os.getenv("BING_API_KEY")
    bing_endpoint: str = os.getenv(
        "BING_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search"
    )

    smtp_host: str | None = os.getenv("SMTP_HOST")
    smtp_port: int = _get_int("SMTP_PORT", 587)
    smtp_user: str | None = os.getenv("SMTP_USER")
    smtp_pass: str | None = os.getenv("SMTP_PASS")
    imap_host: str | None = os.getenv("IMAP_HOST")
    imap_user: str | None = os.getenv("IMAP_USER")
    imap_pass: str | None = os.getenv("IMAP_PASS")
    from_email: str | None = os.getenv("FROM_EMAIL")
    to_email: str | None = os.getenv("TO_EMAIL")

    discovery_interval_hours: int = _get_int("DISCOVERY_INTERVAL_HOURS", 24)
    reply_check_minutes: int = _get_int("REPLY_CHECK_MINUTES", 30)

    max_results_per_query: int = _get_int("MAX_RESULTS_PER_QUERY", 5)
    max_queries_per_project: int = _get_int("MAX_QUERIES_PER_PROJECT", 30)
    followup_depth: int = _get_int("FOLLOWUP_DEPTH", 2)
    debug: bool = os.getenv("DEBUG", "").lower() in {"1", "true", "yes"}
