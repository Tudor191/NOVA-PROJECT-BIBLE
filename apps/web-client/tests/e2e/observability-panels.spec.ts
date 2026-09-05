import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

/**
 * Phase 4B's six observability panels, against the real stack.
 *
 * A separate spec from the golden path on purpose: AC-1 is the acceptance
 * criterion and must keep failing loudly on its own terms, not be diluted by
 * seven more assertions in the same test.
 *
 * **What a green run here proves, and what it does not.** It proves each
 * panel loads through the approved boundaries -- REST via `api-gateway`,
 * realtime via `ws-gateway` -- and renders either its data or an honest
 * statement that it has none. It does *not* prove every panel has data: with
 * no LLM provider and no operator driving the system, nothing plans, nothing
 * reasons, and nothing requests approval, so those panels correctly render
 * empty. Asserting otherwise would require fabricating engine activity, and
 * a test that seeded its own data would stop testing the transport.
 *
 * Health and Events are the exceptions and carry the realtime assertions,
 * because `nova-core` beats every five seconds whether or not anyone is
 * watching -- so they are the two panels a live stack can genuinely fill.
 */

const SESSION_TOKEN = process.env.NOVA_SESSION_TOKEN ?? "";

test.describe("the observability panels", () => {
  test.skip(
    !SESSION_TOKEN,
    "NOVA_SESSION_TOKEN is not set; the stack under test has no provisioned session.",
  );

  async function signIn(page: Page) {
    await page.goto("/");
    await page.getByLabel("Session token").fill(SESSION_TOKEN);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByTestId("panel-nav")).toBeVisible();
  }

  test("every panel loads through the gateways and renders", async ({ page }) => {
    await signIn(page);

    // Each entry is (nav link, the region the panel renders). A panel that
    // fails to load its lazy chunk, or throws while rendering, fails here --
    // which is the "all six panels render" check in its most direct form.
    const panels = [
      ["nav-planning", "Planning"],
      ["nav-reasoning", "Reasoning Trace"],
      ["nav-capabilities", "Capabilities"],
      ["nav-approvals", "Approvals"],
      ["nav-events", "Events"],
      ["nav-health", "Health"],
    ] as const;

    for (const [navTestId, regionName] of panels) {
      await page.getByTestId(navTestId).click();

      // The region appearing is the lazy chunk having loaded and the
      // component having rendered without throwing. A panel that fails
      // either way never gets here.
      const region = page.getByRole("region", { name: regionName });
      await expect(region).toBeVisible({ timeout: 15_000 });

      // And the panel header must carry its own title, so a blank region
      // cannot pass as a rendered one.
      await expect(region).toContainText(regionName);
    }
  });

  test("no panel reports that it could not reach its engine", async ({ page }) => {
    await signIn(page);

    // The four REST-backed panels. If `api-gateway`'s route table is missing
    // a prefix, the gateway 404s and `AsyncPanelBody` renders a degradation
    // notice -- which reads like an engine outage and is in fact a gateway
    // misconfiguration. This is the assertion that tells them apart.
    for (const navTestId of [
      "nav-planning",
      "nav-reasoning",
      "nav-capabilities",
      "nav-approvals",
    ]) {
      await page.getByTestId(navTestId).click();
      await expect(page.getByTestId("panel-empty").first()).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId("degradation-notice")).toHaveCount(0);
    }
  });

  test("the Events panel shows frames actually arriving", async ({ page }) => {
    await signIn(page);
    await page.getByTestId("nav-events").click();

    // `nova-core` beats every 5s, so a live stack fills this panel without
    // anyone doing anything. An empty feed here means the socket is not
    // delivering -- the single most useful thing this panel can tell you.
    const events = page.getByTestId("event");
    await expect(events.first()).toBeVisible({ timeout: 30_000 });

    // Both clocks are shown, and labelled. Presenting arrival time as event
    // time is how out-of-order delivery becomes invisible.
    const times = page.getByTestId("event-times").first();
    await expect(times).toContainText("occurred");
    await expect(times).toContainText("received");
  });

  test("the Health panel reports a real module, not an assumed one", async ({ page }) => {
    await signIn(page);
    await page.getByTestId("nav-health").click();

    await expect(page.getByTestId("health-module").first()).toBeVisible({ timeout: 30_000 });

    // Whatever it shows must come from a stream that named itself. A module
    // rendered without a source would be the panel inventing a row.
    await expect(page.getByTestId("health-source").first()).toContainText("heartbeat");

    // And it must be a status the module actually reported -- never `unknown`
    // dressed up as healthy, nor healthy invented from silence.
    await expect(page.getByTestId("status-dot").first()).toHaveAttribute(
      "data-status",
      /healthy|degraded|down/,
    );
  });
});
