from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from typing import Any


try:
    from google import genai
    from google.genai import types as genai_types

    GENAI_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    genai = None
    genai_types = None
    GENAI_AVAILABLE = False


# Default timeout in seconds for LLM calls
DEFAULT_TIMEOUT = 120


@dataclass
class LLMResponse:
    text: str
    data: Any | None = None


def _extract_json(text: str) -> Any | None:
    match = re.search(r"\{.*\}|\[.*\]", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


class LLMClient:
    def __init__(self, api_key: str | None, model: str) -> None:
        self.available = bool(api_key and GENAI_AVAILABLE)
        self.model = model
        self.api_key = api_key
        if self.available:
            print(f"Initializing Gemini client...", flush=True)
            self.client = genai.Client(api_key=api_key)
            # Skip model resolution - just use the model directly
            # The resolution was causing hangs on client.models.list()
            self.model = model
            print(f"Using model: {self.model}", flush=True)
        else:
            self.client = None

    def _generate(self, prompt: str, timeout: int = DEFAULT_TIMEOUT) -> str:
        """Generate content with timeout handling."""
        if not self.available or not self.client:
            return ""
        
        def _call_api():
            config = genai_types.GenerateContentConfig(temperature=0.3)
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
            return getattr(response, "text", "") or ""
        
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_call_api)
                return future.result(timeout=timeout)
        except FuturesTimeoutError:
            print(f"LLM timeout after {timeout}s")
            return ""
        except Exception as e:
            print(f"LLM error: {e}")
            return ""

    def expand_queries(self, project: dict, angles: list[dict], max_queries: int) -> list[str]:
        if not self.available:
            return _fallback_expand_queries(project, angles, max_queries)
        angle_text = "\n".join(
            f"- {angle['label']} ({angle['angle_type']})" for angle in angles
        )
        prompt = (
            "You are expanding funding search queries for a documentary.\n"
            "Rules: keep queries broad, use at most one theme or category per query, "
            "avoid multi-region combos, and prefer generic funding terms like "
            "'documentary grant', 'film fund', 'open call', 'apply', or a single theme.\n"
            f"Project title: {project['title']}\n"
            f"Synopsis: {project['synopsis']}\n"
            "Angles:\n"
            f"{angle_text}\n"
            f"Return a JSON array of at most {max_queries} search queries."
        )
        text = self._generate(prompt)
        data = _extract_json(text)
        if isinstance(data, list):
            return [str(item) for item in data if str(item).strip()]
        return _fallback_expand_queries(project, angles, max_queries)

    def score_results(self, project: dict, results: list[dict]) -> list[dict]:
        """Score results and extract metadata. Returns list of dicts with score, deadline, contact_info."""
        if not self.available:
            scores = _fallback_score_results(project, results)
            return [{"score": s, "deadline": None, "contact_info": None} for s in scores]
        prompt = (
            "Analyze each search result for a documentary funding search.\n"
            "For each result, provide:\n"
            "- score: 0-1 relevance score (prioritize current/upcoming opportunities, low scores for expired/closed)\n"
            "- deadline: application deadline if mentioned (format: YYYY-MM-DD or 'ongoing' or 'rolling' or null)\n"
            "- contact_info: any email, contact form URL, or contact instructions found (or null)\n\n"
            f"Project title: {project['title']}\n"
            f"Synopsis: {project['synopsis']}\n\n"
            "Return a JSON array of objects with keys: score, deadline, contact_info\n"
            "The array must have exactly the same number of items as the input results.\n\n"
            f"Results: {json.dumps(results, ensure_ascii=True)}"
        )
        text = self._generate(prompt)
        data = _extract_json(text)
        if isinstance(data, list) and len(data) == len(results):
            enriched = []
            for item in data:
                if isinstance(item, dict):
                    enriched.append({
                        "score": float(item.get("score", 0.5)),
                        "deadline": item.get("deadline"),
                        "contact_info": item.get("contact_info"),
                    })
                elif isinstance(item, (int, float)):
                    enriched.append({"score": float(item), "deadline": None, "contact_info": None})
                else:
                    enriched.append({"score": 0.5, "deadline": None, "contact_info": None})
            return enriched
        scores = _fallback_score_results(project, results)
        return [{"score": s, "deadline": None, "contact_info": None} for s in scores]

    def suggest_pivots(self, project: dict, results: list[dict]) -> list[str]:
        if not self.available:
            return []
        prompt = (
            "Suggest optional pivots for segments if funding opportunities imply better fit.\n"
            "Return a JSON array of strings. If helpful, prefix with [segment_id].\n"
            f"Project: {project['title']}\n"
            f"Segments: {json.dumps(project.get('segments', []), ensure_ascii=True)}\n"
            f"Results: {json.dumps(results[:5], ensure_ascii=True)}"
        )
        text = self._generate(prompt)
        data = _extract_json(text)
        if isinstance(data, list):
            return _normalize_pivot_suggestions(data)
        return []

    def draft_application(self, project: dict, result: dict) -> LLMResponse:
        if not self.available:
            return LLMResponse(text=_fallback_draft(project, result))
        prompt = (
            "Draft a short grant application note (max 200 words).\n"
            f"Project: {project['title']}\n"
            f"Synopsis: {project['synopsis']}\n"
            f"Target: {result.get('title')} - {result.get('url')}\n"
        )
        text = self._generate(prompt)
        return LLMResponse(text=text or _fallback_draft(project, result))

    def analyze_result(self, project: dict, result: dict) -> dict:
        """
        Rich analysis of a single search result.
        
        Returns dict with:
        - score: 0-1 relevance score
        - deadline: application deadline (YYYY-MM-DD, 'ongoing', 'rolling', or null)
        - grant_amount: funding amount/range (string or null)
        - is_open: true/false/unknown - is it currently accepting applications
        - eligibility_notes: key eligibility requirements
        - topic_match: which project topics align with this funder
        - funder_type: foundation/government/broadcaster/corporate/ngo/other
        - contact_info: email, form URL, or application instructions
        - summary: 1-2 sentence summary of the opportunity
        """
        if not self.available:
            return self._fallback_analysis(result)
        
        # Build context about the project
        project_context = (
            f"Project: {project.get('title', 'Untitled')}\n"
            f"Synopsis: {project.get('synopsis', '')}\n"
            f"Topics: {', '.join(project.get('topic_summary', []))}\n"
        )
        
        # Get team eligibility info if available
        team_countries = set()
        for member in project.get("team", []):
            team_countries.update(member.get("funding_access", []))
            team_countries.update(member.get("citizenships", []))
        if team_countries:
            project_context += f"Team eligibility: {', '.join(team_countries)}\n"
        
        # Build the full text from the search result
        result_text = result.get("full_text", "")
        if not result_text:
            parts = [result.get("title", "")]
            if result.get("snippet"):
                parts.append(result["snippet"])
            if result.get("extra_snippets"):
                parts.extend(result["extra_snippets"])
            result_text = "\n".join(parts)
        
        prompt = f"""Analyze this funding opportunity for a documentary film project.

{project_context}

Search Result:
Title: {result.get('title', '')}
URL: {result.get('url', '')}
Content:
{result_text}

Respond with a JSON object containing:
{{
  "score": <0-1 relevance score, higher = better match for this project>,
  "deadline": <"YYYY-MM-DD" or "ongoing" or "rolling" or null if unknown>,
  "grant_amount": <amount/range as string like "$25,000" or "$10K-50K" or null>,
  "is_open": <true if accepting applications, false if closed, "unknown" if unclear>,
  "eligibility_notes": <key requirements like "US filmmakers only" or null>,
  "topic_match": <array of project topics that align, e.g. ["rivers", "indigenous rights"]>,
  "funder_type": <"foundation" or "government" or "broadcaster" or "corporate" or "ngo" or "film_fund" or "other">,
  "contact_info": <email, application URL, or brief instructions, or null>,
  "summary": <1-2 sentence summary of what this opportunity offers>
}}

Be accurate. If information is not available in the search result, use null.
Prioritize opportunities that are currently open or upcoming."""

        text = self._generate(prompt)
        data = _extract_json(text)
        
        if isinstance(data, dict):
            return {
                "score": float(data.get("score", 0.5)),
                "deadline": data.get("deadline"),
                "grant_amount": data.get("grant_amount"),
                "is_open": data.get("is_open"),
                "eligibility_notes": data.get("eligibility_notes"),
                "topic_match": data.get("topic_match", []),
                "funder_type": data.get("funder_type"),
                "contact_info": data.get("contact_info"),
                "summary": data.get("summary"),
            }
        
        return self._fallback_analysis(result)
    
    def _fallback_analysis(self, result: dict) -> dict:
        """Fallback when LLM is unavailable."""
        return {
            "score": 0.5,
            "deadline": None,
            "grant_amount": None,
            "is_open": "unknown",
            "eligibility_notes": None,
            "topic_match": [],
            "funder_type": "other",
            "contact_info": None,
            "summary": result.get("title", "No summary available"),
        }

    def analyze_results_batch(self, project: dict, results: list[dict]) -> list[dict]:
        """
        Analyze a batch of search results in a single LLM call.
        Much faster than individual calls.
        """
        if not self.available:
            return [self._fallback_analysis(r) for r in results]
        
        if not results:
            return []
        
        # Build context about the project
        project_context = (
            f"Project: {project.get('title', 'Untitled')}\n"
            f"Synopsis: {project.get('synopsis', '')}\n"
            f"Topics: {', '.join(project.get('topic_summary', []))}\n"
        )
        
        # Get team eligibility info if available
        team_countries = set()
        for member in project.get("team", []):
            team_countries.update(member.get("funding_access", []))
            team_countries.update(member.get("citizenships", []))
        if team_countries:
            project_context += f"Team eligibility: {', '.join(team_countries)}\n"
        
        # Build the results list for the prompt
        results_text = ""
        for i, result in enumerate(results):
            full_text = result.get("full_text", result.get("title", ""))
            results_text += f"\n--- Result {i+1} ---\n"
            results_text += f"Title: {result.get('title', '')}\n"
            results_text += f"URL: {result.get('url', '')}\n"
            results_text += f"Content: {full_text[:500]}\n"  # Limit content length
        
        prompt = f"""Analyze these funding opportunities for a documentary film project.

{project_context}

{results_text}

For EACH result, provide a JSON object with:
- score: 0-1 relevance (higher = better match)
- deadline: "YYYY-MM-DD" or "ongoing" or "rolling" or null
- grant_amount: amount as string like "$25,000" or null
- is_open: true/false/"unknown"
- eligibility_notes: key requirements or null
- topic_match: array of matching project topics
- funder_type: "foundation"/"government"/"broadcaster"/"corporate"/"ngo"/"film_fund"/"other"
- contact_info: email/URL or null
- summary: 1 sentence description

Return a JSON array with exactly {len(results)} objects, one per result in order.
Be accurate - use null if information is not available."""

        text = self._generate(prompt, timeout=180)  # Longer timeout for batch
        data = _extract_json(text)
        
        if isinstance(data, list) and len(data) == len(results):
            analyses = []
            for item in data:
                if isinstance(item, dict):
                    analyses.append({
                        "score": float(item.get("score", 0.5)),
                        "deadline": item.get("deadline"),
                        "grant_amount": item.get("grant_amount"),
                        "is_open": item.get("is_open"),
                        "eligibility_notes": item.get("eligibility_notes"),
                        "topic_match": item.get("topic_match", []),
                        "funder_type": item.get("funder_type"),
                        "contact_info": item.get("contact_info"),
                        "summary": item.get("summary"),
                    })
                else:
                    analyses.append(self._fallback_analysis({}))
            return analyses
        
        # If batch failed, return fallbacks
        print(f"  Batch analysis returned unexpected format, using fallbacks", flush=True)
        return [self._fallback_analysis(r) for r in results]

    def extract_contacts(self, results: list[dict]) -> list[dict]:
        """
        Extract contact information for a list of funding opportunities.
        Returns list of dicts with: url, contact_email, contact_form, contact_instructions
        """
        if not self.available or not results:
            return [{"url": r.get("url", ""), "contact_info": None} for r in results]
        
        prompt = (
            "For each funding opportunity, find contact information.\n"
            "Search for application email addresses, contact forms, or submission instructions.\n\n"
            "For each result, provide:\n"
            "- url: the original URL\n"
            "- contact_email: email address for applications/inquiries (or null)\n"
            "- contact_form: URL of contact/application form (or null)\n"
            "- contact_instructions: brief instructions on how to apply (or null)\n\n"
            "Return a JSON array with one object per input result.\n\n"
            f"Funding opportunities:\n{json.dumps(results, ensure_ascii=True)}"
        )
        text = self._generate(prompt)
        data = _extract_json(text)
        
        if isinstance(data, list) and len(data) == len(results):
            enriched = []
            for item in data:
                if isinstance(item, dict):
                    # Combine contact info into a single string
                    parts = []
                    if item.get("contact_email"):
                        parts.append(f"Email: {item['contact_email']}")
                    if item.get("contact_form"):
                        parts.append(f"Form: {item['contact_form']}")
                    if item.get("contact_instructions"):
                        parts.append(item["contact_instructions"])
                    
                    enriched.append({
                        "url": item.get("url", ""),
                        "contact_info": " | ".join(parts) if parts else None,
                    })
                else:
                    enriched.append({"url": "", "contact_info": None})
            return enriched
        
        return [{"url": r.get("url", ""), "contact_info": None} for r in results]


