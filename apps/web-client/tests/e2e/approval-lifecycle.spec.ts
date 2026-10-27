import { expect, test } from "@playwright/test";

/**
 * AC-3's approval clause, end to end: *"a risky action is blocked pending
 * approval and then approved."*
 *
 * The Action is requested by `tools/e2e_request_risky_action.py`, which the CI
 * job runs just before this spec and whose `action_id` arrives here as
 * `NOVA_E2E_ACTION_ID`. That script stands in for `agent-os/kernel` -- the only
 * component permitted to publish `action.execute` -- because `agent-os` has no
 * compose service until Phase 4C. **Everything after the request is real and
 * browser-driven**: the pending approval is read through `api-gateway`, the
 * decision is posted through `api-gateway`, and the resulting
 * `action.approval.decided` arrives over `ws-gateway`.
 *
 * What the stand-in costs is stated rather than hidden: this proves the
 * approval gate, the browser's view of it, and the decision path. It does not
 * prove that a real agent requests actions, which is 4C's to prove.
 *
 * The gate itself is `action-engine`'s, unchanged: `_run_approval_loop`
 * classifies a filesystem `delete` as `RiskLevel.CRITICAL`, writes
 * `approval_required`, publishes `action.approval.requested`, and blocks the
 * pipeline in `_await_decision` for up to 300s. Nothing here is a second
 * approval system.
 */

const SESSION_TOKEN = process.env.NOVA_SESSION_TOKEN ?? "";
const ACTION_ID = process.env.NOVA_E2E_ACTION_ID ?? "";

test.describe("the approval lifecycle", () => {
  test.skip(
    !SESSION_TOKEN,
    "NOVA_SESSION_TOKEN is not set; the stack under test has no provisioned session.",
  );
  test.skip(
    !ACTION_ID,
    "NOVA_E2E_ACTION_ID is not set; no risky action was requested against this stack.",
  );

  test("shows the pending approval, approves it, and the action proceeds", async ({ page }) => {
    await page.goto("/");
    await page.getByLabel("Session token").fill(SESSION_TOKEN);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByTestId("panel-nav")).toBeVisible();

    // --- the browser sees it ---------------------------------------------
    await page.getByTestId("nav-approvals").click();

    // Matched on the full id via `CorrelationTag`'s `data-correlation-id`,
    // not on the eight visible characters, so a second approval sharing a
    // prefix could never satisfy this.
    const approval = page
      .getByTestId("approval")
      .filter({ has: page.locator(`[data-correlation-id="${ACTION_ID}"]`) });
    await expect(approval).toBeVisible({ timeout: 30_000 });

    // Risk classification is shown, because "approve this" without knowing
    // how dangerous it is is not an informed decision. `delete` is Critical,
    // and Critical is the only tier that gates.
    await expect(approval.getByTestId("approval-risk")).toContainText("critical");

    // --- the browser decides it ------------------------------------------
    await approval.getByRole("button", { name: "Approve" }).click();

    // The row leaves when `action.approval.decided` arrives over the socket,
    // never when the button was pressed -- the no-optimistic-mutation rule
    // for shared cognitive state, asserted here against the real bus rather
    // than a stub.
    await expect(approval).toHaveCount(0, { timeout: 60_000 });

    // --- the resulting event is visible ----------------------------------
    // `action.approval.decided` is published by `_publish_decision` once the
    // pipeline observes the decision and proceeds past its blocked stage.
    // Seeing it here is the browser-visible proof that the action was not
    // merely recorded as approved but actually released.
    await page.getByTestId("nav-events").click();
    await page.getByTestId("event-filter-topic").fill("action.approval.decided");

    const decided = page.getByTestId("event").filter({ hasText: "action.approval.decided" });
    await expect(decided.first()).toBeVisible({ timeout: 60_000 });
  });
});
