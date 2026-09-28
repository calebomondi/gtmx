# WS `connect timed out: ws://localhost:5173/api/v1/discover` — diagnosis & plan

## Diagnosis (verified, no code changes yet)

The reported error is a **transient restart-window collision**, not a config bug:

| Event | Time |
|---|---|
| Vite dev server auto-restarted (triggered by the `.env` edit from the CORS fix) | **17:19:08** (pid 153771) |
| Backend uvicorn restarted (running with `--reload`) | **17:19:29** (pid 154070) |
| User's failed `/new` submit | ~17:19–17:20 |

During the uvicorn `--reload` respawn the master keeps the listening socket open but the worker isn't serving yet → the Vite proxy forwards the WS upgrade to `:8000` and gets **no response** → the client's 15s `DEFAULT_TIMEOUT_MS` (`src/lib/api.ts:189`) fires → `connect timed out`.

Evidence everything works **right now**:
- `curl` WS handshake via `localhost:5173` → `101 Switching Protocols` (proxied, uvicorn headers)
- 3× real WebSocket clients via `ws://localhost:5173/api/v1/discover` → open in 0.01–0.08s (no payload sent, no workspace created)
- Direct `ws://127.0.0.1:8000/...` → open OK
- REST via proxy `GET /api/v1/users/me` → 200

## Plan

1. **Retry the `/new` create-workspace flow now** (refresh the page first). Expected to succeed — both servers are stable and the proxy path is proven end-to-end.
2. **If it still reproduces**, apply the small hardening set (all low-risk):
   - `vite.config.ts`: proxy `target` `http://localhost:8000` → `http://127.0.0.1:8000` (removes `localhost`/IPv6 resolution ambiguity on the proxy's outbound hop).
   - `src/lib/api.ts`: `DEFAULT_TIMEOUT_MS` `15_000` → `30_000` (backend `--reload` respawns can take a few seconds; 15s also races slow first-boot work).
   - Optional UX: on `connect timed out`, show a "Retry" action instead of a bare error.
3. **Ops note** (no code): when `npm run dev` picks up `.env` changes and/or uvicorn `--reload` fires, wait for both processes to be up before submitting the form.

## Verification (after any hardening, if needed)
- `npx tsc -p tsconfig.app.json --noEmit` → 0; `npm run lint` → 0; `npx vite build` → 0
- WS handshake via `localhost:5173` still `101`; browser `/new` submit reaches `workspace_created` frame
