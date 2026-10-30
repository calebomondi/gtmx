// Writes public/shots/lace-chat.jpg and lace-chat-phone.jpg: the hero's
// screenshot of the real app, a Lace's team chat, filled with invented example
// data (no real company or person).
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
const me = { id: "u1", name: "You", email: "you@thalace.com", avatar_url: null, in_pilot: true }
const members = [
  { user_id: "u1", name: "You", email: "you@thalace.com", avatar_url: null, role: "owner", status: "active" },
  { user_id: "u2", name: "Your cofounder", email: "cofounder@thalace.com", avatar_url: null, role: "admin", status: "active" },
]
const account = (id, name, extra) => ({ id, name, account_type: "company", website: null, geo: "Nairobi, Kenya", summary: null, trigger: null, case: null, status: "suggested", contact_status: null, contacts: [], channels: {}, contacts_checked_at: null, first_seen_at: now, last_seen_at: now, ...extra })
const acme = account("A1", "Acme Pay", { status: "target", contact_status: "person", contacts_checked_at: now,
  contacts: [{ name: "Neema Okafor", title: "Founder & CEO", email: "neema@acmepay.example", linkedin: null }, { name: "Tomás Reyes", title: "COO", email: null, linkedin: null }] })
const globex = account("A2", "Globex Freight")
const messages = [
  { role: "founder", content: "Who just raised and is hiring their first sales lead?", author: { id: "u1", name: "You", avatar_url: null } },
  { role: "lace", content: "Two fit right now, both with a reason to buy this month.\n\n**Acme Pay** raised its seed round in June and is hiring its first head of sales, so lead lists are about to become someone's whole job. **Globex Freight** opened a second office in Mombasa and posted for a sales lead last week.\n\nI saved Acme Pay and found two people there; Globex is waiting for your call.",
    ui: [
      { type: "card", kind: "account", id: "A1", title: "Acme Pay", subtitle: "Fintech · Nairobi", body: "Why now: raised a seed round in June, hiring its first head of sales", url: null },
      { type: "card", kind: "account", id: "A2", title: "Globex Freight", subtitle: "Logistics · Mombasa", body: "Why now: opened a second office, hiring a sales lead", url: null },
      { type: "suggestions", options: ["Draft a message to Acme Pay's founder", "Find people at Globex Freight", "Look for more like these"] },
    ] },
]
const body = (path) => {
  if (path === "/api/v1/users/me") return me
  if (path === "/api/v1/laces") return [{ ...lace, mood: null, last_active_at: now }]
  if (path === `/api/v1/laces/${L}`) return lace
  if (path.startsWith(`/api/v1/laces/${L}/members`)) return members
  if (path.startsWith(`/api/v1/laces/${L}/messages`)) return path.includes("mine") ? [] : messages
  if (path.startsWith(`/api/v1/laces/${L}/accounts`)) return path.includes("suggested") ? [globex] : path.includes("target") ? [acme] : []
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
