from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.config import AppConfig
from src.llm import LLMClient
from src.search_providers import (
    BingSearchProvider,
    BraveSearchProvider,
    GeminiGroundedSearchProvider,
    MockSearchProvider,
    MultiSearchProvider,
    SearchResult,
    SerpApiSearchProvider,
)
from src.storage import (
    fetch_pivot_suggestions,
    insert_pivot_suggestions,
    insert_results,
    init_db,
    utc_now,
)


# =============================================================================
# MULTILINGUAL SEARCH SUPPORT
# =============================================================================

# Common funding-related terms in different languages
TRANSLATIONS = {
    "Japanese": {
        "documentary grant": "ドキュメンタリー 助成金",
        "documentary film grant": "ドキュメンタリー映画 助成金",
        "documentary film fund": "ドキュメンタリー映画 基金",
        "film fund": "映画基金",
        "film grant": "映画助成金",
        "documentary funding": "ドキュメンタリー資金",
        "open call": "公募",
        "grant application": "助成金申請",
        "civic technology": "シビックテック",
        "democracy": "民主主義",
        "political participation": "政治参加",
        "digital democracy": "デジタル民主主義",
        "nonprofit organization": "NPO法人",
        "foundation": "財団",
        "cultural fund": "文化基金",
        "arts grant": "芸術助成",
    },
    "Mandarin": {
        "documentary grant": "紀錄片補助",
        "documentary film grant": "紀錄片電影補助金",
        "documentary film fund": "紀錄片基金",
        "film fund": "電影基金",
        "film grant": "電影補助金",
        "documentary funding": "紀錄片資金",
        "open call": "公開徵件",
        "grant application": "補助申請",
        "indigenous rights": "原住民權利",
        "environmental": "環境",
        "river rights": "河流權利",
        "water conservation": "水資源保護",
        "nonprofit organization": "非營利組織",
        "foundation": "基金會",
        "cultural fund": "文化基金",
        "Taiwan film": "台灣電影",
    },
    "Spanish": {
        "documentary grant": "subvención documental",
        "documentary film grant": "beca para documental",
        "documentary film fund": "fondo de cine documental",
        "film fund": "fondo de cine",
        "film grant": "ayuda cinematográfica",
        "documentary funding": "financiación documental",
        "open call": "convocatoria abierta",
        "grant application": "solicitud de subvención",
        "environmental justice": "justicia ambiental",
        "water rights": "derechos del agua",
        "climate": "clima",
        "river": "río",
        "nonprofit organization": "organización sin fines de lucro",
        "foundation": "fundación",
        "cultural fund": "fondo cultural",
        "activism": "activismo",
    },
    "German": {
        "documentary grant": "Dokumentarfilm Förderung",
        "documentary film grant": "Dokumentarfilm Förderung",
        "documentary film fund": "Dokumentarfilm Fonds",
        "film fund": "Filmförderung",
        "film grant": "Filmförderung",
        "documentary funding": "Dokumentarfilm Finanzierung",
        "open call": "offene Ausschreibung",
        "grant application": "Förderantrag",
        "nonprofit organization": "gemeinnützige Organisation",
        "foundation": "Stiftung",
        "cultural fund": "Kulturfonds",
    },
}

# Language codes for location-based inference
LOCATION_LANGUAGES = {
    "Japan": "Japanese",
    "Tokyo": "Japanese",
    "Taiwan": "Mandarin",
    "Southern Taiwan": "Mandarin",
    "Spain": "Spanish",
    "Talavera": "Spanish",
    "Germany": "German",
    "European Union": "German",  # Include some German queries for EU
}


def get_project_languages(project: dict) -> list[str]:
    """Get languages to search in based on project config."""
    # Check explicit language preferences
    search_prefs = project.get("search_preferences", {})
    languages = search_prefs.get("languages", [])
    
    if languages:
        return languages
    
    # Infer from locations
    inferred = {"English"}  # Always include English
    for segment in project.get("segments", []):
        for loc in segment.get("primary_locations", []):
            loc_str = str(loc).replace("_", " ")
            if loc_str in LOCATION_LANGUAGES:
                inferred.add(LOCATION_LANGUAGES[loc_str])
    
    return list(inferred)


def translate_query(query: str, language: str) -> str | None:
    """Translate a query to another language using our dictionary."""
    if language not in TRANSLATIONS:
        return None
    
    translations = TRANSLATIONS[language]
    query_lower = query.lower()
    
    # Try exact match first
    if query_lower in translations:
        return translations[query_lower]
    
    # Try to translate parts of the query
    translated_parts = []
    for eng_term, translated_term in translations.items():
        if eng_term in query_lower:
            # Replace the English term with the translated version
            return query_lower.replace(eng_term, translated_term)
    
    return None


