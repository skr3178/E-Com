# GeM Tender App

This folder contains the new mobile app stack:

- `backend/` is the FastAPI backend that talks to the GeM API.
- `frontend/` is the React frontend optimized for phones.
- `ios/` is reserved for the Capacitor iOS project opened from Xcode.

## App preview

<img src="./demo.gif" alt="GeM Tender App demo" width="360" />

## Python environment

```bash
conda activate app
```

## Backend

```bash
conda run -n app uvicorn app.main:app --app-dir app/backend --reload
```

## Frontend

```bash
cd app
npm install
npm run dev
```

## iOS / Xcode

```bash
cd app
npx cap add ios
npm run build
npm run ios:sync
npm run ios:open
```

In development, set `VITE_API_BASE_URL=http://127.0.0.1:8000` before running the frontend.
