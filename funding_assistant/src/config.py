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


def _get_smtp_host(email: str | None) -> str | None:
    """Infer SMTP host from email address if not explicitly set."""
    explicit = os.getenv("SMTP_HOST", "").strip()
    if explicit:
        return explicit
    
    if not email:
        return None
    
    # Infer from email domain
    domain = email.split("@")[-1].lower() if "@" in email else ""
    
    smtp_hosts = {
        "gmail.com": "smtp.gmail.com",
        "googlemail.com": "smtp.gmail.com",
        "outlook.com": "smtp.office365.com",
        "hotmail.com": "smtp.office365.com",
        "yahoo.com": "smtp.mail.yahoo.com",
        "icloud.com": "smtp.mail.me.com",
    }
    
    return smtp_hosts.get(domain)


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

    # Email config - supports both explicit settings and simple SMTP_EMAIL/SMTP_PASSWORD
    _smtp_email: str | None = os.getenv("SMTP_EMAIL") or os.getenv("SMTP_USER")
    smtp_user: str | None = os.getenv("SMTP_USER") or os.getenv("SMTP_EMAIL")
    smtp_pass: str | None = os.getenv("SMTP_PASS") or os.getenv("SMTP_PASSWORD")
    smtp_host: str | None = _get_smtp_host(_smtp_email)
    smtp_port: int = _get_int("SMTP_PORT", 587)
    from_email: str | None = os.getenv("FROM_EMAIL") or os.getenv("SMTP_EMAIL")
    to_email: str | None = os.getenv("TO_EMAIL")
    imap_host: str | None = os.getenv("IMAP_HOST")
    imap_user: str | None = os.getenv("IMAP_USER")
    imap_pass: str | None = os.getenv("IMAP_PASS")

    discovery_interval_hours: int = _get_int("DISCOVERY_INTERVAL_HOURS", 24)
    reply_check_minutes: int = _get_int("REPLY_CHECK_MINUTES", 30)

    max_results_per_query: int = _get_int("MAX_RESULTS_PER_QUERY", 5)
    max_queries_per_project: int = _get_int("MAX_QUERIES_PER_PROJECT", 30)
    followup_depth: int = _get_int("FOLLOWUP_DEPTH", 2)
    debug: bool = os.getenv("DEBUG", "").lower() in {"1", "true", "yes"}
