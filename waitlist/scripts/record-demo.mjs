// Records the hero's demo: the real app's Lace chat, with Kalev asking for
// accelerators, grants or demo days, Lace working, answering with two
// opportunities, and Kalev saving one. Each cut is captured into .demo-raw/,
// then encode-demo.sh writes public/media/<cut>.mp4 and its poster.
//
// The app is signed in with a stand-in session and every API call is answered
// here, including the reply's event stream, played on a timer: no backend,
// account or real person. The companies and programmes are invented; the faces
// are CC0 avatars from public/people/.
//
// Two cuts: demo.* (4:3, wide screens) and demo-phone.* (3:4, phones).
//
// Run the app first (`bun run dev` in frontend/, on :5173, or set APP), then
// from waitlist/, with Playwright and its Chromium installed:
//   bunx playwright install chromium && bun scripts/record-demo.mjs
// (CHROMIUM sets the browser binary, if Playwright's own isn't the one to use.)
import { execFileSync } from 'node:child_process'
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { chromium } from 'playwright'

const APP = process.env.APP ?? 'http://localhost:5173'
const RAW = new URL('../.demo-raw/', import.meta.url).pathname
const PEOPLE = new URL('../public/people/', import.meta.url).pathname
// supabase-js keeps its session under sb-<project ref>-auth-token.
const ref = readFileSync(new URL('../../frontend/.env', import.meta.url), 'utf8').match(/VITE_SUPABASE_URL=https:\/\/([a-z0-9]+)/)[1]
const SESSION_KEY = `sb-${ref}-auth-token`
const FPS = 30
/** CSS px to leave off the chat's top edge, where the header's border and
 * shade would show as a faint line along the top of the cut. */
const TOP_INSET = 4
/** The two cuts: wide for the hero from sm up, tall for phones. The viewport
 * is sized so the chat, from its top to the input, is the cut's shape. */
const CUTS = [
  { name: 'demo', viewport: { width: 1280, height: 730 }, size: '1200x900', aspect: 4 / 3 },
  { name: 'demo-phone', viewport: { width: 390, height: 713 }, size: '900x1200', aspect: 3 / 4 },
]

// -- The example: who asks, what Lace says, and when (ms after the send). --

const L = 'L1'
const FACES = 'https://faces.example/'
const lace = { id: L, name: 'Lace', website: 'https://thalace.com', startup_name: 'Thalace', status: 'active', pinned: true, role: 'owner', created_at: '2026-10-01T09:00:00Z' }
const kalev = { id: 'u1', name: 'Kalev Mokua', avatar_url: `${FACES}kalev.svg` }
const me = { ...kalev, email: 'kalev@thalace.com', in_pilot: true }
const members = [
  { user_id: 'u1', name: 'Kalev Mokua', email: 'kalev@thalace.com', avatar_url: `${FACES}kalev.svg`, role: 'owner', status: 'active' },
  { user_id: 'u2', name: 'Your cofounder', email: 'cofounder@thalace.com', avatar_url: `${FACES}cofounder.svg`, role: 'admin', status: 'active' },
]
const ASK = 'Any accelerators, grants or demo days we could apply to this quarter?'
const REPLY = "Two open calls fit Thalace right now. **A fintech accelerator's spring cohort** closes on November 28, and **an innovation grant** funds seed-stage teams in Kenya with no equity. Save the ones worth a shot."
const opportunity = (id, title, subtitle, body) => ({ type: 'card', kind: 'opportunity', id, title, subtitle, body, url: null })
const answered = [
  { role: 'founder', content: ASK, author: kalev },
  { role: 'lace', content: REPLY, ui: [
    opportunity('O1', 'Fintech accelerator, spring cohort', 'Accelerator · Nairobi · closes Nov 28', 'Fits: seed-stage B2B tools for founders, which is what you sell'),
    opportunity('O2', 'Innovation grant for seed-stage startups', 'Grant · Kenya · up to $25,000', 'Fits: no equity, open to software startups at your stage'),
    { type: 'suggestions', options: ['Draft the accelerator application', 'Tell me more about the demo day', 'Look for grants in Rwanda too'] },
  ] },
]
const STEPS = [
  [300, 'Reading what Thalace sells'],
  [1400, 'Searching accelerators and grants in Kenya'],
  [2600, 'Checking deadlines and who can apply'],
]
const REPLY_FROM_MS = 3800
const TOKEN_EVERY_MS = 28
const TOKEN_CHARS = 4
/** The run's frames, as the app's event stream would carry them. */
function runFrames() {
  const frames = STEPS.map(([at, text]) => ({ at, frame: { type: 'step', text } }))
  // A bold phrase arrives whole: streamed in parts, its ** would show bare.
  const tokens = REPLY.split(/(\*\*[^*]+\*\*)/).flatMap((part) => part.startsWith('**')
    ? [part] : part.match(new RegExp(`[\\s\\S]{1,${TOKEN_CHARS}}`, 'g')) ?? [])
  tokens.forEach((text, i) => frames.push({ at: REPLY_FROM_MS + i * TOKEN_EVERY_MS, frame: { type: 'token', text } }))
  const end = frames[frames.length - 1].at + 600
  frames.push({ at: end, frame: { type: 'complete' } })
  return frames.map((f, i) => ({ at: f.at, frame: { event_id: i + 1, run_id: 'R1', ...f.frame } }))
}

