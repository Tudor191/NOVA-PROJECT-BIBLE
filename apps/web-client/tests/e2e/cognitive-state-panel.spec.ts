import { type Page, expect, test } from "@playwright/test";

/**
 * **P-21** -- the Cognitive State panel in a real browser against the real stack
 * (TDD 4F.7 §16; A-4F7-5 default (a)).
 *
 * The `e2e` job starts `cognitive-state-engine` behind `api-gateway`, with its
 * schema migrated by the real migrator, and **nothing seeded**: no Active
 * Thought exists in production until the promotion slice (4F.P, K-4), and no
 * `perception-engine` runs in this job, so no sensor has reported. What this
 * proves in a browser is therefore:
 *
 * 1. **the path** -- browser → `api-gateway` → the deployed engine → its real
 *    Postgres schema, for all three routes;
 * 2. **parity** -- what the panel renders is exactly what the same three `GET`s
 *    return through the gateway in the same test;
 * 3. **the honest empty states** -- each renders its statement and nothing else;
 * 4. **read-only at the edge** -- a write is refused with the engine's own 405,
 *    and Refresh re-issues `GET`s and nothing else.
 *
 * Non-empty rendering is proven below the browser: real rows → JSON against real
 * Postgres (P-4, P-6, P-8) and contract-validated fixtures → DOM (P-18). A real
 * sensor report reaching the panel is not asserted here, because K-1's startup
 * race would make any specific state nondeterministic; AC-7's browser
 * demonstration is 4F.8's.
 */

const SESSION_TOKEN = process.env.NOVA_SESSION_TOKEN ?? "";
const ROUTES = ["thoughts", "focus", "sensors"] as const;

async function signIn(page: Page): Promise<void> {
  await page.goto("/");
  await page.getByLabel("Session token").fill(SESSION_TOKEN);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByTestId("panel-nav")).toBeVisible();
}

async function cookieHeader(page: Page): Promise<string> {
  const cookies = await page.context().cookies();
  return cookies.map((c) => `${c.name}=${c.value}`).join("; ");
}

test.describe("the Cognitive State panel", () => {
  test.skip(
    !SESSION_TOKEN,
    "NOVA_SESSION_TOKEN is not set; the stack under test has no provisioned session.",
  );

  test("renders exactly what the gateway serves", async ({ page, request }) => {
    await signIn(page);
    const cookie = await cookieHeader(page);

    const bodies: Record<string, unknown> = {};
    for (const route of ROUTES) {
      const response = await request.get(`/v1/cognitive-state/${route}`, {
        headers: { cookie },
      });
      expect(response.status(), `${route} through api-gateway`).toBe(200);
      const envelope = await response.json();
      expect(envelope.error).toBeNull();
      bodies[route] = envelope.data;
    }

    await page.getByTestId("nav-cognitive-state").click();

    const thoughts = (bodies.thoughts as { thoughts: { thought_id: string }[] }).thoughts;
    const focus = bodies.focus as { capacity: number; entries: { thought: { thought_id: string } }[] };
    const sensors = (bodies.sensors as { sensors: { sensor_id: string; state: string }[] }).sensors;

    if (thoughts.length === 0) {
      await expect(page.getByText("No Active Thoughts.", { exact: true })).toBeVisible();
      await expect(page.getByTestId("thought")).toHaveCount(0);
    } else {
      await expect(page.getByTestId("thought")).toHaveCount(thoughts.length);
    }

    if (focus.entries.length === 0) {
      await expect(page.getByText("Nothing is in focus.", { exact: true })).toBeVisible();
      await expect(page.getByTestId("focus-entry")).toHaveCount(0);
    } else {
      await expect(page.getByTestId("focus-entry")).toHaveCount(focus.entries.length);
      await expect(page.getByTestId("focus-capacity")).toHaveText(
        `${focus.entries.length} of capacity ${focus.capacity}`,
      );
    }

    if (sensors.length === 0) {
      await expect(
        page.getByText("No sensor report has been received.", { exact: true }),
      ).toBeVisible();
      await expect(page.getByTestId("sensor")).toHaveCount(0);
    } else {
      const rows = page.getByTestId("sensor");
      await expect(rows).toHaveCount(sensors.length);
      for (const [index, reported] of sensors.entries()) {
        await expect(rows.nth(index)).toHaveAttribute("data-sensor-id", reported.sensor_id);
        await expect(rows.nth(index)).toHaveAttribute("data-state", reported.state);
      }
    }

    await expect(page.getByTestId("degradation-notice")).toHaveCount(0);
  });

  test("shows the honest empty states of an unseeded stack", async ({ page, request }) => {
    // A-4F7-5 (a): nothing is seeded and no perception-engine runs here, so all
    // three are empty -- and each must render as its statement, not as a
    // placeholder, a sample row or an error.
    await signIn(page);
    const cookie = await cookieHeader(page);
    const data = async (route: string) =>
      (await (await request.get(`/v1/cognitive-state/${route}`, { headers: { cookie } })).json())
        .data;

    expect(await data("thoughts")).toEqual({ thoughts: [] });
    expect((await data("focus")).entries).toEqual([]);
    expect(await data("sensors")).toEqual({ sensors: [] });

    await page.getByTestId("nav-cognitive-state").click();
    const statements = page.getByTestId("panel-empty");
    await expect(statements).toHaveCount(3);
    await expect(statements).toHaveText(
      ["No sensor report has been received.", "Nothing is in focus.", "No Active Thoughts."],
      { ignoreCase: false },
    );
    await expect(page.getByTestId("thought-layer")).toHaveCount(0);
    await expect(page.getByTestId("degradation-notice")).toHaveCount(0);
  });

  test("is read-only at the edge: a write is refused, Refresh only reads", async ({
    page,
    request,
  }) => {
    await signIn(page);
    const cookie = await cookieHeader(page);

    // The engine declares GET only; its 405 comes back through the gateway.
    const write = await request.post("/v1/cognitive-state/thoughts", {
      headers: { cookie },
      data: { description: "should never be created" },
    });
    expect(write.status()).toBe(405);
    expect((await write.json()).data).toBeNull();

    await page.getByTestId("nav-cognitive-state").click();
    await expect(page.getByTestId("panel-empty").first()).toBeVisible();

    const seen: string[] = [];
    page.on("request", (req) => {
      if (req.url().includes("/v1/cognitive-state/")) {
        seen.push(`${req.method()} ${new URL(req.url()).pathname}`);
      }
    });
    await page.getByTestId("cognitive-state-refresh").click();
    await expect.poll(() => seen.length).toBeGreaterThanOrEqual(3);

    expect([...seen].sort()).toEqual([
      "GET /v1/cognitive-state/focus",
      "GET /v1/cognitive-state/sensors",
      "GET /v1/cognitive-state/thoughts",
    ]);
  });
});
