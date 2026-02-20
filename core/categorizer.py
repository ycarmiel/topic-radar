"""Content type classification.

Classifies search results into one of five content types based on domain patterns
and title/snippet heuristics:

- PAPERS      📄  Academic papers, preprints (ArXiv, PubMed, IEEE, …)
- NEWS        📰  Tech news, blog posts, long-form articles
- DISCUSSIONS 💬  Reddit, HackerNews, Stack Overflow, forums
- VIDEOS      🎥  YouTube, Vimeo, conference talks       [Phase 2]
- CODE        💻  GitHub repos, Stack Overflow, Gists    [Phase 2]
"""

from __future__ import annotations

import logging
import re
from enum import Enum
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# ── Content type enum ──────────────────────────────────────────────────────────


class ContentType(str, Enum):
    """Taxonomy for a piece of web content."""

    PAPERS = "papers"
    NEWS = "news"
    DISCUSSIONS = "discussions"
    VIDEOS = "videos"
    CODE = "code"
    UNKNOWN = "unknown"


#: Human-readable emoji labels for each content type.
CONTENT_TYPE_LABELS: dict[ContentType, str] = {
    ContentType.PAPERS: "📄 Research Papers",
    ContentType.NEWS: "📰 News & Articles",
    ContentType.DISCUSSIONS: "💬 Discussions",
    ContentType.VIDEOS: "🎥 Videos",
    ContentType.CODE: "💻 Code",
    ContentType.UNKNOWN: "📌 Other",
}


# ── Domain allow-lists ─────────────────────────────────────────────────────────

_PAPER_DOMAINS: frozenset[str] = frozenset([
    "arxiv.org", "pubmed.ncbi.nlm.nih.gov", "pmc.ncbi.nlm.nih.gov",
    "scholar.google.com", "semanticscholar.org", "papers.ssrn.com",
    "researchgate.net", "dl.acm.org", "ieee.org", "ieeexplore.ieee.org",
    "springer.com", "springerlink.com", "link.springer.com",
    "sciencedirect.com", "elsevier.com", "nature.com", "science.org",
    "cell.com", "biorxiv.org", "medrxiv.org", "plos.org", "plosone.org",
    "frontiersin.org", "mdpi.com", "openreview.net", "acm.org",
    "ncbi.nlm.nih.gov", "nih.gov",
])

_DISCUSSION_DOMAINS: frozenset[str] = frozenset([
    "reddit.com", "news.ycombinator.com", "stackoverflow.com",
    "stackexchange.com", "quora.com", "lobste.rs", "dev.to",
    "forum.fast.ai", "discuss.pytorch.org", "discourse.julialang.org",
])

_VIDEO_DOMAINS: frozenset[str] = frozenset([
    "youtube.com", "youtu.be", "vimeo.com", "twitch.tv",
    "ted.com", "coursera.org", "udemy.com",
])

_CODE_DOMAINS: frozenset[str] = frozenset([
    "github.com", "gitlab.com", "gist.github.com", "codepen.io",
    "replit.com", "colab.research.google.com", "huggingface.co",
    "pypi.org", "npmjs.com",
])


# ── URL-based classification ───────────────────────────────────────────────────


def classify_url(url: str) -> ContentType:
    """Classify a URL into a ``ContentType`` based on its domain.

    Args:
        url: The full URL string to classify.

    Returns:
        The detected ``ContentType``, or ``ContentType.UNKNOWN`` on parse failure.

    Examples:
        >>> classify_url("https://arxiv.org/abs/2401.12345")
        <ContentType.PAPERS: 'papers'>
        >>> classify_url("https://reddit.com/r/MachineLearning/comments/xyz")
        <ContentType.DISCUSSIONS: 'discussions'>
        >>> classify_url("https://github.com/anthropics/anthropic-sdk-python")
        <ContentType.CODE: 'code'>
    """
    try:
        domain = urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        logger.debug("Failed to parse URL for classification: %r", url)
        return ContentType.UNKNOWN

    if not domain:
        return ContentType.UNKNOWN

    if domain in _PAPER_DOMAINS:
        return ContentType.PAPERS
    if domain in _DISCUSSION_DOMAINS:
        return ContentType.DISCUSSIONS
    if domain in _VIDEO_DOMAINS:
        return ContentType.VIDEOS
    if domain in _CODE_DOMAINS:
        return ContentType.CODE

    return ContentType.NEWS  # Default: assume a news article or blog post


# ── Text-based heuristics (fallback) ──────────────────────────────────────────

_PAPER_RE = re.compile(
    r"\b(?:arxiv|preprint|doi|abstract|methodology|findings|peer.reviewed"
    r"|proceedings|conference paper)\b",
    re.IGNORECASE,
)
_DISCUSSION_RE = re.compile(
    r"\b(?:reddit|thread|discussion|comment|ama|posted|r/|upvote)\b",
    re.IGNORECASE,
)
_VIDEO_RE = re.compile(
    r"\b(?:youtube|video|watch|episode|podcast|lecture|talk)\b",
    re.IGNORECASE,
)
_CODE_RE = re.compile(
    r"\b(?:github|repo|repository|package|library|snippet|npm|pip install)\b",
    re.IGNORECASE,
)


def classify_by_text(title: str, snippet: str) -> ContentType:
    """Classify content using title and snippet heuristics when URL fails.

    Args:
        title: The result title.
        snippet: The result preview/snippet text.

    Returns:
        The inferred ``ContentType``.
    """
    combined = f"{title} {snippet}"

    if _PAPER_RE.search(combined):
        return ContentType.PAPERS
    if _DISCUSSION_RE.search(combined):
        return ContentType.DISCUSSIONS
    if _VIDEO_RE.search(combined):
        return ContentType.VIDEOS
    if _CODE_RE.search(combined):
        return ContentType.CODE

    return ContentType.NEWS


# ── Public interface ───────────────────────────────────────────────────────────


def classify_result(result: object) -> ContentType:
    """Classify a search result into a ``ContentType``.

    Tries URL-based classification first; falls back to title/snippet heuristics.

    Args:
        result: A ``SearchResult`` instance (typed as ``object`` to avoid a
            circular import; expects ``.url``, ``.title``, ``.snippet`` attrs).

    Returns:
        The detected ``ContentType``.
    """
    url: str = getattr(result, "url", "") or ""
    title: str = getattr(result, "title", "") or ""
    snippet: str = getattr(result, "snippet", "") or ""

    content_type = classify_url(url)
    if content_type != ContentType.NEWS:
        # URL matched a specific domain pattern — trust it
        return content_type

    # URL defaulted to NEWS; try text heuristics to see if it's something else
    text_type = classify_by_text(title, snippet)
    return text_type
