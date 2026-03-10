from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
import re
from typing import Any

import requests

from .config import settings
from .models import TenderDetail, TenderResult
from .utils import hours_to_close, is_open_tender, parse_iso_datetime

logger = logging.getLogger(__name__)


class GeMApiClient:
    base_url = "https://bidplus.gem.gov.in"
    all_bids_url = f"{base_url}/all-bids"
    all_bids_data_url = f"{base_url}/all-bids-data"

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "en-US,en;q=0.9",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": self.all_bids_url,
                "Origin": self.base_url,
            }
        )
        self.csrf_token: str | None = None

    def fetch_csrf_token(self, force: bool = False) -> str:
        if self.csrf_token and not force:
            return self.csrf_token

        response = self.session.get(self.all_bids_url, timeout=settings.request_timeout_seconds)
        response.raise_for_status()
        match = re.search(r'id=["\']chash["\']\s+value=["\']([0-9a-fA-F]+)["\']', response.text)
        if not match:
            match = re.search(r'value=["\']([0-9a-fA-F]+)["\']\s+id=["\']chash["\']', response.text)
        if not match:
            raise RuntimeError("Unable to locate GeM CSRF token")

        self.csrf_token = match.group(1)
        return self.csrf_token

    def fetch_page(self, keyword: str, page: int = 1, bid_status: str = "ongoing_bids") -> tuple[list[dict[str, Any]], int]:
        csrf_token = self.fetch_csrf_token()
        payload = {
            "payload": json.dumps(
                {
                    "param": {"searchBid": keyword},
                    "filter": {"bidStatusType": bid_status} if bid_status else {},
                }
            ),
            "page": str(page),
            "csrf_bd_gem_nk": csrf_token,
        }

        response = self.session.post(self.all_bids_data_url, data=payload, timeout=settings.request_timeout_seconds)
        if response.status_code == 403:
            csrf_token = self.fetch_csrf_token(force=True)
            payload["csrf_bd_gem_nk"] = csrf_token
            response = self.session.post(self.all_bids_data_url, data=payload, timeout=settings.request_timeout_seconds)
        response.raise_for_status()
        data = response.json()
        inner = data.get("response", {}).get("response", data.get("response", data))
        return inner.get("docs", []), int(inner.get("numFound", 0))

    def search_keyword(self, keyword: str, max_results: int) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        page = 1
        num_found: int | None = None

        while True:
            docs, total = self.fetch_page(keyword=keyword, page=page)
            if num_found is None:
                num_found = total

            if not docs:
                break

            collected.extend(docs)
            if len(collected) >= max_results:
                break
            if len(collected) >= num_found:
                break

            page += 1

        return collected[:max_results]

    @staticmethod
    def _extract(value: Any) -> str:
        if isinstance(value, list):
            return str(value[0]) if value else ""
        return str(value) if value is not None else ""

    @classmethod
    def extract_bid_id(cls, doc: dict[str, Any]) -> str:
        bid_id = doc.get("b_id", "")
        if isinstance(bid_id, list):
            bid_id = bid_id[0] if bid_id else ""
        return str(bid_id)

    @classmethod
    def normalize_doc(
        cls,
        doc: dict[str, Any],
        *,
        matched_terms: list[str] | None = None,
        match_score: float = 0.0,
    ) -> TenderResult:
        bid_id = cls.extract_bid_id(doc)
        category = doc.get("b_category_name", "")
        if isinstance(category, list):
            category = ", ".join(str(item) for item in category)
        end_date = cls._extract(doc.get("final_end_date_sort"))
        return TenderResult(
            bidId=bid_id,
            bidNumber=cls._extract(doc.get("b_bid_number")),
            category=str(category),
            quantity=cls._extract(doc.get("b_total_quantity")),
            startDate=cls._extract(doc.get("final_start_date_sort")),
            endDate=end_date,
            ministry=cls._extract(doc.get("ba_official_details_minName")),
            department=cls._extract(doc.get("ba_official_details_deptName")),
            detailUrl=f"{cls.base_url}/showbidDocument/{bid_id}" if bid_id else "",
            isOpen=is_open_tender(end_date),
            timeToCloseHours=hours_to_close(end_date),
            matchedTerms=matched_terms or [],
            matchScore=match_score,
        )

    def fetch_detail(self, bid_id: str, result: TenderResult | None = None) -> TenderDetail:
        url = f"{self.base_url}/showbidDocument/{bid_id}"
        response = self.session.get(url, timeout=settings.request_timeout_seconds)
        response.raise_for_status()
        html = response.text

        parsed = {
            "bid_number": _extract_first_group(r'BID NUMBER\s*[:\-]?\s*</[^>]+>\s*([^<]+)', html),
            "ministry": _extract_first_group(r'MINISTRY\s*[:\-]?\s*</[^>]+>\s*([^<]+)', html),
            "department": _extract_first_group(r'DEPARTMENT\s*[:\-]?\s*</[^>]+>\s*([^<]+)', html),
            "category": _extract_first_group(r'CATEGORY\s*[:\-]?\s*</[^>]+>\s*([^<]+)', html),
            "quantity": _extract_first_group(r'QUANTITY\s*[:\-]?\s*</[^>]+>\s*([^<]+)', html),
            "start_date": _extract_first_group(r'START DATE\s*[:\-]?\s*</[^>]+>\s*([^<]+)', html),
            "end_date": _extract_first_group(r'END DATE\s*[:\-]?\s*</[^>]+>\s*([^<]+)', html),
            "buyer": _extract_first_group(r'BUYER\s*[:\-]?\s*</[^>]+>\s*([^<]+)', html),
            "address": _extract_first_group(r'ADDRESS\s*[:\-]?\s*</[^>]+>\s*([^<]+)', html),
            "contact_email": _extract_first_group(r'([\w\.-]+@[\w\.-]+\.\w+)', html),
        }

        base_result = result or TenderResult(
            bidId=bid_id,
            bidNumber=parsed["bid_number"] or bid_id,
            category=parsed["category"] or "",
            quantity=parsed["quantity"] or "",
            startDate=_coerce_datetime_string(parsed["start_date"]),
            endDate=_coerce_datetime_string(parsed["end_date"]),
            ministry=parsed["ministry"] or "",
            department=parsed["department"] or "",
            detailUrl=url,
            isOpen=is_open_tender(_coerce_datetime_string(parsed["end_date"])),
            timeToCloseHours=hours_to_close(_coerce_datetime_string(parsed["end_date"])),
            matchedTerms=[],
            matchScore=0.0,
        )

        return TenderDetail(
            bidId=base_result.bid_id,
            bidNumber=base_result.bid_number,
            category=base_result.category,
            quantity=base_result.quantity,
            startDate=base_result.start_date,
            endDate=base_result.end_date,
            ministry=base_result.ministry,
            department=base_result.department,
            detailUrl=base_result.detail_url,
            isOpen=base_result.is_open,
            timeToCloseHours=base_result.time_to_close_hours,
            matchedTerms=base_result.matched_terms,
            matchScore=base_result.match_score,
            buyer=parsed["buyer"],
            contactEmail=parsed["contact_email"],
            address=parsed["address"],
            url=url,
            fetchedAt=datetime.now(UTC),
            rawFields=parsed,
        )


def _extract_first_group(pattern: str, html: str) -> str | None:
    match = re.search(pattern, html, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def _coerce_datetime_string(value: str | None) -> str:
    if not value:
        return ""
    parsed = parse_iso_datetime(value)
    if parsed:
        return parsed.isoformat()
    return value
