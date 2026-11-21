import { expect, test } from "@playwright/test";

/**
 * **AC-5**, end to end in a real browser against the real stack:
 *
 * > *"An autonomous suggestion at Autonomy Level 1 is **proposed, not
 * > executed**, is visible in the Autonomy panel, and executing it requires
 * > explicit user approval."*
 *
 * Four clauses, four assertions, in that order below.
 *
 * The suggestion is produced by `tools/e2e_seed_autonomy_suggestion.py`, which
 * the CI job runs just before this spec and whose id arrives as
 * `NOVA_E2E_SUGGESTION_ID`. That driver runs the **real** decision pipeline --
 * the real Policy, Permission and Trust gates in their binding order -- and
 * persists through the real repository, in one transaction. It stands in for a
 * *producer*, because no shipped component produces a suggestion: decision
 * D-4D-1 removed the Event Bus origin, and TDD 4D §8.1 defines no creation
 * route. 4D builds the decision surface, not the initiative surface (§1.1).
 *
 * What the stand-in costs is stated rather than hidden, and is the same shape
 * as 4B's approval driver: this proves the proposal, the browser's view of it,
 * that nothing executed, and that approval is explicit and gated. It does not
 * prove that NOVA proposes on its own initiative, which no milestone has built.
 */

const SESSION_TOKEN = process.env.NOVA_SESSION_TOKEN ?? "";
const SUGGESTION_ID = process.env.NOVA_E2E_SUGGESTION_ID ?? "";

test.describe("the AC-5 suggestion lifecycle", () => {
  test.skip(
    !SESSION_TOKEN,
    "NOVA_SESSION_TOKEN is not set; the stack under test has no provisioned session.",
  );
  test.skip(
    !SUGGESTION_ID,
    "NOVA_E2E_SUGGESTION_ID is not set; no suggestion was recorded against this stack.",
  );

  test("proposes without executing, and requires an explicit approval", async ({ page }) => {
    await page.goto("/");
    await page.getByLabel("Session token").fill(SESSION_TOKEN);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByTestId("panel-nav")).toBeVisible();

    await page.getByTestId("nav-autonomy").click();

    // --- clause 1: "at Autonomy Level 1" ---------------------------------
    // The driver set the level through the real repository; the panel reads
    // it back through `api-gateway`, so this is the stack's answer and not
    // the driver's.
    await expect(page.getByTestId("current-level")).toContainText("Suggestive", {
      timeout: 30_000,
    });

    // Level 2 is present and **selectable** -- 4F.5, X-1. Asserted here as
    // well as in `vitest` because only the real engine can be wrong about it,
    // and that is exactly what happened: the `vitest` twin kept passing
    // against its stub while this caught the real change.
    //
    // *(This read `await expect(page.getByTestId("level-disabled"))
    // .toBeDisabled();` with the comment "Level 2 is present and disabled --
    // decision D-1" until 2026-09-21. D-1 assigned enabling Level 2 to
    // milestone 4F, and 4F.5 is that milestone, so the **same control is
    // retargeted to the new ratified state** rather than deleted. Preserved
    // per protocol §0.3.4.)*
    await expect(page.getByTestId("level-disabled")).toHaveCount(0);
    const assisted = page.getByTestId("level-option").filter({ hasText: "Assisted" });
    await expect(assisted).toHaveCount(1);
    await expect(assisted.getByTestId("level-select")).toBeEnabled();

    // --- clause 2: "is visible in the Autonomy panel" --------------------
    const suggestion = page.getByTestId("suggestion").first();
    await expect(suggestion).toBeVisible({ timeout: 30_000 });
    await expect(suggestion.getByTestId("suggestion-title")).toContainText(
      "Archive three stale feature branches",
    );
    await expect(suggestion.getByTestId("suggestion-risk")).toContainText("low");

    // --- clause 3: "proposed, not executed" ------------------------------
    // The status is `proposed`, and the gates the engine evaluated are shown
    // -- Part 14's Explanation Engine reduced to what 4D can honestly give.
    await expect(suggestion.getByTestId("suggestion-status")).toContainText("proposed");
    await expect(suggestion.getByTestId("gate-passed")).toBeVisible();

    // Nothing decided it on the way in. The Approve control is still offered,
    // which it would not be for an already-decided suggestion.
    const approve = suggestion.getByTestId("suggestion-approve");
    await expect(approve).toBeEnabled();

    // --- clause 4: "requires explicit user approval" ---------------------
    // Nothing has happened yet. The decision is a deliberate click, and the
    // row's status changes only after the server has answered -- the panel
    // invalidates and re-reads rather than patching its cache, so what is
    // rendered below came back from `autonomy-engine`.
    await approve.click();
    await expect(page.getByTestId("suggestions-empty")).toBeVisible({ timeout: 30_000 });

    // --- and approval still executed nothing -----------------------------
    // The inbox is filtered to `proposed`, so the row leaving proves the
    // status changed. That it changed to *approved* and not to *executed* is
    // what `executed: false` on the decision response carries, and what the
    // Approvals panel below shows: `action-engine` has no new pending
    // approval, because approving an autonomy suggestion creates no Action.
    await page.getByTestId("nav-approvals").click();
    await expect(page.getByTestId("panel-empty").or(page.getByTestId("approval"))).toBeVisible({
      timeout: 30_000,
    });
    await expect(
      page.getByTestId("approval").filter({ hasText: "Archive three stale feature branches" }),
    ).toHaveCount(0);
  });

  test("a second decision on the same suggestion is refused", async ({ page, request }) => {
    // TDD §13: *"Second decision is a 409; the first stands."* Driven through
    // `api-gateway` rather than the UI, because the UI removes the row after
    // the first decision -- the refusal is a property of the engine, and this
    // is the only place the real one can be exercised.
    await page.goto("/");
    await page.getByLabel("Session token").fill(SESSION_TOKEN);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByTestId("panel-nav")).toBeVisible();

    const cookies = await page.context().cookies();
    const cookieHeader = cookies.map((c) => `${c.name}=${c.value}`).join("; ");

    const response = await request.post(
      `/v1/autonomy/suggestions/${SUGGESTION_ID}/decide`,
      {
        data: { decision: "reject" },
        headers: { cookie: cookieHeader, "content-type": "application/json" },
        failOnStatusCode: false,
      },
    );
    expect(response.status()).toBe(409);
  });
});
