# TopicRadar

> AI-powered adaptive research assistant — search any topic, get structured insights instantly.

---

## What It Does

TopicRadar accepts a natural language query, detects your intent, searches the web via the
Claude AI, and presents findings in a prioritised dashboard.

| Query | Detected intent | Top content shown first |
|---|---|---|
| "arxiv papers on LLM reasoning" | Academic | Research Papers → Articles |
| "how to learn React hooks" | Tutorial | Articles → Code → Discussions |
| "TTS startup funding 2024" | Business | Articles → Discussions → Papers |
| "quantum computing breakthroughs" | Exploratory | Articles → Papers → Discussions |

### Key Features

- **Intent detection** — recognises whether you want academic, tutorial, business, or
  exploratory results and re-orders sections accordingly
- **Content categorisation** — results grouped into Papers, News & Articles, Discussions,
  Code, Videos (Phase 2)
- **AI executive summary** — 2–3 paragraph synthesis with key themes and top entities
- **Adaptive display** — primary section expanded, secondary sections collapsed by default;
  one-click "Show all" override

---

## Quick Start

### Prerequisites

- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com/)

### Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=sk-ant-...

# 3. Run the server
python web/app.py
```

Open **http://localhost:5001** in your browser.

---

## Project Structure

```
topic-radar/
├── CLAUDE.md                    # Developer guidelines & coding standards
├── README.md                    # This file
├── requirements.txt             # Python dependencies
│
├── config/
│   └── settings.py             # App configuration (loaded from env vars)
│
├── core/                        # Business logic (Flask-free, fully testable)
│   ├── search.py               # Intent detection + Claude web search
│   ├── summarizer.py           # AI summarisation (executive + per-card)
│   ├── categorizer.py          # Content type classification
│   └── aggregator.py           # Deduplicate, group, and prioritise results
│
├── web/                         # Flask application
│   ├── app.py                  # Routes: /, /api/search, /results
│   ├── static/
│   │   ├── css/styles.css      # Tailwind overrides + animations
│   │   └── js/app.js           # Fetch results, render cards
│   └── templates/
│       ├── base.html           # Shared layout
│       ├── index.html          # Search homepage
│       └── results.html        # Results dashboard
│
└── tests/
    ├── test_search.py
    ├── test_summarizer.py
    └── test_categorizer.py
```

---

## Configuration

| Variable              | Default | Description                              |
|-----------------------|---------|------------------------------------------|
| `ANTHROPIC_API_KEY`   | —       | **Required.** Your Anthropic API key.    |
| `FLASK_DEBUG`         | `0`     | Set to `1` to enable Flask debug mode.   |
| `PORT`                | `5001`  | HTTP port for the web server.            |
| `MAX_SEARCH_RESULTS`  | `10`    | Maximum results returned per search.     |
| `MAX_WEB_SEARCHES`    | `3`     | Maximum Claude web_search calls / query. |

---

## Running Tests

```bash
python -m pytest tests/ -v
```

---

## Tech Stack

| Component    | Technology                                |
|--------------|-------------------------------------------|
| Language     | Python 3.10+                              |
| Web server   | Flask 3.x                                 |
| AI model     | Claude Haiku 4.5 (fast + high rate limit) |
| Web search   | Claude built-in `web_search_20250305`     |
| Frontend CSS | Tailwind CSS (CDN)                        |
| Frontend JS  | Vanilla JavaScript                        |

---

## Roadmap

- **Phase 1 (current):** Text content, intent-aware display, AI summary
- **Phase 2:** Video/podcast results, search history, export, SSE streaming
