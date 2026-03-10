from __future__ import annotations

from datetime import UTC, datetime
import re


def normalize_query(value: str) -> str:
    return " ".join(value.lower().split())


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().lower()


def parse_iso_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def utc_now() -> datetime:
    return datetime.now(UTC)


def hours_to_close(value: str) -> float | None:
    end_date = parse_iso_datetime(value)
    if not end_date:
        return None
    return round((end_date - utc_now()).total_seconds() / 3600, 2)


def is_open_tender(value: str) -> bool:
    end_date = parse_iso_datetime(value)
    if not end_date:
        return True
    return end_date > utc_now()
