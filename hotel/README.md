# DERFED DELICASIES — Base44 dev environment

The hotel site is a standalone Vite + React + Tailwind app in `hotel/`. It does
not talk to the GTMX backend, so it runs on its own.

## Run it

```bash
docker compose -f docker-compose.base44.yml up -d     # http://localhost:3000
docker compose -f docker-compose.base44.yml logs -f hotel
```

The compose file bind-mounts `hotel/` into a Bun container and runs `bun install
--frozen-lockfile` before `vite` starts, so source edits hot-reload without a
rebuild. `node_modules` lives in a named volume, not in the working tree.

## Sandbox overrides

`hotel/vite.config.ts` adds the preview hosts to Vite's `allowedHosts` only when
`BASE44_PREVIEW_MODE === "1"`:

- `3000-$BASE44_PUBLIC_HOST_SUFFIX` — the origin the browser loads the page from
- `.$BASE44_SANDBOX_HOST_DOMAIN` — the rotating sandbox host the proxy forwards

With the flag unset the allowlist stays at `localhost`/`127.0.0.1`, which is the
normal local development behaviour.

## Checks

```bash
docker compose -f docker-compose.base44.yml exec -T hotel bun run build
docker compose -f docker-compose.base44.yml exec -T hotel bun run lint
```

## Imagery

Photography is loaded from Unsplash CDN URLs declared in `hotel/src/lib/content.ts`.
Swap the ids there to re-theme the site.
