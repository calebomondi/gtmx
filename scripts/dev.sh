#!/usr/bin/env bash
#
# Dev backend runner: starts the local Postgres (docker-compose.yml), waits for
# it to be healthy, applies migrations, then runs uvicorn with reload. (The app
# itself refuses to start on an unmigrated database.)
#
# The point of the explicit --reload-dir list: a bare `uvicorn --reload` watches
# the whole CWD, including the frontend tree, and Vite rewrites
# node_modules/.vite and dist/ during normal development. Any of those touches
# was enough to bounce the server -- killing the discovery WebSocket out from
# under a run that is still streaming. Scoping the watcher to the Python source
# dirs makes a reload mean "I edited Python".
#
# Caveat: --reload-dir only takes directories, so a change to the root-level
# config.py is not picked up. Restart manually after editing it.
set -euo pipefail

cd "$(dirname "$0")/.."

docker compose up -d --wait postgres
alembic upgrade head

exec uvicorn backend.app.main:app \
  --reload \
  --host 0.0.0.0 \
  --port 8000 \
  --reload-dir backend \
  --reload-dir agents \
  --reload-dir utils \
  --reload-dir data_sources \
  --reload-dir scripts \
  --reload-dir supabase
