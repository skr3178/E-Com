from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    allowed_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "capacitor://localhost",
        "ionic://localhost",
    )
    request_timeout_seconds: int = int(os.getenv("GEM_REQUEST_TIMEOUT_SECONDS", "30"))
    search_cache_ttl_seconds: int = int(os.getenv("SEARCH_CACHE_TTL_SECONDS", "300"))
    max_results_per_term: int = int(os.getenv("SEARCH_MAX_RESULTS_PER_TERM", "50"))


settings = Settings()
