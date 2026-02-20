"""
Flask web server for Topic Radar.

Routes
──────
GET  /                      Dashboard UI
GET  /api/history           List recent history entries (JSON)
GET  /api/history/<id>      Fetch a specific entry (JSON)
DELETE /api/history/<id>    Delete an entry (JSON)
GET  /api/stream?topic=...  SSE: stream research + final structured result
"""

from __future__ import annotations

import json
import logging
import os
import sys

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request, stream_with_context

# Allow running as `python web/app.py` from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()

from core import history as hist
from core.researcher import research_streaming, structure

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialise the SQLite database on startup
hist.init_db()


# ── UI ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ── History API ────────────────────────────────────────────────────────────

@app.route("/api/history")
def list_history():
    """Return the 50 most recent history entries as JSON."""
    entries = hist.get_all(limit=50)
    return jsonify(
        [
            {
                "id": e.id,
                "topic": e.topic,
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ]
    )


@app.route("/api/history/<int:entry_id>")
def get_history_entry(entry_id: int):
    """Return a full history entry including the TopicSummary."""
    entry = hist.get_by_id(entry_id)
    if entry is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(
        {
            "id": entry.id,
            "topic": entry.topic,
            "created_at": entry.created_at.isoformat(),
            "summary": entry.summary.model_dump(),
        }
    )


@app.route("/api/history/<int:entry_id>", methods=["DELETE"])
def delete_history_entry(entry_id: int):
    """Delete a history entry."""
    deleted = hist.delete(entry_id)
    if not deleted:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": entry_id})


# ── Research stream ────────────────────────────────────────────────────────

@app.route("/api/stream")
def stream_endpoint():
    """SSE endpoint that streams a full research session.

    Query params:
      topic  (required) — the topic to research

    SSE events emitted:
      {"type": "token",      "text": "..."}       streaming text chunk
      {"type": "source",     "data": {...}}        a web source discovered
      {"type": "structured", "data": {...}}        final TopicSummary JSON
      {"type": "history_id", "id": 123}            DB row id after save
      {"type": "error",      "message": "..."}     on failure
    """
    topic = request.args.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "topic query param is required"}), 400

    def generate():
        sources = []
        raw_text = ""

        try:
            for event_type, payload in research_streaming(topic):
                if event_type == "token":
                    data = json.dumps({"type": "token", "text": payload})
                    yield f"data: {data}\n\n"

                elif event_type == "source":
                    sources.append(payload)
                    data = json.dumps(
                        {"type": "source", "data": payload.model_dump()}
                    )
                    yield f"data: {data}\n\n"

                elif event_type == "raw_text":
                    raw_text = payload

            # ── Structure + save ──────────────────────────────────────────
            summary = structure(topic, raw_text, sources)

            data = json.dumps({"type": "structured", "data": summary.model_dump()})
            yield f"data: {data}\n\n"

            entry_id = hist.save(topic, summary)
            data = json.dumps({"type": "history_id", "id": entry_id})
            yield f"data: {data}\n\n"

        except Exception as exc:
            logger.exception("Research stream error for topic=%r", topic)
            data = json.dumps({"type": "error", "message": str(exc)})
            yield f"data: {data}\n\n"

        yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug, host="0.0.0.0", port=5000)
