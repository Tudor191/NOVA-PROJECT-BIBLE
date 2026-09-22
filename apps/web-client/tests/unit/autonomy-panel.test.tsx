import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GatewayError } from "../../src/entities/envelope";
import {
  PERMISSION_CATEGORIES,
  POLICY_EFFECTS,
  isAutonomyUnavailable,
  isDecisionConflict,
  isRefused,
} from "../../src/entities/autonomy";
import { AutonomyPanel } from "../../src/panels/autonomy/AutonomyPanel";

/**
 * The Autonomy panel (Phase 4D) against the surface `autonomy-engine`
 * actually built.
 *
 * Four properties get the attention here, because each is one an ordinary
 * implementation gets wrong in the dangerous direction:
 *
 * 1. **An unknown trust score renders as "insufficient evidence", never as
 *    `0`.** Zero corrections would read as *perfect* trust -- the exactly
 *    inverted claim.
 * 2. **Level 2 is visible and disabled**, not hidden and not selectable.
 * 3. **No optimistic mutation.** A decision the server refuses must never
 *    appear as a decision. This is what AC-5 measures.
 * 4. **Nothing is fabricated.** An empty inbox says why it is empty.
 */

function wrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

/** Mirrors `createQueryClient`, `staleTime: Infinity` included. */
function client(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: Infinity, refetchOnMount: false },
      mutations: { retry: false },
    },
  });
}

const SUGGESTION = "11111111-1111-4111-8111-111111111111";
const POLICY = "22222222-2222-4222-8222-222222222222";

const envelope = (data: unknown) => ({
  data,
  meta: {
    correlation_id: "4f1d9c2a-0000-4000-8000-000000000000",
    generated_at: "2026-09-13T12:00:00.000Z",
  },
  error: null,
});

const failure = (code: string, message: string, upstreamStatus: number | null = null) => ({
  data: null,
  meta: {
    correlation_id: "4f1d9c2a-0000-4000-8000-000000000000",
    generated_at: "2026-09-13T12:00:00.000Z",
  },
  error: { code, message, upstream_status: upstreamStatus },
});

function levelView(overrides: Record<string, unknown> = {}) {
  return {
    level: 0,
    name: "Observation Only",
    updated_at: null,
    configured: false,
    options: [
      { level: 0, name: "Observation Only", selectable: true, note: null },
      { level: 1, name: "Suggestive", selectable: true, note: null },
      // Level 2 became selectable in **4F.5** (X-1): `SELECTABLE_LEVELS` gained
      // `ASSISTED`, so the engine now reports it with `selectable: true` and no
      // note. This stub mirrors the engine; a stub left at the 4D state would
      // make every assertion below pass against a state that no longer exists.
      //
      // *(This entry read `selectable: false, note: "enabled in a later
      // milestone"` until 2026-09-21, matching 4D decision D-1. That was
      // correct for 4D and is now stale; preserved per protocol §0.3.4.)*
      { level: 2, name: "Assisted", selectable: true, note: null },
    ],
    ...overrides,
  };
}

function trust(status = "no_data", score: number | null = null) {
  return PERMISSION_CATEGORIES.map((category) => ({
    category,
    score,
    status,
    evidence_count: 0,
    detail: status === "unavailable" ? "digital-twin-engine exposes no read surface" : null,
  }));
}

function permissions(granted: Record<string, string> = {}) {
  return {
    categories: PERMISSION_CATEGORIES.map((category) => ({
      category,
      max_risk: granted[category] ?? null,
      requires_approval_above: null,
      granted: category in granted,
      updated_at: null,
    })),
  };
}

function overview(overrides: Record<string, unknown> = {}) {
  return {
    level: levelView(),
    trust: trust(),
    permissions: permissions(),
    proposed_count: 0,
    policy_count: 0,
    degraded: [],
    ...overrides,
  };
}

function gates(overrides: Record<string, unknown> = {}) {
  return {
    denied: false,
    gate: null,
    reason: null,
    requires_approval: true,
    policy_checks: [],
    ...overrides,
  };
}