def add_multilingual_queries(queries: list[str], project: dict, max_per_language: int = 10) -> list[str]:
    """Add translated versions of queries for project languages."""
    languages = get_project_languages(project)
    
    # Filter to languages we have translations for (excluding English)
    target_languages = [lang for lang in languages if lang in TRANSLATIONS]
    
    if not target_languages:
        return queries
    
    # Select key queries to translate (prioritize shorter, more generic ones)
    key_queries = [q for q in queries if len(q.split()) <= 4][:max_per_language]
    
    translated = []
    for lang in target_languages:
        for query in key_queries:
            trans = translate_query(query, lang)
            if trans and trans not in translated and trans not in queries:
                translated.append(trans)
    
    # Add translated queries (interleaved with original)
    result = list(queries)
    result.extend(translated)
    
    return result


@dataclass
class DiscoveryReport:
    project_id: str
    stored_results: list
    pivot_suggestions: list[dict[str, Any]]


def load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_projects(projects_path: Path) -> list[dict]:
    data = load_yaml(projects_path)
    return data.get("projects", [])


def load_sources(sources_path: Path) -> dict:
    return load_yaml(sources_path)


def select_search_provider(config: AppConfig):
    provider_key = (config.search_provider or "serpapi").lower()
    if provider_key == "gemini_grounded":
        if not config.gemini_api_key:
            return MockSearchProvider()
        return GeminiGroundedSearchProvider(config.gemini_api_key, config.gemini_model)
    if provider_key == "brave" and config.brave_api_key:
        return BraveSearchProvider(config.brave_api_key)
    if provider_key == "bing" and config.bing_api_key:
        return BingSearchProvider(config.bing_api_key, config.bing_endpoint)
    if provider_key == "serpapi" and config.serpapi_api_key:
        return SerpApiSearchProvider(config.serpapi_api_key)

    providers = []
    if config.brave_api_key:
        providers.append(BraveSearchProvider(config.brave_api_key))
    if config.serpapi_api_key:
        providers.append(SerpApiSearchProvider(config.serpapi_api_key))
    if config.bing_api_key:
        providers.append(BingSearchProvider(config.bing_api_key, config.bing_endpoint))
    if not providers:
        return MockSearchProvider()
    if len(providers) == 1:
        return providers[0]
    return MultiSearchProvider(providers)


def build_angles(project: dict, sources: dict) -> list[dict]:
    angles: list[dict] = []
    for segment in project.get("segments", []):
        angles.append(
            {
                "label": f"{segment.get('title')} - {segment.get('summary')}",
                "angle_type": "segment",
                "segment_id": segment.get("id"),
            }
        )
        for theme in segment.get("themes", []):
            angles.append(
                {
                    "label": f"{theme} documentary funding",
                    "angle_type": "theme",
                    "segment_id": segment.get("id"),
                }
            )
        for community in segment.get("communities", []):
            angles.append(
                {
                    "label": f"{community} storytelling grant",
                    "angle_type": "community",
                    "segment_id": segment.get("id"),
                }
            )
        for location in segment.get("primary_locations", []):
            angles.append(
                {
                    "label": f"{location} film funding",
                    "angle_type": "location",
                    "segment_id": segment.get("id"),
                }
            )
        for location in segment.get("alternate_locations", []):
            angles.append(
                {
                    "label": f"{location} documentary grant",
                    "angle_type": "alternate_location",
                    "segment_id": segment.get("id"),
                }
            )
    for node in project.get("topic_graph", {}).get("nodes", []):
        angles.append(
            {
                "label": node.get("label", node.get("id")),
                "angle_type": "topic_node",
                "segment_id": None,
            }
        )
    for hint in project.get("funding_hints", []):
        angles.append(
            {
                "label": hint.replace("_", " "),
                "angle_type": "funding_hint",
                "segment_id": None,
            }
        )
    for seed in sources.get("seed_queries", []):
        angles.append({"label": seed, "angle_type": "seed", "segment_id": None})
    return angles


