import { Preferences } from "@capacitor/preferences";

import type { TenderResult } from "./types";

const WATCHLIST_KEY = "gem-watchlist";
const RECENT_SEARCH_KEY = "gem-recent-searches";
const LAST_RESULTS_KEY = "gem-last-results";

async function getItem(key: string): Promise<string | null> {
  try {
    const { value } = await Preferences.get({ key });
    return value;
  } catch {
    return window.localStorage.getItem(key);
  }
}

async function setItem(key: string, value: string): Promise<void> {
  try {
    await Preferences.set({ key, value });
  } catch {
    window.localStorage.setItem(key, value);
  }
}

async function readJson<T>(key: string, fallback: T): Promise<T> {
  const value = await getItem(key);
  if (!value) {
    return fallback;
  }
  try {
    return JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}

async function writeJson(key: string, value: unknown): Promise<void> {
  await setItem(key, JSON.stringify(value));
}

export function loadWatchlist(): Promise<TenderResult[]> {
  return readJson<TenderResult[]>(WATCHLIST_KEY, []);
}

export function saveWatchlist(tenders: TenderResult[]): Promise<void> {
  return writeJson(WATCHLIST_KEY, tenders);
}

export function loadRecentSearches(): Promise<string[]> {
  return readJson<string[]>(RECENT_SEARCH_KEY, []);
}

export async function saveRecentSearch(term: string): Promise<string[]> {
  const current = await loadRecentSearches();
  const next = [term, ...current.filter((item) => item !== term)].slice(0, 8);
  await writeJson(RECENT_SEARCH_KEY, next);
  return next;
}

export function loadLastResults(): Promise<TenderResult[]> {
  return readJson<TenderResult[]>(LAST_RESULTS_KEY, []);
}

export function saveLastResults(tenders: TenderResult[]): Promise<void> {
  return writeJson(LAST_RESULTS_KEY, tenders);
}
