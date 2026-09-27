// @vitest-environment node
//
// Route declarations and the panel switcher, checked without rendering. The
// router is built at module scope, so its shape is a static fact; asserting it
// here catches a panel that exists but is unreachable, which no panel's own
// test can see.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { router } from "../../src/app/router";

/**
 * Two failure modes this file exists for, both of which look fine everywhere
 * else:
 *
 * 1. **A panel with no route.** `AgentsPanel` renders correctly in its own
 *    test and is unreachable in the application.
 * 2. **A route with no navigation entry.** Reachable by typing the URL, and
 *    invisible to the operator.
 *
 * Adding a panel means touching two files that do not import each other, so
 * the agreement between them is exactly the kind of thing that silently
 * stops holding.
 */

const APP_SHELL = fileURLToPath(new URL("../../src/app/AppShell.tsx", import.meta.url));
const ROUTER = fileURLToPath(new URL("../../src/app/router.tsx", import.meta.url));

/** The `PANELS` switcher list, read from source rather than exported for a test. */
function navPaths(): string[] {
  const source = readFileSync(APP_SHELL, "utf8");
  const block = source.match(/const PANELS = \[([\s\S]*?)\] as const;/);
  if (!block) {
    throw new Error(
      `Could not find PANELS in ${APP_SHELL}. If the shell changed shape, fix ` +
        `this parser rather than deleting the test.`,
    );
  }
  return [...block[1].matchAll(/path:\s*"([^"]+)"/g)].map((match) => match[1]);
}

const EXPECTED_PANELS = [
  "/",
  "/planning",
  "/reasoning",
  "/capabilities",
  "/approvals",
  "/events",
  "/health",
  "/agents",
  "/autonomy",
  "/digital-twin",
  // Phase 4F.7 (TDD 4F.7 §16 P-19): eleven panels.
  "/cognitive-state",
] as const;

describe("panel routing", () => {
  it("really did read a non-trivial nav list", () => {
    // Anti-decoration control: a parser returning [] would make the
    // comparisons below pass vacuously.
    expect(navPaths().length).toBeGreaterThanOrEqual(7);
    expect(navPaths()).toContain("/health");
  });

  it("declares a route for every panel, including Agents", () => {
    const declared = Object.keys(router.routesById);
    for (const path of EXPECTED_PANELS) {
      const id = path === "/" ? "/shell/" : `/shell${path}`;
      expect(declared).toContain(id);
    }
  });

  it("gives every route a navigation entry, and vice versa", () => {
    expect([...navPaths()].sort()).toEqual([...EXPECTED_PANELS].sort());
  });

  it("adds each new panel by appending, never by rewriting the list", () => {
    // 4C.2f appended Agents, 4D Autonomy, 4E Digital Twin. A slice that
    // rewrote the list could drop a panel and no other test here would
    // notice. The count is derived rather than literal so the next panel
    // updates one place.
    const nav = navPaths();
    for (const path of EXPECTED_PANELS) {
      expect(nav).toContain(path);
    }
    expect(nav).toHaveLength(EXPECTED_PANELS.length);
    // The order is the order panels were added, so a rewrite that reordered
    // them would move the operator's tabs around without anything failing.
    expect(nav.indexOf("/agents")).toBeLessThan(nav.indexOf("/autonomy"));
    expect(nav.indexOf("/autonomy")).toBeLessThan(nav.indexOf("/digital-twin"));
    expect(nav.indexOf("/digital-twin")).toBeLessThan(nav.indexOf("/cognitive-state"));
    expect(nav).toHaveLength(11);
  });

  it("lazily loads the Agents panel like every other one", () => {
    // Each panel pulls its own entity module; bundling them all into the
    // initial download would make the Conversation panel -- the one AC-1
    // measures -- wait for panels the operator may never open.
    const source = readFileSync(ROUTER, "utf8");
    const agents = source.match(/const agentsRoute = createRoute\(\{[\s\S]*?\}\);/);
    expect(agents).not.toBeNull();
    expect(agents?.[0]).toMatch(/lazyRouteComponent/);
    expect(agents?.[0]).toMatch(/panels\/agents\/AgentsPanel/);
  });

  it("nests Agents under the shell so the socket is not remounted", () => {
    // A route outside the shell would remount `RealtimeProvider`, dropping
    // the WebSocket and losing every frame during the reconnect.
    expect(Object.keys(router.routesById)).toContain("/shell/agents");
  });

  it("lazily loads the Autonomy panel like every other one", () => {
    const source = readFileSync(ROUTER, "utf8");
    const autonomy = source.match(/const autonomyRoute = createRoute\(\{[\s\S]*?\}\);/);
    expect(autonomy).not.toBeNull();
    expect(autonomy?.[0]).toMatch(/lazyRouteComponent/);
    expect(autonomy?.[0]).toMatch(/panels\/autonomy\/AutonomyPanel/);
  });

  it("nests Autonomy under the shell too", () => {
    // It subscribes to nothing itself (decision D-4D-1), but it still must
    // not remount the provider the other seven panels depend on.
    expect(Object.keys(router.routesById)).toContain("/shell/autonomy");
  });

  it("lazily loads the Digital Twin panel like every other one", () => {
    const source = readFileSync(ROUTER, "utf8");
    const twin = source.match(/const digitalTwinRoute = createRoute\(\{[\s\S]*?\}\);/);
    expect(twin).not.toBeNull();
    expect(twin?.[0]).toMatch(/lazyRouteComponent/);
    expect(twin?.[0]).toMatch(/panels\/digitalTwin\/DigitalTwinPanel/);
  });

  it("nests Digital Twin under the shell so the socket is not remounted", () => {
    expect(Object.keys(router.routesById)).toContain("/shell/digital-twin");
  });

  it("lazily loads the Cognitive State panel like every other one", () => {
    const source = readFileSync(ROUTER, "utf8");
    const cognitive = source.match(/const cognitiveStateRoute = createRoute\(\{[\s\S]*?\}\);/);
    expect(cognitive).not.toBeNull();
    expect(cognitive?.[0]).toMatch(/lazyRouteComponent/);
    expect(cognitive?.[0]).toMatch(/panels\/cognitiveState\/CognitiveStatePanel/);
  });

  it("nests Cognitive State under the shell so the socket is not remounted", () => {
    expect(Object.keys(router.routesById)).toContain("/shell/cognitive-state");
  });
});
