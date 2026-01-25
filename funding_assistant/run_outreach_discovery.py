#!/usr/bin/env python3
"""
Run outreach-focused discovery to find mission-aligned organizations and individuals.

This is different from grant discovery - it looks for:
- People working in the space (researchers, advocates, thought leaders)
- Organizations with aligned missions (not just funders)
- Potential executive producers, advisors, connectors
- Tech companies, foundations with related programs
"""

import argparse
from pathlib import Path

import yaml

from src.config import AppConfig
from src.llm import LLMClient
from src.pipeline import (
    select_search_provider,
    build_outreach_queries,
    analyze_results,
    DiscoveryReport,
)
from src.search_providers import SearchResult
from src.storage import init_db, insert_results, utc_now


def load_projects(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("projects", [])


def load_sources(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def discover_outreach_targets(
    config: AppConfig,
    project: dict,
    max_queries: int = 30,
    max_results_per_query: int = 8,
) -> DiscoveryReport:
    """Run outreach-focused discovery for a project."""
    
    project_id = project["id"]
    print(f"\n{'='*60}", flush=True)
    print(f"OUTREACH DISCOVERY: {project.get('title', project_id)}", flush=True)
    print(f"{'='*60}", flush=True)
    
    # Initialize
    search_provider = select_search_provider(config)
    llm = LLMClient(config.gemini_api_key, config.gemini_model)
    sources = load_sources(Path("data/sources.yml"))
    
    # Generate outreach queries
    queries = build_outreach_queries(project, sources)[:max_queries]
    print(f"Generated {len(queries)} outreach queries", flush=True)
    
    # Sample queries for debugging
    print("Sample queries:", flush=True)
    for q in queries[:5]:
        print(f"  - {q}", flush=True)
    
    # Run searches
    all_results: list[SearchResult] = []
    seen_urls = set()
    
    for i, query in enumerate(queries):
        print(f"[{i+1}/{len(queries)}] Searching: {query}", flush=True)
        try:
            results = search_provider.search(query, max_results=max_results_per_query)
            new_count = 0
            for r in results:
                if r.url not in seen_urls:
                    seen_urls.add(r.url)
                    all_results.append(r)
                    new_count += 1
            if new_count:
                print(f"  Found {new_count} new results", flush=True)
        except Exception as e:
            print(f"  Error: {e}", flush=True)
    
    print(f"\nTotal unique results: {len(all_results)}", flush=True)
    
    if not all_results:
        return DiscoveryReport(project_id=project_id, stored_results=[], pivot_suggestions=[])
    
    # Analyze with LLM (using outreach-focused prompt)
    print(f"Analyzing {len(all_results)} results with LLM...", flush=True)
    analyzed = analyze_outreach_results(project, llm, all_results)
    
    # Prepare for storage
    to_store = []
    for result, analysis in zip(all_results, analyzed):
        to_store.append({
            "project_id": project_id,
            "segment_id": None,
            "angle_type": "outreach",  # Mark as outreach result
            "query": "outreach_discovery",
            "title": result.title,
            "url": result.url,
            "snippet": result.snippet,
            "source": result.source or "brave",
            "score": analysis.get("score", 0.5),
            "discovered_at": utc_now(),
            "deadline": None,  # Outreach targets don't have deadlines
            "grant_amount": None,
            "is_open": "unknown",
            "eligibility_notes": analysis.get("why_relevant"),
            "topic_match": analysis.get("topic_match", []),
            "funder_type": analysis.get("entity_type", "other"),
            "contact_info": analysis.get("contact_info"),
            "summary": analysis.get("summary"),
        })
    
    # Store results
    stored = insert_results(config.db_path, to_store)
    print(f"Stored {len(stored)} outreach targets", flush=True)
    
    return DiscoveryReport(project_id=project_id, stored_results=stored, pivot_suggestions=[])


def analyze_outreach_results(project: dict, llm: LLMClient, results: list[SearchResult]) -> list[dict]:
    """Analyze results with outreach-focused criteria."""
    
    if not llm.available:
        return [{"score": 0.5, "summary": r.title} for r in results]
    
    BATCH_SIZE = 15
    all_analyses = []
    
    for i in range(0, len(results), BATCH_SIZE):
        batch = results[i:i + BATCH_SIZE]
        print(f"  Analyzing batch {i//BATCH_SIZE + 1} ({len(batch)} results)...", flush=True)
        
        # Build project context
        project_context = f"""Project: {project.get('title', 'Untitled')}
Synopsis: {project.get('synopsis', '')}
Topics: {', '.join(project.get('topic_summary', []))}"""
        
        # Build results for prompt
        results_text = ""
        for j, r in enumerate(batch):
            content = r.snippet or r.title
            results_text += f"\n--- Result {j+1} ---\n"
            results_text += f"Title: {r.title}\n"
            results_text += f"URL: {r.url}\n"
            results_text += f"Content: {content[:400]}\n"
        
        prompt = f"""Analyze these search results to find OUTREACH TARGETS for a documentary project.

We are NOT looking for grants. We're looking for:
- Individuals who work in this space (researchers, advocates, thought leaders, practitioners)
- Organizations with aligned missions (NGOs, tech companies, initiatives)
- Potential executive producers, advisors, or connectors
- People who might know funders or be able to make introductions

{project_context}

{results_text}

For EACH result, provide a JSON object:
- score: 0-1 (how good an outreach target is this? 1 = highly aligned, influential person/org)
- entity_type: "individual" / "organization" / "company" / "research_group" / "media" / "other"
- summary: 1 sentence describing who/what this is
- why_relevant: 1 sentence explaining why reaching out could be valuable
- topic_match: array of project topics this aligns with
- contact_info: any contact info found, or null

Return a JSON array with exactly {len(batch)} objects.
Score LOW (0.1-0.3) for:
- Generic news articles
- Grant databases or aggregators
- Unrelated content

Score HIGH (0.7-1.0) for:
- Specific influential individuals in the space
- Organizations actively working on these topics
- People who have supported similar documentaries"""

        text = llm._generate(prompt, timeout=120)
        
        try:
            import re
            import json
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                if isinstance(data, list) and len(data) == len(batch):
                    all_analyses.extend(data)
                    continue
        except:
            pass
        
        # Fallback
        all_analyses.extend([{"score": 0.5, "summary": r.title} for r in batch])
    
    return all_analyses


def main():
    parser = argparse.ArgumentParser(description="Run outreach discovery")
    parser.add_argument("--project", "-p", help="Specific project ID")
    parser.add_argument("--max-queries", type=int, default=30, help="Max queries per project")
    args = parser.parse_args()
    
    config = AppConfig()
    init_db(config.db_path)
    
    projects = load_projects(Path("data/projects.yml"))
    
    if args.project:
        projects = [p for p in projects if p["id"] == args.project]
        if not projects:
            print(f"Project not found: {args.project}")
            return
    
    print("=" * 60, flush=True)
    print("OUTREACH DISCOVERY", flush=True)
    print("Finding mission-aligned organizations and individuals", flush=True)
    print("=" * 60, flush=True)
    
    for project in projects:
        discover_outreach_targets(config, project, max_queries=args.max_queries)
    
    print("\n" + "=" * 60, flush=True)
    print("OUTREACH DISCOVERY COMPLETE", flush=True)
    print("Run 'python generate_digest.py' to see results", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
