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
  // The golden path alone can legitimately spend ~12s waiting for the
  // reasoning fallback, and its two assertions budget 30s + 45s for it. 90s
  // would leave the test timeout, not the assertion, as the thing that fires
  // -- which reports "timed out" instead of naming the step that never
  // happened.
  timeout: 180_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  // `json` is not decoration: the CI job prints a compact summary from it on
  // failure. Playwright's own output otherwise scrolls off behind the compose
  // log dump, and a run whose failure reason is unreadable is barely better
  // than no run at all -- which is exactly what happened on the first attempt.
  reporter: process.env.CI
    ? [
        ["github"],
        ["list"],
        ["json", { outputFile: "playwright-results.json" }],
        ["html", { open: "never" }],
      ]
    : [["list"]],
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
    //
    // No CLI flags: port, host and strictPort all live in `vite.config.ts`,
    // which keeps `pnpm run`'s argument forwarding out of the picture
    // entirely and leaves one place where the address is decided.
    command: "pnpm run build && pnpm run preview",
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    // A cold `vite build` on a runner is slower than the ~2s it takes
    // locally, and 120s already proved too tight once.
    timeout: 180_000,
    // Without these the server's own output is swallowed, so a failed build
    // presents only as "timed out waiting from config.webServer" -- which is
    // exactly how the previous run wasted a cycle.
    stdout: "pipe",
    stderr: "pipe",
  },
});
