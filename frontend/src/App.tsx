import { App as CapacitorApp } from "@capacitor/app";
import { useDeferredValue, useEffect, useMemo, useState, startTransition } from "react";

import { API_BASE_URL, fetchOpenTenders, fetchTenderDetail, searchTenders } from "./api";
import {
  ensureNotificationPermission,
  registerNotificationTapListener,
  syncTenderNotifications,
} from "./notifications";
import {
  loadLastResults,
  loadRecentSearches,
  loadWatchlist,
  saveLastResults,
  saveRecentSearch,
  saveWatchlist,
} from "./storage";
import type { NotificationStatus, TenderDetail, TenderResult } from "./types";

type Tab = "search" | "watchlist" | "settings";

function normalizeTerm(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, " ");
}

function splitSearchTerms(value: string): string[] {
  return value
    .split(/[,;/|+\n]+/)
    .map((item) => normalizeTerm(item))
    .filter(Boolean);
}

function uniqueTerms(values: string[]): string[] {
  const seen = new Set<string>();
  const next: string[] = [];
  for (const value of values) {
    const normalized = normalizeTerm(value);
    if (!normalized || seen.has(normalized)) {
      continue;
    }
    seen.add(normalized);
    next.push(normalized);
  }
  return next;
}

function buildSearchText(query: string, selectedKeywords: string[]): string {
  return uniqueTerms([query, ...selectedKeywords]).join(", ");
}

function formatCloseLabel(hours: number | null): string {
  if (hours == null) {
    return "Close time unavailable";
  }
  if (hours < 0) {
    return "Closed";
  }
  if (hours < 24) {
    return `${Math.round(hours)}h left`;
  }
  return `${Math.round(hours / 24)}d left`;
}

function isClosingSoon(hours: number | null): boolean {
  return hours !== null && hours > 0 && hours <= 24;
}