function suggestion(overrides: Record<string, unknown> = {}) {
  return {
    id: SUGGESTION,
    category: "modify",
    risk: "low",
    title: "archive three stale branches",
    detail: "",
    status: "proposed",
    created_at: "2026-09-13T11:00:00.000Z",
    decided_at: null,
    gates: gates(),
    ...overrides,
  };
}

function policy(overrides: Record<string, unknown> = {}) {
  return {
    id: POLICY,
    name: "never delete files automatically",
    effect: "deny",
    match_category: "delete",
    match_min_risk: null,
    match_capability_class: null,
    enabled: true,
    created_at: "2026-09-13T10:00:00.000Z",
    updated_at: "2026-09-13T10:00:00.000Z",
    ...overrides,
  };
}

/** Routes a stubbed `fetch` by path, so one test can serve several endpoints. */
function stubFetch(routes: Record<string, { status?: number; body: unknown }>) {
  const calls: { url: string; method: string }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: unknown, init?: RequestInit) => {
      const url = String(input);
      calls.push({ url, method: init?.method ?? "GET" });
      // Longest match first, so `/v1/autonomy/suggestions` wins over
      // `/v1/autonomy`.
      const match = Object.keys(routes)
        .sort((a, b) => b.length - a.length)
        .find((path) => url.includes(path));
      if (match === undefined) {
        return new Response(JSON.stringify(failure("not_found", `no stub for ${url}`)), {
          status: 404,
          headers: { "content-type": "application/json" },
        });
      }
      const route = routes[match];
      return new Response(JSON.stringify(route.body), {
        status: route.status ?? 200,
        headers: { "content-type": "application/json" },
      });
    }),
  );
  return calls;
}

