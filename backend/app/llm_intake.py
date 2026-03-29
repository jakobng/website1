"""LLM-driven project intake using Gemini.

Maintains a short multi-turn conversation to extract ProjectInput fields
from the user. Runs preliminary scenario analysis mid-conversation to ask
targeted follow-up questions about near-miss incentives and cultural tests.
"""
from __future__ import annotations

import io
import json
import os
import uuid
from typing import Any

from dotenv import load_dotenv
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

load_dotenv()

_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# In-memory session store: session_id -> {"history": [...], "draft": {...}}
_sessions: dict[str, dict[str, Any]] = {}

BASE_SYSTEM_PROMPT = """You are a specialist film co-production data assistant. Your objective is to extract and confirm project details with high precision.

TONE & STYLE:
- Professional, direct, and concise. 
- Do NOT comment on the film's content, quality, or artistic merit.
- Do NOT use conversational filler or "chatbot" pleasantries (e.g., "That sounds like a great project!").
- Confirm facts briefly (e.g., "Confirmed: British/Spanish director.").

ACCURACY & GROUNDING:
- **CRITICAL**: Direct answers from the user in the chat ALWAYS take precedence over information extracted from a PDF treatment. If the treatment says "Taiwanese" but the user says "British", the nationality is British.
- ONLY set is_ready to true when you have: budget > 0 AND title AND at least one shoot location AND director nationality AND producer nationality AND production company countries.

FIELDS TO EXTRACT:
- title
- format: "feature_fiction", "documentary", "series", "animation"
- stage: "development", "production", "post"
- budget (number, default EUR)
- budget_currency (3-letter ISO)
- development_fraction: 0.05
- above_the_line_fraction: 0.20
- production_btl_fraction: 0.40
- post_production_btl_fraction: 0.25
- other_fraction: 0.10
- director_nationalities (list of country names)
- producer_nationalities (list of country names)
- production_company_countries (list of country names)
- shoot_locations (list of {country, percent})
- open_to_copro_countries (list)
- willing_add_coproducer (boolean)
- post_flexible (boolean)
- shoot_locations_flexible (boolean)
- cultural_test_passed / cultural_test_failed (ISO codes)

ADAPTIVE QUESTIONS:
- When completeness > 0.5, you will receive ADAPTIVE_CONTEXT about near-miss incentives.
- Ask ONLY about the specific missing requirements (e.g., "This project is close to qualifying for the UK AVEC. Does it pass the British cultural content test?").
- Do not ask about every project about every test. Be surgical.

RESPONSE FORMAT (JSON ONLY):
{
  "reply": "<concise confirmation or question>",
  "project_draft": {
    "title": "",
    "format": "feature_fiction",
    "stage": "production",
    "budget": 0,
    "budget_currency": "EUR",
    "development_fraction": 0.05,
    "above_the_line_fraction": 0.20,
    "production_btl_fraction": 0.40,
    "post_production_btl_fraction": 0.25,
    "other_fraction": 0.10,
    "director_nationalities": [],
    "producer_nationalities": [],
    "production_company_countries": [],
    "shoot_locations": [],
    "willing_add_coproducer": true,
    "post_flexible": false,
    "shoot_locations_flexible": false,
    "cultural_test_passed": [],
    "cultural_test_failed": []
  },
  "completeness_score": 0.0,
  "is_ready": false
}
"""


def _call_gemini(messages: list[dict], system_prompt: str = BASE_SYSTEM_PROMPT) -> dict:
    """Call Gemini and parse the JSON response. Returns the parsed dict."""
    if genai is None:
        return {
            "reply": "The AI intake feature requires the google-genai package. Please run: pip install google-genai",
            "project_draft": _empty_draft(),
            "completeness_score": 0.0,
            "is_ready": False,
        }

    if not _GEMINI_API_KEY:
        return {
            "reply": "GEMINI_API_KEY not set. Please add it to backend/.env and restart the server.",
            "project_draft": _empty_draft(),
            "completeness_score": 0.0,
            "is_ready": False,
        }

    try:
        client = genai.Client(api_key=_GEMINI_API_KEY)

        # Convert messages to Gemini format (role: user/model)
        contents = []
        for m in messages:
            role = "user" if m["role"] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=m["content"])]))

        response = client.models.generate_content(
            model="gemini-3.0-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
            )
        )

        text = response.text.strip()
        return json.loads(text)
    except Exception as e:
        print(f"Gemini Error: {e}")
        return {
            "reply": f"Sorry, I encountered an error with the AI: {str(e)}",
            "project_draft": _empty_draft(),
            "completeness_score": 0.0,
            "is_ready": False,
        }


