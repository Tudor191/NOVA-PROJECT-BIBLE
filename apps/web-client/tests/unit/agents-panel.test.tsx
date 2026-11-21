import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { isInvalidCursor, isRegistryUnavailable, isUnknownInstance } from "../../src/entities/agents";
import { AgentsPanel } from "../../src/panels/agents/AgentsPanel";

/**
 * The Agents panel (Phase 4C, 4C.2f) against the surface 4C.2c actually
 * built.
 *
 * The empty case gets more attention here than in any other panel, and
 * deliberately: with no model provider configured, **zero instances is the
 * steady state**, not an edge case. A panel that rendered that as broken --
 * or filled it with placeholder agents to look alive -- would misreport the
 * system every single time it was opened. Master scope §1.1 defers AC-4's
 * instance clauses for exactly this reason.
 *
 * The other rule under test is decision D-1's: `200 []` and `503` are
 * different answers about the Registry and must never look the same.
 */

function wrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
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

const INSTANCE = "44444444-4444-4444-8444-444444444444";
const PACKAGE = "66666666-6666-4666-8666-666666666666";

const envelope = (data: unknown) => ({
  data,
  meta: {
    correlation_id: "4f1d9c2a-0000-4000-8000-000000000000",
    generated_at: "2026-09-10T12:00:00.000Z",
  },
  error: null,
});

const failure = (code: string, message: string, upstreamStatus: number | null = null) => ({
  data: null,
  meta: {
    correlation_id: "4f1d9c2a-0000-4000-8000-000000000000",
    generated_at: "2026-09-10T12:00:00.000Z",
  },
  error: { code, message, upstream_status: upstreamStatus },
});

function agentPackage(overrides: Record<string, unknown> = {}) {
  return {
    id: PACKAGE,
    manifest_id: "research-agent",
    category: "research",
    version: "0.1.0",
    health_status: "healthy",
    ...overrides,
  };
}

function agentInstance(overrides: Record<string, unknown> = {}) {
  return {
    id: INSTANCE,
    agent_package_id: PACKAGE,
    category: "research",
    execution_backend: "inprocess",
    status: "completed",
    health_status: "healthy",
    assigned_task_node_id: "33333333-3333-4333-8333-333333333333",
    supervisor_id: null,
    started_at: "2026-09-10T11:59:00.000Z",
    ...overrides,
  };
}

function supervisor(overrides: Record<string, unknown> = {}) {
  return {
    category: "engineering",
    instance_ids: [INSTANCE],
    membership_is_derived: true,
    ...overrides,
  };
}

/** The degradation notice's title, which is what names the failing upstream. */
function noticeTitle(notice: HTMLElement): string {
  return notice.querySelector(".nova-degradation-title")?.textContent ?? "";
}

function overview(overrides: Record<string, unknown> = {}) {
  return { packages: [], instances: [], supervisors: [], ...overrides };
}

