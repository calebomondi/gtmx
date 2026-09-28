# Fix CORS error on `/api/v1/users/me` — use the Vite dev proxy

## Root cause
1. `frontend/.env` sets `VITE_API_ORIGIN=http://127.0.0.1:8000` → `apiFetch` (`src/lib/api.ts:339`) and `discoverySocketUrl()` (`src/lib/api.ts:198`) call the backend **directly** at `127.0.0.1:8000`, bypassing the Vite proxy.
2. The backend only installs `CORSMiddleware` when `settings.ALLOWED_ORIGINS` is non-empty (`backend/app/main.py:74`); default is empty → responses carry no `Access-Control-Allow-Origin` → browser blocks the cross-origin request.

Same-origin proxying avoids CORS entirely; `.env.example` documents this as the intended default ("Leave empty to use the SAME origin as the frontend — which is what the dev proxy assumes").

## Change (1 line)
`frontend/.env`:
```
- VITE_API_ORIGIN=http://127.0.0.1:8000
+ VITE_API_ORIGIN=
```

Effect:
- **REST**: `API_BASE = "".trim() ?? ""` → requests go to `http://localhost:5173/api/v1/...` → Vite proxy (`vite.config.ts`, `/api` → `http://localhost:8000`, `ws: true`) → backend. Same-origin, no CORS.
- **Discovery WS**: `discoverySocketUrl()` sees empty origin → falls back to `window.location.origin` → `ws://localhost:5173/api/v1/discover` → Vite WS proxy → backend. Path is under `/api`, so the existing proxy rule covers it.
- Backend config unchanged (`ALLOWED_ORIGINS` stays empty — correct for same-origin dev).

## No other code changes
`vite.config.ts` proxy and backend CORS logic are already correct for this architecture.

## Steps
1. Edit `frontend/.env` → `VITE_API_ORIGIN=` (empty, matches `.env.example`).
2. Restart the frontend dev server (`npm run dev`) — Vite reads `.env` at startup (it usually auto-restarts on `.env` change, but restart to be safe). Backend keeps running on `:8000`.
3. Verify:
   - `curl -s http://localhost:5173/api/v1/users/me` → `200` JSON (proxy path works without browser/CORS).
   - Reload `http://localhost:5173` → no CORS console error; sidebar shows the real user (`/users/me` now same-origin).
   - `/new` submit still reaches the discovery WS at `ws://localhost:5173/api/v1/discover`.

## Fallback (if a split-origin setup is ever needed)
Set backend env `ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173` and keep an absolute `VITE_API_ORIGIN`. Not needed now — both processes are local and the proxy is the documented default.
