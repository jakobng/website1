"""Generate curated funding digests using LLM analysis."""

from __future__ import annotations

import json
import re
from urllib.parse import urlparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import AppConfig
from .llm import LLMClient, _extract_json
from .storage import (
    StoredResult,
    fetch_results_for_digest,
    mark_results_shown,
    update_result_type,
    init_db,
)


@dataclass
class DigestEntry:
    """A curated entry for the digest."""
    result: StoredResult
    result_type: str  # specific_grant, funder_org
    description: str  # What is this fund/org?
    why_fits: str  # Why this fits the project
    eligibility_summary: str  # Key eligibility in plain language
    confidence: str  # high, medium, low
    primary_url: str  # Actual funder URL (may differ from result.url if news article)
    is_new: bool  # First time being shown


@dataclass  
class ProjectDigest:
    """Digest for a single project."""
    project_id: str
    project_title: str
    grants: list[DigestEntry]
    organizations: list[DigestEntry]
    deadline_reminders: list[DigestEntry]  # Previously shown, upcoming deadlines
    outreach_targets: list[DigestEntry]  # Mission-aligned people/orgs to approach


def classify_results_heuristic(results: list[StoredResult]) -> dict[int, str]:
    """
    Fast heuristic-based classification using URL and title patterns.
    No LLM calls - instant results.
    """
    # Known aggregator domains (host-only or host/path)
    aggregator_domains = {
        "documentary.org", "filmdaily.tv", "filmfreeway.com", "withoutabox.com",
        "shortfilmdepot.com", "reelport.com", "submittable.com", "slideroom.com",
        "wikipedia.org", "en.wikipedia.org", "libraryguides.missouri.edu",
        "filmmakers.com", "indiewire.com/galleries", "screendaily.com/festivals",
    }
    
    # Known news domains (host-only or host/path)
    news_domains = {
        "deadline.com", "variety.com", "hollywoodreporter.com", "indiewire.com",
        "screendaily.com", "realscreen.com", "documentary.org/news", "vurchel.com",
    }
    
    # Aggregator title patterns
    aggregator_patterns = [
        r"funding resources",
        r"funding guide",
        r"list of.*grants",
        r"grant database",
        r"where to find.*funding",
        r"documentary funding.*resource",
        r"library guide",
    ]
    
    classifications: dict[int, str] = {}
    
    for r in results:
        url_lower = r.url.lower()
        title_lower = r.title.lower()
        
        # Extract domain and path
        domain = ""
        if "://" in url_lower:
            parsed = urlparse(url_lower)
            domain = parsed.netloc
            if domain.startswith("www."):
                domain = domain[4:]
        
        # Check aggregator domains
        if any("/" in agg and agg in url_lower for agg in aggregator_domains):
            classifications[r.id] = "aggregator"
            continue
        if any("/" not in agg and agg in domain for agg in aggregator_domains):
            classifications[r.id] = "aggregator"
            continue
        
        # Check news domains (but not if it looks like an actual grant page)
        if any("/" in news and news in url_lower for news in news_domains):
            if "apply" in title_lower or "deadline" in title_lower or "application" in url_lower:
                classifications[r.id] = "specific_grant"
            else:
                classifications[r.id] = "news"
            continue
        if any("/" not in news and news in domain for news in news_domains):
            # Could be news, but might reference actual grants
            if "apply" in title_lower or "deadline" in title_lower or "application" in url_lower:
                classifications[r.id] = "specific_grant"
            else:
                classifications[r.id] = "news"
            continue
        
        # Check aggregator patterns in title
        if any(re.search(pat, title_lower) for pat in aggregator_patterns):
            classifications[r.id] = "aggregator"
            continue
        
        # Check for Wikipedia
        if "wikipedia" in url_lower:
            classifications[r.id] = "irrelevant"
            continue
        
        # Check for grant-like indicators
        grant_indicators = ["apply", "application", "deadline", "grant", "fund", "award", "submit"]
        org_indicators = ["about us", "our work", "mission", "who we are"]
        
        has_grant_indicator = any(ind in title_lower or ind in url_lower for ind in grant_indicators)
        has_org_indicator = any(ind in title_lower or ind in url_lower for ind in org_indicators)
        
        if has_grant_indicator:
            classifications[r.id] = "specific_grant"
        elif has_org_indicator:
            classifications[r.id] = "funder_org"
        else:
            # Default to specific_grant for foundation/organization domains
            classifications[r.id] = "specific_grant"
    
    return classifications