// -- The stand-in backend. --

let sent = false
function answer(method, path) {
  if (path === '/api/v1/users/me') return me
  if (path === '/api/v1/laces') return [{ ...lace, mood: null, last_active_at: '2026-10-30T09:00:00Z' }]
  if (path === `/api/v1/laces/${L}`) return lace
  if (path.startsWith(`/api/v1/laces/${L}/members`)) return members
  if (path.startsWith(`/api/v1/laces/${L}/messages`)) {
    if (method === 'POST') {
      sent = true
      return { run_id: 'R1', queued: false }
    }
    return sent && !path.includes('mine') ? answered : []
  }
  if (path.includes('/briefs/latest')) return null
  if (method === 'PATCH') return {}
  return []
}

// In the page: the reply's event stream, played on a timer, and a cursor (a
// browser capture has none).
function inPage({ key, frames, kalevFace }) {
  const t = Math.floor(Date.now() / 1000) + 31536000
  const user = { id: 'u1', email: 'kalev@thalace.com', aud: 'authenticated', role: 'authenticated', app_metadata: {},
    user_metadata: { full_name: 'Kalev Mokua', avatar_url: kalevFace }, created_at: '2026-10-01T00:00:00Z' }
  localStorage.setItem('vite-ui-theme', 'light')
  localStorage.setItem(key, JSON.stringify({ access_token: 'x.y.z', token_type: 'bearer', expires_in: 31536000, expires_at: t, refresh_token: 'r', user }))

  const realFetch = window.fetch.bind(window)
  window.fetch = (input, init) => {
    const url = typeof input === 'string' ? input : input.url
    if (!url.includes('/api/v1/runs/R1/events')) return realFetch(input, init)
    const encoder = new TextEncoder()
    const body = new ReadableStream({
      start(controller) {
        for (const { at, frame } of frames) {
          setTimeout(() => {
            controller.enqueue(encoder.encode(JSON.stringify(frame) + '\n'))
            if (frame.type === 'complete') controller.close()
          }, at)
        }
      },
    })
    return Promise.resolve(new Response(body, { status: 200, headers: { 'content-type': 'application/x-ndjson' } }))
  }

  addEventListener('DOMContentLoaded', () => {
    const cursor = document.createElement('div')
    cursor.style.cssText = 'position:fixed;left:0;top:0;width:22px;height:22px;z-index:2147483647;pointer-events:none;'
      + 'transform:translate(-100px,-100px);transition:transform 40ms linear'
    cursor.innerHTML = '<svg viewBox="0 0 24 24" width="22" height="22"><path d="M4 2l15 9-6.5 1.5L10 19z" fill="#121212" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/></svg>'
    document.body.append(cursor)
    addEventListener('mousemove', (e) => { cursor.style.transform = `translate(${e.clientX - 3}px, ${e.clientY - 2}px)` }, true)
    // "Latest" shows whenever the chat isn't scrolled to its end; it's noise here.
    new MutationObserver(() => {
      for (const b of document.querySelectorAll('button')) if (/Latest$/.test(b.textContent ?? '')) b.style.display = 'none'
    }).observe(document.body, { childList: true, subtree: true })
  })
}

// -- Record. --

/** Plays the story in the app and captures it; returns the frames and the
 * region to keep (CSS px): from the top of the chat to just under the input. */
