"""Search orchestration and intent detection.

Responsibilities:
- Detect user intent from the query (academic / tutorial / business / exploratory)
- Parse optional time-range hints ("past 6 months", "2024")
- Orchestrate Claude web_search calls
- Return structured SearchResponse objects

Phase 1 implementation:
    Intent detection uses lightweight keyword heuristics.
    Phase 2 will replace this with a Claude classification call for higher accuracy.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Optional
from urllib.parse import urlparse

if TYPE_CHECKING:
    from config.settings import Settings

logger = logging.getLogger(__name__)

# ── Enums ──────────────────────────────────────────────────────────────────────


class Intent(str, Enum):
    """Detected user intent for a search query."""

    ACADEMIC = "academic"          # Seeking research papers, studies, methodology
    TUTORIAL = "tutorial"          # Learning, how-to guides, examples
    BUSINESS = "business"          # News, funding, market intelligence
    EXPLORATORY = "exploratory"    # General overview, broad exploration


# ── Data classes ───────────────────────────────────────────────────────────────


@dataclass
class SearchResult:
    """A single search result from any content source."""

    title: str
    url: str
    snippet: str
    source: str
    published_date: Optional[str] = None
    content_type: str = "news"          # Filled in by categorizer.py
    relevance_explanation: str = ""     # Filled in by summarizer.py
    ai_summary: str = ""               # Filled in by summarizer.py


@dataclass
class SearchResponse:
    """Complete response from a full search operation."""

    query: str
    intent: Intent
    time_range: Optional[str]
    results: list[SearchResult] = field(default_factory=list)
    raw_text: str = ""


# ── Intent detection ───────────────────────────────────────────────────────────

#: Keyword sets used for heuristic intent classification.
_ACADEMIC_SIGNALS: frozenset[str] = frozenset([
    "paper", "papers", "research", "study", "studies", "arxiv", "journal",
    "doi", "scholar", "preprint", "methodology", "findings", "experiment",
    "hypothesis", "citation", "peer-reviewed", "abstract",
])
_TUTORIAL_SIGNALS: frozenset[str] = frozenset([
    "how to", "tutorial", "learn", "guide", "example", "examples",
    "step by step", "beginner", "introduction to", "getting started",
    "course", "walkthrough", "explained", "for dummies",
])
_BUSINESS_SIGNALS: frozenset[str] = frozenset([
    "funding", "startup", "startups", "market", "revenue", "valuation",
    "raised", "acquisition", "ipo", "series a", "series b", "venture",
    "investor", "unicorn", "mrr", "arr", "churn", "b2b", "saas",
])


def detect_intent(query: str) -> Intent:
    """Detect the user's likely intent from their natural language query.

    Uses keyword heuristics in Phase 1. Phase 2 will use a Claude API call
    for higher accuracy on ambiguous queries.

    Args:
        query: The raw search query string.

    Returns:
        The most likely ``Intent`` for this query.

    Examples:
        >>> detect_intent("arxiv papers on transformer attention mechanisms")
        <Intent.ACADEMIC: 'academic'>
        >>> detect_intent("how to use React hooks tutorial")
        <Intent.TUTORIAL: 'tutorial'>
        >>> detect_intent("OpenAI funding round Series C 2024")
        <Intent.BUSINESS: 'business'>
    """
    query_lower = query.lower()

    # Count signal hits per intent category
    academic_hits = sum(1 for sig in _ACADEMIC_SIGNALS if sig in query_lower)
    tutorial_hits = sum(1 for sig in _TUTORIAL_SIGNALS if sig in query_lower)
    business_hits = sum(1 for sig in _BUSINESS_SIGNALS if sig in query_lower)

    if not any([academic_hits, tutorial_hits, business_hits]):
        return Intent.EXPLORATORY

    # Return the category with the most signal hits
    scores = {
        Intent.ACADEMIC: academic_hits,
        Intent.TUTORIAL: tutorial_hits,
        Intent.BUSINESS: business_hits,
    }
    return max(scores, key=lambda k: scores[k])


# ── Time-range parsing ─────────────────────────────────────────────────────────

#: Regex patterns for extracting time range hints from a query.
_TIME_RANGE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"past \d+ (?:months?|years?|weeks?|days?)", re.IGNORECASE),
    re.compile(r"last \d+ (?:months?|years?|weeks?|days?)", re.IGNORECASE),
    re.compile(r"(?:this|last) (?:year|month|week)", re.IGNORECASE),
    re.compile(r"\b20\d{2}\b"),   # Four-digit year e.g. 2024
]


def parse_time_range(query: str) -> Optional[str]:
    """Extract an optional time-range hint from a natural language query.

    Args:
        query: The raw search query string.

    Returns:
        A normalised time-range string, or ``None`` if no hint was detected.

    Examples:
        >>> parse_time_range("AI papers past 6 months")
        'past 6 months'
        >>> parse_time_range("2024 startup funding rounds")
        '2024'
        >>> parse_time_range("quantum computing basics")
        None
    """
    for pattern in _TIME_RANGE_PATTERNS:
        match = pattern.search(query)
        if match:
            return match.group(0)
    return None


# ── Search orchestrator ────────────────────────────────────────────────────────

#: Beta header name for the Claude web_search tool.
_WEB_SEARCH_BETA = "web-search-2025-03-05"
#: Tool definition passed to the Claude beta messages API.
_WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
}

_WWW_PREFIX = re.compile(r"^www\.")


def _hostname(url: str) -> str:
    """Return the bare hostname of *url*, stripping any ``www.`` prefix."""
    try:
        return _WWW_PREFIX.sub("", urlparse(url).netloc) or url
    except Exception:
        return url


class SearchOrchestrator:
    """Orchestrates web searches using the Claude ``web_search`` tool.

    Responsible for:
    - Building lens-appropriate system prompts based on detected intent
    - Executing Claude API calls with the web_search beta tool
    - Extracting ``SearchResult`` objects from the API response
    - Returning a structured ``SearchResponse``

    The Anthropic client is lazy-initialised to allow instantiation without
    a live API key (useful in tests when the client is mocked).
    """

    #: System prompt templates keyed by intent.
    _SYSTEM_PROMPTS: dict[str, str] = {
        Intent.ACADEMIC: (
            "You are a scientific research assistant. Search the web 2–3 times: "
            "find recent studies and preprints, then look for meta-analyses or expert "
            "consensus. Write a concise report covering: abstract-style overview, "
            "5 key findings with evidence quality, research trends, and methodological "
            "limitations. Prioritise peer-reviewed sources and preprints (ArXiv, PubMed)."
        ),
        Intent.TUTORIAL: (
            "You are a technical education specialist. Search the web 2–3 times: "
            "find the best tutorials, official docs, and community guides. Write a "
            "concise report covering: quick-start overview, 5 key learning resources "
            "with skill level, recommended learning path, common pitfalls to avoid."
        ),
        Intent.BUSINESS: (
            "You are a market intelligence analyst. Search the web 2–3 times: "
            "find recent news, funding rounds, and market data. Write a concise report "
            "covering: market overview with size/growth, 5 notable companies/deals, "
            "emerging trends, key risks. Include data points (TAM, CAGR, round sizes) "
            "where available."
        ),
        Intent.EXPLORATORY: (
            "You are a research assistant. Search the web 2–3 times: start broad, "
            "then drill into the most interesting angle. Write a concise report covering: "
            "overview, 5 key points, current trends, known gaps. Be factual and balanced."
        ),
    }

    def __init__(self, settings: Settings) -> None:
        """Initialise the orchestrator.

        Args:
            settings: Application configuration (must have ``anthropic_api_key``).
        """
        self.settings = settings
        self._client: object = None  # Lazy-initialised anthropic.Anthropic instance

    @property
    def client(self) -> object:
        """Lazy-initialise and return the Anthropic SDK client."""
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(
                api_key=self.settings.anthropic_api_key,
                max_retries=5,
            )
        return self._client

    def search(self, query: str, time_range: Optional[str] = None) -> SearchResponse:
        """Perform a full search for the given query.

        Detects intent, selects the appropriate system prompt, calls the Claude
        web_search API, and returns a structured ``SearchResponse``.

        Args:
            query: Natural language search query.
            time_range: Optional time constraint parsed from the query or provided
                by the caller (e.g. ``"past 6 months"``).

        Returns:
            A ``SearchResponse`` containing detected intent, time range, raw text,
            and a list of ``SearchResult`` objects.

        Raises:
            ValueError: If the query is blank.
            anthropic.APIError: On API failures.
        """
        query = query.strip()
        if not query:
            raise ValueError("Search query must not be empty.")

        intent = detect_intent(query)
        detected_time_range = time_range or parse_time_range(query)
        system = self._SYSTEM_PROMPTS[intent]

        # Append time constraint to the user message if present
        user_message = f"Research: {query}"
        if detected_time_range:
            user_message += f" (focus on: {detected_time_range})"

        logger.info(
            "Search query=%r intent=%s time_range=%s",
            query, intent.value, detected_time_range,
        )

        results: list[SearchResult] = []
        text_parts: list[str] = []
        tool = {**_WEB_SEARCH_TOOL, "max_uses": self.settings.max_web_searches}

        with self.client.beta.messages.stream(
            model=self.settings.research_model,
            max_tokens=800,
            betas=[_WEB_SEARCH_BETA],
            tools=[tool],
            system=system,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            for event in stream:
                event_type = getattr(event, "type", None)

                # ── Capture sources from web_search_result blocks ──────────
                if event_type == "content_block_start":
                    block = getattr(event, "content_block", None)
                    if block and getattr(block, "type", None) == "web_search_tool_result":
                        for item in getattr(block, "content", []) or []:
                            if getattr(item, "type", None) == "web_search_result":
                                url = getattr(item, "url", "") or ""
                                results.append(SearchResult(
                                    title=getattr(item, "title", "") or "",
                                    url=url,
                                    snippet="",
                                    source=_hostname(url),
                                    published_date=getattr(item, "page_age", None) or None,
                                ))

                # ── Collect Claude's text response ─────────────────────────
                elif event_type == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    if delta and getattr(delta, "type", None) == "text_delta":
                        text_parts.append(delta.text)

        logger.info("Search complete: %d sources found", len(results))
        return SearchResponse(
            query=query,
            intent=intent,
            time_range=detected_time_range,
            results=results[:self.settings.max_search_results],
            raw_text="".join(text_parts),
        )
