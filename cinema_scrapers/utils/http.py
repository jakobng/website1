"""Shared HTTP helpers used by the cinema scrapers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import requests
from requests import Session

DEFAULT_TIMEOUT = 20


@dataclass(slots=True)
class HttpClient:
    """Small wrapper around :class:`requests.Session` with sane defaults."""

    session: Session
    headers: Dict[str, str]
    timeout: int = DEFAULT_TIMEOUT

    def get(self, url: str, *, binary: bool = False, **kwargs) -> str | bytes:
        merged_headers = dict(self.headers)
        merged_headers.update(kwargs.pop("headers", {}))
        response = self.session.get(url, headers=merged_headers, timeout=kwargs.pop("timeout", self.timeout), **kwargs)
        response.raise_for_status()
        if binary:
            return response.content
        response.encoding = response.encoding or "utf-8"
        return response.text


_default_client: Optional[HttpClient] = None


def get_default_client(headers: Optional[Dict[str, str]] = None) -> HttpClient:
    global _default_client
    if _default_client is None:
        _default_client = HttpClient(session=requests.Session(), headers=headers or {})
    elif headers:
        _default_client.headers.update(headers)
    return _default_client
