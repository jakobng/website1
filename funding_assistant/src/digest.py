"""Generate curated funding digests using LLM analysis."""

from __future__ import annotations

import json
import re
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
    explanation: str  # Why this fits the project
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
    # Known aggregator domains
    aggregator_domains = {
        "documentary.org", "filmdaily.tv", "filmfreeway.com", "withoutabox.com",
        "shortfilmdepot.com", "reelport.com", "submittable.com", "slideroom.com",
        "wikipedia.org", "en.wikipedia.org", "libraryguides.missouri.edu",
        "filmmakers.com", "indiewire.com/galleries", "screendaily.com/festivals",
    }
    
    # Known news domains
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
        
        # Extract domain
        domain = ""
        if "://" in url_lower:
            domain = url_lower.split("://")[1].split("/")[0]
            if domain.startswith("www."):
                domain = domain[4:]
        
        # Check aggregator domains
        if any(agg in domain for agg in aggregator_domains):
            classifications[r.id] = "aggregator"
            continue
        
        # Check news domains (but not if it looks like an actual grant page)
        if any(news in domain for news in news_domains):
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


def generate_explanations(
    llm: LLMClient,
    project: dict,
    entries: list[tuple[StoredResult, str]],  # (result, result_type)
) -> list[str]:
    """
    Generate personalized explanations for why each result fits this project.
    
    Returns list of explanation strings in same order as entries.
    """
    if not llm.available or not entries:
        return [r.summary or r.title for r, _ in entries]
    
    # Build project context
    project_context = f"""Project: {project.get('title', 'Untitled')}
Synopsis: {project.get('synopsis', '')}
Topics: {', '.join(project.get('topic_summary', []))}"""
    
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
        })
    
    prompt = f"""You are helping a documentary filmmaker understand funding opportunities.

{project_context}

For each opportunity below, write a 1-2 sentence explanation of WHY it's relevant for THIS SPECIFIC film.
Be specific - reference the film's themes, locations, or approach. Don't just describe the grant.

Opportunities:
{json.dumps(entries_info, indent=2)}

Return a JSON array of strings, one explanation per opportunity, in the same order.
Each explanation should be personalized, e.g.:
- "Your film's focus on [specific theme] aligns well with their [specific program]. They've funded similar projects about [topic]."
- "Given your Japan location and civic tech angle, this Japanese foundation could be a natural fit."
- "Their interest in [topic] makes this worth exploring, though you'd need to emphasize the [aspect] of your project."

Be honest - if the fit is weak, say so briefly."""

    text = llm._generate(prompt, timeout=120)
    data = _extract_json(text)
    
    if isinstance(data, list) and len(data) == len(entries):
        return [str(e) for e in data]
    
    # Fallback
    return [r.summary or r.title for r, _ in entries]


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
    
    for r in results:
        rtype = classifications.get(r.id, "specific_grant")
        is_new = r.shown_in_digest is None
        
        # Skip aggregators and irrelevant
        if rtype in ("aggregator", "irrelevant"):
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
    
    # Generate explanations for all selected
    all_selected = selected_grants + selected_orgs + deadline_reminders + selected_outreach
    
    if all_selected:
        print(f"  Generating explanations for {len(all_selected)} opportunities...", flush=True)
        explanations = generate_explanations(llm, project, all_selected)
    else:
        explanations = []
    
    # Build digest entries
    grant_entries = []
    org_entries = []
    reminder_entries = []
    outreach_entries = []
    
    idx = 0
    for r, rtype in selected_grants:
        grant_entries.append(DigestEntry(
            result=r,
            result_type=rtype,
            explanation=explanations[idx] if idx < len(explanations) else "",
            primary_url=r.url,
            is_new=True,
        ))
        idx += 1
    
    for r, rtype in selected_orgs:
        org_entries.append(DigestEntry(
            result=r,
            result_type=rtype,
            explanation=explanations[idx] if idx < len(explanations) else "",
            primary_url=r.url,
            is_new=True,
        ))
        idx += 1
    
    for r, rtype in deadline_reminders:
        reminder_entries.append(DigestEntry(
            result=r,
            result_type=rtype,
            explanation=explanations[idx] if idx < len(explanations) else "",
            primary_url=r.url,
            is_new=False,
        ))
        idx += 1
    
    for r, rtype in selected_outreach:
        outreach_entries.append(DigestEntry(
            result=r,
            result_type=rtype,
            explanation=explanations[idx] if idx < len(explanations) else r.eligibility_notes or "",
            primary_url=r.url,
            is_new=True,
        ))
        idx += 1
    
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
                if r.deadline and r.deadline not in ("null", "unknown"):
                    meta_parts.append(f"Deadline: {r.deadline}")
                if r.grant_amount:
                    meta_parts.append(f"Amount: {r.grant_amount}")
                if r.is_open and r.is_open.lower() == "true":
                    meta_parts.append("OPEN")
                elif r.is_open and r.is_open.lower() == "false":
                    meta_parts.append("CLOSED")
                
                if meta_parts:
                    lines.append(f"   {' | '.join(meta_parts)}")
                
                lines.append("")
                lines.append(f"   Why it fits: {entry.explanation}")
                lines.append("")
                
                if r.eligibility_notes:
                    lines.append(f"   Eligibility: {r.eligibility_notes}")
                
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
                
                lines.append("")
                lines.append(f"   Why approach: {entry.explanation}")
                lines.append("")
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
                
                lines.append("")
                lines.append(f"   Why reach out: {entry.explanation}")
                lines.append("")
                
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