def _normalize_pivot_suggestions(items: list[Any]) -> list[str]:
    suggestions: list[str] = []
    for item in items:
        if isinstance(item, dict):
            suggestion = (
                item.get("pivot_suggestion")
                or item.get("suggestion")
                or item.get("text")
            )
            if not suggestion:
                continue
            segment = item.get("segment_id") or item.get("segment")
            if segment:
                suggestions.append(f"[{segment}] {suggestion}")
            else:
                suggestions.append(str(suggestion))
        else:
            text = str(item).strip()
            if text:
                suggestions.append(text)
    deduped = []
    seen = set()
    for suggestion in suggestions:
        if suggestion not in seen:
            seen.add(suggestion)
            deduped.append(suggestion)
    return deduped


def _resolve_model_name(client, requested: str) -> str:
    if not GENAI_AVAILABLE or not client:
        return requested

    def normalize(name: str) -> str:
        return name.replace("models/", "")

    try:
        models = list(client.models.list())
    except Exception:
        return requested

    available = [
        normalize(model.name)
        for model in models
        if "generateContent" in getattr(model, "supported_generation_methods", [])
    ]
    requested_norm = normalize(requested)
    if requested_norm in available:
        return requested_norm

    preferred = [
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
    ]
    for name in preferred:
        if name in available:
            return name
    for name in available:
        if "gemini" in name:
            return name
    return requested_norm