def _empty_draft() -> dict:
    return {
        "title": "",
        "format": "feature_fiction",
        "stage": "production",
        "budget": 0,
        "budget_currency": "EUR",
        "budget_min": None,
        "budget_max": None,
        "development_fraction": 0.05,
        "above_the_line_fraction": 0.20,
        "production_btl_fraction": 0.40,
        "post_production_btl_fraction": 0.25,
        "other_fraction": 0.10,
        "director_nationalities": [],
        "producer_nationalities": [],
        "production_company_countries": [],
        "shoot_locations": [],
        "open_to_copro_countries": [],
        "willing_add_coproducer": True,
        "post_flexible": false,
        "shoot_locations_flexible": false,
        "spend_allocations": [],
        "languages": [],
        "has_coproducer": [],
        "streamer_attached": False,
        "vfx_flexible": False,
        "cultural_test_passed": [],
        "cultural_test_failed": [],
    }


def _build_adaptive_context(draft: dict, db) -> tuple[str, list[dict]]:
    """Run preliminary scenario analysis and build adaptive context for the LLM.

    Returns (context_string, investigating_items) where context_string is injected
    into the system prompt and investigating_items is sent to the frontend.
    """
    if db is None:
        return "", []

    # Only run if we have enough data for meaningful analysis
    budget = draft.get("budget", 0)
    shoot_locations = draft.get("shoot_locations", [])
    if budget <= 0 or not shoot_locations:
        return "", []

    try:
        from app.schemas import ProjectInput, ShootLocation
        from app.scenario_generator import generate_scenarios
        from app import countries as country_mod

        # Build a ProjectInput from the draft
        locs = []
        for loc in shoot_locations:
            country = loc.get("country", "")
            pct = loc.get("percent", 0)
            if country and pct > 0:
                locs.append(ShootLocation(country=country, percent=pct))

        if not locs:
            return "", []

        project = ProjectInput(
            title=draft.get("title", "Untitled"),
            format=draft.get("format", "feature_fiction"),
            stage=draft.get("stage", "production"),
            budget=budget,
            budget_currency=draft.get("budget_currency", "EUR"),
            development_fraction=draft.get("development_fraction", 0.05),
            above_the_line_fraction=draft.get("above_the_line_fraction", 0.20),
            production_btl_fraction=draft.get("production_btl_fraction", 0.40),
            post_production_btl_fraction=draft.get("post_production_btl_fraction", 0.25),
            other_fraction=draft.get("other_fraction", 0.10),
            director_nationalities=draft.get("director_nationalities", []),
            producer_nationalities=draft.get("producer_nationalities", []),
            production_company_countries=draft.get("production_company_countries", []),
            shoot_locations=locs,
            willing_add_coproducer=draft.get("willing_add_coproducer", True),
            post_flexible=draft.get("post_flexible", False),
            shoot_locations_flexible=draft.get("shoot_locations_flexible", False),
            has_coproducer=draft.get("has_coproducer", []),
            cultural_test_passed=draft.get("cultural_test_passed", []),
            cultural_test_failed=draft.get("cultural_test_failed", []),
        )

        scenarios = generate_scenarios(project, db)

        # Collect near-misses and cultural test requirements from all scenarios
        context_parts = []
        investigating = []
        seen_incentives = set()

        for scenario in scenarios[:5]:  # Top 5 scenarios
            for partner in scenario.partners:
                for inc in partner.eligible_incentives:
                    if inc.name in seen_incentives:
                        continue
                    seen_incentives.add(inc.name)

                    # Cultural test requirements
                    cultural_reqs = [r for r in inc.requirements if r.category == "cultural"]
                    ct_passed = [c.upper() for c in (draft.get("cultural_test_passed") or [])]
                    ct_failed = [c.upper() for c in (draft.get("cultural_test_failed") or [])]

                    for req in cultural_reqs:
                        cc = inc.country_code.upper()
                        if cc not in ct_passed and cc not in ct_failed:
                            country_name = country_mod.display_name(cc)
                            context_parts.append(
                                f"- [{inc.name}] ({country_name}): requires cultural test — "
                                f"{req.description}. Ask about cultural content, "
                                f"key creative nationalities, and language if relevant."
                            )
                            investigating.append({
                                "incentive": inc.name,
                                "country": country_name,
                                "gap": req.description,
                                "potential_amount": inc.benefit.benefit_amount if inc.benefit else None,
                                "potential_currency": inc.benefit.benefit_currency if inc.benefit else "EUR",
                            })

                    # Other unmet requirements (spend, shoot, producer)
                    other_reqs = [r for r in inc.requirements
                                  if r.category not in ("cultural",) and r.category != "format"]
                    for req in other_reqs:
                        country_name = country_mod.display_name(inc.country_code)
                        context_parts.append(
                            f"- [{inc.name}] ({country_name}): {req.description}"
                        )

            # Near-misses from the scenario
            for nm in scenario.near_misses:
                key = f"{nm.incentive_name}_{nm.gap_category}"
                if key in seen_incentives:
                    continue
                seen_incentives.add(key)
                context_parts.append(
                    f"- [NEAR-MISS: {nm.incentive_name}] ({nm.country_name}): "
                    f"{nm.gap_description}. "
                    f"Potential benefit: ~{nm.potential_benefit_currency} {nm.potential_benefit_amount:,.0f}"
                )
                investigating.append({
                    "incentive": nm.incentive_name,
                    "country": nm.country_name,
                    "gap": nm.gap_description,
                    "potential_amount": nm.potential_benefit_amount,
                    "potential_currency": nm.potential_benefit_currency,
                })

        if not context_parts:
            return "", []

        adaptive_context = (
            "\n\nADAPTIVE_CONTEXT — Based on preliminary analysis of this project:\n"
            + "\n".join(context_parts[:15])  # Limit to avoid token bloat
            + "\n\nAsk ONLY about the relevant requirements listed above. "
            "Don't ask about every incentive — focus on the most impactful ones "
            "(highest potential benefit or smallest gap to qualifying). "
            "For cultural tests, use what you already know about the project to pre-fill "
            "obvious answers. Only ask about criteria you genuinely can't infer."
        )

        return adaptive_context, investigating

    except Exception as e:
        print(f"Adaptive context error: {e}")
        return "", []


