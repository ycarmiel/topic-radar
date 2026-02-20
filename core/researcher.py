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

MODEL = "claude-opus-4-6"
WEB_SEARCH_BETA = "web-search-2025-03-05"
WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search"}

RESEARCH_SYSTEM = """You are Topic Radar, a senior research analyst.
The user will give you a topic. Use the web_search tool as many times as needed
to gather comprehensive, up-to-date information. Then write a detailed research
report covering:

1. A clear overview of the topic (2-4 sentences)
2. The most important key points (as a numbered list)
3. Current trends and emerging developments
4. Known gaps, limitations, or caveats in the available information

Cite sources inline where relevant. Be factual and concise."""

STRUCTURE_SYSTEM = """You are a data-extraction assistant.
You will receive a research report and a list of web sources.
Extract and return ONLY a JSON object that strictly matches the schema provided.
Do not add commentary outside the JSON."""


# ── Streaming research ─────────────────────────────────────────────────────

def research_streaming(
    topic: str,
) -> Generator[tuple[str, object], None, None]:
    """Stream a Claude research session with web search.

    Yields ``(event_type, payload)`` tuples:

    * ``("token",   str)``           — a text chunk from Claude's response
    * ``("source",  SourceRef)``     — a web source discovered during search
    * ``("raw_text", str)``          — the complete assembled text (last event)

    Args:
        topic: The topic to research.

    Raises:
        ValueError: If topic is blank.
        anthropic.APIError: On API errors.
    """
    topic = topic.strip()
    if not topic:
        raise ValueError("Topic must not be empty.")

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    sources: list[SourceRef] = []
    text_parts: list[str] = []

    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=8192,
        thinking={"type": "adaptive"},
        betas=[WEB_SEARCH_BETA],
        tools=[WEB_SEARCH_TOOL],
        system=RESEARCH_SYSTEM,
        messages=[{"role": "user", "content": f"Research this topic in depth: {topic}"}],
    ) as stream:
        for event in stream:
            event_type = getattr(event, "type", None)

            # ── Capture sources from web_search_result blocks ──────────────
            if event_type == "content_block_start":
                block = getattr(event, "content_block", None)
                if block and getattr(block, "type", None) == "web_search_tool_result":
                    for result in getattr(block, "content", []) or []:
                        if getattr(result, "type", None) == "web_search_result":
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

    source_list = "\n".join(f"- {s.title}: {s.url}" for s in sources)
    user_content = (
        f"Topic: {topic}\n\n"
        f"Sources:\n{source_list or '(none)'}\n\n"
        f"Research report:\n{raw_text}"
    )

    schema = TopicSummary.model_json_schema()

    response = client.messages.parse(
        model=MODEL,
        max_tokens=4096,
        system=STRUCTURE_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
        output_format=TopicSummary,
    )

    structured = response.parsed_output

    # Merge streaming-captured sources if Claude produced fewer
    if not structured.sources and sources:
        structured = structured.model_copy(update={"sources": sources[:10]})

    # Ensure topic is set correctly
    structured = structured.model_copy(update={"topic": topic})

    return structured


# ── Convenience wrapper ────────────────────────────────────────────────────

def research(topic: str) -> TopicSummary:
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

    for event_type, payload in research_streaming(topic):
        if event_type == "source":
            sources.append(payload)
        elif event_type == "raw_text":
            raw_text = payload

    return structure(topic, raw_text, sources)
