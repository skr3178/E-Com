from __future__ import annotations

from dataclasses import dataclass
import logging
from time import monotonic

from rapidfuzz import fuzz

from .config import settings
from .gem_api import GeMApiClient
from .models import SearchResponse, TenderResult
from .synonyms import build_keyword_plan, featured_keywords
from .utils import normalize_query, normalize_text

logger = logging.getLogger(__name__)


@dataclass
class CachedSearch:
    response: SearchResponse
    expires_at: float


class SearchService:
    def __init__(self, client: GeMApiClient) -> None:
        self.client = client
        self._cache: dict[tuple[str, int, bool], CachedSearch] = {}

    def list_open_tenders(self, limit: int = 20) -> SearchResponse:
        return self.search("", limit=limit, open_only=True)

    def search(self, query: str, limit: int = 20, open_only: bool = True) -> SearchResponse:
        normalized = normalize_query(query)
        cache_key = (normalized, limit, open_only)
        cached = self._cache.get(cache_key)
        now = monotonic()
        if cached and cached.expires_at > now:
            return cached.response

        keyword_plan = build_keyword_plan(normalized) if normalized else None
        search_terms = keyword_plan.expanded_terms if keyword_plan and keyword_plan.expanded_terms else [""]
        expanded_terms = keyword_plan.expanded_terms if keyword_plan else []
        suggested_keywords = keyword_plan.suggested_keywords if keyword_plan else featured_keywords()
        primary_terms = keyword_plan.primary_terms if keyword_plan else []
        raw_docs_by_bid: dict[str, dict] = {}
        matched_terms_by_bid: dict[str, set[str]] = {}

        per_term_limit = max(limit, settings.max_results_per_term)
        for term in search_terms:
            docs = self.client.search_keyword(term, max_results=per_term_limit)
            logger.info("Fetched %d docs for term %r", len(docs), term)
            for doc in docs:
                bid_number = self.client._extract(doc.get("b_bid_number"))
                if not bid_number:
                    continue
                raw_docs_by_bid.setdefault(bid_number, doc)
                matched_terms_by_bid.setdefault(bid_number, set()).add(term or "open")

        results: list[TenderResult] = []
        for bid_number, doc in raw_docs_by_bid.items():
            matched_terms = sorted(matched_terms_by_bid.get(bid_number, set()))
            match_score = self._score_result(primary_terms, matched_terms, doc)
            result = self.client.normalize_doc(doc, matched_terms=matched_terms, match_score=match_score)
            if open_only and not result.is_open:
                continue
            results.append(result)

        results.sort(
            key=lambda item: (
                -item.match_score,
                item.time_to_close_hours if item.time_to_close_hours is not None else float("inf"),
                item.bid_number,
            )
        )
        response = SearchResponse(
            query=normalized,
            expandedTerms=expanded_terms,
            suggestedKeywords=suggested_keywords,
            count=min(len(results), limit),
            results=results[:limit],
        )
        self._cache[cache_key] = CachedSearch(
            response=response,
            expires_at=now + settings.search_cache_ttl_seconds,
        )
        return response

    def _score_result(self, primary_terms: list[str], matched_terms: list[str], doc: dict) -> float:
        if not primary_terms:
            return 0.0

        category = normalize_text(self.client._extract(doc.get("b_category_name")))
        ministry = normalize_text(self.client._extract(doc.get("ba_official_details_minName")))
        department = normalize_text(self.client._extract(doc.get("ba_official_details_deptName")))
        haystack = " | ".join([category, ministry, department])

        exact_hits = sum(1 for term in primary_terms if term and term in haystack)
        synonym_hits = sum(1 for term in matched_terms if term and term != "open" and term in haystack)

        if exact_hits == len(primary_terms) and exact_hits > 0:
            return float(120 + exact_hits + min(synonym_hits, 5))
        if exact_hits > 0:
            return float(105 + exact_hits * 3 + min(synonym_hits, 5))
        if synonym_hits > 0:
            return float(88 + min(synonym_hits, 10))

        fuzzy_terms = list(dict.fromkeys(primary_terms + [term for term in matched_terms if term not in {"", "open"}]))
        scores = []
        for term in fuzzy_terms:
            scores.extend(
                [
                    fuzz.WRatio(term, category),
                    fuzz.WRatio(term, ministry),
                    fuzz.WRatio(term, department),
                ]
            )
        return float(max(scores))
