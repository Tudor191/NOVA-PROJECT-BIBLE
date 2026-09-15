import { expect, test } from "@playwright/test";

/**
 * **AC-6**, end to end in a real browser against the real stack:
 *
 * > *"The Digital Twin's project model correctly reconstructs 'what was I doing
 * > on Project X' **after a simulated multi-week gap**, and the reconstruction
 * > is visible in the Digital Twin panel."*
 *
 * Four clauses, four assertions, in that order below.
 *
 * The history is written by `tools/e2e_seed_digital_twin_project.py`, which the
 * CI job runs just before this spec and whose `project_id` arrives as
 * `NOVA_E2E_PROJECT_ID`. That driver persists real `MemoryRecord`s carrying real
 * past `created_at` values through the **real** `PostgresMemoryRepository`
 * against **real** PostgreSQL, with the real transactional outbox row in the
 * same transaction -- so `memory-engine`'s own worker publishes real
 * `memory.long_term.created` events, and `digital-twin-engine`'s real subscriber
 * derives from them. The driver never touches `digital-twin-engine`.
 *
 * It stands in for **elapsed time**, not for the engine: no shipped component
 * can produce a four-month-old memory, and ratified decision TDD 4E §20.1
 * settled that the gap is simulated in the *data* rather than in the clock --
 * no fake clock, no system-time manipulation, no new time abstraction, and no
 * change to any Memory HTTP contract.
 *
 * What the stand-in costs, stated rather than hidden: this does not prove that
 * a NOVA installation accumulates months of memory on its own. Everything
 * downstream of the write is real -- the outbox, the bus, the subscriber, the
 * persisted timestamps, the gap arithmetic, and the panel.
 */

const SESSION_TOKEN = process.env.NOVA_SESSION_TOKEN ?? "";
const PROJECT_ID = process.env.NOVA_E2E_PROJECT_ID ?? "";

/** The driver's newest record is 37 days old; anything under three weeks means
 *  the historical timestamps did not survive persistence. */
const MIN_GAP_DAYS = 21;

