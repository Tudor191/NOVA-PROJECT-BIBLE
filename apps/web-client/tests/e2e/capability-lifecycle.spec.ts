import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

/**
 * DEV-1 -- the Capabilities panel's install and uninstall halves, against the
 * real stack.
 *
 * Master scope §5 specifies **Capabilities (list / install / uninstall)**, and
 * 4B originally shipped list only. This spec exercises the two that were
 * missing, end to end and through the approved boundaries: the browser calls
 * `api-gateway`, which forwards `/v1/capabilities` verbatim to
 * `capability-engine`, which runs its real 8-stage installation pipeline.
 *
 * **`exact: true` on the Install button is load-bearing.** Playwright matches
 * accessible names by substring, and "Uninstall" contains "Install" -- so the
 * inexact locator resolves to the install button plus every uninstall button
 * on the page and fails strict mode. Found by CI run #73.
 *
 * Its own spec file rather than more assertions in `observability-panels`,
 * for the reason that file already gives: a criterion should fail on its own
 * terms. This one mutates real registry state, so keeping it separate also
 * keeps the read-only panel spec read-only.
 *
 * **Install is deliberately not routed through Approvals.** The installation
 * pipeline's stage 4 is best-effort permission *disclosure* that "never blocks
 * the pipeline ... unlike `action-engine`'s Critical-risk approval loop"
 * (`capability-engine/domain/pipeline.py`). Sending it through the Approvals
 * panel would invent a gate the architecture does not have.
 */

const SESSION_TOKEN = process.env.NOVA_SESSION_TOKEN ?? "";

/**
 * A manifest the engine will actually accept: `filesystem` is one of the four
 * adapters `capability-engine` registers at boot, so stage 5's adversarial
 * sandbox probe has something real to probe. The name is unique to this spec
 * so it can never collide with the four built-ins, and the version makes a
 * re-run idempotent rather than duplicative (Fork 3C-4, Option B).
 */
const MANIFEST = {
  name: "e2e-probe-capability",
  description: "Installed by the Phase 4B capability-lifecycle E2E.",
  category: "filesystem",
  version: "1.0.0",
  dependencies: [],
  required_permissions: ["filesystem:read"],
  required_resources: ["/tmp"],
  input_schema: { type: "object" },
  output_schema: { type: "object" },
  execution_adapter: "filesystem",
};

test.describe("the capability lifecycle", () => {
  test.skip(
    !SESSION_TOKEN,
    "NOVA_SESSION_TOKEN is not set; the stack under test has no provisioned session.",
  );

  async function openCapabilities(page: Page) {
    await page.goto("/");
    await page.getByLabel("Session token").fill(SESSION_TOKEN);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByTestId("panel-nav")).toBeVisible();
    await page.getByTestId("nav-capabilities").click();
    await expect(page.getByTestId("capability").first()).toBeVisible({ timeout: 15_000 });
  }

  test("installs a capability, shows it, then uninstalls it", async ({ page }) => {
    await openCapabilities(page);

    const before = await page.getByTestId("capability").count();
    // The four built-ins `capability-engine` bootstrap-installs before it
    // reports ready. If this is ever 0 the engine did not finish booting, and
    // every assertion below would be measuring the wrong thing.
    expect(before).toBeGreaterThan(0);

    const row = page.getByTestId("capability").filter({ hasText: MANIFEST.name });

    // --- install ---------------------------------------------------------
    await page.getByTestId("capability-manifest-input").fill(JSON.stringify(MANIFEST));
    await page.getByRole("button", { name: "Install", exact: true }).click();

    // The row appears because the engine confirmed the install and the panel
    // re-read the registry -- never because the button was pressed. There is
    // no optimistic insert, so a capability that failed the sandbox probe
    // would not be drawn here.
    await expect(row).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("capability-install-error")).toHaveCount(0);
    await expect(page.getByTestId("capability")).toHaveCount(before + 1);

    // --- uninstall -------------------------------------------------------
    await row.getByTestId("capability-uninstall").click();

    // Gone for the same reason it appeared: the engine confirmed a 204 and
    // the panel re-read. Back to exactly the boot set.
    await expect(row).toHaveCount(0, { timeout: 30_000 });
    await expect(page.getByTestId("capability")).toHaveCount(before);
  });

  test("reports the engine's own refusal rather than a generic failure", async ({ page }) => {
    await openCapabilities(page);

    // `execution_adapter` names an adapter that does not exist, so stage 5
    // fails with `no adapter registered for ...` and the endpoint answers
    // 422. What matters is that the operator sees *that*, not "something
    // went wrong": the failing stage is the actionable part.
    await page
      .getByTestId("capability-manifest-input")
      .fill(JSON.stringify({ ...MANIFEST, name: "e2e-bad-adapter", execution_adapter: "nope" }));
    await page.getByRole("button", { name: "Install", exact: true }).click();

    const notice = page.getByTestId("capability-install-error");
    await expect(notice).toBeVisible({ timeout: 30_000 });
    await expect(notice).toContainText("nope");

    // And a refused install adds nothing to the registry.
    await expect(
      page.getByTestId("capability").filter({ hasText: "e2e-bad-adapter" }),
    ).toHaveCount(0);
  });

  test("refuses a malformed manifest without troubling the gateway", async ({ page }) => {
    await openCapabilities(page);

    await page.getByTestId("capability-manifest-input").fill("{ not json");
    await page.getByRole("button", { name: "Install", exact: true }).click();

    // Caught client-side: "that is not JSON" is something this side already
    // knows, and sending it would come back as an opaque 422.
    await expect(page.getByTestId("capability-manifest-error")).toBeVisible();
    await expect(page.getByTestId("capability-install-error")).toHaveCount(0);
  });
});
