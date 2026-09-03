import { expect, test } from "@playwright/test";

/**
 * Phase 4 **AC-1**, and `3-P` §11 criterion 1: *open the web client,
 * authenticate, hold a live text conversation, see it rendered.*
 *
 * This is the acceptance criterion Phase 2D set and never delivered. It runs
 * against the real stack -- both gateways, `communication-engine`,
 * `reasoning-engine`, `personality-engine`, NATS, Postgres -- because the
 * property under test is precisely that those pieces connect. Stubbing any
 * of them would test the stub.
 *
 * **CI-only.** Docker is unavailable in the development environment, so this
 * has never been executed locally and no local result should be reported for
 * it (TDD 4A §10, R-1; Phase 3E condition C-1).
 */

const SESSION_TOKEN = process.env.NOVA_SESSION_TOKEN ?? "";

test.describe("the golden path", () => {
  test.skip(
    !SESSION_TOKEN,
    "NOVA_SESSION_TOKEN is not set; the stack under test has no provisioned session.",
  );

  test("a user signs in and holds a live text conversation", async ({ page }) => {
    await page.goto("/");

    // 1. First-run session flow (D-3): the instance's local token, once.
    await page.getByLabel("Session token").fill(SESSION_TOKEN);
    await page.getByRole("button", { name: "Sign in" }).click();

    // 2. The shell appears, with its instruments.
    await expect(page.getByRole("region", { name: "Conversation" })).toBeVisible();

    // 3. Open a conversation.
    await page.getByRole("button", { name: "Start a conversation" }).click();
    await expect(page.getByPlaceholder("Say something to NOVA")).toBeVisible();

    // 4. Say something.
    await page.getByPlaceholder("Say something to NOVA").fill("Hello NOVA, are you there?");
    await page.getByRole("button", { name: "Send" }).click();

    // 5. The user's own turn appears only once the bus confirms it --
    //    `communication.turn.received` through ws-gateway, not an optimistic
    //    render. This assertion is therefore a real round trip.
    const turns = page.getByTestId("transcript-entry");
    await expect(turns.filter({ hasText: "Hello NOVA, are you there?" })).toHaveCount(1, {
      timeout: 30_000,
    });

    // 6. NOVA answers. This is the leg that did not exist before 4A:
    //    `communication.intent.delivered`, published by communication-engine
    //    after the ADR-005 intent gate passes the utterance, bridged by
    //    ws-gateway. Without it this assertion could never pass.
    //
    //    The timeout is raised from the 15s default deliberately, and the
    //    arithmetic is the reason: with no LLM provider configured,
    //    `communication_engine_reasoning_rpc_timeout_ms` (10s) has to expire
    //    before `conversation_orchestration` falls back, and personality
    //    validation can add its own 2s on top. A 15s budget leaves ~3s of
    //    headroom over a 12s path, which is a flake waiting to happen rather
    //    than a real signal. This is the *fallback* path's cost, not slowness
    //    in the transport under test.
    const reply = page.locator('[data-testid="transcript-entry"][data-author="nova"]');
    await expect(reply.first()).toBeVisible({ timeout: 45_000 });
    await expect(reply.first()).not.toHaveText("");

    // 7. The envelope is rendered, not hidden (TDD 4A §5.2 property 4).
    await expect(page.getByTestId("correlation-tag").first()).toBeVisible();
    await expect(page.getByTestId("confidence-tier-badge").first()).toBeVisible();
  });

  test("the shell reports real telemetry and never invents it", async ({ page }) => {
    await page.goto("/");
    await page.getByLabel("Session token").fill(SESSION_TOKEN);
    await page.getByRole("button", { name: "Sign in" }).click();

    // The System Pulse binds to `nova.heartbeat`. Against a running stack it
    // must reach a real status rather than sitting at "no heartbeat yet" --
    // and a dot that animates while reporting `unknown` would be exactly the
    // fake animation Bible Part 6 forbids.
    const pulse = page.getByTestId("status-dot").first();
    await expect(pulse).toHaveAttribute("data-status", /healthy|degraded|down/);

    const stillUnknown = page.locator(
      '[data-testid="status-dot"][data-status="unknown"] .nova-status-dot[data-animated="true"]',
    );
    await expect(stillUnknown).toHaveCount(0);
  });
});

/**
 * **AC-2**, from the browser's own context.
 *
 * The unit suite proves the client cannot be *written* to reach the bus or an
 * engine. This proves the deployed surface does not answer if something tries
 * anyway -- the two halves TDD 4A §9 asks for.
 */
test.describe("security boundaries", () => {
  test("the browser cannot reach an engine's internal surface", async ({ page }) => {
    await page.goto("/");

    const internal = await page.evaluate(async () => {
      try {
        const response = await fetch("/internal/health", { credentials: "include" });
        return { ok: response.ok, status: response.status };
      } catch (error) {
        return { ok: false, status: -1, error: String(error) };
      }
    });

    // Whatever answers the page's own origin, it must not be an engine's
    // internal health surface reporting success (doc 11 §3).
    expect(internal.ok).toBe(false);
  });

  test("the browser cannot open a socket to the event bus", async ({ page }) => {
    await page.goto("/");

    const reachedBus = await page.evaluate(async () => {
      return await new Promise<boolean>((resolve) => {
        let socket: WebSocket;
        try {
          socket = new WebSocket("ws://localhost:4222");
        } catch {
          resolve(false);
          return;
        }
        const timer = setTimeout(() => {
          socket.close();
          resolve(false);
        }, 3000);
        socket.onopen = () => {
          clearTimeout(timer);
          socket.close();
          resolve(true);
        };
        socket.onerror = () => {
          clearTimeout(timer);
          resolve(false);
        };
        socket.onclose = () => {
          clearTimeout(timer);
          resolve(false);
        };
      });
    });

    expect(reachedBus).toBe(false);
  });
});
