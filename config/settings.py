"""Application settings — all configuration loaded from environment variables.

Usage:
    from config.settings import Settings
    settings = Settings()
    settings.validate()   # raises ValueError if ANTHROPIC_API_KEY is missing
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    """Centralised application configuration.

    All values are read from environment variables at instantiation time
    so that tests can override them by patching ``os.environ``.
    """

    # ── API Keys ────────────────────────────────────────────────────────────
    anthropic_api_key: str = field(
        default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", "")
    )

    # ── Flask ───────────────────────────────────────────────────────────────
    debug: bool = field(
        default_factory=lambda: os.environ.get("FLASK_DEBUG", "0") == "1"
    )
    port: int = field(
        default_factory=lambda: int(os.environ.get("PORT", "5001"))
    )

    # ── Search ──────────────────────────────────────────────────────────────
    max_search_results: int = field(
        default_factory=lambda: int(os.environ.get("MAX_SEARCH_RESULTS", "10"))
    )
    max_web_searches: int = field(
        default_factory=lambda: int(os.environ.get("MAX_WEB_SEARCHES", "1"))
    )

    # ── AI Models ───────────────────────────────────────────────────────────
    #: Fast model used for the web-search + research pass.
    research_model: str = "claude-haiku-4-5"
    #: Model used for the summarisation / structuring pass.
    summary_model: str = "claude-haiku-4-5"

    def validate(self) -> None:
        """Raise ``ValueError`` if any required setting is missing."""
        if not self.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Copy .env.example to .env and add your key."
            )
