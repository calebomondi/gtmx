# GTMX waitlist page (gtmx.co)

The public landing page: what GTMX does, and a two-step signup (email, then
optional details and a pilot opt-in). It talks only to the GTMX API under
`/api/v1/waitlist`; signups appear in the admin dashboard's Waitlist page.

```bash
bun install
bun run dev      # Vite on :5174, proxies /api to the backend on :8000
bun run build    # tsc -b && vite build -> dist/
bun run lint     # oxlint
```

- `src/components/`: the page's sections (hero, example run, what you get, pilot, FAQ).
- `src/features/signup/`: the signup flow.
- `src/lib/api.ts`: the typed API client; types mirror `backend/app/schemas/waitlist.py`.

In production nginx serves `dist/` at gtmx.co and proxies `/api` to the same
backend as the app (see `deploy/`).