def classify_results(
    llm: LLMClient,
    results: list[StoredResult],
    batch_size: int = 10,
    use_heuristic: bool = True,  # Use fast heuristics instead of LLM
) -> dict[int, str]:
    """
    Classify results into types.
    
    Returns dict mapping result.id -> result_type
    Types: specific_grant, funder_org, aggregator, news, irrelevant
    """
    if use_heuristic or not llm.available or not results:
        return classify_results_heuristic(results)
    
    # LLM-based classification (slower but more accurate)
    classifications: dict[int, str] = {}
    
    for i in range(0, len(results), batch_size):
        batch = results[i:i + batch_size]
        print(f"  Classifying results {i+1}-{i+len(batch)} of {len(results)}...", flush=True)
        
        # Build batch info
        batch_info = []
        for r in batch:
            batch_info.append({
                "id": r.id,
                "title": r.title,
                "url": r.url,
                "snippet": (r.snippet or "")[:300],
            })
        
        prompt = f"""Classify each search result into one of these categories:

- "specific_grant": An actual grant/fund with application process (e.g., "Catapult Film Fund - Apply by Feb 12")
- "funder_org": An organization that funds films, but no specific grant listed (e.g., Ford Foundation main page)
- "aggregator": A database or list of grants, not a grant itself (e.g., "Documentary Funding Resources" pages, FilmFreeway, film festival databases)
- "news": A news article about grants/funding (e.g., Deadline.com, IndieWire announcing winners)
- "irrelevant": Wikipedia, blogs, general how-to articles, unrelated content

IMPORTANT: Be strict about "aggregator" - sites like documentary.org/funding, filmdaily.tv, festival databases are aggregators, NOT grants.

Results to classify:
{json.dumps(batch_info, indent=2)}

Return a JSON array with exactly {len(batch)} objects:
[{{"id": <result_id>, "type": "<classification>", "primary_url": "<actual funder URL if this is news, otherwise same as result URL>"}}]

For news articles, extract the actual grant/funder URL being discussed if possible."""

        text = llm._generate(prompt, timeout=60)
        data = _extract_json(text)
        
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "id" in item and "type" in item:
                    result_id = item["id"]
                    result_type = item["type"]
                    if result_type in ("specific_grant", "funder_org", "aggregator", "news", "irrelevant"):
                        classifications[result_id] = result_type
        
        # Fill in any missing with fallback
        for r in batch:
            if r.id not in classifications:
                classifications[r.id] = "specific_grant"  # Assume grant if unsure
    
    return classifications


@dataclass
class OpportunityInfo:
    """Structured info about an opportunity for the digest."""
    description: str  # What is this fund/org?
    why_fits: str  # Why it fits this specific project
    eligibility_summary: str  # Key eligibility in plain language
    confidence: str  # "high", "medium", "low" - how confident are we this is relevant?