def _fallback_expand_queries(
    project: dict, angles: list[dict], max_queries: int
) -> list[str]:
    queries = []
    title = project.get("title", "documentary")
    topics = project.get("topic_summary", [])
    for angle in angles:
        label = angle.get("label", "")
        queries.extend(
            [
                f"{label} documentary grant",
                f"{label} film funding",
                f"{label} foundation funding",
                f"{label} NGO film grant",
            ]
        )
    for topic in topics:
        queries.append(f"{topic} documentary funding")
    queries.append(f"{title} funding opportunity")
    deduped = []
    seen = set()
    for query in queries:
        if query and query not in seen:
            seen.add(query)
            deduped.append(query)
        if len(deduped) >= max_queries:
            break
    return deduped


def _fallback_score_results(project: dict, results: list[dict]) -> list[float]:
    keywords = _project_keywords(project)
    scores: list[float] = []
    for result in results:
        text = f"{result.get('title', '')} {result.get('snippet', '')}".lower()
        hits = sum(1 for kw in keywords if kw in text)
        score = min(1.0, hits / max(1, len(keywords)))
        scores.append(score)
    return scores


def _project_keywords(project: dict) -> list[str]:
    keywords: list[str] = []
    for field in ("title", "synopsis"):
        if project.get(field):
            keywords.extend(re.findall(r"[a-zA-Z]{4,}", project[field].lower()))
    for item in project.get("topic_summary", []):
        keywords.append(str(item).lower().replace("_", " "))
    for segment in project.get("segments", []):
        for list_key in ("themes", "communities", "institutions", "primary_locations"):
            keywords.extend(
                str(value).lower().replace("_", " ")
                for value in segment.get(list_key, [])
            )
    return list({kw for kw in keywords if kw})


def _fallback_draft(project: dict, result: dict) -> str:
    return (
        f"Hello,\n\n"
        f"I'm reaching out regarding potential support for {project.get('title')}.\n"
        f"The film explores {project.get('synopsis')}.\n"
        f"Your organization ({result.get('title')}) appears aligned with these themes.\n"
        f"We would value a conversation about fit and next steps.\n\n"
        f"Thank you,\n"
        f"[Your Name]"
    )
