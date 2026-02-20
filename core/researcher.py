"""
AI researcher for Topic Radar.

Uses Claude Opus 4.6 with the built-in web_search tool to autonomously
research a topic, then structures the findings as a TopicSummary.

Flow
────
1. research_streaming(topic)
     → yields text tokens in real-time while Claude searches + writes
     → captures web sources from server_tool_use events
     → returns the complete (text, sources) pair when exhausted

2. structure(topic, raw_text, sources)
     → second Claude call (fast, non-streaming) to convert the free-form
       research text into a validated TopicSummary JSON object via Pydantic
"""

from __future__ import annotations

import logging
import os
from collections.abc import Generator

import anthropic
from pydantic import ValidationError

from core.models import SourceRef, TopicSummary

logger = logging.getLogger(__name__)

RESEARCH_MODEL  = "claude-haiku-4-5"   # fast + high rate limits for web search pass
STRUCTURE_MODEL = "claude-haiku-4-5"   # fast for structuring pass
WEB_SEARCH_BETA = "web-search-2025-03-05"
WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 3}

# ── Lens-specific system prompts ───────────────────────────────────────────

LENS_SYSTEMS: dict[str, str] = {
    "general": (
        "You are a research assistant. Search the web 2-3 times: start broad, "
        "then drill into the most interesting angle. Write a concise report: "
        "overview, 5 key points, current trends, known gaps. Be factual."
    ),
    "scientific": (
        "You are a scientific research assistant. Search 2-3 times: find recent studies, "
        "then look for meta-analyses or expert consensus. Write a concise report: "
        "abstract-style overview, 5 key findings with evidence quality, research trends, "
        "methodological limitations. Prioritise peer-reviewed sources and preprints."
    ),
    "startup": (
        "You are a startup analyst. Search 2-3 times: find recent launches and funding, "
        "then look for competitive dynamics. Write a concise report: "
        "market summary, 5 key opportunities, startup trends, risks and challenges. "
        "Focus on actionable insights for founders."
    ),
    "vc": (
        "You are a venture capital analyst. Search 2-3 times: find market size data, "
        "then notable deals and exits. Write a concise report: "
        "market overview, 5 investment highlights, market trends, due-diligence risks. "
        "Use data: TAM, CAGR, multiples, notable rounds."
    ),
}

STRUCTURE_SYSTEM = (
    "Extract structured data from the research report into the JSON schema provided. "
    "Return only JSON, no commentary."
)


# ── Streaming research ─────────────────────────────────────────────────────

def research_streaming(
    topic: str,
    lens: str = "general",
) -> Generator[tuple[str, object], None, None]:
    """Stream a Claude research session with web search.

    Yields ``(event_type, payload)`` tuples:

    * ``("token",   str)``           — a text chunk from Claude's response
    * ``("source",  SourceRef)``     — a web source discovered during search
    * ``("raw_text", str)``          — the complete assembled text (last event)

    Args:
        topic: The topic to research.
        lens: Research perspective — "general" | "scientific" | "startup" | "vc".

    Raises:
        ValueError: If topic is blank.
        anthropic.APIError: On API errors.
    """
    topic = topic.strip()
    if not topic:
        raise ValueError("Topic must not be empty.")

    system = LENS_SYSTEMS.get(lens, LENS_SYSTEMS["general"])
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    sources: list[SourceRef] = []
    text_parts: list[str] = []

    with client.beta.messages.stream(
        model=RESEARCH_MODEL,
        max_tokens=1200,
        betas=[WEB_SEARCH_BETA],
        tools=[WEB_SEARCH_TOOL],
        system=system,
        messages=[{"role": "user", "content": f"Research: {topic}"}],
    ) as stream:
        for event in stream:
            event_type = getattr(event, "type", None)

            # ── Capture sources from web_search_result blocks ──────────────
            if event_type == "content_block_start":
                block = getattr(event, "content_block", None)
                if block and getattr(block, "type", None) == "web_search_tool_result":
                    for result in getattr(block, "content", []) or []:
                        if getattr(result, "type", None) == "web_search_result" and len(sources) < 5:
                            src = SourceRef(
                                title=getattr(result, "title", "") or "",
                                url=getattr(result, "url", "") or "",
                                snippet=(getattr(result, "page_age", "") or ""),
                            )
                            sources.append(src)
                            yield ("source", src)

            # ── Stream text tokens ─────────────────────────────────────────
            elif event_type == "content_block_delta":
                delta = getattr(event, "delta", None)
                if delta and getattr(delta, "type", None) == "text_delta":
                    chunk = delta.text
                    text_parts.append(chunk)
                    yield ("token", chunk)

    raw_text = "".join(text_parts)
    yield ("raw_text", raw_text)


# ── Structuring pass ───────────────────────────────────────────────────────

def structure(
    topic: str,
    raw_text: str,
    sources: list[SourceRef],
    lens: str = "general",
) -> TopicSummary:
    """Convert free-form research text into a validated TopicSummary.

    Makes a fast, non-streaming Claude call asking it to extract structured
    JSON from the research text.

    Args:
        topic: The original topic string.
        raw_text: The full text from the research_streaming pass.
        sources: Web sources collected during the streaming pass.

    Returns:
        A validated TopicSummary.

    Raises:
        RuntimeError: If Claude's output cannot be parsed into TopicSummary.
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Keep the structuring prompt small to stay within rate limits
    truncated = raw_text[:2000] if len(raw_text) > 2000 else raw_text
    source_list = "\n".join(f"- {s.title}: {s.url}" for s in sources[:5])
    user_content = (
        f"Topic: {topic}\n\n"
        f"Sources:\n{source_list or '(none)'}\n\n"
        f"Report:\n{truncated}"
    )

    response = client.messages.parse(
        model=STRUCTURE_MODEL,
        max_tokens=700,
        system=STRUCTURE_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
        output_format=TopicSummary,
    )

    structured = response.parsed_output

    # Merge streaming-captured sources if Claude produced fewer
    if not structured.sources and sources:
        structured = structured.model_copy(update={"sources": sources[:10]})

    # Ensure topic and lens are set correctly
    structured = structured.model_copy(update={"topic": topic, "lens": lens})

    return structured


# ── Convenience wrapper ────────────────────────────────────────────────────

def research(topic: str, lens: str = "general") -> TopicSummary:
    """Blocking research call — searches, writes, and structures in one go.

    Useful for CLI usage or testing. For web use, prefer research_streaming()
    so the user sees progress.

    Args:
        topic: The topic to research.

    Returns:
        A validated TopicSummary.
    """
    sources: list[SourceRef] = []
    raw_text = ""

    for event_type, payload in research_streaming(topic, lens=lens):
        if event_type == "source":
            sources.append(payload)
        elif event_type == "raw_text":
            raw_text = payload

    return structure(topic, raw_text, sources, lens=lens)
