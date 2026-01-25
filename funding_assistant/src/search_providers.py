from __future__ import annotations

import dataclasses
import json
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Iterable

import requests

try:
    from google import genai as genai_ground
    from google.genai import types as genai_types

    GENAI_GROUND_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    genai_ground = None
    genai_types = None
    GENAI_GROUND_AVAILABLE = False


# Default timeout in seconds for grounded search
DEFAULT_SEARCH_TIMEOUT = 90


@dataclasses.dataclass
class SearchResult:
    title: str
    url: str
    snippet: str | None = None
    extra_snippets: list[str] | None = None  # Additional excerpts from the page
    source: str | None = None
    raw: dict | None = None
    
    def get_full_text(self) -> str:
        """Combine all text for LLM analysis."""
        parts = [self.title or ""]
        if self.snippet:
            parts.append(self.snippet)
        if self.extra_snippets:
            parts.extend(self.extra_snippets)
        return "\n".join(parts)


class SearchProvider:
    name = "base"

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        raise NotImplementedError


def _extract_json(text: str) -> list[dict]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


class GeminiGroundedSearchProvider(SearchProvider):
    name = "gemini_grounded"

    def __init__(self, api_key: str, model: str) -> None:
        if not GENAI_GROUND_AVAILABLE:
            raise RuntimeError(
                "google-genai is required for Gemini grounding. Install with: pip install google-genai"
            )
        self.client = genai_ground.Client(api_key=api_key)
        self.model = model

    def _build_config(self):
        if not genai_types:
            return None
        tool = None
        if hasattr(genai_types, "Tool") and hasattr(genai_types, "GoogleSearch"):
            tool = genai_types.Tool(google_search=genai_types.GoogleSearch())
        elif hasattr(genai_types, "Tool") and hasattr(genai_types, "GoogleSearchRetrieval"):
            tool = genai_types.Tool(
                google_search_retrieval=genai_types.GoogleSearchRetrieval()
            )
        if not tool or not hasattr(genai_types, "GenerateContentConfig"):
            return None
        return genai_types.GenerateContentConfig(
            tools=[tool],
            temperature=0.2,
        )

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        config = self._build_config()
        if config is None:
            raise RuntimeError(
                "Gemini grounding tool not available in google-genai SDK. Update the package."
            )
        prompt = (
            "Search the web for current documentary film funding opportunities.\n"
            f"Query: {query}\n"
            f"Return a JSON array of up to {max_results} items with keys: title, url, snippet."
        )
        
        def _call_api():
            return self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
        
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_call_api)
                response = future.result(timeout=DEFAULT_SEARCH_TIMEOUT)
        except FuturesTimeoutError:
            print(f"Search timeout for query: {query[:50]}...")
            return []
        except Exception as e:
            print(f"Search error: {e}")
            return []
        
        results: list[SearchResult] = []
        
        # Try to extract grounding metadata first (more reliable)
        grounding_results = self._extract_grounding_sources(response, max_results)
        if grounding_results:
            results.extend(grounding_results)
        
        # Also parse the model's JSON response for additional context
        text = getattr(response, "text", "") or ""
        data = _extract_json(text)
        
        # Merge grounding sources with model's parsed results
        seen_urls = {r.url for r in results}
        for item in data[:max_results]:
            url = str(item.get("url", ""))
            if url and url not in seen_urls:
                results.append(
                    SearchResult(
                        title=str(item.get("title", "")),
                        url=url,
                        snippet=item.get("snippet"),
                        source=self.name,
                        raw=item,
                    )
                )
                seen_urls.add(url)
        
        return results[:max_results]
    
    def _extract_grounding_sources(self, response, max_results: int) -> list[SearchResult]:
        """Extract actual sources from Gemini's grounding metadata."""
        results: list[SearchResult] = []
        
        try:
            # Navigate the response structure to find grounding metadata
            candidates = getattr(response, "candidates", None)
            if not candidates:
                return results
            
            for candidate in candidates:
                grounding_metadata = getattr(candidate, "grounding_metadata", None)
                if not grounding_metadata:
                    continue
                
                # Try grounding_chunks (newer API)
                chunks = getattr(grounding_metadata, "grounding_chunks", None)
                if chunks:
                    for chunk in chunks[:max_results]:
                        web = getattr(chunk, "web", None)
                        if web:
                            results.append(
                                SearchResult(
                                    title=getattr(web, "title", "") or "",
                                    url=getattr(web, "uri", "") or "",
                                    snippet=None,
                                    source=f"{self.name}_grounded",
                                    raw={"grounded": True},
                                )
                            )
                
                # Try grounding_supports (alternative structure)
                supports = getattr(grounding_metadata, "grounding_supports", None)
                if supports:
                    for support in supports[:max_results]:
                        sources = getattr(support, "grounding_chunk_indices", None)
                        # This gives indices into grounding_chunks, already handled above
                
                # Try search_entry_point for rendered results
                search_entry = getattr(grounding_metadata, "search_entry_point", None)
                if search_entry:
                    rendered = getattr(search_entry, "rendered_content", None)
                    # This is HTML content, could parse if needed
                
                # Try web_search_queries to see what was searched
                web_queries = getattr(grounding_metadata, "web_search_queries", None)
                if web_queries:
                    # Could log these for debugging
                    pass
                    
        except Exception as e:
            # Grounding metadata extraction failed, fall back to JSON parsing
            print(f"Grounding metadata extraction failed: {e}")
        
        return results


