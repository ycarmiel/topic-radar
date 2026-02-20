"""Tests for core/categorizer.py — URL and text-based content classification."""

from __future__ import annotations

import pytest

from core.categorizer import ContentType, classify_url, classify_by_text


# ── URL classification ─────────────────────────────────────────────────────────


class TestClassifyUrl:
    def test_arxiv_is_paper(self):
        assert classify_url("https://arxiv.org/abs/2401.12345") == ContentType.PAPERS

    def test_pubmed_is_paper(self):
        assert classify_url("https://pubmed.ncbi.nlm.nih.gov/12345678/") == ContentType.PAPERS

    def test_reddit_is_discussion(self):
        assert classify_url("https://reddit.com/r/MachineLearning/comments/xyz") == ContentType.DISCUSSIONS

    def test_hackernews_is_discussion(self):
        assert classify_url("https://news.ycombinator.com/item?id=12345") == ContentType.DISCUSSIONS

    def test_github_is_code(self):
        assert classify_url("https://github.com/anthropics/anthropic-sdk-python") == ContentType.CODE

    def test_youtube_is_video(self):
        assert classify_url("https://youtube.com/watch?v=abc123") == ContentType.VIDEOS

    def test_youtu_be_is_video(self):
        assert classify_url("https://youtu.be/abc123") == ContentType.VIDEOS

    def test_techcrunch_is_news(self):
        assert classify_url("https://techcrunch.com/2024/01/01/story") == ContentType.NEWS

    def test_www_prefix_stripped(self):
        assert classify_url("https://www.arxiv.org/abs/2401.12345") == ContentType.PAPERS

    def test_invalid_url_returns_unknown(self):
        assert classify_url("not-a-url") == ContentType.UNKNOWN

    def test_empty_url_returns_unknown(self):
        assert classify_url("") == ContentType.UNKNOWN


# ── Text-based classification ──────────────────────────────────────────────────


class TestClassifyByText:
    def test_arxiv_in_title(self):
        assert classify_by_text("ArXiv preprint on attention", "") == ContentType.PAPERS

    def test_reddit_in_snippet(self):
        assert classify_by_text("Discussion", "reddit thread about AI safety") == ContentType.DISCUSSIONS

    def test_youtube_in_title(self):
        assert classify_by_text("YouTube lecture on transformers", "") == ContentType.VIDEOS

    def test_github_in_snippet(self):
        assert classify_by_text("Open source lib", "github repository with 10k stars") == ContentType.CODE

    def test_generic_defaults_to_news(self):
        assert classify_by_text("Tech article headline", "some article content") == ContentType.NEWS
