# Film Funding Assistant

This project builds a flexible discovery system for film funding sources. Each film can be modeled with segments and alternates plus a topic graph. The pipeline runs wide, out-of-the-box searches, scores relevance, and emails digests you can reply to for deeper searches, details, draft notes, or pivot suggestions.

## Quick Start

1. Create a virtual environment and install dependencies:
   - `pip install -r requirements.txt`
2. Copy `env.example` to `.env` and fill in keys (or set env vars directly).
3. Initialize the database:
   - `python -m src.cli init-db`
4. Run discovery and email a digest:
   - `python -m src.cli discover --send-email`
5. Or generate a local report (no email):
   - `python -m src.cli report`
6. One-command local run (discover + report, no email):
   - `python run_local.py`
7. Start the scheduler (optional):
   - `python -m src.cli schedule`

## Project Modeling

Edit `data/projects.yml` to model each film:

- `segments`: chapters or sequences with primary and alternate locations.
- `topic_graph`: themes, communities, institutions, and optional relationships.
- `funding_hints`: seed ideas (e.g., democracy foundations, indigenous film funds).
- `constraints`: placeholders for future filters.

This structure is designed to support pivot ideas (for example, swapping an alternate location if funding is stronger elsewhere).

## Email Reply Actions

Reply to the digest with commands:

- `deeper <RID>` for deeper searches on a result
- `details <RID>` for a short details email
- `draft <RID>` for a short draft application note
- `pivot <RID>` to suggest alternative angles

## Local Reports (No Email)

You can print or save a report without configuring SMTP/IMAP:

- Print to console: `python -m src.cli report`
- Save to a file: `python -m src.cli report --output reports/latest.txt`
- One-command run: `python run_local.py` (or add `--output`)

## Search Providers

Configure at least one search API:

- `BRAVE_API_KEY` for Brave Search
- `SERPAPI_API_KEY` for SerpAPI
- `BING_API_KEY` and optional `BING_ENDPOINT` for Bing
- Set `SEARCH_PROVIDER` to `serpapi`, `brave`, `bing`, or `gemini_grounded`

If no provider is configured, the system will return placeholder results.

### Gemini Search Grounding (LLM-only)

To use Gemini with search grounding:

1. Install `google-genai` (included in `requirements.txt`)
2. Set `SEARCH_PROVIDER=gemini_grounded`
3. Ensure `GEMINI_API_KEY` and `GEMINI_MODEL` are set

## Query Strategy

- `QUERY_STRATEGY=broad` starts with global documentary funding queries
- `QUERY_STRATEGY=angles` uses project-specific angles for narrower queries

## Files

- `data/projects.yml` film profiles and flexible segments
- `data/sources.yml` funder types and seed queries
- `src/pipeline.py` discovery pipeline
- `src/emailer.py` digest formatting and sending
- `src/reply_parser.py` reply commands
- `src/service.py` orchestration and reply handling

## Notes

- This tool does not apply ethical filters by default.
- Gemini is optional but improves search expansion, scoring, and drafting.
