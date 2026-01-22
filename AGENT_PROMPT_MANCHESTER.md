# Manchester Cinema Scraper Development Agent Prompt

## Mission
Create a Manchester cinema scraper that follows the EXACT patterns established in the existing Tokyo and London projects. This is not a greenfield project - it's a careful replication and adaptation of proven working systems.

## Critical Context

### Existing Infrastructure Analysis
**Tokyo Project** (cinema-scrapers/):
- 42+ cinemas, sophisticated Japanese title handling
- Uses Gemini AI for English translations
- Complex TMDB integration with bilingual support
- Main scraper: main_scraper.py (2000+ lines)

**London Project** (london-cinema-scrapers/):
- 30+ cinemas, English-only but complex event filtering
- TMDB integration with broadcast brand handling
- Main scraper: main_scraper.py (1200+ lines)
- Email alerts and monitoring system

**Key Patterns to Replicate EXACTLY:**
1. Directory structure: {city}-cinema-scrapers/
2. Module organization: cinema_modules/ with individual .py files
3. Main scraper orchestrates all modules and handles enrichment
4. Consistent error handling with ScrapeReport class
5. TMDB caching system with JSON files
6. GitHub Actions integration for daily runs

### Manchester Target Cinemas (Priority Order)
1. **HOME Manchester** (homemcr.org) - 5 screens, BFI-affiliated
2. **Cultplex** (cultplex.co.uk) - Cult films, expanding venue
3. **The Savoy** (savoycinemas.co.uk) - 1920s restored, Stockport
4. **Mini Cini** (duciestreetwarehouse.com) - 36-seat venue
5. **Everyman Manchester** (everymancinema.com) - Chain venue
6. **The Light** (thelight.co.uk) - Stockport, 12 screens
7. **Regent Cinema** (regentcinemamarple.co.uk) - 1931 venue
8. **The Plaza** (plazastockport.co.uk) - 1932 art deco

## Implementation Requirements

### Phase 1: Infrastructure Setup (CRITICAL)
manchester-cinema-scrapers/
├── main_scraper.py              # EXACT pattern replication
├── cinema_modules/              # One file per cinema
│   ├── home_mcr_module.py
│   ├── cultplex_module.py
│   ├── savoy_module.py
│   └── ...
├── cinema_assets/               # Cinema logos/images
│   ├── home_mcr.jpg
│   ├── cultplex.jpg
│   └── ...
├── data/                        # Cache and output
│   ├── showtimes.json
│   ├── tmdb_cache.json
│   └── ...
├── requirements.txt             # Dependencies
└── generate_post.py             # Instagram generation

### Phase 2: Main Scraper Implementation
**MUST replicate these exact components from London project:**

1. **ScrapeReport class** - Identical error handling and email alerts
2. **TMDB Utilities** - Same title cleaning and search logic
3. **Timezone handling** - GMT/BST instead of JST/UTC
4. **Parallel execution** - concurrent.futures.ThreadPoolExecutor
5. **JSON output format** - Exact same schema as existing projects

**Key differences for Manchester:**
- UK timezone: timezone(timedelta(hours=0)) with BST awareness
- No Japanese title handling (remove all Japanese-specific code)
- Simpler title cleaning (no kanji brackets or Japanese suffixes)
- Same broadcast brand filtering as London (NT Live, Met Opera, etc.)

### Phase 3: Cinema Module Template
Each cinema module MUST follow this exact pattern:

```python
def scrape_cinema_name():
    """
    Scrapes [Cinema Name] for film showings.
    Returns: list of dicts with exact schema matching existing projects
    """
    listings = []
    
    try:
        # 1. Fetch website/schedule
        # 2. Parse HTML/JSON/API
        # 3. Extract consistent data format
        # 4. Handle missing data gracefully
        
        for showing in showings:
            listings.append({
                "cinema_name": "Exact Cinema Name",
                "movie_title": title,
                "date_text": date_isoformat,  # YYYY-MM-DD
                "showtime": time_24hr,       # HH:MM
                "detail_page_url": url,
                "director": director_or_empty,
                "year": year_or_empty,
                "country": country_or_empty,
                "runtime_min": runtime_or_empty,
                "synopsis": synopsis_or_empty,
                "movie_title_en": ""  # Will be populated by TMDB
            })
    except Exception as e:
        print(f"Error scraping [Cinema Name]: {e}")
        return []
    
    return listings
```