def build_query_templates(project: dict, sources: dict) -> list[str]:
    templates = []
    for topic in project.get("topic_summary", []):
        templates.extend(
            [
                f"{topic} documentary grant",
                f"{topic} film funding",
                f"{topic} foundation funding",
            ]
        )
        for funder in sources.get("funder_types", []):
            templates.append(f"{topic} {funder.replace('_', ' ')} film")
    for region in sources.get("regions", {}).get("global", []):
        templates.append(f"{region} documentary grant")
    return list(dict.fromkeys([template.strip() for template in templates if template]))


def build_broad_queries(project: dict, sources: dict) -> list[str]:
    """
    Build queries that are specific about ONE dimension at a time.
    
    Good: "digital democracy documentary grant" (topic-specific)
    Good: "Japan film fund" (location-specific)
    Bad: "digital democracy Japan documentary grant" (too many specifics)
    
    Strategy:
    1. Generic documentary funding queries (always useful)
    2. Topic-specific queries (one topic + documentary grant)
    3. Location-specific queries (one location + film fund)
    4. Category-specific queries (one category + grant)
    """
    queries: list[str] = []
    
    # 1. Generic documentary funding queries (cast a wide net)
    generic_queries = [
        "documentary grant",
        "documentary film grant",
        "documentary film fund",
        "documentary development grant",
        "documentary open call",
        "nonfiction film grant",
        "documentary funding apply now",
        "documentary production grant",
    ]
    queries.extend(generic_queries)
    
    # 2. Topic-specific queries (one topic at a time)
    for topic in project.get("topic_summary", []):
        topic_label = str(topic).replace("_", " ").strip()
        if topic_label and topic_label not in ("documentary", "film"):
            queries.append(f"{topic_label} documentary grant")
            queries.append(f"{topic_label} film fund")
    
    # 3. Location-specific queries (one location at a time)
    locations = set()
    for segment in project.get("segments", []):
        for loc in segment.get("primary_locations", []):
            locations.add(str(loc).replace("_", " ").strip())
    
    # Also check team eligibility for funding access
    for member in project.get("team", []):
        for loc in member.get("funding_access", []):
            locations.add(str(loc).replace("_", " ").strip())
    
    for location in locations:
        if location:
            queries.append(f"{location} documentary grant")
            queries.append(f"{location} film fund")
    
    # 4. Category-specific queries (one category at a time)
    for category in project.get("funding_categories", []):
        label = str(category).replace("_", " ").strip()
        if label and "documentary" not in label.lower():
            queries.append(f"{label} grant")
            queries.append(f"{label} film funding")
    
    # 5. Funding hints (explicit suggestions from project config)
    for hint in project.get("funding_hints", []):
        hint_label = str(hint).replace("_", " ").strip()
        if hint_label:
            queries.append(f"{hint_label}")
            queries.append(f"{hint_label} grant")
    
    # 6. Community-specific queries (one community at a time)
    communities = set()
    for segment in project.get("segments", []):
        for comm in segment.get("communities", []):
            communities.add(str(comm).replace("_", " ").strip())
    
    for community in communities:
        if community and len(community) > 3:
            queries.append(f"{community} documentary grant")
    
    # Add seed queries from sources.yml
    queries.extend(sources.get("seed_queries", []))
    
    # Deduplicate while preserving order
    queries = list(dict.fromkeys([q.strip() for q in queries if q.strip()]))
    
    # Add multilingual versions of key queries
    queries = add_multilingual_queries(queries, project, max_per_language=8)
    
    return queries


