"""
Tests for core/history.py

Uses a temporary SQLite file so the real history DB is never touched.

Run with: pytest tests/test_history.py
"""

import os
import tempfile
from pathlib import Path

import pytest

from core.models import SourceRef, TopicSummary
import core.history as hist


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Point DB_PATH to a fresh temp file for each test."""
    db_file = tmp_path / "test_history.db"
    monkeypatch.setenv("DB_PATH", str(db_file))
    hist.init_db()
    yield


@pytest.fixture
def sample_summary() -> TopicSummary:
    return TopicSummary(
        topic="machine learning",
        overview="ML is a subset of AI.",
        key_points=["Supervised learning", "Neural networks"],
        trends="Large language models dominate.",
        gaps_and_caveats="Interpretability remains challenging.",
        sources=[SourceRef(title="Wikipedia", url="https://en.wikipedia.org/wiki/ML")],
    )


class TestSaveAndRetrieve:
    def test_save_returns_positive_id(self, sample_summary):
        row_id = hist.save("machine learning", sample_summary)
        assert isinstance(row_id, int)
        assert row_id > 0

    def test_get_by_id_returns_entry(self, sample_summary):
        row_id = hist.save("machine learning", sample_summary)
        entry = hist.get_by_id(row_id)

        assert entry is not None
        assert entry.id == row_id
        assert entry.topic == "machine learning"
        assert entry.summary.overview == "ML is a subset of AI."

    def test_get_by_id_missing_returns_none(self):
        assert hist.get_by_id(99999) is None

    def test_get_all_returns_newest_first(self, sample_summary):
        id1 = hist.save("topic A", sample_summary.model_copy(update={"topic": "topic A"}))
        id2 = hist.save("topic B", sample_summary.model_copy(update={"topic": "topic B"}))

        entries = hist.get_all()

        assert entries[0].id == id2  # newest first
        assert entries[1].id == id1

    def test_get_all_respects_limit(self, sample_summary):
        for i in range(5):
            hist.save(f"topic {i}", sample_summary.model_copy(update={"topic": f"topic {i}"}))

        entries = hist.get_all(limit=3)
        assert len(entries) == 3


class TestDelete:
    def test_delete_existing(self, sample_summary):
        row_id = hist.save("ml", sample_summary)
        assert hist.delete(row_id) is True
        assert hist.get_by_id(row_id) is None

    def test_delete_missing_returns_false(self):
        assert hist.delete(99999) is False

    def test_deleted_entry_absent_from_get_all(self, sample_summary):
        row_id = hist.save("ml", sample_summary)
        hist.delete(row_id)
        ids = [e.id for e in hist.get_all()]
        assert row_id not in ids
