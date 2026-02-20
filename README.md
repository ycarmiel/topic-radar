# Topic Radar

> Search the web on any topic, then get an AI-powered summary dashboard — all in one place.

## What It Does

1. **Search** — Enter a topic. Topic Radar queries DuckDuckGo and fetches the top results.
2. **Aggregate** — The fetched pages are cleaned and combined into a unified body of content.
3. **Summarize** — Claude (Opus 4.6) reads the aggregated content and produces a structured summary, streamed live to your browser.
4. **Dashboard** — View key takeaways, source links, and a topic overview in a clean UI.

## Quick Start

### Prerequisites

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/)

### Setup

```bash
# 1. Clone / navigate to the project
cd topic-radar

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=sk-ant-...

# 4. Run the server
python web/app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

## Architecture

```
User Input (topic)
      │
      ▼
core/search.py          ← DuckDuckGo search + page fetch
      │
      ▼
core/aggregator.py      ← Merge & deduplicate results
      │
      ▼
core/summarizer.py      ← Claude API (streaming summary)
      │
      ▼
web/app.py (Flask)      ← SSE stream to browser
      │
      ▼
Dashboard (HTML/JS/CSS)
```

## Project Structure

```
topic-radar/
├── CLAUDE.md              # Developer guidelines
├── README.md              # This file
├── requirements.txt       # Python dependencies
├── core/
│   ├── search.py          # Web search logic
│   ├── summarizer.py      # AI summarization via Claude
│   └── aggregator.py      # Combine & clean results
├── web/
│   ├── app.py             # Flask routes + SSE
│   ├── static/
│   │   ├── style.css
│   │   └── script.js
│   └── templates/
│       └── index.html
└── tests/
    ├── test_search.py
    └── test_summarizer.py
```

## Configuration

| Variable              | Default | Description                              |
|-----------------------|---------|------------------------------------------|
| `ANTHROPIC_API_KEY`   | —       | Required. Your Anthropic API key.        |
| `FLASK_DEBUG`         | `0`     | Set to `1` to enable Flask debug mode.  |
| `MAX_SEARCH_RESULTS`  | `5`     | Number of web results to fetch per query.|

## Running Tests

```bash
python -m pytest tests/
```

## Tech Stack

| Component    | Technology                  |
|--------------|-----------------------------|
| Language     | Python 3.11+                |
| Web server   | Flask 3.x                   |
| AI model     | Claude Opus 4.6             |
| Web search   | DuckDuckGo (duckduckgo-search) |
| HTML parsing | BeautifulSoup4              |
| Frontend     | Vanilla HTML/CSS/JS         |