def generate_opportunity_info(
    llm: LLMClient,
    project: dict,
    entries: list[tuple[StoredResult, str]],  # (result, result_type)
) -> list[OpportunityInfo]:
    """
    Generate detailed info about each opportunity.
    
    Returns structured info for each entry.
    """
    if not llm.available or not entries:
        return [
            OpportunityInfo(
                description=r.summary or r.title,
                why_fits="",
                eligibility_summary=r.eligibility_notes or "",
                confidence="medium",
            )
            for r, _ in entries
        ]
    
    # Build project context
    project_context = f"""Project: {project.get('title', 'Untitled')}
Synopsis: {project.get('synopsis', '')}
Topics: {', '.join(project.get('topic_summary', []))}
Team locations/eligibility: {', '.join(project.get('eligibility', {}).get('countries_access', []))}"""
    
    # Build entries info
    entries_info = []
    for r, rtype in entries:
        entries_info.append({
            "id": r.id,
            "type": rtype,
            "title": r.title,
            "url": r.url,
            "summary": r.summary or r.snippet or "",
            "deadline": r.deadline,
            "amount": r.grant_amount,
            "funder_type": r.funder_type,
            "topics": r.topic_match,
            "eligibility_notes": r.eligibility_notes or "",
        })
    
    prompt = f"""You are helping a documentary filmmaker evaluate funding opportunities.

{project_context}

For each opportunity, provide structured analysis. Be CRITICAL and HONEST.

IMPORTANT RULES:
1. If the opportunity seems closed, outdated, or the URL looks like a generic resource page, set confidence to "low"
2. If eligibility doesn't match (wrong country, wrong project type), set confidence to "low" and note why
3. Only set confidence "high" if it's clearly a good match with open applications
4. For "description", explain WHAT this fund/organization IS in 1 sentence (not why it fits)
5. For "why_fits", explain specifically why it's relevant to THIS film's themes

Opportunities:
{json.dumps(entries_info, indent=2)}

Return a JSON array with one object per opportunity:
[
  {{
    "id": <result_id>,
    "description": "One sentence explaining what this fund/organization is and does",
    "why_fits": "1-2 sentences on why specifically relevant for this film's themes/approach",
    "eligibility_summary": "Key requirements in plain language (country, project stage, format, etc.)",
    "confidence": "high|medium|low"
  }}
]

Examples:
- description: "The Catapult Film Fund provides development grants up to $35K for feature documentaries focused on social justice issues."
- why_fits: "Your focus on environmental justice and indigenous communities aligns with their track record of funding climate and human rights stories."
- eligibility_summary: "US or international filmmakers; feature documentaries; development or production stage; rolling deadlines"
- confidence: "high" (if clearly open and good match) / "low" (if eligibility unclear or poor match)"""

    text = llm._generate(prompt, timeout=180)
    data = _extract_json(text)
    
    results = []
    id_to_info = {}
    
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "id" in item:
                id_to_info[item["id"]] = OpportunityInfo(
                    description=item.get("description", ""),
                    why_fits=item.get("why_fits", ""),
                    eligibility_summary=item.get("eligibility_summary", ""),
                    confidence=item.get("confidence", "medium"),
                )
    
    # Build results in order, with fallbacks
    for r, _ in entries:
        if r.id in id_to_info:
            results.append(id_to_info[r.id])
        else:
            results.append(OpportunityInfo(
                description=r.summary or r.title,
                why_fits="",
                eligibility_summary=r.eligibility_notes or "",
                confidence="medium",
            ))
    
    return results


def generate_explanations(
    llm: LLMClient,
    project: dict,
    entries: list[tuple[StoredResult, str]],  # (result, result_type)
) -> list[str]:
    """
    Generate personalized explanations for why each result fits this project.
    
    Returns list of explanation strings in same order as entries.
    NOTE: This is a simplified wrapper. For full info, use generate_opportunity_info().
    """
    infos = generate_opportunity_info(llm, project, entries)
    return [info.why_fits or info.description for info in infos]


def _is_opportunity_active(r: StoredResult) -> bool:
    """Check if an opportunity appears to be active/open."""
    # Skip if explicitly marked as closed
    if r.is_open and r.is_open.lower() == "false":
        return False
    
    # Check deadline for past dates
    if r.deadline:
        deadline_lower = r.deadline.lower().strip()
        
        # Skip obviously closed deadlines
        if deadline_lower in ("closed", "expired", "ended"):
            return False
        
        # Try to parse date formats like "2023-12-31" or "December 31, 2023"
        try:
            # Common formats
            for fmt in ("%Y-%m-%d", "%B %d, %Y", "%d/%m/%Y", "%m/%d/%Y"):
                try:
                    deadline_date = datetime.strptime(deadline_lower, fmt)
                    if deadline_date < datetime.now():
                        return False
                    break
                except ValueError:
                    continue
            
            # Check for year in text like "2023-12-31" or "2024"
            import re
            year_match = re.search(r'\b(20\d{2})\b', deadline_lower)
            if year_match:
                year = int(year_match.group(1))
                if year < datetime.now().year:
                    return False
        except Exception:
            pass
    
    return True