def build_outreach_queries(project: dict, sources: dict) -> list[str]:
    """
    Build creative queries to find mission-aligned organizations and individuals.
    
    These are NOT grant-focused - they look for:
    - People doing work in the space (researchers, advocates, practitioners)
    - Organizations with aligned missions (not necessarily funders)
    - Potential executive producers, advisors, or connectors
    - Tech companies, foundations, NGOs with related programs
    """
    queries: list[str] = []
    
    topics = project.get("topic_summary", [])
    title = project.get("title", "")
    
    # 1. Find people working in the space
    for topic in topics[:5]:  # Limit to avoid too many queries
        topic_label = str(topic).replace("_", " ").strip()
        if topic_label:
            # Researchers and thought leaders
            queries.append(f"{topic_label} researcher documentary")
            queries.append(f"{topic_label} thought leader")
            queries.append(f"{topic_label} advocate speaker")
            
            # Organizations doing work (not funders)
            queries.append(f"{topic_label} nonprofit organization")
            queries.append(f"{topic_label} initiative program")
            queries.append(f"who is working on {topic_label}")
            
            # Executive producers / film supporters
            queries.append(f"{topic_label} documentary executive producer")
            queries.append(f"{topic_label} film supporter")
    
    # 2. Find tech companies and foundations with related programs
    tech_related_topics = ["ai", "civic_technology", "digital_democracy", "open_source", 
                          "data_governance", "technology"]
    env_related_topics = ["rivers", "environmental_justice", "climate", "rights_of_nature",
                         "indigenous_reciprocity", "ecology"]
    
    has_tech_topic = any(t in topics for t in tech_related_topics)
    has_env_topic = any(t in topics for t in env_related_topics)
    
    if has_tech_topic:
        queries.extend([
            "tech philanthropy democracy",
            "silicon valley documentary supporter",
            "tech executive producer film",
            "digital rights organization",
            "civic tech organization",
            "democracy technology nonprofit",
            "AI ethics organization documentary",
            "responsible AI initiative",
            "open source foundation film",
        ])
    
    if has_env_topic:
        queries.extend([
            "environmental philanthropy documentary",
            "climate documentary executive producer", 
            "river conservation organization film",
            "indigenous rights organization documentary",
            "water rights activist",
            "environmental justice leader",
            "rights of nature organization",
            "ecology documentary supporter",
        ])
    
    # 3. Location-specific influential people
    locations = set()
    for segment in project.get("segments", []):
        for loc in segment.get("primary_locations", []):
            locations.add(str(loc).replace("_", " ").strip())
    
    for location in list(locations)[:3]:
        if location:
            queries.append(f"{location} documentary producer")
            queries.append(f"{location} film industry leader")
            queries.append(f"{location} philanthropist film")
    
    # 4. Key participants / inspirations mentioned in project
    for inspiration in project.get("inspirations", []):
        name = str(inspiration).replace("_", " ")
        queries.append(f"{name} documentary")
        queries.append(f"{name} film support")
    
    for segment in project.get("segments", []):
        for participant in segment.get("key_participants", [])[:2]:
            name = str(participant).replace("_", " ")
            queries.append(f"{name} documentary support")
    
    # 5. Look for people who funded/supported similar documentaries
    queries.extend([
        "documentary angel investor",
        "film impact producer",
        "documentary strategic advisor",
        "film philanthropist nonprofit",
        "impact documentary funder interview",
    ])
    
    # Deduplicate
    queries = list(dict.fromkeys([q.strip() for q in queries if q.strip()]))
    
    # Add multilingual versions of key queries
    queries = add_multilingual_queries(queries, project, max_per_language=5)
    
    return queries


def generate_queries(project: dict, sources: dict, llm: LLMClient, max_queries: int, strategy: str) -> list[str]:
    if strategy == "broad":
        queries = build_broad_queries(project, sources)
        return queries[:max_queries]
    if strategy == "outreach":
        queries = build_outreach_queries(project, sources)
        return queries[:max_queries]
    angles = build_angles(project, sources)
    queries = llm.expand_queries(project, angles, max_queries)
    if not queries:
        queries = build_query_templates(project, sources)
    return queries[:max_queries]


def analyze_results(project: dict, llm: LLMClient, results: list[SearchResult], debug: bool = False) -> list[dict]:
    """Analyze results in batches with rich LLM analysis."""
    BATCH_SIZE = 15  # Process 15 results per LLM call
    
    analyses = []
    total_batches = (len(results) + BATCH_SIZE - 1) // BATCH_SIZE
    
    for batch_num in range(total_batches):
        start_idx = batch_num * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, len(results))
        batch = results[start_idx:end_idx]
        
        print(f"  Analyzing batch {batch_num + 1}/{total_batches} ({len(batch)} results)...", flush=True)
        
        batch_dicts = [
            {
                "title": r.title,
                "url": r.url,
                "snippet": r.snippet,
                "extra_snippets": r.extra_snippets,
                "full_text": r.get_full_text(),
            }
            for r in batch
        ]
        
        batch_analyses = llm.analyze_results_batch(project, batch_dicts)
        analyses.extend(batch_analyses)
    
    return analyses