/** Routes a stubbed `fetch` by path, so one test can serve several endpoints. */
function stubFetch(routes: Record<string, { status?: number; body: unknown }>) {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: unknown) => {
      const url = String(input);
      calls.push(url);
      const match = Object.keys(routes).find((path) => url.includes(path));
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

beforeEach(() => {
  vi.unstubAllGlobals();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// --- the provider-free steady state ---------------------------------------

describe("AgentsPanel, provider-free", () => {
  it("renders a healthy empty-instance state rather than an error", async () => {
    stubFetch({ "/v1/agents": { body: envelope(overview({ packages: [agentPackage()] })) } });
    render(<AgentsPanel />, { wrapper: wrapper(client()) });

    expect(await screen.findByTestId("instances-empty")).toBeTruthy();
    // Not an error, and not a "loading forever" state.
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByTestId("panel-loading")).toBeNull();
  });

  it("fabricates no running agents", async () => {
    stubFetch({ "/v1/agents": { body: envelope(overview({ packages: [agentPackage()] })) } });
    render(<AgentsPanel />, { wrapper: wrapper(client()) });

    await screen.findByTestId("instances-empty");
    expect(screen.queryAllByTestId("agent-instance")).toHaveLength(0);
  });

  it("still shows installed packages when nothing is running", async () => {
    // Packages are real without a provider: Registry discovers them from
    // disk at startup. An empty instance list must not blank the panel.
    stubFetch({ "/v1/agents": { body: envelope(overview({ packages: [agentPackage()] })) } });
    render(<AgentsPanel />, { wrapper: wrapper(client()) });

    expect(await screen.findByTestId("package-name")).toBeTruthy();
    expect(screen.getByTestId("package-name").textContent).toBe("research-agent");
  });
});

// --- rendering ------------------------------------------------------------

describe("AgentsPanel rendering", () => {
  it("renders package identity, version, health and category", async () => {
    stubFetch({ "/v1/agents": { body: envelope(overview({ packages: [agentPackage()] })) } });
    render(<AgentsPanel />, { wrapper: wrapper(client()) });

    expect((await screen.findByTestId("package-name")).textContent).toBe("research-agent");
    expect(screen.getByTestId("package-version").textContent).toBe("v0.1.0");
    expect(screen.getByTestId("package-category").textContent).toBe("research");
    const dot = screen
      .getAllByTestId("status-dot")
      .find((el) => el.getAttribute("data-instrument") === "package-health");
    expect(dot?.getAttribute("data-status")).toBe("healthy");
  });

  it("falls back to the package id when the manifest declares no name", async () => {
    stubFetch({
      "/v1/agents": { body: envelope(overview({ packages: [agentPackage({ manifest_id: null })] })) },
    });
    render(<AgentsPanel />, { wrapper: wrapper(client()) });

    expect((await screen.findByTestId("package-name")).textContent).toBe(PACKAGE);
  });

  it("renders instance status, backend and start time", async () => {
    stubFetch({
      "/v1/agents": { body: envelope(overview({ instances: [agentInstance()] })) },
    });
    render(<AgentsPanel />, { wrapper: wrapper(client()) });

    expect((await screen.findByTestId("instance-status")).textContent).toBe("completed");
    expect(screen.getByTestId("instance-category").textContent).toBe("research");
    expect(screen.getByTestId("instance-backend").textContent).toBe("inprocess");
    expect(screen.getByTestId("instance-started").textContent).toBe("2026-09-10T11:59:00.000Z");
  });

  it("shows an unreported instance health as unknown, never as healthy", async () => {
    stubFetch({
      "/v1/agents": {
        body: envelope(overview({ instances: [agentInstance({ health_status: "unknown" })] })),
      },
    });
    render(<AgentsPanel />, { wrapper: wrapper(client()) });

    await screen.findByTestId("agent-instance");
    const dot = screen
      .getAllByTestId("status-dot")
      .find((el) => el.getAttribute("data-instrument") === "instance-health");
    expect(dot?.getAttribute("data-status")).toBe("unknown");
  });

  it("renders the supervisor topology and discloses that membership is derived", async () => {
    stubFetch({
      "/v1/agents": {
        body: envelope(overview({ instances: [agentInstance()], supervisors: [supervisor()] })),
      },
    });
    render(<AgentsPanel />, { wrapper: wrapper(client()) });

    expect((await screen.findByTestId("supervisor-category")).textContent).toBe("engineering");
    expect(screen.getByTestId("supervisor-count").textContent).toBe("1 instance");
    // The Kernel marks its own answer as derived; the panel must repeat that
    // rather than presenting a construction as a recorded relationship.
    expect(screen.getByTestId("supervisor-derived")).toBeTruthy();
  });

  it("animates nothing: no status dot pulses on a standing reading", async () => {
    stubFetch({
      "/v1/agents": {
        body: envelope(overview({ packages: [agentPackage()], instances: [agentInstance()] })),
      },
    });
    render(<AgentsPanel />, { wrapper: wrapper(client()) });

    await screen.findByTestId("agent-instance");
    for (const dot of screen.getAllByTestId("status-dot")) {
      expect(dot.querySelector("[data-animated='true']")).toBeNull();
    }
  });
});

// --- loading, empty, error, degraded --------------------------------------

describe("AgentsPanel states", () => {
  it("shows a loading state before the first answer", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    render(<AgentsPanel />, { wrapper: wrapper(client()) });

    expect(screen.getByTestId("panel-loading")).toBeTruthy();
  });

  it("distinguishes a healthy empty Registry from a degraded one", async () => {
    stubFetch({ "/v1/agents": { body: envelope(overview()) } });
    render(<AgentsPanel />, { wrapper: wrapper(client()) });

    // 200 + [] -- the Registry answered and holds nothing.
    expect(await screen.findByTestId("panel-empty")).toBeTruthy();
    expect(screen.queryByText(/could not be reached/i)).toBeNull();
  });

  it("renders a 503 as a named Registry outage, not as an empty install list", async () => {
    stubFetch({
      "/v1/agents": {
        status: 503,
        body: failure("upstream_unavailable", "The Agent Registry could not be reached.", 503),
      },
    });
    render(<AgentsPanel />, { wrapper: wrapper(client()) });

    const notice = await screen.findByTestId("degradation-notice");
    // The **title** is what distinguishes the two paths. Matching on the body
    // text would not: the gateway's own error message contains these words
    // too, so a panel that had lost its D-1 branch entirely and fallen
    // through to the generic notice would still satisfy a body-text match.
    expect(noticeTitle(notice)).toBe("The Agent Registry could not be reached");
    // Decision D-1: no fallback package data is invented to fill the gap, and
    // the "reachable, holds nothing" wording must not appear either.
    expect(screen.queryAllByTestId("agent-package")).toHaveLength(0);
    expect(screen.queryByTestId("packages-empty")).toBeNull();
    expect(screen.queryByTestId("panel-empty")).toBeNull();
  });

  it("renders a generic upstream failure through the shared degradation notice", async () => {
    stubFetch({
      "/v1/agents": { status: 502, body: failure("upstream_unavailable", "kernel is down", 502) },
    });
    render(<AgentsPanel />, { wrapper: wrapper(client()) });

    const notice = await screen.findByTestId("degradation-notice");
    expect(noticeTitle(notice)).toBe("This panel could not read its data");
  });
});

// --- instance detail and activity -----------------------------------------

describe("AgentsPanel activity", () => {
  it("reads a known instance with no activity as a successful empty page", async () => {
    stubFetch({
      "/v1/agents/": { body: envelope({ items: [], next_cursor: null }) },
      "/v1/agents": { body: envelope(overview({ instances: [agentInstance()] })) },
    });
    render(<AgentsPanel />, { wrapper: wrapper(client()) });

    await userEvent.click(await screen.findByRole("button", { name: /show activity/i }));

    expect(await screen.findByTestId("panel-empty")).toBeTruthy();
    // Empty is not "unknown instance".
    expect(screen.queryByTestId("activity-unknown-instance")).toBeNull();
  });

  it("renders activity rows with their kind and correlation id", async () => {
    stubFetch({
      "/v1/agents/": {
        body: envelope({
          items: [
            {
              id: "77777777-7777-4777-8777-777777777777",
              agent_instance_id: INSTANCE,
              occurred_at: "2026-09-10T11:59:30.000Z",
              kind: "completed",
              correlation_id: "88888888-8888-4888-8888-888888888888",
              detail: { outcome: "success" },
            },
          ],
          next_cursor: null,
        }),
      },
      "/v1/agents": { body: envelope(overview({ instances: [agentInstance()] })) },
    });
    render(<AgentsPanel />, { wrapper: wrapper(client()) });

    await userEvent.click(await screen.findByRole("button", { name: /show activity/i }));

    expect((await screen.findByTestId("activity-kind")).textContent).toBe("completed");
    expect(screen.getByTestId("activity-at").textContent).toBe("2026-09-10T11:59:30.000Z");
  });

  it("renders a 404 as an unknown instance, distinct from an empty page", async () => {
    stubFetch({
      "/v1/agents/": {
        status: 404,
        body: failure("http_error", "No agent instance found", 404),
      },
      "/v1/agents": { body: envelope(overview({ instances: [agentInstance()] })) },
    });
    render(<AgentsPanel />, { wrapper: wrapper(client()) });

    await userEvent.click(await screen.findByRole("button", { name: /show activity/i }));

    expect(await screen.findByTestId("activity-unknown-instance")).toBeTruthy();
    expect(screen.queryByTestId("activity-row")).toBeNull();
  });

  it("follows the server's cursor and stops when it says there is no more", async () => {
    const row = (id: string) => ({
      id,
      agent_instance_id: INSTANCE,
      occurred_at: "2026-09-10T11:59:30.000Z",
      kind: "dispatched",
      correlation_id: null,
      detail: {},
    });
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: unknown) => {
        const url = String(input);
        calls.push(url);
        let body: unknown;
        if (url.includes("/activity")) {
          body = url.includes("cursor=")
            ? envelope({ items: [row("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")], next_cursor: null })
            : envelope({
                items: [row("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")],
                next_cursor: "Y3Vyc29y",
              });
        } else {
          body = envelope(overview({ instances: [agentInstance()] }));
        }
        return new Response(JSON.stringify(body), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }),
    );
    render(<AgentsPanel />, { wrapper: wrapper(client()) });

    await userEvent.click(await screen.findByRole("button", { name: /show activity/i }));
    await screen.findByTestId("activity-row");

    // `next_cursor` non-null -> a way to ask for more exists.
    const more = await screen.findByRole("button", { name: /load older activity/i });
    await userEvent.click(more);

    await waitFor(() => expect(screen.getAllByTestId("activity-row")).toHaveLength(2));
    // The second request carried the server's cursor verbatim -- no offset,
    // no page number.
    expect(calls.some((url) => url.includes("cursor=Y3Vyc29y"))).toBe(true);
    expect(calls.every((url) => !url.includes("offset="))).toBe(true);
    // `next_cursor: null` on the last page removes the control entirely.
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: /load older activity/i })).toBeNull(),
    );
  });

  it("surfaces a rejected cursor instead of silently restarting at page one", async () => {
    stubFetch({
      "/v1/agents/": { status: 400, body: failure("http_error", "cursor is not decodable", 400) },
      "/v1/agents": { body: envelope(overview({ instances: [agentInstance()] })) },
    });
    render(<AgentsPanel />, { wrapper: wrapper(client()) });

    await userEvent.click(await screen.findByRole("button", { name: /show activity/i }));

    expect(await screen.findByText(/could not read its data/i)).toBeTruthy();
    expect(screen.queryByTestId("activity-row")).toBeNull();
  });
});

// --- error classifiers ----------------------------------------------------

describe("agent error classifiers", () => {
  it("classifies only the statuses they name", () => {
    const err = (status: number, upstream: number | null = null) =>
      new (class extends Error {
        code = "http_error";
        status = status;
        upstreamStatus = upstream;
        correlationId = null;
      })();

    // Non-GatewayError values must never be classified as a known condition.
    for (const classifier of [isRegistryUnavailable, isUnknownInstance, isInvalidCursor]) {
      expect(classifier(null)).toBe(false);
      expect(classifier(new Error("boom"))).toBe(false);
      expect(classifier(err(503))).toBe(false);
    }
  });
});
