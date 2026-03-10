# GeM Tender iPhone App Plan

## Summary
- Build an iPhone-first mobile app under `app/` using a React/Vite frontend wrapped with Capacitor so it runs in Xcode and the iOS Simulator.
- Add a Python/FastAPI backend that reuses the existing GeM extraction logic from `Scripts/`.
- Use the GeM API request flow from `Scripts/gem_bidplus_scraper.py` as the primary extraction engine, while porting the field/filter behavior from `Scripts/scrape_gem_tenders.py` and using `Scripts/download_bid_details.py` for tender detail enrichment.
- V1 includes keyword search, synonym/fuzzy matching, open tender list, tender detail, watchlist, and on-device notifications before tender closure.
- V1 excludes billing, subscriptions, login, voice search, email alerts, and Android packaging.

## Key Changes
- Create `app/frontend` as a mobile-first React app with these screens: Search, Results, Tender Detail, Watchlist/Alerts, Settings.
- Create `app/backend` as a FastAPI service; do not invoke the scraper scripts as subprocesses in request handling. Refactor their logic into importable services.
- Create `app/ios` as a Capacitor iOS project committed to the repo and runnable in Xcode.

- Backend search behavior:
  - Implement `GET /api/tenders/search?q=&limit=&open_only=true`.
  - Normalize the query by lowercasing, trimming, tokenizing, and removing duplicates.
  - Expand queries with a curated synonym map for GeM/lifting terms such as `sling`, `wire rope sling`, `webbing sling`, `chain sling`, `lifting chain`, `shackle`, `hook`, and `wire rope`.
  - Query the GeM API for the original term plus expansions, merge results, dedupe by `Bid Number`, and return only tenders whose `End Date` is still in the future.
  - Rank results in this order: exact keyword match, synonym match, fuzzy match.
  - Use `rapidfuzz` against category, ministry, and department text.
  - Add a 5-minute in-memory TTL cache per normalized query to reduce GeM rate pressure.

- Backend detail behavior:
  - Implement `GET /api/tenders/{bidId}`.
  - Fetch the GeM bid detail page on demand and merge additional fields into the normalized tender response.

- Frontend behavior:
  - Search screen includes keyword input, recent searches, synonym hint chips, loading state, empty state, and retry state.
  - Results cards show category/title, bid number, ministry, department, quantity, close time countdown, and a watch toggle.
  - Tender detail view shows full metadata, direct GeM link, close time, and watch controls.
  - Watchlist shows all watched tenders sorted by nearest close time, plus “closing soon” grouping.
  - Persist recent searches, watchlist, and last successful results locally with Capacitor Preferences.

- Notification behavior:
  - Use Capacitor Local Notifications only.
  - Ask for notification permission on the first watch action.
  - Schedule two local alerts per watched tender: 24 hours before close and 2 hours before close.
  - On app launch, app foreground, manual refresh, and watchlist edits, re-fetch watched tenders and cancel/reschedule notifications if the close time changed or the tender is no longer open.
  - If permission is denied, keep the watchlist active and show in-app “closing soon” badges plus a permission reminder.

- Xcode/iOS workflow:
  - Sync the web app into Capacitor iOS.
  - Open `app/ios/App/App.xcworkspace` in Xcode and run it in the iPhone Simulator.
  - Use an environment-based API URL; default local simulator target is `http://127.0.0.1:8000`.

## Public Interfaces
- `GET /api/health`
- `GET /api/tenders/search?q={query}&limit={n}&open_only=true`
- `GET /api/tenders/{bidId}`

- Tender response shape:
  - `bidId`
  - `bidNumber`
  - `category`
  - `quantity`
  - `startDate`
  - `endDate`
  - `ministry`
  - `department`
  - `detailUrl`
  - `isOpen`
  - `timeToClose`
  - `matchedTerms`
  - `matchScore`

- Local watchlist item shape:
  - `bidId`
  - `bidNumber`
  - `title`
  - `endDate`
  - `detailUrl`
  - `notify24h`
  - `notify2h`

## Test Plan
- Unit test query normalization, synonym expansion, fuzzy ranking, deduplication, and open/closed filtering.
- API test GeM token fetch and `/all-bids-data` parsing with mocked responses.
- API test tender detail enrichment with mocked bid detail HTML.
- Frontend test search flow, empty/error states, watch/unwatch flow, and persisted recent searches.
- iOS simulator test local notification scheduling, permission-denied fallback, app relaunch resync, and deep linking from notification to tender detail.
- Acceptance checks:
  - Searching `sling` returns open tenders only.
  - Misspelled or close-match terms still return relevant tenders.
  - Watching a tender schedules two device notifications.
  - Closing-soon tenders surface in both results and watchlist.

## Assumptions
- iOS is the first delivery target because the app will be tested in Xcode; Android is deferred.
- The app uses a backend service; the mobile app does not run Selenium directly.
- `scrape_gem_tenders.py` is treated as behavior/reference logic, not the runtime extraction engine.
- No billing, paywall, or user accounts are included in v1.
- Local notifications are sufficient for v1; if GeM changes a tender deadline after a notification is scheduled, the app corrects it on the next refresh/app open rather than through server push.
