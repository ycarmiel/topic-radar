"""
Pydantic models shared across the Topic Radar core.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SourceRef(BaseModel):
    """A single web source referenced in a research result."""

    title: str
    url: str
    snippet: str = ""


class TopicSummary(BaseModel):
    """Structured summary produced by the researcher for a given topic."""

    topic: str
    overview: str
    key_points: list[str]
    trends: str
    gaps_and_caveats: str
    sources: list[SourceRef]


class HistoryEntry(BaseModel):
    """A persisted research result stored in SQLite."""

    id: int
    topic: str
    created_at: datetime
    summary: TopicSummary
