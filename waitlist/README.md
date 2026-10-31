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

## The hero's recording

The hero plays a short recording of the real app (`product-demo.tsx`): Thalace's
own Lace in its team chat, Kalev asking for accelerators, grants or demo days,
Lace working and answering with two opportunities, and one being saved. The
data is invented; the faces (`public/people/`) are Notionists avatars by Zoish
via DiceBear, CC0 1.0.

`scripts/record-demo.mjs` records it from a running frontend, with a stand-in
session and every API call (and the reply's event stream) answered in the
script, then runs `scripts/encode-demo.sh` into `public/media/`. Instructions
are at the top of the script. Captions are in `src/components/demo-video.ts`,
timed to the clip: retime them if the storyboard changes.

The player (`product-demo.tsx`) shows the poster first, loads the video after the
page, plays only while on screen, and has a pause button. With reduced motion or
data saver it waits for a click.
