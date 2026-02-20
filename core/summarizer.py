"""AI summarisation using the Claude API.

Provides two levels of summarisation:

1. **Card-level** — ``Summarizer.summarize_result()``:
   A concise 2-sentence summary for an individual result card.

2. **Executive** — ``Summarizer.generate_executive_summary()``:
   A 2–3 paragraph synthesis across all results with key themes, notable
   trends, and top entities (people, companies, concepts).

The Anthropic client is lazy-initialised so that the class can be
instantiated in tests without requiring a live API key.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from config.settings import Settings
    from core.search import Intent, SearchResult

logger = logging.getLogger(__name__)


# ── Result types ───────────────────────────────────────────────────────────────


@dataclass
class ExecutiveSummary:
    """AI-generated executive summary of a complete search result set."""

    overview: str
    """2–3 paragraph narrative overview of the findings."""

    key_themes: list[str] = field(default_factory=list)
    """Top recurring themes extracted from all results (e.g. ``["LLM reasoning", ...]``)."""

    notable_trends: list[str] = field(default_factory=list)
    """Patterns or directional shifts observed across results."""

    top_entities: list[str] = field(default_factory=list)
    """Notable people, companies, or concepts frequently mentioned."""


# ── Summariser ─────────────────────────────────────────────────────────────────

#: System prompt for the executive summary call.
_EXEC_SUMMARY_SYSTEM = (
    "You are a research analyst. Read the provided search results and produce a "
    "structured JSON summary. Return only valid JSON, no commentary, no markdown fences."
)

#: Pydantic-compatible JSON schema used for structured output.
_EXEC_SUMMARY_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "overview": {
            "type": "string",
            "description": "2-3 paragraph narrative overview of the findings.",
        },
        "key_themes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Up to 5 recurring themes or topics.",
        },
        "notable_trends": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Directional patterns or shifts observed.",
        },
        "top_entities": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Notable people, companies, or concepts.",
        },
    },
    "required": ["overview", "key_themes", "notable_trends", "top_entities"],
    "additionalProperties": False,
}


class Summarizer:
    """Generates AI-powered summaries using the Claude API.

    All methods are intentionally side-effect-free (pure input → output)
    so they are easy to unit-test with mocked API responses.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialise the summariser.

        Args:
            settings: Application configuration.
        """
        self.settings = settings
        self._client: object = None  # Lazy-initialised anthropic.Anthropic

    @property
    def client(self) -> object:
        """Lazy-initialise and return the Anthropic SDK client."""
        if self._client is None:
            import anthropic
            # max_retries=5 so the SDK backs off and retries on 429 rate-limit
            # errors that occur after the heavier search call.
            self._client = anthropic.Anthropic(
                api_key=self.settings.anthropic_api_key,
                max_retries=5,
            )
        return self._client

    # ── Card-level summary ─────────────────────────────────────────────────

    def summarize_result(
        self,
        title: str,
        snippet: str,
        url: str,  # noqa: ARG002  (reserved for future URL fetching)
    ) -> str:
        """Generate a concise 2-sentence summary for a single result card.

        Phase 1 returns the snippet directly (truncated). Phase 2 will call
        the Claude API to produce a genuinely synthesised summary.

        Args:
            title: The result title.
            snippet: The raw snippet/preview text from the search result.
            url: The source URL (reserved for Phase 2 content fetching).

        Returns:
            A 2-sentence summary string (≤ 300 characters in Phase 1).
        """
        # TODO Phase 2: call Claude to generate a true 2-sentence summary
        # combining title + snippet context.
        combined = snippet or title
        return combined[:300].rstrip() + ("…" if len(combined) > 300 else "")

    # ── Executive summary ──────────────────────────────────────────────────

    def generate_executive_summary(
        self,
        query: str,
        results: list[SearchResult],
        intent: Intent,
        raw_text: Optional[str] = None,
    ) -> ExecutiveSummary:
        """Generate an executive summary across all search results.

        Uses structured output (JSON schema) to produce a validated
        ``ExecutiveSummary`` object.

        Args:
            query: The original search query.
            results: List of classified search results to synthesise.
            intent: Detected user intent; used to tailor the summary tone.
            raw_text: Optional full research text from the streaming pass
                (if available, preferred over individual snippets).

        Returns:
            An ``ExecutiveSummary`` with overview, themes, trends, and entities.

        Raises:
            anthropic.APIError: On API failures.
        """
        if not results:
            return ExecutiveSummary(
                overview=f"No results found for '{query}'.",
            )

        # If Claude's research report is available, use it directly as the
        # overview — this avoids a second API call and the associated rate-limit
        # risk.  A follow-up structured call is only made when raw_text is absent.
        if raw_text and raw_text.strip():
            return ExecutiveSummary(overview=raw_text.strip())

        # Fallback: build a compact title list and ask Claude to summarise.
        context = "\n".join(
            f"[{i + 1}] {r.title}" for i, r in enumerate(results[:10])
        )
        intent_instruction = {
            "academic": "Focus on methodology, evidence quality, and research gaps.",
            "tutorial": "Focus on learning progression, skill level, and best resources.",
            "business": "Focus on market dynamics, key players, and financial data.",
            "exploratory": "Provide a balanced overview with key takeaways.",
        }.get(str(intent.value), "Provide a balanced overview.")

        user_content = (
            f"Query: {query}\n"
            f"Intent: {intent.value} — {intent_instruction}\n\n"
            f"Sources:\n{context}"
        )

        try:
            response = self.client.messages.create(
                model=self.settings.summary_model,
                max_tokens=500,
                system=_EXEC_SUMMARY_SYSTEM,
                messages=[{"role": "user", "content": user_content}],
                output_config={
                    "format": {"type": "json_schema", "schema": _EXEC_SUMMARY_SCHEMA}
                },
            )
            data = json.loads(response.content[0].text)
            return ExecutiveSummary(
                overview=data.get("overview", ""),
                key_themes=data.get("key_themes", []),
                notable_trends=data.get("notable_trends", []),
                top_entities=data.get("top_entities", []),
            )
        except Exception:
            logger.exception("Executive summary failed for query=%r", query)
            return ExecutiveSummary(
                overview=f"Found {len(results)} results for '{query}'.",
            )