def discover_project(
    config: AppConfig,
    project: dict,
    depth: int,
    max_results_per_query: int,
) -> DiscoveryReport:
    init_db(config.db_path)
    sources = load_sources(config.sources_path)
    llm = LLMClient(config.gemini_api_key, config.gemini_model)
    provider = select_search_provider(config)

    print(f"[{project['id']}] Generating queries...", flush=True)
    queries = generate_queries(
        project,
        sources,
        llm,
        config.max_queries_per_project,
        config.query_strategy,
    )
    print(f"[{project['id']}] Provider: {provider.name}", flush=True)
    print(f"[{project['id']}] Running {len(queries)} queries (depth={depth})...", flush=True)
    result_items: list[dict[str, Any]] = []
    for index, query in enumerate(queries, start=1):
        print(f"[{project['id']}] Query {index}/{len(queries)}: {query[:60]}...", flush=True)
        for result in provider.search(query, max_results=max_results_per_query):
            result_items.append({"query": query, "result": result})
        if index % 5 == 0:
            print(f"[{project['id']}] ... found {len(result_items)} results so far", flush=True)

    if depth > 1 and result_items:
        followups = build_followup_queries(
            [item["result"] for item in result_items], limit=10
        )
        _debug(config, f"[{project['id']}] Follow-up queries: {len(followups)}")
        for index, query in enumerate(followups, start=1):
            _debug(config, f"[{project['id']}] Follow-up {index}/{len(followups)}: {query}")
            for result in provider.search(query, max_results=max_results_per_query):
                result_items.append({"query": query, "result": result})

    all_results = [item["result"] for item in result_items]
    print(f"[{project['id']}] Analyzing {len(all_results)} results with LLM...", flush=True)
    analyses = analyze_results(project, llm, all_results, debug=config.debug)
    
    prepared: list[dict[str, Any]] = []
    for item, analysis in zip(result_items, analyses):
        result = item["result"]
        prepared.append(
            {
                "project_id": project["id"],
                "segment_id": None,
                "angle_type": "primary",
                "query": item["query"],
                "title": result.title or "Untitled result",
                "url": result.url or "",
                "snippet": result.snippet,
                "source": result.source,
                "score": analysis.get("score", 0.5),
                "deadline": analysis.get("deadline"),
                "grant_amount": analysis.get("grant_amount"),
                "is_open": analysis.get("is_open"),
                "eligibility_notes": analysis.get("eligibility_notes"),
                "topic_match": analysis.get("topic_match"),
                "funder_type": analysis.get("funder_type"),
                "contact_info": analysis.get("contact_info"),
                "summary": analysis.get("summary"),
                "discovered_at": utc_now(),
                "raw": result.raw or {},
            }
        )

    stored_results = insert_results(config.db_path, prepared)
    pivot_suggestions = []
    if stored_results:
        # Contacts are now extracted during the main analysis
        print(f"[{project['id']}] Generating pivot suggestions...", flush=True)
        pivot_texts = llm.suggest_pivots(
            project,
            [
                {
                    "title": result.get("title"),
                    "url": result.get("url"),
                    "snippet": result.get("snippet"),
                }
                for result in prepared[:10]
            ],
        )
        pivot_suggestions = [
            {
                "project_id": project["id"],
                "segment_id": None,
                "suggestion": text,
                "source_result_id": stored_results[0].id,
            }
            for text in pivot_texts
        ]
        if pivot_suggestions:
            insert_pivot_suggestions(config.db_path, pivot_suggestions)

    return DiscoveryReport(
        project_id=project["id"],
        stored_results=stored_results,
        pivot_suggestions=pivot_suggestions or fetch_pivot_suggestions(
            config.db_path, project["id"]
        ),
    )


def build_followup_queries(results: list[SearchResult], limit: int = 10) -> list[str]:
    followups = []
    for result in results:
        if result.title:
            followups.append(f"{result.title} film grant")
        if result.url:
            domain = result.url.split("/")[2] if "://" in result.url else result.url
            followups.append(f"site:{domain} documentary funding")
        if len(followups) >= limit:
            break
    return followups


def run_discovery(
    config: AppConfig,
    project_id: str | None = None,
    depth: int | None = None,
    max_results_per_query: int | None = None,
) -> list[DiscoveryReport]:
    projects = load_projects(config.projects_path)
    reports = []
    for project in projects:
        if project_id and project.get("id") != project_id:
            continue
        report = discover_project(
            config,
            project,
            depth or config.followup_depth,
            max_results_per_query or config.max_results_per_query,
        )
        reports.append(report)
    return reports


def _debug(config: AppConfig, message: str) -> None:
    if config.debug:
        print(message, flush=True)


def _update_result_contacts(db_path, contact_data: list[dict]) -> None:
    """Update results with extracted contact information."""
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        for item in contact_data:
            url = item.get("url")
            contact_info = item.get("contact_info")
            if url and contact_info:
                conn.execute(
                    "UPDATE search_results SET contact_info = ? WHERE url = ? AND contact_info IS NULL",
                    (contact_info, url),
                )