test.describe("the AC-6 project reconstruction", () => {
  test.skip(
    !SESSION_TOKEN,
    "NOVA_SESSION_TOKEN is not set; the stack under test has no provisioned session.",
  );
  test.skip(
    !PROJECT_ID,
    "NOVA_E2E_PROJECT_ID is not set; no project history was seeded against this stack.",
  );

  test("reconstructs a project across a genuine multi-week gap", async ({ page }) => {
    await page.goto("/");
    await page.getByLabel("Session token").fill(SESSION_TOKEN);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByTestId("panel-nav")).toBeVisible();

    await page.getByTestId("nav-digital-twin").click();

    // --- clause 1: "the Digital Twin's project model" --------------------
    // The project exists because a memory carried its `project_id` --
    // `MemoryRecord.project_id` is the only project identity in the system,
    // and the row here was derived from the event, not from the driver.
    const project = page
      .getByTestId("twin-project")
      .filter({ has: page.getByTestId("twin-project-id").getByText(PROJECT_ID) });
    await expect(project).toBeVisible({ timeout: 60_000 });

    // --- clause 2: "after a simulated multi-week gap" ---------------------
    // The number rendered here was computed from `created_at` values that are
    // real columns in real PostgreSQL, written months in the past. Parsed and
    // compared rather than matched as a string: an assertion on the *words*
    // would pass just as happily on "0 days since last activity", which is the
    // one answer that would mean the whole mechanism had failed.
    const gapText = (await project.getByTestId("twin-project-gap").textContent()) ?? "";
    expect(gapText).not.toContain("no dated activity");
    const gapDays = Number(gapText.match(/^(\d+) days/)?.[1] ?? NaN);
    expect(Number.isFinite(gapDays)).toBe(true);
    expect(gapDays).toBeGreaterThanOrEqual(MIN_GAP_DAYS);

    // --- clause 3: "correctly reconstructs what I was doing" --------------
    await project.getByTestId("reconstruct-project").click();
    const reconstruction = page.getByTestId("project-reconstruction");
    await expect(reconstruction).toBeVisible({ timeout: 30_000 });

    // Five memories, and exactly five. The driver also wrote a CONFIDENTIAL
    // record against this same project through the identical path: TDD 4E
    // §14.5 control 6 and ratified §19.3 require it to contribute nothing, so
    // a count of six here is the negative control failing in the browser.
    await expect(reconstruction.getByTestId("project-memory-count")).toContainText(
      "5 memory records",
    );

    // The activity window is derived from the persisted timestamps too, and
    // spans months rather than collapsing to a moment.
    await expect(reconstruction.getByTestId("project-activity-window")).not.toContainText(
      "no dated activity",
    );

    // What kind of work it was -- the memory types the history carried. Not
    // its content: no subscribed payload carries any (§5.2), which is why a
    // derived domain cannot leak a memory's text even in principle.
    const types = reconstruction.getByTestId("project-memory-type");
    await expect(types.filter({ hasText: "project" })).toHaveCount(1);
    await expect(types.filter({ hasText: "decision" })).toHaveCount(1);

    // --- clause 4: "visible in the Digital Twin panel" --------------------
    // Already true by construction -- everything above was read from the
    // rendered page, through `api-gateway`, in a real browser.
  });

  test("renders an unpopulated domain's reason rather than a zero", async ({ page }) => {
    // TDD 4E §14.5 controls 5 and 10, in the browser. `Hardware Environment`
    // has no producing engine until Phase 4F, and the panel has to say so --
    // a blank card or a `0` would report "NOVA knows nothing about your
    // hardware" where the truth is "nothing reports hardware yet".
    await page.goto("/");
    await page.getByLabel("Session token").fill(SESSION_TOKEN);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByTestId("panel-nav")).toBeVisible();

    await page.getByTestId("nav-digital-twin").click();

    const domains = page.getByTestId("twin-domain");
    await expect(domains.first()).toBeVisible({ timeout: 60_000 });
    // All eleven Part 16 domains, not only the nine 4E adds.
    await expect(domains).toHaveCount(11);

    const hardware = domains.filter({ has: page.getByText("Hardware Environment") });
    await expect(hardware).toHaveAttribute("data-state", "empty");
    await expect(hardware.getByTestId("domain-reason-code")).toHaveText("no_source_engine");
    await expect(hardware.getByTestId("domain-unavailable-fields")).toContainText("cpu");

    // And the distinction the reason codes exist to preserve: `Projects` was
    // derived from real evidence in the same page load, so "empty" here is a
    // statement about the source rather than about the system being broken.
    const projects = domains.filter({ has: page.getByText("Projects", { exact: true }) });
    await expect(projects).toHaveAttribute("data-state", "populated");
  });

  test("a confidential memory never reaches the rendered twin", async ({ page, request }) => {
    // The negative control at the API boundary rather than through the UI:
    // the panel can only show what the engine returns, so asserting on the
    // engine's own answer is the stronger statement. Driven through
    // `api-gateway`, so it also exercises the forwarding path.
    await page.goto("/");
    await page.getByLabel("Session token").fill(SESSION_TOKEN);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByTestId("panel-nav")).toBeVisible();

    const cookies = await page.context().cookies();
    const cookieHeader = cookies.map((c) => `${c.name}=${c.value}`).join("; ");

    const response = await request.get(`/v1/digital-twin/domains/projects/${PROJECT_ID}`, {
      headers: { cookie: cookieHeader },
    });
    expect(response.status()).toBe(200);

    const body = await response.json();
    // Five, not six: the CONFIDENTIAL record the driver wrote against this
    // project contributed no evidence row at all.
    expect(body.data.project.memory_count).toBe(5);
    expect(body.data.project.gap_days).toBeGreaterThanOrEqual(MIN_GAP_DAYS);
    // And no rendered field carries its content -- no subscribed payload has
    // any, so this is asserted over the whole serialised response.
    expect(JSON.stringify(body)).not.toContain("credentials");
  });
});
