"""Utility helpers shared across scrapers."""
from .http import HttpClient, get_default_client
from .parsing import clean_title, extract_runtime, extract_year

__all__ = [
    "HttpClient",
    "get_default_client",
    "clean_title",
    "extract_runtime",
    "extract_year",
]
