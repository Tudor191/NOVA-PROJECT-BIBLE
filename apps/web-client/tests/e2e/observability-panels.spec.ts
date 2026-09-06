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
 * Three panels are filled by a live stack on its own, and they carry the
 * positive assertions:
 *
 *   Events, Health   `nova-core` beats every five seconds whether or not
 *                    anyone is watching, so both fill over the socket.
 *   Capabilities     `capability-engine` bootstrap-installs four built-ins
 *                    before reporting ready, so this one is populated over
 *                    REST -- by construction, not by activity.
 *
 * Planning, Reasoning and Approvals are the genuinely activity-driven three,
 * and empty is their correct live state -- but no test below pins that.
 * How much data a panel happens to hold is a fact about how busy the system
 * is on the day, and asserting it is what made the check below wrong twice.
 * What is asserted is that each panel *settles* and does not settle on a
 * failure notice.
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
    // misconfiguration. `degradation-notice` absent is the assertion that
    // tells them apart, and it applies to all four.
    //
    // What each panel shows *instead* differs, and the split is not
    // cosmetic. Plans, traces and approvals are produced by activity: with
    // no LLM provider and nobody driving the system, there is none, so those
    // three render their empty label. Capabilities are not produced by
    // activity at all -- `capability-engine`'s startup bootstrap installs
    // four built-ins through the real 8-stage pipeline before it reports
    // ready (`main.py`), so a *healthy* stack always has capabilities and an
    // empty Capabilities panel would mean the bootstrap did not run.
    //
    // Asserting `panel-empty` there was wrong, and wrong in the direction
    // that matters: it would have passed on a broken bootstrap and failed on
    // a working one.
    //
    // So the check is stated as the property itself rather than as a proxy
    // for it: the panel must *settle* -- stop reading and commit to
    // something -- and what it settles on must not be a degradation notice.
    // Whether it settles on rows or on an empty label is a fact about how
    // busy the system is, which is not what this test is about, and pinning
    // it here is what made this test wrong twice.
    for (const [navTestId, label] of [
      ["nav-planning", "Planning"],
      ["nav-reasoning", "Reasoning Trace"],
      ["nav-approvals", "Approvals"],
      ["nav-capabilities", "Capabilities"],
    ] as const) {
      await page.getByTestId(navTestId).click();

      // Settled means the reading state is gone. A panel still reading after
      // 15s has not reached its engine either -- it just has not said so yet,
      // and left unasserted it would read as success.
      await expect(
        page.getByTestId("panel-loading"),
        `${label} was still reading after 15s -- it never reached its engine`,
      ).toHaveCount(0, { timeout: 15_000 });

      // The assertion this test is named for. If `api-gateway`'s route table
      // is missing a prefix, the gateway 404s and this is what renders.
      await expect(
        page.getByTestId("degradation-notice"),
        `${label} reported that it could not reach its engine`,
      ).toHaveCount(0);
    }

    // And Capabilities carries a positive half on top, so the loop above
    // cannot pass by every panel rendering nothing at all: real rows, read
    // from a real engine, through the gateway route this milestone added.
    await expect(
      page.getByTestId("capability").first(),
      "Capabilities reached its engine but rendered no built-in capabilities",
    ).toBeVisible({ timeout: 15_000 });
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