def start_session() -> dict:
    """Create a new intake session and return the opening message."""
    session_id = str(uuid.uuid4())
    opening_prompt = (
        "New producer, no data yet. Greet them and ask for the project title, "
        "format (feature/doc/series/animation), and total budget to get started."
    )
    messages = [{"role": "user", "content": opening_prompt}]
    result = _call_gemini(messages)

    _sessions[session_id] = {
        "history": [
            {"role": "user", "content": opening_prompt},
            {"role": "assistant", "content": json.dumps(result)},
        ],
        "draft": result.get("project_draft", _empty_draft()),
    }

    return {
        "session_id": session_id,
        "reply": result.get("reply", "Hello! Let's get started. What's the working title of your project?"),
        "project_draft": result.get("project_draft", _empty_draft()),
        "completeness_score": result.get("completeness_score", 0.0),
        "is_ready": result.get("is_ready", False),
    }


def send_message(session_id: str, user_message: str, db=None) -> dict:
    """Send a message in an existing session and return the updated state.

    When enough project data has been gathered (completeness > 0.5), runs
    preliminary scenario analysis and injects adaptive context so the LLM
    asks targeted questions about near-miss incentives and cultural tests.
    """
    session = _sessions.get(session_id)
    if not session:
        return {
            "session_id": session_id,
            "reply": "Session not found. Please start a new interview.",
            "project_draft": _empty_draft(),
            "completeness_score": 0.0,
            "is_ready": False,
            "error": "session_not_found",
        }

    # Build adaptive context if we have enough data
    draft = session["draft"]
    completeness = session.get("completeness", 0.0)
    # Also check if draft has budget and shoot locations as a proxy
    has_basics = draft.get("budget", 0) > 0 and len(draft.get("shoot_locations", [])) > 0
    adaptive_context = ""
    investigating = []
    if (completeness > 0.5 or has_basics) and db is not None:
        adaptive_context, investigating = _build_adaptive_context(draft, db)

    # Build system prompt with adaptive context
    system_prompt = BASE_SYSTEM_PROMPT
    if adaptive_context:
        system_prompt = BASE_SYSTEM_PROMPT + adaptive_context

    # Add current draft context to user message so Gemini has full picture
    current_draft_json = json.dumps(draft)
    contextual_message = (
        f"Current project draft: {current_draft_json}\n\nUser says: {user_message}"
    )

    history = session["history"] + [{"role": "user", "content": contextual_message}]

    result = _call_gemini(history, system_prompt=system_prompt)

    # Update session
    session["history"] = history + [
        {"role": "assistant", "content": json.dumps(result)}
    ]
    session["draft"] = result.get("project_draft", session["draft"])
    session["completeness"] = result.get("completeness_score", 0.0)

    response = {
        "session_id": session_id,
        "reply": result.get("reply", ""),
        "project_draft": session["draft"],
        "completeness_score": result.get("completeness_score", 0.0),
        "is_ready": result.get("is_ready", False),
    }
    if investigating:
        response["investigating"] = investigating

    return response