class BraveSearchProvider(SearchProvider):
    name = "brave"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self._last_request_time = 0.0

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        import time
        
        # Rate limiting: wait at least 1 second between requests (free tier limit)
        elapsed = time.time() - self._last_request_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self._last_request_time = time.time()
                response = requests.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={
                        "q": query,
                        "count": max_results,
                        "extra_snippets": "true",  # Get additional excerpts from pages
                        "text_decorations": "false",  # Clean text without HTML
                    },
                    headers={"X-Subscription-Token": self.api_key, "Accept": "application/json"},
                    timeout=30,
                )
                
                if response.status_code == 429:
                    # Rate limited - wait and retry
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    print(f"  Rate limited, waiting {wait_time}s...", flush=True)
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                data = response.json()
                results = []
                for item in data.get("web", {}).get("results", [])[:max_results]:
                    results.append(
                        SearchResult(
                            title=item.get("title", ""),
                            url=item.get("url", ""),
                            snippet=item.get("description"),
                            extra_snippets=item.get("extra_snippets"),  # Up to 5 additional excerpts
                            source=self.name,
                            raw=item,
                        )
                    )
                return results
                
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429 and attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"  Rate limited, waiting {wait_time}s...", flush=True)
                    time.sleep(wait_time)
                    continue
                print(f"  Search error: {e}", flush=True)
                return []
            except Exception as e:
                print(f"  Search error: {e}", flush=True)
                return []
        
        print(f"  Max retries exceeded for query", flush=True)
        return []


class SerpApiSearchProvider(SearchProvider):
    name = "serpapi"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        response = requests.get(
            "https://serpapi.com/search.json",
            params={"q": query, "api_key": self.api_key, "engine": "google"},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        results = []
        for item in data.get("organic_results", [])[:max_results]:
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet"),
                    source=self.name,
                    raw=item,
                )
            )
        return results


class BingSearchProvider(SearchProvider):
    name = "bing"

    def __init__(self, api_key: str, endpoint: str) -> None:
        self.api_key = api_key
        self.endpoint = endpoint

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        response = requests.get(
            self.endpoint,
            params={"q": query, "count": max_results},
            headers={"Ocp-Apim-Subscription-Key": self.api_key},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        results = []
        for item in data.get("webPages", {}).get("value", [])[:max_results]:
            results.append(
                SearchResult(
                    title=item.get("name", ""),
                    url=item.get("url", ""),
                    snippet=item.get("snippet"),
                    source=self.name,
                    raw=item,
                )
            )
        return results


class MockSearchProvider(SearchProvider):
    name = "mock"

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        return [
            SearchResult(
                title=f"No provider configured for query: {query}",
                url="",
                snippet="Set BRAVE_API_KEY or SERPAPI_API_KEY or BING_API_KEY.",
                source=self.name,
                raw={"query": query},
            )
        ]


class MultiSearchProvider(SearchProvider):
    def __init__(self, providers: Iterable[SearchProvider]) -> None:
        self.providers = list(providers)
        self.name = ",".join(provider.name for provider in self.providers) or "multi"

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        results: list[SearchResult] = []
        per_provider = max(1, max_results // max(1, len(self.providers)))
        for provider in self.providers:
            results.extend(provider.search(query, per_provider))
        return results[:max_results]
