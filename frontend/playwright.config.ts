import { defineConfig } from "@playwright/test"

// Release smoke test, run by hand before promoting dev -> main (it starts a
// real, paid discovery run). Needs the API, this app and the admin console
// running; see e2e/smoke.spec.ts for the env it reads.
export default defineConfig({
  testDir: "e2e",
  timeout: 25 * 60_000,
  expect: { timeout: 30_000 },
  workers: 1,
  reporter: "list",
  use: {
    baseURL: process.env.E2E_APP_URL ?? "http://localhost:5173",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
})
