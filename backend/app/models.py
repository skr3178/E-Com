from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TenderResult(BaseModel):
    bid_id: str = Field(alias="bidId")
    bid_number: str = Field(alias="bidNumber")
    category: str
    quantity: str
    start_date: str = Field(alias="startDate")
    end_date: str = Field(alias="endDate")
    ministry: str
    department: str
    detail_url: str = Field(alias="detailUrl")
    is_open: bool = Field(alias="isOpen")
    time_to_close_hours: float | None = Field(alias="timeToCloseHours", default=None)
    matched_terms: list[str] = Field(alias="matchedTerms", default_factory=list)
    match_score: float = Field(alias="matchScore", default=0.0)


class TenderDetail(TenderResult):
    buyer: str | None = None
    contact_email: str | None = Field(default=None, alias="contactEmail")
    address: str | None = None
    url: str | None = None
    fetched_at: datetime = Field(alias="fetchedAt")
    raw_fields: dict[str, Any] = Field(default_factory=dict, alias="rawFields")


class SearchResponse(BaseModel):
    query: str
    expanded_terms: list[str] = Field(alias="expandedTerms")
    suggested_keywords: list[str] = Field(alias="suggestedKeywords")
    count: int
    results: list[TenderResult]


class HealthResponse(BaseModel):
    status: str
