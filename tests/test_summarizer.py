"""Tests for core/summarizer.py — AI summarisation stubs."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from core.summarizer import ExecutiveSummary, Summarizer
from core.search import Intent, SearchResult


# ── Fixtures ───────────────────────────────────────────────────────────────────


def make_settings(**overrides):
    """Return a minimal Settings-like object for testing."""
    settings = MagicMock()
    settings.anthropic_api_key = "test-key"
    settings.summary_model = "claude-haiku-4-5"
    for k, v in overrides.items():
        setattr(settings, k, v)
    return settings


def make_results(n: int = 3) -> list[SearchResult]:
    return [
        SearchResult(
            title=f"Result {i}",
            url=f"https://example.com/{i}",
            snippet=f"Snippet text for result {i} with useful content.",
            source="example.com",
        )
        for i in range(n)
    ]


# ── ExecutiveSummary dataclass ─────────────────────────────────────────────────


class TestExecutiveSummary:
    def test_defaults_to_empty_lists(self):
        s = ExecutiveSummary(overview="Test overview")
        assert s.key_themes == []
        assert s.notable_trends == []
        assert s.top_entities == []

    def test_stores_overview(self):
        s = ExecutiveSummary(overview="Hello world")
        assert s.overview == "Hello world"


# ── Summarizer.summarize_result ────────────────────────────────────────────────


class TestSummarizeResult:
    def test_short_snippet_returned_as_is(self):
        s = Summarizer(make_settings())
        result = s.summarize_result("Title", "Short snippet.", "https://x.com")
        assert result == "Short snippet."

    def test_long_snippet_truncated_to_300(self):
        s = Summarizer(make_settings())
        long = "x" * 400
        result = s.summarize_result("Title", long, "https://x.com")
        assert len(result) <= 304  # 300 chars + "…"
        assert result.endswith("…")

    def test_empty_snippet_falls_back_to_title(self):
        s = Summarizer(make_settings())
        result = s.summarize_result("My Title", "", "https://x.com")
        assert "My Title" in result


# ── Summarizer.generate_executive_summary ─────────────────────────────────────


class TestGenerateExecutiveSummary:
    def test_empty_results_returns_no_results_message(self):
        s = Summarizer(make_settings())
        summary = s.generate_executive_summary("AI", [], Intent.EXPLORATORY)
        assert "No results" in summary.overview

    def test_returns_executive_summary_instance(self):
        s = Summarizer(make_settings())
        results = make_results(3)
        summary = s.generate_executive_summary("quantum", results, Intent.ACADEMIC)
        assert isinstance(summary, ExecutiveSummary)
        assert isinstance(summary.overview, str)
        assert len(summary.overview) > 0
