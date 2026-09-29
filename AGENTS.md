# GTMX — Base44 Development Notes

## Architecture

Fullstack app: **FastAPI backend** (uvicorn) + **Vite/React frontend** (bun).

- **Single-origin wiring**: only port 3000 (Vite dev server) is public. The
  frontend proxies `/api` — including the discovery WebSocket — to the backend
  on the internal docker network. No CORS needed.
- **Backend** uses SQLite (`blog.db`) in development — no external database.
  The LangGraph agent checkpointer shares the same SQLite file (WAL mode).
- The agent compiles at **boot** without any API keys; keys are only needed
  when a discovery **run** executes (LLM + web search calls).

## Running

```
docker compose -f docker-compose.base44.yml up -d
```

- Frontend: `oven/bun:1` — `bun install --frozen-lockfile && bun run dev`
  (port 5173 → host 3000). The project's canonical lockfile is `bun.lock`;
  `package-lock.json` is stale and `npm ci` will fail.
- Backend: `python:3.12-slim` + uv — `uv sync --frozen-lockfile && uv run
  uvicorn ...` (port 8000, internal only). Live reload scoped to Python
  source dirs via `--reload-dir`.
- `vite.config.ts` reads `API_PROXY_TARGET` for the proxy target (defaults to
  `http://localhost:8000` for non-docker local dev).

## Quirks

- **SQLite busy timeout**: the app engine and the agent checkpointer both open
  `blog.db`. Without a busy timeout, concurrent access causes "database is
  locked". `connect.py` sets `timeout=30` to handle this.
- **Auth is faked**: a mock user (`kalebmokua@gmail.com`) is seeded at startup
  and used for all workspace ownership.
- `config.py` (repo root) is not watched by `--reload-dir` — restart the
  backend manually after editing it.

## External Credentials (not needed to boot)

The agent discovery feature needs these to actually run:

| Key | Purpose | Where to get it |
|-----|---------|-----------------|
| `DASHSCOPE_API_KEY` | Qwen LLM (primary provider) | https://dashscope.console.aliyun.com/ |
| `EXA_API_KEY` | Web scraping for research | https://dashboard.exa.ai/ |
| `TAVILY_API_KEY` | Web search for market research | https://tavily.com/ |
| `OPENAI_API_KEY` | OpenRouter (optional, Qwen is default) | https://openrouter.ai/ |

## Verifying

- Backend health: `docker compose exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read().decode())"`
- Frontend: `curl http://localhost:3000/` should return the Vite dev HTML.
- API proxy: `curl http://localhost:3000/api/v1/users/me` returns the mock user.
