"""Tests for core/search.py — intent detection and time-range parsing."""

from __future__ import annotations

import pytest

from core.search import Intent, detect_intent, parse_time_range


# ── Intent detection ───────────────────────────────────────────────────────────


class TestDetectIntent:
    def test_academic_paper_keyword(self):
        assert detect_intent("arxiv papers on LLM reasoning") == Intent.ACADEMIC

    def test_academic_study_keyword(self):
        assert detect_intent("latest study on transformer attention") == Intent.ACADEMIC

    def test_tutorial_how_to(self):
        assert detect_intent("how to use React hooks tutorial") == Intent.TUTORIAL

    def test_tutorial_learn_keyword(self):
        assert detect_intent("learn Python for beginners guide") == Intent.TUTORIAL

    def test_business_funding(self):
        assert detect_intent("OpenAI Series C funding round 2024") == Intent.BUSINESS

    def test_business_startup(self):
        assert detect_intent("TTS startup market valuation 2024") == Intent.BUSINESS

    def test_exploratory_no_signals(self):
        assert detect_intent("quantum computing") == Intent.EXPLORATORY

    def test_empty_query_is_exploratory(self):
        assert detect_intent("") == Intent.EXPLORATORY

    def test_case_insensitive(self):
        assert detect_intent("ARXIV PAPER on vision transformers") == Intent.ACADEMIC


# ── Time-range parsing ─────────────────────────────────────────────────────────


class TestParseTimeRange:
    def test_past_months(self):
        result = parse_time_range("AI news past 6 months")
        assert result is not None
        assert "6" in result

    def test_four_digit_year(self):
        result = parse_time_range("startup funding 2024")
        assert result == "2024"

    def test_last_year(self):
        result = parse_time_range("last year's breakthroughs")
        assert result is not None

    def test_no_time_range(self):
        assert parse_time_range("quantum computing basics") is None

    def test_case_insensitive(self):
        result = parse_time_range("Past 3 Months AI trends")
        assert result is not None
