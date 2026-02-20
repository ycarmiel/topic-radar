# CLAUDE.md — Topic Radar

## Project Overview

**Topic Radar** is a Python-based web application that helps users find, aggregate, and summarize information from the web on any topic. It uses the Claude API for AI-powered summarization and presents results in a clean dashboard UI.

## Technologies

- **Language:** Python 3.11+
- **Web Framework:** Flask 3.x
- **AI:** Claude API (`claude-opus-4-6`) via `anthropic` SDK — adaptive thinking, streaming, web_search tool
- **Data models:** Pydantic v2 (structured output validation)
- **Persistence:** SQLite via `sqlite3` stdlib (no ORM)
- **Frontend:** Vanilla JS + CSS (no framework dependency)
- **Config:** `python-dotenv` for environment variables

## Project Structure

```
topic-radar/
├── CLAUDE.md               # This file
├── README.md               # User-facing docs
├── requirements.txt        # Python dependencies
├── .env.example            # Sample env vars (never commit .env)
├── data/                   # Created at runtime
│   └── history.db          # SQLite database
├── core/                   # Backend logic (no Flask dependency)
│   ├── __init__.py
│   ├── models.py           # Pydantic models: TopicSummary, HistoryEntry, SourceRef
│   ├── researcher.py       # Claude + web_search tool: research + structure pipeline
│   └── history.py          # SQLite CRUD for search history
├── web/                    # Flask app
│   ├── app.py              # Server routes and SSE streaming
│   ├── static/
│   │   ├── style.css
│   │   └── script.js
│   └── templates/
│       └── index.html
└── tests/
    ├── test_researcher.py
    └── test_history.py
```

## Architecture

```
User submits topic
      │
      ▼
web/app.py  GET /api/stream (SSE)
      │
      ▼
core/researcher.py  research_streaming(topic)
  ├── Claude Opus 4.6 + web_search_20250305 tool (beta)
  │     → streams text tokens + captures SourceRef objects
  └── structure(topic, raw_text, sources)
        → client.messages.parse() → validated TopicSummary (Pydantic)
      │
      ▼
core/history.py  save(topic, summary)
  └── SQLite: data/history.db
      │
      ▼
SSE events to browser:
  {type:"token"}      → live stream box
  {type:"source"}     → source chips
  {type:"structured"} → populate 5 summary cards
  {type:"history_id"} → refresh history sidebar
```

## Coding Standards

### General
- Follow PEP 8. Max line length: 100 characters.
- Use type hints on all public functions and class methods.
- Write docstrings for all public classes and functions.
- Prefer explicit over implicit; avoid magic values — use named constants.
- Keep functions small and single-purpose.

### Error Handling
- Always catch specific exceptions, not bare `except:`.
- Log errors with context; never silently swallow exceptions.
- Surface user-friendly error messages to the UI; log technical details server-side.

### Claude API Usage
- Use model `claude-opus-4-6` as default.
- Enable `thinking: {"type": "adaptive"}` on all calls (Opus 4.6).
- Web search uses `client.beta.messages.stream(betas=["web-search-2025-03-05"], tools=[{"type":"web_search_20250305"}])`.
- Structured output uses `client.messages.parse(output_format=PydanticModel)`.
- Never combine web_search + structured output in the same call — use two passes (research_streaming → structure).
- Use streaming + `.get_final_message()` for all long-running calls to avoid HTTP timeouts.
- Never hardcode the API key — always load from `ANTHROPIC_API_KEY` env var.
- Handle `anthropic.RateLimitError` and `anthropic.APIStatusError` (5xx) with retry logic.

### Security
- Validate and sanitize all user-supplied topic strings before use in prompts or URLs.
- Never expose raw API keys or internal errors to the frontend.
- Treat all scraped web content as untrusted input.

### Frontend
- Keep JS vanilla (no jQuery, no large frameworks).
- Use Server-Sent Events (SSE) for streaming Claude responses to the browser.
- Separate concerns: HTML in templates, styles in style.css, behavior in script.js.

## Environment Variables

| Variable            | Required | Description                        |
|---------------------|----------|------------------------------------|
| `ANTHROPIC_API_KEY` | Yes      | Your Anthropic API key             |
| `FLASK_DEBUG`       | No       | Set to `1` for debug mode          |
| `MAX_SEARCH_RESULTS`| No       | Max results per search (default 5) |

## Running the App

```bash
cp .env.example .env          # Fill in your API key
pip install -r requirements.txt
python web/app.py
```

## Key Decisions

- **`core/` is Flask-free** — all business logic lives in `core/` so it can be tested independently of the web layer.
- **Streaming preferred** — Claude responses stream to the browser via SSE to avoid long blocking waits.
- **DuckDuckGo search** — no API key needed; good for prototyping. Swap to SerpAPI/Bing for production.