export default function App() {
  const [tab, setTab] = useState<Tab>("search");
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const [results, setResults] = useState<TenderResult[]>([]);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);
  const [watchlist, setWatchlist] = useState<TenderResult[]>([]);
  const [expandedTerms, setExpandedTerms] = useState<string[]>([]);
  const [suggestedKeywords, setSuggestedKeywords] = useState<string[]>([]);
  const [selectedKeywords, setSelectedKeywords] = useState<string[]>([]);
  const [selectedTender, setSelectedTender] = useState<TenderDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notificationStatus, setNotificationStatus] =
    useState<NotificationStatus>("unknown");

  const watchedBidIds = useMemo(
    () => new Set(watchlist.map((tender) => tender.bidId)),
    [watchlist],
  );
  const queryTerms = useMemo(() => splitSearchTerms(query), [query]);
  const activeKeywordSet = useMemo(
    () => new Set(uniqueTerms([...queryTerms, ...selectedKeywords])),
    [queryTerms, selectedKeywords],
  );

  useEffect(() => {
    async function hydrate() {
      const [savedWatchlist, searches, cachedResults] = await Promise.all([
        loadWatchlist(),
        loadRecentSearches(),
        loadLastResults(),
      ]);
      setWatchlist(savedWatchlist);
      setRecentSearches(searches);
      setResults(cachedResults);
    }

    hydrate().catch((reason) => {
      setError(reason instanceof Error ? reason.message : "Failed to restore app state.");
    });
  }, []);

  useEffect(() => {
    async function bootstrap() {
      if (results.length) {
        return;
      }
      setLoading(true);
      try {
        const response = await fetchOpenTenders();
        startTransition(() => {
          setResults(response.results);
          setExpandedTerms(response.expandedTerms);
          setSuggestedKeywords(response.suggestedKeywords);
        });
        await saveLastResults(response.results);
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "Failed to load open tenders.");
      } finally {
        setLoading(false);
      }
    }

    bootstrap().catch(() => {
      setError("Failed to load open tenders.");
    });
  }, [results.length]);

  useEffect(() => {
    let dispose = () => {};
    registerNotificationTapListener((bidId) => {
      const tender = watchlist.find((item) => item.bidId === bidId) || results.find((item) => item.bidId === bidId);
      if (tender) {
        openTender(tender);
        setTab("watchlist");
      }
    }).then((cleanup) => {
      dispose = cleanup;
    });

    const appState = CapacitorApp.addListener("appStateChange", ({ isActive }) => {
      if (isActive) {
        syncTenderNotifications(watchlist).catch(() => undefined);
      }
    });

    return () => {
      dispose();
      appState.then((listener) => listener.remove());
    };
  }, [results, watchlist]);

  async function runSearch(searchValue: string, keywordValues: string[] = selectedKeywords) {
    const combinedSearch = buildSearchText(searchValue, keywordValues);
    setLoading(true);
    setError(null);
    try {
      const response = combinedSearch
        ? await searchTenders(combinedSearch)
        : await fetchOpenTenders();
      startTransition(() => {
        setResults(response.results);
        setExpandedTerms(response.expandedTerms);
        setSuggestedKeywords(response.suggestedKeywords);
      });
      await saveLastResults(response.results);
      if (combinedSearch) {
        const saved = await saveRecentSearch(combinedSearch);
        setRecentSearches(saved);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Search failed.");
    } finally {
      setLoading(false);
    }
  }

  async function openTender(tender: TenderResult) {
    setSelectedTender(null);
    setDetailLoading(true);
    try {
      const detail = await fetchTenderDetail(tender.bidId);
      setSelectedTender(detail);
    } catch {
      setSelectedTender({
        ...tender,
        fetchedAt: new Date().toISOString(),
        rawFields: {},
      });
    } finally {
      setDetailLoading(false);
    }
  }

  async function toggleWatch(tender: TenderResult) {
    const exists = watchedBidIds.has(tender.bidId);
    const next = exists
      ? watchlist.filter((item) => item.bidId !== tender.bidId)
      : [...watchlist, tender].sort((a, b) => {
          const aHours = a.timeToCloseHours ?? Number.MAX_SAFE_INTEGER;
          const bHours = b.timeToCloseHours ?? Number.MAX_SAFE_INTEGER;
          return aHours - bHours;
        });

    setWatchlist(next);
    await saveWatchlist(next);

    if (!exists) {
      const permission = await ensureNotificationPermission();
      setNotificationStatus(permission);
    }

    await syncTenderNotifications(next);
  }

  async function toggleKeyword(keyword: string) {
    const normalizedKeyword = normalizeTerm(keyword);
    if (!normalizedKeyword || queryTerms.includes(normalizedKeyword)) {
      return;
    }

    const exists = selectedKeywords.some((item) => normalizeTerm(item) === normalizedKeyword);
    const nextKeywords = exists
      ? selectedKeywords.filter((item) => normalizeTerm(item) !== normalizedKeyword)
      : uniqueTerms([...selectedKeywords, keyword]);

    setSelectedKeywords(nextKeywords);
    await runSearch(query, nextKeywords);
  }

  function clearSelectedKeyword(keyword: string) {
    const normalizedKeyword = normalizeTerm(keyword);
    const nextKeywords = selectedKeywords.filter((item) => normalizeTerm(item) !== normalizedKeyword);
    setSelectedKeywords(nextKeywords);
    runSearch(query, nextKeywords).catch(() => undefined);
  }

  const closingSoon = useMemo(
    () => watchlist.filter((tender) => isClosingSoon(tender.timeToCloseHours)),
    [watchlist],
  );

  return (
    <div className="shell">
      <header className="hero">
        <div className="hero-badge">GeM Tender</div>
        <h1>Search open tenders from your phone.</h1>
        <p>
          API-backed GeM tender search with watchlists and device alerts, ready for
          Xcode simulator testing.
        </p>
      </header>

      <main className="content">
        {tab === "search" && (
          <>
            <section className="panel search-panel">
              <label className="field-label" htmlFor="query">
                Keyword
              </label>
              <div className="search-row">
                <input
                  id="query"
                  type="search"
                  placeholder="Try sling, shackle, turnbuckle or multiple words..."
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
                <button onClick={() => runSearch(deferredQuery)}>Search</button>
              </div>
              <div className="keyword-section">
                <p className="section-caption">Recent searches</p>
                <div className="hint-row">
                  {recentSearches.map((term) => (
                    <button
                      key={term}
                      className="chip"
                      onClick={() => {
                        setSelectedKeywords([]);
                        setQuery(term);
                        runSearch(term, []).catch(() => undefined);
                      }}
                    >
                      {term}
                    </button>
                  ))}
                </div>
              </div>
              {selectedKeywords.length > 0 && (
                <div className="keyword-section">
                  <p className="section-caption">Selected industrial keywords</p>
                  <div className="hint-row">
                    {selectedKeywords.map((term) => (
                      <button
                        key={term}
                        className="chip chip-active"
                        onClick={() => clearSelectedKeyword(term)}
                      >
                        {term} ×
                      </button>
                    ))}
                  </div>
                </div>
              )}
              <div className="keyword-section">
                <p className="section-caption">Related industrial keywords</p>
                <div className="hint-row">
                  {suggestedKeywords.map((term) => {
                    const active = activeKeywordSet.has(normalizeTerm(term));
                    return (
                      <button
                        key={term}
                        className={active ? "chip chip-active" : "chip"}
                        onClick={() => toggleKeyword(term)}
                      >
                        {term}
                      </button>
                    );
                  })}
                </div>
              </div>
              {!!expandedTerms.length && (
                <div className="search-summary">
                  <p className="section-caption">Backend search terms</p>
                  <p className="muted">
                    {expandedTerms.filter(Boolean).join(", ")}
                  </p>
                </div>
              )}
            </section>

            {error && <div className="panel error-panel">{error}</div>}

            <section className="results-header">
              <div>
                <h2>{loading ? "Searching..." : "Open tenders"}</h2>
                <p className="muted">{results.length} items loaded</p>
              </div>
              <button className="ghost-button" onClick={() => runSearch(query)}>
                Refresh
              </button>
            </section>

            <section className="results-list">
              {results.map((tender) => (
                <article className="panel tender-card" key={tender.bidId}>
                  <div className="card-topline">
                    <span className="muted">{tender.bidNumber}</span>
                    <span className={isClosingSoon(tender.timeToCloseHours) ? "badge badge-hot" : "badge"}>
                      {formatCloseLabel(tender.timeToCloseHours)}
                    </span>
                  </div>
                  <h3>{tender.category}</h3>
                  <p className="muted">
                    {tender.ministry} · {tender.department}
                  </p>
                  <p className="muted">Quantity: {tender.quantity || "N/A"}</p>
                  <div className="card-actions">
                    <button className="ghost-button" onClick={() => openTender(tender)}>
                      {detailLoading && selectedTender?.bidId === tender.bidId ? "Loading..." : "View"}
                    </button>
                    <button onClick={() => toggleWatch(tender)}>
                      {watchedBidIds.has(tender.bidId) ? "Watching" : "Watch"}
                    </button>
                  </div>
                </article>
              ))}
            </section>
          </>
        )}

        {tab === "watchlist" && (
          <>
            <section className="panel">
              <h2>Watchlist</h2>
              <p className="muted">
                Device alerts: {notificationStatus}. {closingSoon.length} tender(s) closing within 24 hours.
              </p>
            </section>
            <section className="results-list">
              {watchlist.length === 0 && (
                <div className="panel">
                  <h3>No watched tenders yet.</h3>
                  <p className="muted">Save a tender from the search results to schedule alerts.</p>
                </div>
              )}
              {watchlist.map((tender) => (
                <article className="panel tender-card" key={tender.bidId}>
                  <div className="card-topline">
                    <span className="muted">{tender.bidNumber}</span>
                    <span className={isClosingSoon(tender.timeToCloseHours) ? "badge badge-hot" : "badge"}>
                      {formatCloseLabel(tender.timeToCloseHours)}
                    </span>
                  </div>
                  <h3>{tender.category}</h3>
                  <p className="muted">
                    {tender.ministry} · {tender.department}
                  </p>
                  <div className="card-actions">
                    <button className="ghost-button" onClick={() => openTender(tender)}>
                      View
                    </button>
                    <button onClick={() => toggleWatch(tender)}>Remove</button>
                  </div>
                </article>
              ))}
            </section>
          </>
        )}

        {tab === "settings" && (
          <section className="stack">
            <div className="panel">
              <h2>Environment</h2>
              <p className="muted">API base URL: {API_BASE_URL}</p>
              <p className="muted">Xcode 16.4 is available on this machine for simulator testing.</p>
            </div>
            <div className="panel">
              <h2>Later</h2>
              <p className="muted">
                Voice search, billing, and store packaging are intentionally deferred. The current build
                focuses on search, watchlists, and local notifications.
              </p>
            </div>
          </section>
        )}
      </main>

      {selectedTender && (
        <aside className="detail-sheet">
          <div className="detail-sheet__card">
            <div className="card-topline">
              <span className="muted">{selectedTender.bidNumber}</span>
              <button className="ghost-button" onClick={() => setSelectedTender(null)}>
                Close
              </button>
            </div>
            <h2>{selectedTender.category}</h2>
            <p className="muted">
              {selectedTender.ministry} · {selectedTender.department}
            </p>
            <dl className="detail-grid">
              <div>
                <dt>Quantity</dt>
                <dd>{selectedTender.quantity || "N/A"}</dd>
              </div>
              <div>
                <dt>Buyer</dt>
                <dd>{selectedTender.buyer || "N/A"}</dd>
              </div>
              <div>
                <dt>End date</dt>
                <dd>{selectedTender.endDate || "N/A"}</dd>
              </div>
              <div>
                <dt>Contact</dt>
                <dd>{selectedTender.contactEmail || "N/A"}</dd>
              </div>
              <div className="span-2">
                <dt>Address</dt>
                <dd>{selectedTender.address || "N/A"}</dd>
              </div>
            </dl>
            <div className="card-actions">
              <a className="link-button" href={selectedTender.detailUrl} target="_blank" rel="noreferrer">
                Open GeM
              </a>
              <button onClick={() => toggleWatch(selectedTender)}>
                {watchedBidIds.has(selectedTender.bidId) ? "Watching" : "Watch"}
              </button>
            </div>
          </div>
        </aside>
      )}

      <nav className="bottom-nav">
        <button className={tab === "search" ? "active" : ""} onClick={() => setTab("search")}>
          Search
        </button>
        <button className={tab === "watchlist" ? "active" : ""} onClick={() => setTab("watchlist")}>
          Watchlist
        </button>
        <button className={tab === "settings" ? "active" : ""} onClick={() => setTab("settings")}>
          Settings
        </button>
      </nav>
    </div>
  );
}
