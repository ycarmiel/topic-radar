# CLAUDE.md — TopicRadar

## Project Overview

**TopicRadar** is an AI-powered adaptive research assistant. It accepts natural language
queries, detects user intent (academic / tutorial / business / exploratory), searches the
web via the Claude API, and presents structured findings in a dynamic dashboard that
prioritises content based on what the user is trying to accomplish.

**Status:** MVP Development (Phase 1)

---

## Technologies

| Layer       | Technology                                                        |
|-------------|-------------------------------------------------------------------|
| Language    | Python 3.10+ with full type hints                                 |
| Web server  | Flask 3.x                                                         |
| AI          | Claude API — `claude-haiku-4-5` for search/summarise             |
| Data models | Pydantic v2 (structured output validation)                        |
| Frontend    | Tailwind CSS (CDN) + Vanilla JS                                   |
| Config      | `python-dotenv` + `config/settings.py`                           |
| Testing     | pytest ≥ 8.0, target ≥ 80 % coverage on `core/`                 |

---

## Project Structure

```
topic-radar/
├── CLAUDE.md               # This file
├── README.md               # User-facing documentation
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
│
├── config/
│   ├── __init__.py
│   └── settings.py         # Centralised app configuration
│
├── core/                   # Business logic — NO Flask imports here
│   ├── __init__.py
│   ├── search.py           # Intent detection + Claude web_search orchestration
│   ├── summarizer.py       # AI executive summary + per-card summaries
│   ├── categorizer.py      # Content type classification (papers/news/discussions/…)
│   └── aggregator.py       # Deduplicate, group, and prioritise results
│
├── web/                    # Flask application
│   ├── app.py              # Routes: GET /, POST /api/search, GET /results
│   ├── static/
│   │   ├── css/
│   │   │   └── styles.css  # Tailwind overrides + custom animations
│   │   └── js/
│   │       └── app.js      # Frontend: fetch results, render cards, toggle sections
│   └── templates/
│       ├── base.html       # Shared layout (header, footer, Tailwind CDN)
│       ├── index.html      # Homepage: search form + example queries
│       └── results.html    # Results dashboard: summary + categorised sections
│
└── tests/
    ├── test_search.py      # Tests for intent detection, time parsing
    ├── test_summarizer.py  # Tests for summary generation
    └── test_categorizer.py # Tests for URL/content classification
```

---

## Architecture

```
User enters query
      │
      ▼
web/app.py  POST /api/search
      │
      ├── core/search.py  detect_intent(query) → Intent
      │                   parse_time_range(query) → Optional[str]
      │                   SearchOrchestrator.search(query) → SearchResponse
      │                       └── Claude API (web_search_20250305 tool, beta)
      │
      ├── core/categorizer.py  classify_result(result) → ContentType
      │                        (applied to each SearchResult)
      │
      ├── core/aggregator.py   aggregate(results, intent) → prioritised sections
      │
      └── core/summarizer.py   Summarizer.generate_executive_summary(...)
                                → ExecutiveSummary
      │
      ▼
JSON response → web/static/js/app.js → render cards + sections
```

**SSE (Phase 2):** When search latency grows, convert `/api/search` to an SSE endpoint
that streams status updates, then structured results. See the existing `researcher.py`
for a reference SSE implementation.

---

## Coding Standards

### Python
- Follow PEP 8; max line length **100 characters**.
- Type hints on **all** public functions and class attributes.
- Google-style docstrings for all public classes and functions.
- Named constants in `UPPER_CASE` at module top — no inline magic strings.
- Prefer `match/case` over long `if/elif` chains when dispatching on strings or enums.
- Keep `core/` fully **Flask-free** — all business logic must be importable and
  testable without a Flask application context.
- Use generator functions (`yield`) for streaming pipelines; never buffer an entire
  API response unless necessary.
- Prefer `model_copy(update={...})` over mutating Pydantic models in-place.
- Validate `lens` / `intent` values against an explicit allowlist before injecting
  into prompts.

### Error Handling
- Catch **specific** exceptions — never bare `except:`.
- Log errors with context using the standard `logging` module; never `print()` for
  diagnostics in production code.
- Surface user-friendly messages to the UI; log technical details server-side.
- Handle `anthropic.RateLimitError` and `anthropic.APIStatusError` (5xx) explicitly.

### Claude API Usage
- Default model: `claude-haiku-4-5` (fast + high rate limits for MVP).
- Web search: `client.beta.messages.stream(betas=["web-search-2025-03-05"],
  tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}])`.
- Structured output: `client.messages.parse(output_format=PydanticModel)`.
- **Never** combine `web_search` + structured output in a single call — use two passes
  (search streaming → structure).
- Never hardcode API keys — always read from `ANTHROPIC_API_KEY` env var.
- Graceful degradation: if the API is unavailable, return a partial result rather than
  crashing.

### Security
- Validate and sanitise all user-supplied queries before embedding in prompts.
- Never expose raw API keys, stack traces, or internal errors to the frontend.
- Treat all scraped web content as untrusted.

### Frontend
- Tailwind CSS via CDN for MVP (no build step required).
- Vanilla JS — no jQuery or large framework dependencies.
- Semantic HTML5 with ARIA labels for key interactive elements.
- Keyboard navigable (Tab + Enter work for search).
- Mobile-first: single column → 2-col → 3-col grid as viewport widens.

### Testing
- Use `pytest`; mock all external API calls with `unittest.mock.patch`.
- Target ≥ 80 % branch coverage on `core/`.
- Test business logic (intent detection, categorisation, aggregation) thoroughly —
  these are pure functions and should be 100 % covered.
- Write the test first (TDD) when implementing a new `core/` function.

---

## Environment Variables

| Variable              | Required | Default | Description                              |
|-----------------------|----------|---------|------------------------------------------|
| `ANTHROPIC_API_KEY`   | Yes      | —       | Anthropic API key                        |
| `FLASK_DEBUG`         | No       | `0`     | Set to `1` for Flask debug / auto-reload |
| `PORT`                | No       | `5001`  | HTTP port                                |
| `MAX_SEARCH_RESULTS`  | No       | `10`    | Max results returned per search          |
| `MAX_WEB_SEARCHES`    | No       | `3`     | Max Claude web_search calls per query    |

---

## Running the App

```bash
cp .env.example .env          # Fill in ANTHROPIC_API_KEY
pip install -r requirements.txt
python web/app.py
# Open http://localhost:5001
```

## Running Tests

```bash
python -m pytest tests/ -v --tb=short
```

---

## Phase Scope

### Phase 1 — MVP (current)
- Text content only: papers, news articles, discussions
- Single search at a time (no history, no comparison)
- Basic adaptive display (intent-ordered sections)
- Essential UI only — no account system

### Phase 2 — Planned
- Video & podcast result types (YouTube API, podcast feeds)
- Search history + saved results (SQLite)
- Code results (GitHub API, Stack Overflow)
- Export: PDF, Markdown
- Advanced filtering (date range, domain allow/block)
- SSE streaming for progressive result delivery

---

## Key Decisions

- **`core/` is Flask-free** — business logic lives in `core/` so every function can
  be unit-tested without spinning up a server.
- **Intent drives layout** — the aggregator re-orders result sections per-query so the
  most relevant content type is always first.
- **Tailwind CDN for MVP** — avoids a build pipeline; switch to compiled Tailwind in
  Phase 2 once the design stabilises.
- **Claude web_search tool** — single API (no DuckDuckGo, no external search key
  required); search + content understanding happen in one model call.
- **Stateless JSON for Phase 1** — no DB, no session state; clean slate every request.
  Phase 2 adds SQLite for history.
