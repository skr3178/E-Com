from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .gem_api import GeMApiClient
from .models import HealthResponse, SearchResponse, TenderDetail
from .search import SearchService

app = FastAPI(title="GeM Tender Backend", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = GeMApiClient()
search_service = SearchService(client)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/api/tenders/open", response_model=SearchResponse)
def list_open_tenders(limit: int = Query(default=20, ge=1, le=100)) -> SearchResponse:
    return search_service.list_open_tenders(limit=limit)


@app.get("/api/tenders/search", response_model=SearchResponse)
def search_tenders(
    q: str = Query(default="", alias="q"),
    limit: int = Query(default=20, ge=1, le=100),
    open_only: bool = Query(default=True, alias="open_only"),
) -> SearchResponse:
    return search_service.search(q, limit=limit, open_only=open_only)


@app.get("/api/tenders/{bid_id}", response_model=TenderDetail)
def get_tender_detail(bid_id: str) -> TenderDetail:
    results = search_service.search("", limit=100, open_only=False)
    existing = next((item for item in results.results if item.bid_id == bid_id), None)
    try:
        return client.fetch_detail(bid_id, result=existing)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch GeM detail for {bid_id}") from exc
