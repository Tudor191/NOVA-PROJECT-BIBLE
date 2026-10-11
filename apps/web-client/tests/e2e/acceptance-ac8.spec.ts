import { type Page, expect, test } from "@playwright/test";

/**
 * **P-AC8-1** -- AC-8's browser-visible clause, in a real browser against the
 * real stack (TDD 4F.8 §19; A-4F8-7 (a), ratified 2026-10-11):
 *
 * > *"The same action category that is blocked at Level 1 auto-executes at
 * > Level 2 for a low-risk case, purely by policy -- no code path differs."*
 *
 * `tools/e2e_acceptance.py ac8` has just run the same T1 category twice from
 * the **production trigger**: once at Level 1 and once at Level 2, from two
 * never-observed files. Its step hands this spec the two runs' file names and
 * decision subjects. What a browser can honestly show of AC-8 is asserted
 * here, and the execution itself is asserted by independent SQL in that
 * harness (E-9):
 *
 * 1. **the level selector shows Level 2**, the level of the second run;
 * 2. **the Level-1 run is a proposal awaiting approval**, found by its own
 *    file name;
 * 3. **the Level-2 run proposed nothing**: no suggestion carries its file
 *    name;
 * 4. **the panel shows what the gateway serves**: the same two facts, read
 *    through `api-gateway`.
 *
 * Nothing is approved or changed here. Runs in its own Playwright invocation,
 * after the P8 services start, and skips anywhere its inputs are not set --
 * including the golden-path run, which comes first (F-4F8-16). No retries: a
 * second attempt would observe a stack the first attempt already looked at.
 */

const SESSION_TOKEN = process.env.NOVA_SESSION_TOKEN ?? "";
const LEVEL1_LABEL = process.env.NOVA_ACCEPTANCE_AC8_LEVEL1_LABEL ?? "";
const LEVEL1_ID = process.env.NOVA_ACCEPTANCE_AC8_LEVEL1_SUBJECT_ID ?? "";
const LEVEL2_LABEL = process.env.NOVA_ACCEPTANCE_AC8_LEVEL2_LABEL ?? "";
const LEVEL2_ID = process.env.NOVA_ACCEPTANCE_AC8_LEVEL2_SUBJECT_ID ?? "";

async function signIn(page: Page): Promise<string> {
  await page.goto("/");
  await page.getByLabel("Session token").fill(SESSION_TOKEN);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByTestId("panel-nav")).toBeVisible();
  const cookies = await page.context().cookies();
  return cookies.map((c) => `${c.name}=${c.value}`).join("; ");
}

test.describe("P-AC8-1: AC-8 in the Autonomy panel", () => {
  test.describe.configure({ retries: 0 });
  test.skip(
    !SESSION_TOKEN || !LEVEL1_LABEL || !LEVEL1_ID || !LEVEL2_LABEL || !LEVEL2_ID,
    "Set only by the 4F.8 acceptance step, after tools/e2e_acceptance.py ac8 has run.",
  );

  test("Level 1 proposed and awaits approval; Level 2 proposed nothing", async ({
    page,
    request,
  }) => {
    const cookie = await signIn(page);

    // --- what the gateway serves ---------------------------------------------
    const response = await request.get("/v1/autonomy/suggestions?status=proposed&limit=200", {
      headers: { cookie },
    });
    expect(response.status(), "suggestions through api-gateway").toBe(200);
    const envelope = await response.json();
    expect(envelope.error).toBeNull();
    const ids = (envelope.data.items as { id: string }[]).map((item) => item.id);
    expect(ids, "the Level-1 run's proposal is served").toContain(LEVEL1_ID);
    expect(ids, "the Level-2 run has no proposal").not.toContain(LEVEL2_ID);

    // --- what the panel renders ----------------------------------------------
    await page.getByTestId("nav-autonomy").click();
    await expect(page.getByTestId("current-level")).toContainText("Level 2", {
      timeout: 30_000,
    });

    const level1 = page.getByTestId("suggestion").filter({ hasText: LEVEL1_LABEL });
    await expect(level1).toHaveCount(1, { timeout: 30_000 });
    await expect(level1.getByTestId("suggestion-status")).toContainText("proposed");
    await expect(level1.getByTestId("suggestion-risk")).toContainText("low");
    // It awaits an explicit decision: the control is offered, and not used.
    await expect(level1.getByTestId("suggestion-approve")).toBeEnabled();

    await expect(page.getByTestId("suggestion").filter({ hasText: LEVEL2_LABEL })).toHaveCount(0);
  });
});