### Phase 4: Data Schema Compliance
**CRITICAL: Output must match exact schema from existing projects**

Required fields (from existing showtimes.json):
```json
{
  "cinema_name": string,
  "movie_title": string,
  "date_text": "YYYY-MM-DD",
  "showtime": "HH:MM",
  "detail_page_url": string,
  "director": string,
  "year": string,
  "country": string,
  "runtime_min": string,
  "synopsis": string,
  "movie_title_en": string,
  "tmdb_id": number,
  "tmdb_title": string,
  "tmdb_poster_path": string,
  "tmdb_backdrop_path": string,
  "tmdb_overview": string,
  "genres": [string],
  "vote_average": number
}
```

## Technical Implementation Notes

### Website Analysis Strategy
1. **HOME Manchester**: Modern React-based site, likely API endpoints
2. **Cultplex**: WordPress-based, standard HTML parsing
3. **Everyman**: Chain website, consistent with London Everyman modules
4. **The Light**: Commercial chain, potentially API-based
5. **Independent venues**: Likely simple HTML structures

### Error Handling Requirements
- Use EXACT same ScrapeReport pattern as London project
- Individual cinema failures must not crash entire scraper
- Email alerts for failures (reuse existing SMTP system)
- Graceful degradation when websites are down

### TMDB Integration
- Reuse existing fetch_tmdb_details() function from London project
- Same title cleaning logic (adapted for English titles)
- Same cache mechanism with tmdb_cache.json
- Same broadcast brand filtering (NT Live, Met Opera, etc.)

## Testing & Validation

### Must Pass These Tests:
1. **Schema validation**: Output JSON matches existing format exactly
2. **Date handling**: Correct GMT/BST timezone conversion
3. **Error resilience**: Individual failures don't crash system
4. **TMDB enrichment**: Works with existing enrichment pipeline
5. **GitHub Actions**: Integrates into existing CI/CD pipeline

### Performance Requirements:
- Complete scrape in under 5 minutes
- Handle 8-10 cinemas in parallel
- Cache TMDB results to avoid API limits
- Email reports for monitoring

## Deployment Checklist
- [ ] All cinema modules implemented and tested
- [ ] Main scraper passes London project structure validation
- [ ] TMDB enrichment works correctly
- [ ] GitHub Actions workflow configured
- [ ] Cinema assets (logos) collected and optimized
- [ ] Error handling and monitoring operational
- [ ] Documentation updated
- [ ] Instagram generation ready (if applicable)

## Success Criteria
1. **Functional**: Successfully scrapes 8+ Manchester cinemas daily
2. **Consistent**: Output format matches existing projects exactly
3. **Reliable**: <10% failure rate for individual cinemas
4. **Maintainable**: Follows existing patterns for easy updates
5. **Monitored**: Integrated into existing alerting system

## Anti-Patterns to Avoid
❌ Creating new directory structures or naming conventions
❌ Reinventing error handling or monitoring systems
❌ Using different TMDB integration approaches
❌ Changing JSON output schemas
❌ Ignoring existing timezone handling patterns
❌ Creating custom scraping libraries

## Starting Point
Begin by studying these files in exact order:
1. `london-cinema-scrapers/main_scraper.py` - Master template
2. `london-cinema-scrapers/cinema_modules/prince_charles_module.py` - Simple example
3. `london-cinema-scrapers/cinema_modules/everyman_chain_module.py` - Chain cinema example
4. Any Tokyo module for advanced patterns (if needed)

Remember: This is about precise replication with Manchester-specific adaptations, not innovation.