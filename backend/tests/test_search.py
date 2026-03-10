from __future__ import annotations

from app.search import SearchService
from app.synonyms import build_keyword_plan, expand_terms, suggest_keywords


class FakeClient:
    def __init__(self) -> None:
        self.docs = {
            "sling": [
                {
                    "b_id": "1",
                    "b_bid_number": "GEM/1",
                    "b_category_name": "Wire rope sling for heavy lift",
                    "b_total_quantity": "10",
                    "final_start_date_sort": "2026-03-01T10:00:00Z",
                    "final_end_date_sort": "2099-03-20T10:00:00Z",
                    "ba_official_details_minName": "Ministry of Railways",
                    "ba_official_details_deptName": "Stores",
                }
            ],
            "wire rope sling": [
                {
                    "b_id": "1",
                    "b_bid_number": "GEM/1",
                    "b_category_name": "Wire rope sling for heavy lift",
                    "b_total_quantity": "10",
                    "final_start_date_sort": "2026-03-01T10:00:00Z",
                    "final_end_date_sort": "2099-03-20T10:00:00Z",
                    "ba_official_details_minName": "Ministry of Railways",
                    "ba_official_details_deptName": "Stores",
                },
                {
                    "b_id": "2",
                    "b_bid_number": "GEM/2",
                    "b_category_name": "Webbing sling assembly",
                    "b_total_quantity": "4",
                    "final_start_date_sort": "2026-03-01T10:00:00Z",
                    "final_end_date_sort": "2099-03-18T10:00:00Z",
                    "ba_official_details_minName": "Ministry of Defence",
                    "ba_official_details_deptName": "Procurement",
                },
            ],
            "": [
                {
                    "b_id": "3",
                    "b_bid_number": "GEM/3",
                    "b_category_name": "Anchor shackle set",
                    "b_total_quantity": "3",
                    "final_start_date_sort": "2026-03-01T10:00:00Z",
                    "final_end_date_sort": "2099-03-14T10:00:00Z",
                    "ba_official_details_minName": "Ministry of Ports",
                    "ba_official_details_deptName": "Marine Logistics",
                }
            ],
        }

    def search_keyword(self, keyword: str, max_results: int):
        return self.docs.get(keyword, [])[:max_results]

    @staticmethod
    def _extract(value):
        if isinstance(value, list):
            return value[0] if value else ""
        return str(value or "")

    @staticmethod
    def normalize_doc(doc, *, matched_terms=None, match_score=0.0):
        from app.gem_api import GeMApiClient

        return GeMApiClient.normalize_doc(doc, matched_terms=matched_terms, match_score=match_score)


def test_expand_terms_includes_synonyms():
    terms = expand_terms("sling")
    assert "sling" in terms
    assert "wire rope sling" in terms
    assert "webbing sling" in terms


def test_keyword_plan_suggests_industrial_terms_for_close_word():
    plan = build_keyword_plan("slng")

    assert "sling" in plan.suggested_keywords
    assert "wire rope sling" in plan.expanded_terms


def test_search_deduplicates_and_scores_results():
    service = SearchService(FakeClient())
    response = service.search("sling", limit=10, open_only=True)

    assert response.count == 2
    assert {item.bid_number for item in response.results} == {"GEM/1", "GEM/2"}
    assert all(item.match_score >= 88 for item in response.results)
    assert "sling" in response.expanded_terms
    assert "wire rope sling" in response.suggested_keywords


def test_open_listing_supports_blank_query():
    service = SearchService(FakeClient())
    response = service.list_open_tenders(limit=5)

    assert response.query == ""
    assert response.results[0].bid_number == "GEM/3"
    assert "sling" in response.suggested_keywords


def test_search_supports_multiple_terms_in_one_query():
    service = SearchService(FakeClient())
    response = service.search("wire sling, shackle", limit=10, open_only=True)

    assert "wire sling" in response.expanded_terms
    assert "shackle" in response.suggested_keywords