def _extract_text_from_pdf(content: bytes) -> str:
    """Extract text from a PDF byte content."""
    if PdfReader is None:
        return ""

    try:
        pdf_file = io.BytesIO(content)
        reader = PdfReader(pdf_file)
        text_parts = []
        for page_num, page in enumerate(reader.pages[:5]):  # Limit to first 5 pages
            text = page.extract_text()
            if text:
                text_parts.append(text)
        return "\n".join(text_parts)
    except Exception as e:
        print(f"PDF extraction error: {e}")
        return ""


def process_upload(session_id: str, content: bytes, mime_type: str, db=None) -> dict:
    """Process an uploaded file (PDF treatment/document) for the session."""
    session = _sessions.get(session_id)
    if not session:
        return {
            "session_id": session_id,
            "reply": "Session not found.",
            "success": False,
            "error": "session_not_found",
        }

    # Extract text from PDF if applicable
    extracted_text = ""
    if mime_type == "application/pdf":
        extracted_text = _extract_text_from_pdf(content)

    if not extracted_text:
        return {
            "session_id": session_id,
            "reply": "I couldn't extract text from the document. Could you tell me the key details manually?",
            "success": False,
        }

    # Build adaptive context if available
    draft = session["draft"]
    adaptive_context = ""
    investigating = []
    has_basics = draft.get("budget", 0) > 0 and len(draft.get("shoot_locations", [])) > 0
    if has_basics and db is not None:
        adaptive_context, investigating = _build_adaptive_context(draft, db)

    system_prompt = BASE_SYSTEM_PROMPT
    if adaptive_context:
        system_prompt = BASE_SYSTEM_PROMPT + adaptive_context

    # Create a message that feeds the extracted text to Gemini
    contextual_message = (
        f"Current project draft: {json.dumps(draft)}\n\n"
        f"User uploaded a document with this content:\n{extracted_text}\n\n"
        f"Please extract any project details from this document and update the project draft accordingly."
    )

    history = session["history"] + [{"role": "user", "content": contextual_message}]
    result = _call_gemini(history, system_prompt=system_prompt)

    # Update session with the extracted info
    session["history"] = history + [
        {"role": "assistant", "content": json.dumps(result)}
    ]
    session["draft"] = result.get("project_draft", session["draft"])

    response = {
        "session_id": session_id,
        "reply": result.get("reply", "Thank you for uploading the document. I've extracted the information."),
        "project_draft": session["draft"],
        "completeness_score": result.get("completeness_score", 0.0),
        "is_ready": result.get("is_ready", False),
        "success": True,
    }
    if investigating:
        response["investigating"] = investigating

    return response


# ---------------------------------------------------------------------------
# Cultural test review
# ---------------------------------------------------------------------------

CULTURAL_TEST_SYSTEM_PROMPT = """You are a cultural test evaluator for film co-production incentives.

You are reviewing the cultural test for **{country_name}** ({incentive_name}).
{score_info_line}

The producer's project details are provided below. Walk through the test criteria ONE at a time.
For each criterion, ask a clear yes/no question. When you can infer the answer from the project data
(e.g. the director's nationality is already known), state that you're scoring it automatically and
explain why.

After evaluating all criteria, declare a verdict: pass or fail.

Keep the conversation short and practical — 3-6 questions at most. Focus on criteria that are
ambiguous given what you already know about the project.

RESPONSE FORMAT — you MUST respond with ONLY valid JSON:
{{
  "reply": "<your conversational message>",
  "current_score": <int or null if not yet tracking>,
  "required_score": <int or null>,
  "total_possible": <int or null>,
  "is_complete": false,
  "verdict": null,
  "project_draft": <the full updated project draft object>
}}

When you reach a verdict, set is_complete to true and verdict to "pass" or "fail".
Update project_draft.cultural_test_passed or project_draft.cultural_test_failed accordingly
(add the country code "{country_code}" to the appropriate list).
"""