async function capture(browser, viewport) {
  sent = false
  const page = await browser.newPage({ viewport, deviceScaleFactor: 2 })
  await page.addInitScript(inPage, { key: SESSION_KEY, frames: runFrames(), kalevFace: `${FACES}kalev.svg` })
  await page.route('**/auth/v1/**', (r) => r.fulfill({ json: {} }))
  await page.route(`${FACES}*`, (r) => r.fulfill({ path: PEOPLE + new URL(r.request().url()).pathname.slice(1) }))
  await page.route('**/api/v1/**', (r) => {
    const u = new URL(r.request().url())
    r.fulfill({ json: answer(r.request().method(), u.pathname + u.search) })
  })

  await page.goto(`${APP}/lace/${L}`)
  await page.waitForTimeout(2500)
  await page.locator('[aria-label^="Chat with Lace"]:visible').first().click()
  await page.waitForTimeout(1500)
  const input = page.locator('textarea').first()
  const box = await input.boundingBox()
  await page.mouse.move(box.x + box.width * 0.6, box.y - 140)

  const cdp = await page.context().newCDPSession(page)
  const shots = []
  cdp.on('Page.screencastFrame', async ({ data, metadata, sessionId }) => {
    shots.push({ at: metadata.timestamp, data })
    await cdp.send('Page.screencastFrameAck', { sessionId }).catch(() => {})
  })
  // The screencast sends CSS pixels whatever is asked; encode-demo.sh scales.
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 95, everyNthFrame: 1 })

  const marks = {}
  const mark = (name) => { marks[name] = Date.now() / 1000 }
  await page.waitForTimeout(900)
  mark('asks')
  await page.mouse.move(box.x + 60, box.y + box.height / 2, { steps: 18 })
  await input.click()
  await page.keyboard.type(ASK, { delay: 38 })
  await page.waitForTimeout(350)
  await page.keyboard.press('Enter')
  mark('works')
  marks.answers = marks.works + REPLY_FROM_MS / 1000
  await page.waitForTimeout(runFrames().at(-1).at + 1400)
  const save = page.getByRole('button', { name: 'Save' }).first()
  const target = await save.boundingBox()
  await page.mouse.move(target.x + target.width / 2, target.y + target.height / 2, { steps: 24 })
  await page.waitForTimeout(250)
  mark('saves')
  await save.click()
  await page.waitForTimeout(2600)

  const region = await page.evaluate(() => {
    const column = document.querySelector('div.mx-auto.max-w-3xl').getBoundingClientRect()
    const scroller = document.querySelector('div.mx-auto.max-w-3xl').closest('.overflow-y-auto').getBoundingClientRect()
    // Down to the Lace's tab bar on phones, else the window's bottom.
    const bar = [...document.querySelectorAll('nav')].map((n) => n.getBoundingClientRect())
      .find((r) => r.height > 0 && r.top > innerHeight / 2)
    return { cx: column.left + column.width / 2, top: scroller.top, bottom: bar ? bar.top : innerHeight }
  })
  await cdp.send('Page.stopScreencast')
  await page.close()
  // Seconds into the clip, on the screencast's own clock (epoch seconds).
  const at = Object.fromEntries(Object.entries(marks).map(([k, t]) => [k, Number((t - shots[0].at).toFixed(1))]))
  return { shots, region, at }
}

/** Frames to a clip, each held until the next. */
function toClip(shots, dir) {
  mkdirSync(`${dir}frames`, { recursive: true })
  const list = []
  shots.forEach((shot, i) => {
    const file = `${dir}frames/${String(i).padStart(5, '0')}.jpg`
    writeFileSync(file, Buffer.from(shot.data, 'base64'))
    const next = shots[i + 1]?.at ?? shot.at + 0.5
    list.push(`file '${file}'`, `duration ${(next - shot.at).toFixed(4)}`)
  })
  list.push(`file '${dir}frames/${String(shots.length - 1).padStart(5, '0')}.jpg'`)
  writeFileSync(`${dir}frames.txt`, list.join('\n') + '\n')
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', `${dir}frames.txt`,
    '-vf', `fps=${FPS},scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p`, '-c:v', 'libx264', '-crf', '12', `${dir}raw.mp4`])
  return `${dir}raw.mp4`
}

const probe = (file, entry) => Number(execFileSync('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-show_entries', entry,
  '-of', 'csv=p=0', file]).toString())

rmSync(RAW, { recursive: true, force: true })
const browser = await chromium.launch(process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {})
for (const cut of CUTS) {
  const { shots, region, at } = await capture(browser, cut.viewport)
  const raw = toClip(shots, `${RAW}${cut.name}/`)
  // The frames' own scale: the screencast sends CSS pixels.
  const frameWidth = probe(raw, 'stream=width')
  const k = frameWidth / cut.viewport.width
  const height = Math.round((region.bottom - region.top - TOP_INSET) * k)
  const width = Math.min(frameWidth, Math.round(height * cut.aspect))
  // Too narrow for the shape (phones): keep the full width and the bottom of the region.
  const keptHeight = Math.round(width / cut.aspect)
  const x = Math.min(frameWidth - width, Math.max(0, Math.round(region.cx * k - width / 2)))
  const y = Math.round(region.bottom * k) - keptHeight
  const seconds = probe(raw, 'format=duration')
  execFileSync(new URL('./encode-demo.sh', import.meta.url).pathname, [raw, '--crop', `${width}:${keptHeight}:${x}:${y}`,
    '--poster', (seconds - 0.4).toFixed(2), '--size', cut.size, '--name', cut.name], { stdio: 'inherit' })
  console.log(`${cut.name}: ${shots.length} frames, ${seconds.toFixed(1)}s, crop ${width}x${keptHeight}+${x}+${y}`)
  console.log(`  caption times (demo-video.ts): ${JSON.stringify(at)}`)
}
await browser.close()
