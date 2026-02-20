"""Result aggregation and adaptive prioritisation.

Responsibilities:
- Deduplicate results by URL
- Group results by content type (papers / news / discussions / …)
- Order sections based on the detected user intent
- Return a clean, prioritised list of (section_type, results) tuples

The intent → section ordering is the core of TopicRadar's "adaptive display":
- Academic intent  → Papers first, then News, then Discussions
- Tutorial intent  → News/Articles first (often tutorials), then Code, Discussions
- Business intent  → News first, then Discussions, then Papers
- Exploratory      → News first, Papers second, Discussions third
"""

from __future__ import annotations

import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


# ── Intent → content type priority mappings ────────────────────────────────────

#: Maps intent string → preferred display order for content type sections.
#: First entry in each list is expanded by default in the UI.
INTENT_PRIORITY: dict[str, list[str]] = {
    "academic":    ["papers", "news", "discussions", "videos", "code"],
    "tutorial":    ["news", "code", "discussions", "videos", "papers"],
    "business":    ["news", "discussions", "papers", "videos", "code"],
    "exploratory": ["news", "papers", "discussions", "videos", "code"],
}

#: Fallback order when intent is unknown.
_DEFAULT_PRIORITY: list[str] = INTENT_PRIORITY["exploratory"]


# ── Deduplication ──────────────────────────────────────────────────────────────


def deduplicate(results: list[object]) -> list[object]:
    """Remove duplicate search results by URL, keeping the first occurrence.

    Normalises URLs by stripping trailing slashes and lowercasing before
    comparison so that ``https://example.com/`` and ``https://example.com``
    are treated as the same resource.

    Args:
        results: List of ``SearchResult`` objects (typed as ``object`` to
            avoid circular import; expects a ``.url`` attribute).

    Returns:
        Deduplicated list in original order.

    Examples:
        >>> len(deduplicate([r1, r2, r1]))  # r1 duplicated
        2
    """
    seen: set[str] = set()
    unique: list[object] = []

    for result in results:
        url: str = getattr(result, "url", "") or ""
        normalised = url.rstrip("/").lower()
        if normalised and normalised not in seen:
            seen.add(normalised)
            unique.append(result)

    return unique


# ── Grouping ───────────────────────────────────────────────────────────────────


def group_by_type(results: list[object]) -> dict[str, list[object]]:
    """Group search results by their ``content_type`` attribute.

    Args:
        results: List of classified ``SearchResult`` objects.

    Returns:
        Dict mapping ``content_type`` string → list of results.
        Uses ``defaultdict`` internally; always returns a regular ``dict``.
    """
    groups: dict[str, list[object]] = defaultdict(list)
    for result in results:
        content_type: str = getattr(result, "content_type", "news") or "news"
        groups[content_type].append(result)
    return dict(groups)


# ── Prioritisation ─────────────────────────────────────────────────────────────


def prioritize_sections(
    grouped: dict[str, list[object]],
    intent: str,
) -> list[tuple[str, list[object]]]:
    """Order content sections by intent-based priority.

    Sections with zero results are omitted. Sections not listed in the intent
    priority map are appended at the end in arbitrary order.

    Args:
        grouped: Dict mapping content_type → results (from ``group_by_type``).
        intent: Detected user intent string (``"academic"``, ``"tutorial"``, …).

    Returns:
        List of ``(content_type, results)`` tuples, highest priority first.

    Examples:
        >>> prioritize_sections({"papers": [...], "news": [...]}, "academic")
        [("papers", [...]), ("news", [...])]
    """
    priority_order = INTENT_PRIORITY.get(intent, _DEFAULT_PRIORITY)

    ordered: list[tuple[str, list[object]]] = []
    appended_types: set[str] = set()

    # First: add sections in priority order (skip empty ones)
    for content_type in priority_order:
        if content_type in grouped and grouped[content_type]:
            ordered.append((content_type, grouped[content_type]))
            appended_types.add(content_type)

    # Then: append any remaining types not in the priority list
    for content_type, results in grouped.items():
        if content_type not in appended_types and results:
            ordered.append((content_type, results))

    return ordered


# ── Public pipeline ────────────────────────────────────────────────────────────


def aggregate(
    results: list[object],
    intent: str,
    max_results: int = 10,
) -> list[tuple[str, list[object]]]:
    """Full aggregation pipeline: deduplicate → group → prioritise.

    This is the single entry point used by ``web/app.py``.

    Args:
        results: Raw ``SearchResult`` list from the search pass.
        intent: Detected user intent string.
        max_results: Maximum total results to include across all sections.

    Returns:
        Prioritised list of ``(content_type, results)`` tuples, each section
        ordered highest-priority first.
    """
    unique = deduplicate(results)[:max_results]
    grouped = group_by_type(unique)
    return prioritize_sections(grouped, intent)
