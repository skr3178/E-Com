# GeM Tender Backend

This backend exposes a small FastAPI service for the mobile app. It reuses the GeM API logic from the existing helper scripts and keeps Selenium out of the request path.

## Run

```bash
conda run -n app uvicorn app.main:app --app-dir app/backend --reload
```

## Endpoints

- `GET /api/health`
- `GET /api/tenders/open?limit=20`
- `GET /api/tenders/search?q=sling&limit=20&open_only=true`
- `GET /api/tenders/{bidId}`

## Test

```bash
conda run -n app pytest app/backend/tests -q
```