def build_project_digest(
    llm: LLMClient,
    project: dict,
    results: list[StoredResult],
    classifications: dict[int, str],
    max_grants: int = 20,
    max_orgs: int = 10,
    max_outreach: int = 10,
) -> ProjectDigest:
    """Build a curated digest for a single project."""
    
    # Separate by type and whether previously shown
    new_grants = []
    new_orgs = []
    shown_grants = []
    outreach_targets = []
    skipped_closed = 0
    
    for r in results:
        rtype = classifications.get(r.id, "specific_grant")
        is_new = r.shown_in_digest is None
        
        # Skip aggregators and irrelevant
        if rtype in ("aggregator", "irrelevant"):
            continue
        
        # Skip closed/expired opportunities
        if not _is_opportunity_active(r):
            skipped_closed += 1
            continue
        
        # Check if this is an outreach result (from outreach discovery)
        if r.angle_type == "outreach":
            if is_new:
                outreach_targets.append((r, "outreach"))
            continue
        
        # News articles: include if we can use their info, but they'll need URL extraction
        if rtype == "news":
            # For now, treat news as potential grants if they have good info
            rtype = "specific_grant"
        
        if rtype == "specific_grant":
            if is_new:
                new_grants.append((r, rtype))
            else:
                shown_grants.append((r, rtype))
        elif rtype == "funder_org":
            if is_new:
                new_orgs.append((r, rtype))
    
    if skipped_closed > 0:
        print(f"  Filtered out {skipped_closed} closed/expired opportunities", flush=True)
    
    # Sort by score
    new_grants.sort(key=lambda x: x[0].score or 0, reverse=True)
    new_orgs.sort(key=lambda x: x[0].score or 0, reverse=True)
    shown_grants.sort(key=lambda x: x[0].score or 0, reverse=True)
    outreach_targets.sort(key=lambda x: x[0].score or 0, reverse=True)
    
    # Take top N
    selected_grants = new_grants[:max_grants]
    selected_orgs = new_orgs[:max_orgs]
    selected_outreach = outreach_targets[:max_outreach]
    
    # For deadline reminders, only include previously shown with upcoming deadlines
    deadline_reminders = []
    for r, rtype in shown_grants[:10]:
        if r.deadline and r.deadline not in ("ongoing", "rolling", "unknown", "null"):
            deadline_reminders.append((r, rtype))
    
    # Generate detailed info for all selected
    all_selected = selected_grants + selected_orgs + deadline_reminders + selected_outreach
    
    if all_selected:
        print(f"  Analyzing {len(all_selected)} opportunities...", flush=True)
        infos = generate_opportunity_info(llm, project, all_selected)
    else:
        infos = []
    
    # Build digest entries, filtering out low-confidence results
    grant_entries = []
    org_entries = []
    reminder_entries = []
    outreach_entries = []
    
    idx = 0
    low_confidence_skipped = 0
    
    for r, rtype in selected_grants:
        info = infos[idx] if idx < len(infos) else OpportunityInfo("", "", "", "medium")
        idx += 1
        
        # Skip low confidence results
        if info.confidence == "low":
            low_confidence_skipped += 1
            continue
        
        grant_entries.append(DigestEntry(
            result=r,
            result_type=rtype,
            description=info.description,
            why_fits=info.why_fits,
            eligibility_summary=info.eligibility_summary,
            confidence=info.confidence,
            primary_url=r.url,
            is_new=True,
        ))
    
    for r, rtype in selected_orgs:
        info = infos[idx] if idx < len(infos) else OpportunityInfo("", "", "", "medium")
        idx += 1
        
        if info.confidence == "low":
            low_confidence_skipped += 1
            continue
        
        org_entries.append(DigestEntry(
            result=r,
            result_type=rtype,
            description=info.description,
            why_fits=info.why_fits,
            eligibility_summary=info.eligibility_summary,
            confidence=info.confidence,
            primary_url=r.url,
            is_new=True,
        ))
    
    for r, rtype in deadline_reminders:
        info = infos[idx] if idx < len(infos) else OpportunityInfo("", "", "", "medium")
        idx += 1
        
        reminder_entries.append(DigestEntry(
            result=r,
            result_type=rtype,
            description=info.description,
            why_fits=info.why_fits,
            eligibility_summary=info.eligibility_summary,
            confidence=info.confidence,
            primary_url=r.url,
            is_new=False,
        ))
    
    for r, rtype in selected_outreach:
        info = infos[idx] if idx < len(infos) else OpportunityInfo("", "", "", "medium")
        idx += 1
        
        if info.confidence == "low":
            low_confidence_skipped += 1
            continue
        
        outreach_entries.append(DigestEntry(
            result=r,
            result_type=rtype,
            description=info.description,
            why_fits=info.why_fits or r.eligibility_notes or "",
            eligibility_summary=info.eligibility_summary,
            confidence=info.confidence,
            primary_url=r.url,
            is_new=True,
        ))
    
    if low_confidence_skipped > 0:
        print(f"  Filtered out {low_confidence_skipped} low-confidence results", flush=True)
    
    return ProjectDigest(
        project_id=project["id"],
        project_title=project.get("title", project["id"]),
        grants=grant_entries,
        organizations=org_entries,
        deadline_reminders=reminder_entries,
        outreach_targets=outreach_entries,
    )


