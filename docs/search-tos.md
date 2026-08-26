# Web-search & weather data sources - legal/ethics note

> Report-notes file. The paragraph below is normative for the report's legal/ethics section.

Saathi's primary search uses the unofficial `ddgs` library, which retrieves publicly accessible results from search engines' HTML/Lite endpoints. This violates those sites' terms of service in letter, though it sits in a long-accepted gray zone for personal, non-commercial, educational use. We mitigate harm by keeping volume minimal (single-user-triggered queries, ≤10 results), caching responses in SQLite to avoid redundant load, identifying our HTTP client honestly, honoring failures rather than circumventing blocks, and never republishing scraped content beyond titles/URLs/snippets needed for navigation. Wherever possible we prefer official, sanctioned interfaces — Wikipedia's REST API and Open-Meteo are used exactly per their published policies (attribution included under CC BY 4.0). This design choice is documented transparently as a deliberate, bounded trade-off appropriate to an academic setting, not a pattern suitable for commercial deployment.

## Attribution

- **Open-Meteo** (geocoding + forecast APIs): keyless, free for non-commercial use
  (~10k calls/day); licensed **CC-BY-4.0** — attribution required in the report footer.
  https://open-meteo.com/en/docs
- **Wikipedia OpenSearch API**: official MediaWiki Action API, no key; results are
  CC BY-SA licensed; a descriptive User-Agent is sent per Wikimedia API etiquette.
  https://www.mediawiki.org/wiki/API:Opensearch
- **ddgs** (`ddgs>=9.15,<10`, MIT): PyPI carries the disclaimer *"This library is
  for educational purposes only"* — matching this project's framing exactly.
  https://pypi.org/project/ddgs/

## Mitigations implemented in code

- SQLite result cache (6 h TTL) + opportunistic 7-day pruning → bounded upstream load.
- Per-session self-throttle (3 s between network searches); cache hits bypass it.
- Hard timeouts on every outbound call — `(3.05, 7)` connect/read, ddgs `timeout=8`.
- Failures honored, never retried aggressively or circumvented; errors are not cached.
- Only titles/URLs/snippets stored and shown, wrapped in `rel="noopener noreferrer"`.
