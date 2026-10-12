import { chmodSync, statSync } from "node:fs";
import { type Page, expect, test } from "@playwright/test";

/**
 * **P-AC7-1** -- AC-7's second clause, in a real browser against the real
 * stack, **with the genuine revocation made here** (TDD 4F.8 §19; A-4F8-1 (a),
 * A-4F8-7 (a); §28.7 (B), all ratified 2026-10-11):
 *
 * > *"... and revoking that sensor's OS-level permission stops the perception
 * > stream, **visibly**, in the Digital Twin / Cognitive State panel."*
 *
 * The Cognitive State panel shows `companion-filesystem` as `running`. Then
 * this spec withdraws the companion's OS permission on the watched workspace,
 * and a Refresh shows `failed`, with when it was last reported. The panel's
 * rows equal `GET /v1/cognitive-state/sensors` through `api-gateway` both
 * times.
 *
 * **The revocation is real, and is the sensor's alone.** The acceptance
 * override runs the companion as uid 1100 with this runner's gid, so it
 * reaches the runner-owned workspace through the group bits. `chmod g-rx`,
 * made by the owner, withdraws exactly that. `capability-engine` keeps its
 * access through the other bits (E-18, asserted afterwards by
 * `tools/e2e_acceptance.py ac7-revocation`, with E-5 and E-6).
 *
 * **Why the revocation is made in the browser run** (TDD 4F.8 §35): P-AC7-1
 * must show `running`, *then* `failed`. A revocation made before this spec
 * would leave only the second state to show.
 *
 * The panel fetches on mount and on Refresh, and never polls (A-4F7-3 (a)).
 * So `failed` is waited for by pressing Refresh, a bounded number of times.
 * That is observation; the revocation is made once and never repeated. No
 * retries: the revocation is terminal for this stack (A-4F8-1 (a2)).
 */

const SESSION_TOKEN = process.env.NOVA_SESSION_TOKEN ?? "";
const WORKSPACE = process.env.NOVA_ACCEPTANCE_WORKSPACE ?? "";
const SENSOR = "companion-filesystem";

type Sensor = { sensor_id: string; state: string; reported_at: string };

async function signIn(page: Page): Promise<string> {
  await page.goto("/");
  await page.getByLabel("Session token").fill(SESSION_TOKEN);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByTestId("panel-nav")).toBeVisible();
  const cookies = await page.context().cookies();
  return cookies.map((c) => `${c.name}=${c.value}`).join("; ");
}

test.describe("P-AC7-1: the revocation, visibly, in the Cognitive State panel", () => {
  test.describe.configure({ retries: 0 });
  test.skip(
    !SESSION_TOKEN || !WORKSPACE,
    "Set only by the 4F.8 acceptance step: it revokes the companion's real permission.",
  );

  test("running, then a genuine revocation, then failed after Refresh", async ({
    page,
    request,
  }) => {
    test.setTimeout(240_000);
    const cookie = await signIn(page);
    const served = async (): Promise<Sensor[]> => {
      const response = await request.get("/v1/cognitive-state/sensors", { headers: { cookie } });
      expect(response.status(), "sensors through api-gateway").toBe(200);
      return (await response.json()).data.sensors as Sensor[];
    };
    const row = page.getByTestId("sensor").and(page.locator(`[data-sensor-id="${SENSOR}"]`));

    // --- before: running, and the panel shows what the gateway serves -------
    const before = (await served()).find((s) => s.sensor_id === SENSOR);
    expect(before?.state, "the companion's sensor before the revocation").toBe("running");
    await page.getByTestId("nav-cognitive-state").click();
    await expect(row).toHaveAttribute("data-state", "running", { timeout: 30_000 });

    // --- the genuine revocation, once ----------------------------------------
    const mode = statSync(WORKSPACE).mode & 0o777;
    expect(mode & 0o050, "the companion reaches the workspace through its group bits").toBe(
      0o050,
    );
    chmodSync(WORKSPACE, mode & ~0o050);
    expect(statSync(WORKSPACE).mode & 0o050, "chmod g-rx took effect").toBe(0);

    // --- after: failed, shown after a Refresh ---------------------------------
    await expect(async () => {
      await page.getByTestId("cognitive-state-refresh").click();
      await expect(row).toHaveAttribute("data-state", "failed", { timeout: 2_000 });
    }).toPass({ timeout: 120_000, intervals: [2_000] });
    await expect(row).toContainText("last reported");

    const after = (await served()).find((s) => s.sensor_id === SENSOR);
    expect(after?.state, "the gateway serves the same state").toBe("failed");
    await expect(row).toContainText(after?.reported_at ?? "<missing>");
  });
});