def format_digest_text(digests: list[ProjectDigest]) -> str:
    """Format digests as readable text."""
    
    lines = []
    lines.append("=" * 70)
    lines.append("FUNDING DISCOVERY DIGEST")
    lines.append(f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}")
    lines.append("=" * 70)
    lines.append("")
    
    for digest in digests:
        lines.append("")
        lines.append("#" * 70)
        lines.append(f"# {digest.project_title.upper()}")
        lines.append("#" * 70)
        lines.append("")
        
        # New grants
        if digest.grants:
            lines.append(f"## GRANTS TO CONSIDER ({len(digest.grants)} opportunities)")
            lines.append("")
            
            for i, entry in enumerate(digest.grants, 1):
                r = entry.result
                lines.append(f"{i}. **{r.title}**")
                
                meta_parts = []
                if r.deadline and r.deadline not in ("null", "unknown", ""):
                    meta_parts.append(f"Deadline: {r.deadline}")
                if r.grant_amount:
                    meta_parts.append(f"Amount: {r.grant_amount}")
                if r.is_open and r.is_open.lower() == "true":
                    meta_parts.append("OPEN")
                
                # Add confidence indicator for medium confidence
                if entry.confidence == "medium":
                    meta_parts.append("(verify eligibility)")
                
                if meta_parts:
                    lines.append(f"   {' | '.join(meta_parts)}")
                
                # What is this fund?
                if entry.description:
                    lines.append("")
                    lines.append(f"   What: {entry.description}")
                
                # Why it fits
                if entry.why_fits:
                    lines.append("")
                    lines.append(f"   Fit: {entry.why_fits}")
                
                # Eligibility
                if entry.eligibility_summary:
                    lines.append("")
                    lines.append(f"   Eligibility: {entry.eligibility_summary}")
                
                lines.append(f"   -> {entry.primary_url}")
                lines.append("")
        
        # Organizations
        if digest.organizations:
            lines.append("")
            lines.append(f"## ORGANIZATIONS TO APPROACH ({len(digest.organizations)} suggestions)")
            lines.append("")
            
            for i, entry in enumerate(digest.organizations, 1):
                r = entry.result
                lines.append(f"{i}. **{r.title}**")
                
                if r.funder_type:
                    lines.append(f"   Type: {r.funder_type}")
                
                if entry.description:
                    lines.append("")
                    lines.append(f"   What: {entry.description}")
                
                if entry.why_fits:
                    lines.append("")
                    lines.append(f"   Fit: {entry.why_fits}")
                
                lines.append(f"   -> {entry.primary_url}")
                lines.append("")
        
        # Deadline reminders
        if digest.deadline_reminders:
            lines.append("")
            lines.append(f"## DEADLINE REMINDERS ({len(digest.deadline_reminders)} upcoming)")
            lines.append("")
            
            for entry in digest.deadline_reminders:
                r = entry.result
                lines.append(f"• {r.title} — Deadline: {r.deadline}")
                lines.append(f"  -> {entry.primary_url}")
            lines.append("")
        
        # Outreach targets (mission-aligned people/orgs to approach)
        if digest.outreach_targets:
            lines.append("")
            lines.append(f"## PEOPLE & ORGANIZATIONS TO APPROACH ({len(digest.outreach_targets)} targets)")
            lines.append("These aren't grants - they're mission-aligned people and orgs worth reaching out to.")
            lines.append("")
            
            for i, entry in enumerate(digest.outreach_targets, 1):
                r = entry.result
                lines.append(f"{i}. **{r.title}**")
                
                # Show entity type
                entity_type = r.funder_type or "unknown"
                if entity_type not in ("unknown", "other"):
                    lines.append(f"   Type: {entity_type}")
                
                if entry.description:
                    lines.append("")
                    lines.append(f"   Who: {entry.description}")
                
                if entry.why_fits:
                    lines.append("")
                    lines.append(f"   Why: {entry.why_fits}")
                
                if r.contact_info:
                    lines.append(f"   Contact: {r.contact_info}")
                
                lines.append(f"   -> {entry.primary_url}")
                lines.append("")
        
        # No results case
        if not digest.grants and not digest.organizations and not digest.deadline_reminders and not digest.outreach_targets:
            lines.append("No new opportunities found this time.")
            lines.append("Try running discovery again or adjusting search queries.")
        
        lines.append("")
    
    lines.append("")
    lines.append("=" * 70)
    lines.append("END OF DIGEST")
    lines.append("=" * 70)
    
    return "\n".join(lines)


