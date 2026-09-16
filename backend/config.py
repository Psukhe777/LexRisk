"""
backend/config.py — environment-only configuration.

Rules for this layer:
- No Streamlit anywhere in this layer, and no Streamlit secrets store.
- Every value comes from an environment variable.
"""

import os
from dataclasses import dataclass, field


def _csv(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


@dataclass
class Settings:
    app_name: str = "LexRisk API"
    api_version: str = "v1"
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))

    database_url: str | None = field(default_factory=lambda: os.getenv("DATABASE_URL"))

    groq_api_key: str | None = field(default_factory=lambda: os.getenv("GROQ_API_KEY"))
    openai_api_key: str | None = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))

    # PWA client origins allowed to call this API.
    cors_origins: list[str] = field(default_factory=lambda: _csv("CORS_ORIGINS", "*"))

    enable_nlp_filter: bool = field(
        default_factory=lambda: os.getenv("ENABLE_NLP_FILTER", "true").lower() == "true"
    )

    @property
    def api_prefix(self) -> str:
        return f"/api/{self.api_version}"

    @property
    def has_llm_key(self) -> bool:
        return bool(self.groq_api_key or self.openai_api_key)


_settings: Settings | None = None


def get_settings() -> Settings:
    """Cached settings accessor (FastAPI dependency friendly)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
