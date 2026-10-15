import { expect, test, type Page } from "@playwright/test"

// signup is done once by hand; the smoke signs in with that account, which must
// also be an admin so the last step can see the run in the admin console.
const EMAIL = process.env.E2E_EMAIL ?? ""
const PASSWORD = process.env.E2E_PASSWORD ?? ""
const ADMIN_URL = process.env.E2E_ADMIN_URL ?? "http://localhost:5174"
const OFFER = { name: process.env.E2E_OFFER_NAME ?? "Plausible", url: process.env.E2E_OFFER_URL ?? "https://plausible.io" }
const DISCOVERY_TIMEOUT = 20 * 60_000

test.skip(!EMAIL || !PASSWORD, "set E2E_EMAIL and E2E_PASSWORD")

async function signIn(page: Page) {
  await page.goto("/auth/login")
  await page.getByLabel("Email").fill(EMAIL)
  await page.getByLabel("Password").fill(PASSWORD)
  await page.getByRole("button", { name: "Login" }).click()
  await expect(page).not.toHaveURL(/\/auth\//)
}

test("discovery to outreach, and the admin sees the run", async ({ page, browser }) => {
  const errors: string[] = []
  page.on("pageerror", (e) => errors.push(e.message))

  await test.step("sign in", () => signIn(page))

  await test.step("start a workspace", async () => {
    await page.goto("/new")
    await page.locator("#product-name").fill(OFFER.name)
    await page.locator("#website-url").fill(OFFER.url)
    await page.getByPlaceholder("Select target markets").fill("United States")
    await page.getByRole("option", { name: "United States", exact: true }).click()
    await page.locator("#product-name").click() // the country list only closes on blur
    await page.getByRole("button", { name: "Create Workspace" }).click()
  })

  await test.step("confirm the description and wait for insights", async () => {
    // The agent may ask more than once; accept until the workspace opens.
    const deadline = Date.now() + DISCOVERY_TIMEOUT
    while (!/\/workspace\//.test(page.url())) {
      expect(Date.now(), "discovery did not finish in time").toBeLessThan(deadline)
      const proceed = page.getByRole("button", { name: "Yes, Proceed" })
      if (await proceed.isVisible().catch(() => false)) await proceed.click()
      await page.waitForTimeout(5_000)
    }
    await expect(page.getByText("Product").first()).toBeVisible()
  })

  for (const section of ["Market", "Competition", "Ideal Customers"]) {
    await test.step(`open ${section}`, async () => {
      await page.getByText(section, { exact: true }).first().click()
      await expect(page.getByText(/something went wrong/i)).toHaveCount(0)
    })
  }

  await test.step("outreach and accounts pages load", async () => {
    await page.goto("/accounts")
    await expect(page.getByText(/something went wrong/i)).toHaveCount(0)
  })

  await test.step("the admin console shows the run completed", async () => {
    const admin = await browser.newPage()
    await admin.goto(ADMIN_URL)
    await admin.getByLabel("Email").fill(EMAIL)
    await admin.getByLabel("Password").fill(PASSWORD)
    await admin.getByRole("button", { name: "Sign in" }).click()
    await admin.getByRole("link", { name: "Runs" }).click()
    // The workspace page opens mid-run, so completion is checked here: the
    // newest discovery run (this one) must reach "completed".
    const newest = admin.getByRole("row").filter({ hasText: "discovery" }).first()
    const deadline = Date.now() + DISCOVERY_TIMEOUT
    for (;;) {
      await expect(newest).toBeVisible()
      const text = (await newest.textContent()) ?? ""
      expect(text, "discovery run failed").not.toContain("failed")
      if (text.includes("completed")) break
      expect(Date.now(), "discovery did not complete in time").toBeLessThan(deadline)
      await admin.waitForTimeout(10_000)
      await admin.reload()
    }
    await admin.close()
  })

  expect(errors, "uncaught errors in the app").toEqual([])
})