def generate_digest(
    config: AppConfig,
    projects: list[dict],
    mark_shown: bool = True,
    min_score: float = 0.5,
    max_grants_per_project: int = 20,
    max_orgs_per_project: int = 10,
) -> str:
    """
    Generate a full funding digest for all projects.
    
    Args:
        config: App configuration
        projects: List of project dicts
        mark_shown: Whether to mark included results as shown
        min_score: Minimum score threshold
        max_grants_per_project: Max grants to include per project
        max_orgs_per_project: Max organizations to include per project
    
    Returns:
        Formatted digest text
    """
    init_db(config.db_path)
    
    llm = LLMClient(config.gemini_api_key, config.gemini_model)
    
    print("=" * 60, flush=True)
    print("GENERATING FUNDING DIGEST", flush=True)
    print("=" * 60, flush=True)
    
    digests = []
    all_shown_ids = []
    
    # Pre-filter limit: only classify top N results per project
    # This dramatically reduces API calls
    classify_limit = (max_grants_per_project + max_orgs_per_project) * 2
    
    for project in projects:
        project_id = project["id"]
        print(f"\nProcessing: {project.get('title', project_id)}", flush=True)
        
        # Fetch results for this project
        results = fetch_results_for_digest(
            config.db_path,
            project_id=project_id,
            min_score=min_score,
            include_shown=True,
        )
        
        if not results:
            print(f"  No results found for {project_id}", flush=True)
            digests.append(ProjectDigest(
                project_id=project_id,
                project_title=project.get("title", project_id),
                grants=[],
                organizations=[],
                deadline_reminders=[],
            ))
            continue
        
        print(f"  Found {len(results)} results (score >= {min_score})", flush=True)
        
        # Only classify top results to save API calls
        # Results are already sorted by (unseen first, then score)
        results_to_classify = results[:classify_limit]
        print(f"  Classifying top {len(results_to_classify)} results...", flush=True)
        
        # Classify results
        classifications = classify_results(llm, results_to_classify)
        
        # Update result_type in database
        for result_id, result_type in classifications.items():
            update_result_type(config.db_path, result_id, result_type)
        
        # Count by type
        type_counts = {}
        for rtype in classifications.values():
            type_counts[rtype] = type_counts.get(rtype, 0) + 1
        print(f"  Classification: {type_counts}", flush=True)
        
        # Build digest (only from classified results)
        digest = build_project_digest(
            llm,
            project,
            results_to_classify,
            classifications,
            max_grants=max_grants_per_project,
            max_orgs=max_orgs_per_project,
        )
        digests.append(digest)
        
        # Collect IDs to mark as shown
        for entry in digest.grants + digest.organizations:
            if entry.is_new:
                all_shown_ids.append(entry.result.id)
    
    # Format output
    output = format_digest_text(digests)
    
    # Mark results as shown
    if mark_shown and all_shown_ids:
        print(f"\nMarking {len(all_shown_ids)} results as shown...", flush=True)
        mark_results_shown(config.db_path, all_shown_ids)
    
    print("\nDigest generation complete!", flush=True)
    
    return output
