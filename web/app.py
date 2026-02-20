"""Flask web server for TopicRadar.

Routes
──────
GET  /               Homepage — search form
GET  /results?q=...  Results page (server-rendered shell, JS fetches data)
POST /api/search     Search API — returns JSON with results + summary
"""

from __future__ import annotations

import json
import logging
import os
import sys

# Allow running as `python web/app.py` from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, jsonify, render_template, request

from config.settings import Settings
from core.aggregator import aggregate
from core.categorizer import classify_result
from core.search import SearchOrchestrator, detect_intent, parse_time_range
from core.summarizer import Summarizer

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
settings = Settings()

# Initialise core services
_orchestrator = SearchOrchestrator(settings)
_summarizer = Summarizer(settings)


# ── UI routes ──────────────────────────────────────────────────────────────────


@app.route("/")
def index() -> str:
    """Render the homepage with the search form."""
    return render_template("index.html")


@app.route("/results")
def results() -> str:
    """Render the results page shell.

    The actual results are fetched client-side by ``js/app.js`` via
    ``POST /api/search``. This server-rendered shell provides the query
    value and skeleton layout for a fast perceived load time.
    """
    query = request.args.get("q", "").strip()
    return render_template("results.html", query=query)


# ── Search API ─────────────────────────────────────────────────────────────────


@app.route("/api/search", methods=["POST"])
def search_api():
    """Search API endpoint.

    Expected JSON body::

        {
            "query": "quantum computing breakthroughs 2024",
            "time_range": "2024"  // optional
        }

    Response JSON::

        {
            "query": "...",
            "intent": "academic" | "tutorial" | "business" | "exploratory",
            "time_range": "...",           // null if not detected
            "summary": {
                "overview": "...",
                "key_themes": ["...", ...],
                "notable_trends": ["...", ...],
                "top_entities": ["...", ...]
            },
            "sections": [
                {
                    "type": "papers",
                    "label": "📄 Research Papers",
                    "results": [
                        {
                            "title": "...",
                            "url": "...",
                            "snippet": "...",
                            "ai_summary": "...",
                            "source": "arxiv.org",
                            "published_date": "...",
                            "relevance_explanation": "..."
                        },
                        ...
                    ]
                },
                ...
            ]
        }
    """
    data = request.get_json(silent=True)
    if not data or not data.get("query"):
        return jsonify({"error": "query is required"}), 400

    query: str = data["query"].strip()
    time_range: str | None = data.get("time_range") or parse_time_range(query)

    if not query:
        return jsonify({"error": "query must not be blank"}), 400

    try:
        # 1. Search
        response = _orchestrator.search(query, time_range=time_range)

        # 2. Classify each result by content type
        for result in response.results:
            result.content_type = classify_result(result).value

        # 3. Aggregate + prioritise
        sections = aggregate(
            response.results,
            intent=response.intent.value,
            max_results=settings.max_search_results,
        )

        # 4. Executive summary
        summary = _summarizer.generate_executive_summary(
            query=query,
            results=response.results,
            intent=response.intent,
            raw_text=response.raw_text or None,
        )

        # 5. Serialise
        from core.categorizer import CONTENT_TYPE_LABELS, ContentType
        sections_json = [
            {
                "type": section_type,
                "label": CONTENT_TYPE_LABELS.get(
                    ContentType(section_type), section_type
                ),
                "results": [
                    {
                        "title": r.title,
                        "url": r.url,
                        "snippet": r.snippet,
                        "ai_summary": r.ai_summary or r.snippet,
                        "source": r.source,
                        "published_date": r.published_date,
                        "relevance_explanation": r.relevance_explanation,
                    }
                    for r in section_results
                ],
            }
            for section_type, section_results in sections
        ]

        return jsonify({
            "query": query,
            "intent": response.intent.value,
            "time_range": response.time_range,
            "summary": {
                "overview": summary.overview,
                "key_themes": summary.key_themes,
                "notable_trends": summary.notable_trends,
                "top_entities": summary.top_entities,
            },
            "sections": sections_json,
        })

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.exception("Search error for query=%r", query)
        return jsonify({"error": f"Search failed: {type(exc).__name__}"}), 500


# ── Entry point ────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    port = int(os.getenv("PORT", "5001"))
    app.run(debug=debug, host="0.0.0.0", port=port)
