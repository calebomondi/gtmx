# Thalace waitlist page (thalace.com)

The public landing page: Lace, the startup's own assistant, what it does, and a
two-step signup (email, then optional details and a pilot opt-in). It talks only to the Thalace API under
`/api/v1/waitlist`; signups appear in the admin dashboard's Waitlist page.

```bash
bun install
bun run dev      # Vite on :5174, proxies /api to the backend on :8000
bun run build    # tsc -b && vite build -> dist/
bun run lint     # oxlint
```

- `src/components/`: the page's sections (hero, what your Lace does, how it works, worldwide, pilot, FAQ, closing). `lace-mascot.tsx` is a copy of the app's mascot: change both together.
- `src/features/signup/`: the signup flow.
- `src/lib/api.ts`: the typed API client; types mirror `backend/app/schemas/waitlist.py`.

In production nginx serves `dist/` at thalace.com and proxies `/api` to the same
backend as the app (see `deploy/`).

## The hero's product recording

Until a recording is published, the hero acts out a labelled example with an
invented Lace (`lace-preview.tsx`). To show the real product instead:

1. **Record** (~20 s once edited, no audio) at 1440×900, browser zoom 110–125%,
   light theme. Storyboard: name a Lace and paste the website on `/new` → the
   mascot printing while it reads the site → confirm what it learned → ask it in
   chat for customers, then an opportunity → a draft in Messaging, brainstorm it
   shorter, and **Send** (hold on it). Blur any real contact names or emails you
   can't publish.
2. **Encode**: `scripts/encode-demo.sh raw.mp4 --start 2 --end 24 --crop W:H:X:Y --poster 1`
   writes `public/media/demo.mp4`, `demo.webm` and `demo-poster.webp` (1200×900).
   Aim for under ~2 MB per video.
3. **Publish**: fill in `DEMO_VIDEO` in `src/components/demo-video.ts` (the subject,
   the three paths under `/media/`, and captions timed in seconds to the clip).

The player (`product-demo.tsx`) shows the poster first, loads the video after the
page, plays only while on screen, and has a pause button. With reduced motion or
data saver it waits for a click.