def handle_cultural_test(
    session_id: str, country_code: str, country_name: str,
    action: str, incentive_name: str = "", score_info: str = "",
) -> dict:
    """Handle cultural test pass/fail/start_review actions."""
    session = _sessions.get(session_id)
    if not session:
        return {"error": "session_not_found", "project_draft": _empty_draft()}

    draft = session["draft"]
    cc = country_code.upper()

    if action == "pass":
        passed = draft.get("cultural_test_passed") or []
        failed = draft.get("cultural_test_failed") or []
        if cc not in passed:
            passed.append(cc)
        failed = [c for c in failed if c != cc]
        draft["cultural_test_passed"] = passed
        draft["cultural_test_failed"] = failed
        session["draft"] = draft
        return {"project_draft": draft}

    if action == "fail":
        passed = draft.get("cultural_test_passed") or []
        failed = draft.get("cultural_test_failed") or []
        if cc not in failed:
            failed.append(cc)
        passed = [c for c in passed if c != cc]
        draft["cultural_test_passed"] = passed
        draft["cultural_test_failed"] = failed
        session["draft"] = draft
        return {"project_draft": draft}

    if action == "start_review":
        score_info_line = f"Score threshold: {score_info}." if score_info else ""
        system_prompt = CULTURAL_TEST_SYSTEM_PROMPT.format(
            country_name=country_name,
            country_code=cc,
            incentive_name=incentive_name,
            score_info_line=score_info_line,
        )

        opening = (
            f"Start the cultural test review for {country_name} ({incentive_name}). "
            f"Project details: {json.dumps(draft)}"
        )
        messages = [{"role": "user", "content": opening}]
        result = _call_gemini(messages, system_prompt=system_prompt)

        # Store sub-conversation
        reviews = session.get("cultural_reviews", {})
        reviews[cc] = {
            "history": [
                {"role": "user", "content": opening},
                {"role": "assistant", "content": json.dumps(result)},
            ],
            "system_prompt": system_prompt,
        }
        session["cultural_reviews"] = reviews

        # If the LLM auto-completed (e.g. all criteria obvious), update draft
        if result.get("is_complete") and result.get("verdict"):
            _apply_verdict(session, cc, result)

        return {
            "reply": result.get("reply", "Let's review the cultural test criteria."),
            "current_score": result.get("current_score"),
            "required_score": result.get("required_score"),
            "total_possible": result.get("total_possible"),
            "is_complete": result.get("is_complete", False),
            "verdict": result.get("verdict"),
            "project_draft": session["draft"],
        }

    return {"error": f"Unknown action: {action}", "project_draft": draft}


def handle_cultural_test_message(
    session_id: str, country_code: str, message: str,
) -> dict:
    """Continue an interactive cultural test review conversation."""
    session = _sessions.get(session_id)
    if not session:
        return {"error": "session_not_found", "reply": "Session not found."}

    cc = country_code.upper()
    reviews = session.get("cultural_reviews", {})
    review = reviews.get(cc)
    if not review:
        return {"error": "no_review", "reply": "No cultural test review in progress for this country."}

    review["history"].append({"role": "user", "content": message})
    result = _call_gemini(review["history"], system_prompt=review["system_prompt"])
    review["history"].append({"role": "assistant", "content": json.dumps(result)})

    if result.get("is_complete") and result.get("verdict"):
        _apply_verdict(session, cc, result)

    return {
        "reply": result.get("reply", ""),
        "current_score": result.get("current_score"),
        "required_score": result.get("required_score"),
        "total_possible": result.get("total_possible"),
        "is_complete": result.get("is_complete", False),
        "verdict": result.get("verdict"),
        "project_draft": session["draft"],
    }


def _apply_verdict(session: dict, country_code: str, result: dict) -> None:
    """Update session draft based on cultural test verdict."""
    draft = session["draft"]
    passed = draft.get("cultural_test_passed") or []
    failed = draft.get("cultural_test_failed") or []
    cc = country_code.upper()

    if result["verdict"] == "pass":
        if cc not in passed:
            passed.append(cc)
        failed = [c for c in failed if c != cc]
    elif result["verdict"] == "fail":
        if cc not in failed:
            failed.append(cc)
        passed = [c for c in passed if c != cc]

    draft["cultural_test_passed"] = passed
    draft["cultural_test_failed"] = failed
    session["draft"] = draft
