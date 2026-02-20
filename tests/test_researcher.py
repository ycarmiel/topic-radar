"""
Tests for core/researcher.py

Run with: pytest tests/test_researcher.py
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from core.models import SourceRef, TopicSummary
from core.researcher import research, research_streaming, structure


@pytest.fixture
def sample_summary() -> TopicSummary:
    return TopicSummary(
        topic="quantum computing",
        overview="Quantum computing uses qubits.",
        key_points=["Superposition", "Entanglement"],
        trends="Increasing investment in 2025.",
        gaps_and_caveats="Limited real-world applications so far.",
        sources=[SourceRef(title="IBM Quantum", url="https://ibm.com/quantum")],
    )


class TestResearchStreaming:
    def test_empty_topic_raises(self):
        with pytest.raises(ValueError, match="empty"):
            list(research_streaming(""))

    def test_blank_topic_raises(self):
        with pytest.raises(ValueError, match="empty"):
            list(research_streaming("   "))

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    @patch("core.researcher.anthropic.Anthropic")
    def test_yields_tokens_and_raw_text(self, mock_cls):
        # Build fake streaming events
        text_event = MagicMock()
        text_event.type = "content_block_delta"
        delta = MagicMock()
        delta.type = "text_delta"
        delta.text = "Hello world"
        text_event.delta = delta

        fake_stream = MagicMock()
        fake_stream.__iter__ = MagicMock(return_value=iter([text_event]))
        fake_stream.__enter__ = MagicMock(return_value=fake_stream)
        fake_stream.__exit__ = MagicMock(return_value=False)

        mock_client = MagicMock()
        mock_client.beta.messages.stream.return_value = fake_stream
        mock_cls.return_value = mock_client

        events = list(research_streaming("quantum computing"))

        token_events = [(t, p) for t, p in events if t == "token"]
        raw_events   = [(t, p) for t, p in events if t == "raw_text"]

        assert len(token_events) == 1
        assert token_events[0][1] == "Hello world"
        assert len(raw_events) == 1
        assert raw_events[0][1] == "Hello world"


class TestStructure:
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    @patch("core.researcher.anthropic.Anthropic")
    def test_returns_topic_summary(self, mock_cls, sample_summary):
        fake_response = MagicMock()
        fake_response.parsed_output = sample_summary

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = fake_response
        mock_cls.return_value = mock_client

        result = structure(
            topic="quantum computing",
            raw_text="Some research text",
            sources=[],
        )

        assert isinstance(result, TopicSummary)
        assert result.topic == "quantum computing"

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    @patch("core.researcher.anthropic.Anthropic")
    def test_merges_sources_when_empty(self, mock_cls, sample_summary):
        """If Claude returns no sources, streaming-captured sources are used."""
        no_sources = sample_summary.model_copy(update={"sources": []})
        fake_response = MagicMock()
        fake_response.parsed_output = no_sources

        mock_client = MagicMock()
        mock_client.messages.parse.return_value = fake_response
        mock_cls.return_value = mock_client

        extra_source = SourceRef(title="Nature", url="https://nature.com")
        result = structure(
            topic="quantum computing",
            raw_text="text",
            sources=[extra_source],
        )

        assert result.sources == [extra_source]
