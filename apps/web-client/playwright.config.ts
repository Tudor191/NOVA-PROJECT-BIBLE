import { defineConfig, devices } from "@playwright/test";

/**
 * The golden-path E2E run — Phase 4 **AC-1**.
 *
 * **This suite is CI-only evidence.** Docker has been unavailable in the
 * development environment throughout Phase 3 and remains so, and this run
 * needs the whole local stack (`infra/docker/docker-compose.local.yml`) plus
 * both gateways. Per TDD 4A §10's R-1 rule and Phase 3E's condition C-1, a
 * green local run would not be equivalent evidence and must never be reported
 * as though it were. The authoritative signal is the `e2e` job in
 * `pr-checks.yml`.
 *
 * It is a separate job from the unit suite on purpose (TDD 4A §11): a
 * browser-and-stack test that could mask a unit failure would let the cheap
 * signal disappear behind the expensive one.
 */

const BASE_URL = process.env.NOVA_WEB_CLIENT_URL ?? "http://127.0.0.1:4173";

export default defineConfig({
  testDir: "./tests/e2e",
  // The golden path exercises a real conversation through real engines;
  // model latency is genuinely variable and a tight timeout would produce
  // flakes that say nothing about the code.
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : [["list"]],
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    video: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    // `preview` serves the real production build rather than the dev server,
    // so the artefact under test is the one that would ship.
    command: "pnpm run build && pnpm run preview --port 4173 --strictPort",
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
