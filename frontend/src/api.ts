import type { SearchResponse, TenderDetail } from "./types";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";

async function readJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export function fetchOpenTenders(limit = 20): Promise<SearchResponse> {
  return readJson<SearchResponse>(`/api/tenders/open?limit=${limit}`);
}

export function searchTenders(query: string, limit = 20): Promise<SearchResponse> {
  const searchParams = new URLSearchParams({
    q: query,
    limit: String(limit),
    open_only: "true",
  });
  return readJson<SearchResponse>(`/api/tenders/search?${searchParams.toString()}`);
}

export function fetchTenderDetail(bidId: string): Promise<TenderDetail> {
  return readJson<TenderDetail>(`/api/tenders/${encodeURIComponent(bidId)}`);
}