function baseRoutes(over: Record<string, unknown> = {}) {
  return {
    "/v1/autonomy/suggestions": { body: envelope({ items: [], next_cursor: null }) },
    "/v1/autonomy/policies": { body: envelope([]) },
    "/v1/autonomy": { body: envelope(overview(over)) },
  } as Record<string, { status?: number; body: unknown }>;
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// --- the four widgets -------------------------------------------------------

describe("AutonomyPanel widgets", () => {
  it("renders all four widgets", async () => {
    stubFetch(baseRoutes());
    render(<AutonomyPanel />, { wrapper: wrapper(client()) });

    expect(await screen.findByTestId("autonomy-level")).toBeTruthy();
    expect(screen.getByTestId("autonomy-trust")).toBeTruthy();
    expect(screen.getByTestId("autonomy-policies")).toBeTruthy();
    expect(screen.getByTestId("autonomy-suggestions")).toBeTruthy();
  });

  it("names an unconfigured level as the default rather than a choice", async () => {
    stubFetch(baseRoutes());
    render(<AutonomyPanel />, { wrapper: wrapper(client()) });

    const current = await screen.findByTestId("current-level");
    expect(current.textContent).toContain("Observation Only");
    expect(current.textContent).toContain("never configured");
  });
});

// --- Level 2: present and selectable (4F.5, X-1) ----------------------------
//
// *(This block read "**Level 2: present and disabled (decision D-1)**" and
// asserted the disabled attribute and the "later milestone" note until
// 2026-09-21. 4F.5 makes Level 2 selectable, so the control is **retargeted to
// the new expected state rather than removed** — it still pins exactly what
// the panel does with level 2, and the stub above was corrected in the same
// pass so this stops asserting a state the engine no longer reports.
// Preserved per protocol §0.3.4.)*

describe("the level selector", () => {
  it("offers levels 0, 1 and 2, with level 2 now selectable", async () => {
    stubFetch(baseRoutes());
    render(<AutonomyPanel />, { wrapper: wrapper(client()) });

    const options = await screen.findAllByTestId("level-option");
    expect(options).toHaveLength(3);
    // All three are selectable now, and — the retargeted half of the old
    // assertion — **nothing** is left rendering the disabled state.
    expect(screen.getAllByTestId("level-select")).toHaveLength(3);
    expect(screen.queryByTestId("level-disabled")).toBeNull();
    expect(screen.queryByTestId("level-note")).toBeNull();

    // Level 2 specifically: present, named, and enabled rather than merely
    // absent from the disabled set.
    const assisted = options.find((option) =>
      option.textContent?.includes("Assisted"),
    );
    expect(assisted).toBeTruthy();
    const button = assisted!.querySelector("[data-testid='level-select']");
    expect(button).toBeTruthy();
    expect(button!.hasAttribute("disabled")).toBe(false);
  });

  it("does not render levels 3 to 5 at all", async () => {
    stubFetch(baseRoutes());
    render(<AutonomyPanel />, { wrapper: wrapper(client()) });

    const names = (await screen.findAllByTestId("level-name")).map((node) => node.textContent);
    expect(names.join(" ")).not.toContain("Supervised");
    expect(names.join(" ")).not.toContain("Highly Autonomous");
    expect(names.join(" ")).not.toContain("Full Organizational");
  });

  it("shows the server's reason when a level is refused, and does not clamp", async () => {
    const routes = baseRoutes();
    routes["/v1/autonomy/level"] = {
      status: 422,
      body: failure("http_error", "autonomy level 2 (Assisted) is defined but not enabled"),
    };
    stubFetch(routes);
    render(<AutonomyPanel />, { wrapper: wrapper(client()) });

    await userEvent.click((await screen.findAllByTestId("level-select"))[1]);
    const error = await screen.findByTestId("level-error");
    expect(error.textContent).toContain("not enabled");
    // The displayed level did not silently change to something else.
    expect(screen.getByTestId("current-level").textContent).toContain("Observation Only");
  });
});

// --- trust: `null` is never a number ----------------------------------------

describe("trust scores", () => {
  it("renders an unknown score as insufficient evidence, never as zero", async () => {
    stubFetch(baseRoutes());
    render(<AutonomyPanel />, { wrapper: wrapper(client()) });

    const values = (await screen.findAllByTestId("trust-value")).map((n) => n.textContent);
    expect(values).toHaveLength(10);
    expect(values.every((value) => value === "insufficient evidence")).toBe(true);
    expect(values).not.toContain("0");
    expect(values).not.toContain("0.00");
  });

  it("distinguishes an unavailable source from no data yet", async () => {
    stubFetch(baseRoutes({ trust: trust("unavailable"), degraded: ["conversational_trust"] }));
    render(<AutonomyPanel />, { wrapper: wrapper(client()) });

    const values = (await screen.findAllByTestId("trust-value")).map((n) => n.textContent);
    expect(values.every((value) => value === "unavailable")).toBe(true);
    expect(screen.getByTestId("trust-degraded").textContent).toContain("could not be read");
  });

  it("renders a real score as a number", async () => {
    stubFetch(baseRoutes({ trust: trust("available", 0.75) }));
    render(<AutonomyPanel />, { wrapper: wrapper(client()) });

    const values = (await screen.findAllByTestId("trust-value")).map((n) => n.textContent);
    expect(values.every((value) => value === "0.75")).toBe(true);
  });

  it("scores every one of Bible Part 14's ten categories", async () => {
    stubFetch(baseRoutes());
    render(<AutonomyPanel />, { wrapper: wrapper(client()) });

    const categories = (await screen.findAllByTestId("trust-category")).map((n) => n.textContent);
    expect(categories).toEqual([...PERMISSION_CATEGORIES]);
  });
});

// --- the permission matrix --------------------------------------------------

describe("the permission matrix", () => {
  it("shows all ten categories, including the ungranted ones", async () => {
    stubFetch(baseRoutes({ permissions: permissions({ read: "moderate" }) }));
    render(<AutonomyPanel />, { wrapper: wrapper(client()) });

    const rows = await screen.findAllByTestId("permission-grant");
    expect(rows).toHaveLength(10);
    const ceilings = screen.getAllByTestId("permission-ceiling").map((n) => n.textContent);
    expect(ceilings[0]).toBe("moderate");
    expect(ceilings.filter((c) => c === "no autonomous authority")).toHaveLength(9);
  });
});

// --- the policy editor ------------------------------------------------------

describe("the policy editor", () => {
  it("offers deny and require_approval only -- there is no allow effect", async () => {
    stubFetch(baseRoutes());
    render(<AutonomyPanel />, { wrapper: wrapper(client()) });

    const select = (await screen.findByTestId("policy-effect")) as HTMLSelectElement;
    expect([...select.options].map((option) => option.value)).toEqual([...POLICY_EFFECTS]);
    expect([...select.options].map((option) => option.value)).not.toContain("allow");
  });

  it("says an empty policy set is not permissive", async () => {
    stubFetch(baseRoutes());
    render(<AutonomyPanel />, { wrapper: wrapper(client()) });

    const empty = await screen.findByTestId("policies-empty");
    expect(empty.textContent).toContain("not permissive");
  });

  it("renders stored policies", async () => {
    const routes = baseRoutes();
    routes["/v1/autonomy/policies"] = { body: envelope([policy()]) };
    stubFetch(routes);
    render(<AutonomyPanel />, { wrapper: wrapper(client()) });

    expect((await screen.findByTestId("policy-label")).textContent).toContain(
      "never delete files automatically",
    );
    expect(screen.getByTestId("policy-effect-value").textContent).toBe("deny");
  });
});

// --- AC-5: the suggestion inbox ---------------------------------------------

describe("the suggestion inbox (AC-5)", () => {
  it("renders a healthy empty state that names why it is empty", async () => {
    stubFetch(baseRoutes());
    render(<AutonomyPanel />, { wrapper: wrapper(client()) });

    const empty = await screen.findByTestId("suggestions-empty");
    expect(empty.textContent).toContain("no suggestion source is enabled");
    expect(screen.queryByTestId("suggestion")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("renders a proposed suggestion with its risk and which gates it passed", async () => {
    const routes = baseRoutes();
    routes["/v1/autonomy/suggestions"] = {
      body: envelope({ items: [suggestion()], next_cursor: null }),
    };
    stubFetch(routes);
    render(<AutonomyPanel />, { wrapper: wrapper(client()) });

    expect((await screen.findByTestId("suggestion-title")).textContent).toContain(
      "archive three stale branches",
    );
    expect(screen.getByTestId("suggestion-risk").textContent).toBe("low");
    expect(screen.getByTestId("suggestion-status").textContent).toContain("proposed");
    expect(screen.getByTestId("gate-passed")).toBeTruthy();
  });

  it("executes nothing on render -- it only reads", async () => {
    const routes = baseRoutes();
    routes["/v1/autonomy/suggestions"] = {
      body: envelope({ items: [suggestion()], next_cursor: null }),
    };
    const calls = stubFetch(routes);
    render(<AutonomyPanel />, { wrapper: wrapper(client()) });
    await screen.findByTestId("suggestion");

    expect(calls.every((call) => call.method === "GET")).toBe(true);
  });

  it("requires an explicit approval, and approval executes nothing", async () => {
    const routes = baseRoutes();
    routes["/v1/autonomy/suggestions"] = {
      body: envelope({ items: [suggestion()], next_cursor: null }),
    };
    routes[`/v1/autonomy/suggestions/${SUGGESTION}/decide`] = {
      body: envelope({
        suggestion: suggestion({ status: "approved", decided_at: "2026-09-13T12:00:00.000Z" }),
        outcome: "propose",
        executed: false,
      }),
    };
    const calls = stubFetch(routes);
    render(<AutonomyPanel />, { wrapper: wrapper(client()) });

    await userEvent.click(await screen.findByTestId("suggestion-approve"));

    await waitFor(() => {
      expect(calls.some((call) => call.method === "POST" && call.url.includes("/decide"))).toBe(
        true,
      );
    });
    // No call to any execution surface -- `/v1/action` in particular.
    expect(calls.some((call) => call.url.includes("/v1/action"))).toBe(false);
  });

  it("does not mark a suggestion decided when the server refuses", async () => {
    // The no-optimistic-mutation rule, which is what AC-5 turns on: a
    // conflict must leave the inbox showing the suggestion still proposed.
    const routes = baseRoutes();
    routes["/v1/autonomy/suggestions"] = {
      body: envelope({ items: [suggestion()], next_cursor: null }),
    };
    routes[`/v1/autonomy/suggestions/${SUGGESTION}/decide`] = {
      status: 409,
      body: failure("http_error", "was already decided (rejected); the first decision stands"),
    };
    stubFetch(routes);
    render(<AutonomyPanel />, { wrapper: wrapper(client()) });

    await userEvent.click(await screen.findByTestId("suggestion-approve"));

    const error = await screen.findByTestId("decision-error");
    expect(error.textContent).toContain("first decision stands");
    expect(screen.getByTestId("suggestion-status").textContent).toContain("proposed");
  });

  it("cannot approve a suggestion a gate denies", async () => {
    const routes = baseRoutes();
    routes["/v1/autonomy/suggestions"] = {
      body: envelope({
        items: [
          suggestion({
            gates: gates({
              denied: true,
              gate: "permission",
              reason: "no permission grant for category=modify",
            }),
          }),
        ],
        next_cursor: null,
      }),
    };
    stubFetch(routes);
    render(<AutonomyPanel />, { wrapper: wrapper(client()) });

    const approve = await screen.findByTestId("suggestion-approve");
    expect(approve.hasAttribute("disabled")).toBe(true);
    expect(screen.getByTestId("gate-denied").textContent).toContain("permission");
  });

  it("shows every policy that was consulted, not only those that fired", async () => {
    const routes = baseRoutes();
    routes["/v1/autonomy/suggestions"] = {
      body: envelope({
        items: [
          suggestion({
            gates: gates({
              policy_checks: [
                { policy_id: POLICY, name: "ask first", effect: "require_approval", matched: true },
                { policy_id: "x", name: "unrelated", effect: "deny", matched: false },
              ],
            }),
          }),
        ],
        next_cursor: null,
      }),
    };
    stubFetch(routes);
    render(<AutonomyPanel />, { wrapper: wrapper(client()) });

    const checks = await screen.findAllByTestId("policy-check");
    expect(checks).toHaveLength(2);
    expect(checks[1].textContent).toContain("consulted, did not match");
  });
});

// --- no polling, and a degraded engine --------------------------------------

describe("freshness and degradation", () => {
  it("does not poll", async () => {
    const calls = stubFetch(baseRoutes());
    render(<AutonomyPanel />, { wrapper: wrapper(client()) });
    await screen.findByTestId("autonomy-level");

    const initial = calls.length;
    await new Promise((resolve) => setTimeout(resolve, 250));
    expect(calls.length).toBe(initial);
  });

  it("reports an unreachable engine as unreachable, not as autonomy switched off", async () => {
    stubFetch({
      "/v1/autonomy": {
        status: 503,
        body: failure("upstream_unavailable", "autonomy-engine unreachable", 503),
      },
    });
    render(<AutonomyPanel />, { wrapper: wrapper(client()) });

    const notice = await screen.findByRole("alert");
    expect(notice.textContent).toContain("could not be reached");
    expect(notice.textContent).toContain("not the same as autonomy being switched off");
    expect(screen.queryByTestId("level-option")).toBeNull();
  });
});

// --- the error predicates ----------------------------------------------------

describe("error predicates", () => {
  /** Real `GatewayError`s -- the predicates are `instanceof` checks, so a
   *  shape-alike object would pass the test while failing in production. */
  const gatewayError = (status: number, upstream: number | null = null) =>
    new GatewayError("http_error", "refused", status, null, upstream);

  it("classifies the statuses the engine actually returns", () => {
    expect(isDecisionConflict(gatewayError(409))).toBe(true);
    expect(isRefused(gatewayError(422))).toBe(true);
    expect(isAutonomyUnavailable(gatewayError(503))).toBe(true);
    expect(isAutonomyUnavailable(gatewayError(502, 503))).toBe(true);
  });

  it("does not classify an unrelated failure as one of them", () => {
    expect(isDecisionConflict(gatewayError(404))).toBe(false);
    expect(isRefused(gatewayError(409))).toBe(false);
    expect(isAutonomyUnavailable(gatewayError(404))).toBe(false);
    expect(isDecisionConflict(new Error("network down"))).toBe(false);
    expect(isRefused(new Error("network down"))).toBe(false);
    expect(isAutonomyUnavailable(new Error("network down"))).toBe(false);
  });
});
