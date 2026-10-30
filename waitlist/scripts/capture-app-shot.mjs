// Writes public/shots/lace-chat.jpg and lace-chat-phone.jpg: the hero's
// screenshot of the real app, a Lace's team chat, filled with invented example
// data: the companies and programmes are made up; the founder is Kalev Mokua,
// with CC0 avatars from public/people/.
//
// Run the app first (`bun run dev` in frontend/, on :5173, or set APP), then
// from waitlist/, with Playwright and its Chromium installed:
//   bunx playwright install chromium && bun scripts/capture-app-shot.mjs
// The app is signed in with a stand-in session and every API call is answered
// here, so no backend or account is needed.
import { readFileSync } from 'node:fs'
import { chromium } from 'playwright'

const APP = process.env.APP ?? 'http://localhost:5173'
const OUT = new URL('../public/shots', import.meta.url).pathname
// supabase-js keeps its session under sb-<project ref>-auth-token.
const ref = readFileSync(new URL('../../frontend/.env', import.meta.url), 'utf8').match(/VITE_SUPABASE_URL=https:\/\/([a-z0-9]+)/)[1]
const SESSION_KEY = `sb-${ref}-auth-token`

const L = "L1"
const now = "2026-10-30T09:00:00Z"
const lace = { id: L, name: "Lace", website: "https://thalace.com", startup_name: "Thalace", status: "active", pinned: true, role: "owner", created_at: "2026-10-01T09:00:00Z" }
// Served from the waitlist's public/people/ (the routes below answer these URLs).
const FACES = "https://faces.example/"
const me = { id: "u1", name: "Kalev Mokua", email: "kalev@thalace.com", avatar_url: `${FACES}kalev.svg`, in_pilot: true }
const members = [
  { user_id: "u1", name: "Kalev Mokua", email: "kalev@thalace.com", avatar_url: `${FACES}kalev.svg`, role: "owner", status: "active" },
  { user_id: "u2", name: "Your cofounder", email: "cofounder@thalace.com", avatar_url: `${FACES}cofounder.svg`, role: "admin", status: "active" },
]
const opportunity = (id, title, subtitle, body) => ({ type: "card", kind: "opportunity", id, title, subtitle, body, url: null })
const messages = [
  { role: "founder", content: "Any accelerators, grants or demo days we could apply to this quarter?",
    author: { id: "u1", name: "Kalev Mokua", avatar_url: `${FACES}kalev.svg` } },
  { role: "lace", content: "Two open calls fit Thalace right now, both with room for a seed-stage team selling to startups.\n\n**A fintech accelerator's spring cohort** takes B2B tools for early-stage founders, and applications close on November 28. **An innovation grant for seed-stage startups** funds up to $25,000 with no equity, for teams in Kenya.\n\nThere's also a demo day in Nairobi with pitch slots left. Save the ones worth a shot and I'll draft the applications.",
    ui: [
      opportunity("O1", "Fintech accelerator, spring cohort", "Accelerator · Nairobi · closes Nov 28", "Fits: seed-stage B2B tools for founders, which is what you sell"),
      opportunity("O2", "Innovation grant for seed-stage startups", "Grant · Kenya · up to $25,000", "Fits: no equity, open to software startups at your stage"),
      { type: "suggestions", options: ["Draft the accelerator application", "Tell me more about the demo day", "Look for grants in Rwanda too"] },
    ] },
]
const body = (path) => {
  if (path === "/api/v1/users/me") return me
  if (path === "/api/v1/laces") return [{ ...lace, mood: null, last_active_at: now }]
  if (path === `/api/v1/laces/${L}`) return lace
  if (path.startsWith(`/api/v1/laces/${L}/members`)) return members
  if (path.startsWith(`/api/v1/laces/${L}/messages`)) return path.includes("mine") ? [] : messages
  if (path.includes("/briefs/latest")) return null
  return []
}
const b = await chromium.launch()
for (const [n, vp] of [["desk", { width: 1280, height: 860 }], ["phone", { width: 430, height: 900 }]]) {
  const p = await b.newPage({ viewport: vp, deviceScaleFactor: 2 })
  await p.addInitScript((key) => {
    const t = Math.floor(Date.now() / 1000) + 3600 * 24 * 365
    const user = { id: "u1", email: "you@thalace.com", aud: "authenticated", role: "authenticated", app_metadata: {}, user_metadata: { full_name: "You" }, created_at: "2026-10-01T00:00:00Z" }
    localStorage.setItem("vite-ui-theme", "light")
    localStorage.setItem(key, JSON.stringify({ access_token: "x.y.z", token_type: "bearer", expires_in: 31536000, expires_at: t, refresh_token: "r", user }))
  }, SESSION_KEY)
  await p.route("**/auth/v1/**", (r) => r.fulfill({ json: {} }))
  await p.route(`${FACES}*`, (r) => r.fulfill({ path: new URL(`../public/people/${new URL(r.request().url()).pathname.slice(1)}`, import.meta.url).pathname }))
  await p.route("**/api/v1/**", (r) => {
    const u = new URL(r.request().url()); const path = u.pathname + u.search
    r.fulfill({ json: body(path) })
  })
  await p.goto(`${APP}/lace/${L}`); await p.waitForTimeout(2500)
  await p.locator('[aria-label^="Chat with Lace"]:visible').first().click()
  await p.waitForTimeout(2500)
  // Start of the conversation, not its end.
  await p.evaluate(() => document.querySelectorAll(".overflow-y-auto").forEach((el) => { el.scrollTop = 0 }))
  await p.waitForTimeout(600)
  // The "Latest" button only shows because we scrolled to the start.
  await p.addStyleTag({ content: '[aria-label="Go to latest"]{display:none!important}' })
  const box = await p.locator("div.mx-auto.max-w-3xl").first().boundingBox()
  const pad = n === "desk" ? 24 : 0
  const width = box.width + pad * 2
  const clip = { x: box.x - pad, y: box.y, width, height: Math.round(width * (n === "desk" ? 0.75 : 1.22)) }
  await p.screenshot({ path: `${OUT}/lace-chat${n === "desk" ? "" : "-phone"}.jpg`, type: "jpeg", quality: 88, clip })
  await p.close()
}

await b.close()
