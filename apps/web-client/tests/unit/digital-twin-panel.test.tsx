import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TWIN_DOMAINS } from "../../src/entities/digitalTwin";
import { DigitalTwinPanel } from "../../src/panels/digitalTwin/DigitalTwinPanel";

/**
 * The Digital Twin panel (Phase 4E) against the surface `digital-twin-engine`
 * actually built.
 *
 * Four properties get the attention, each one an ordinary implementation gets
 * wrong in the dangerous direction:
 *
 * 1. **A `null` gap renders as "no dated activity", never as `0`.** Zero would
 *    read as *active today* -- the exactly inverted claim, and the same trap
 *    2D-D's `null` trust score set.
 * 2. **Every unpopulated domain renders its machine-readable reason**, and the
 *    distinct reasons stay distinct: "no engine produces this yet" and "nothing
 *    has produced one yet" are different things to do next.
 * 3. **No optimistic mutation.** A re-derive that the server reports as still
 *    empty must not render as derived.
 * 4. **Nothing is fabricated.** No domain gets a default, a zero or an average.
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

const PROJECT = "33333333-3333-4333-8333-333333333333";

const envelope = (data: unknown) => ({
  data,
  meta: {
    correlation_id: "4f1d9c2a-0000-4000-8000-000000000000",
    generated_at: "2026-09-15T12:00:00.000Z",
  },
  error: null,
});

function domain(overrides: Record<string, unknown> = {}) {
  return {
    domain: "goals",
    state: "empty",
    reason: { code: "no_evidence_observed", detail: "No decision has been recorded yet." },
    evidence_count: 0,
    facts: {},
    unavailable_fields: ["priority", "progress"],
    derived_at: "2026-09-15T12:00:00.000Z",
    shipped_before_4e: false,
    ...overrides,
  };
}

/** All eleven, so the panel is always driven with Part 16's real list. */
function allDomains(overrides: Record<string, Record<string, unknown>> = {}) {
  return TWIN_DOMAINS.map((name) => domain({ domain: name, ...(overrides[name] ?? {}) }));
}

function project(overrides: Record<string, unknown> = {}) {
  return {
    project_id: PROJECT,
    memory_count: 3,
    memory_type_counts: { project: 2, episodic: 1 },
    first_activity_at: "2026-06-01T09:00:00.000Z",
    last_activity_at: "2026-08-05T09:00:00.000Z",
    gap_days: 41.2,
    derived_at: "2026-09-15T12:00:00.000Z",
    ...overrides,
  };
}

/** Route the panel's three GETs by path; each test supplies only what it varies. */
function mockFetch(routes: {
  domains?: unknown;
  projects?: unknown;
  projectDetail?: unknown;
  refresh?: unknown;
}) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    const body =
      method === "POST"
        ? (routes.refresh ?? domain())
        : url.includes("/domains/projects/")
          ? { project: routes.projectDetail ?? project() }
          : url.includes("/domains/projects")
            ? {
                domain: domain({ domain: "projects", state: "populated", reason: null,
                  evidence_count: 3, facts: { project_count: 1 } }),
                projects: routes.projects ?? [project()],
              }
            : { domains: routes.domains ?? allDomains() };
    return new Response(JSON.stringify(envelope(body)), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  });
}

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch({}));
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("DigitalTwinPanel", () => {
  it("renders all eleven Part 16 domains, not only the nine 4E adds", async () => {
    render(<DigitalTwinPanel />, { wrapper: wrapper(client()) });

    await waitFor(() => expect(screen.getAllByTestId("twin-domain")).toHaveLength(11));
    const names = screen.getAllByTestId("twin-domain").map((el) => el.dataset.domain);
    expect(names).toEqual([...TWIN_DOMAINS]);
  });

  it("renders a machine-readable reason for every unpopulated domain", async () => {
    render(<DigitalTwinPanel />, { wrapper: wrapper(client()) });

    await waitFor(() => expect(screen.getAllByTestId("twin-domain")).toHaveLength(11));
    expect(screen.getAllByTestId("domain-reason-code")).toHaveLength(11);
  });

  it("keeps distinct reasons distinct rather than collapsing them to 'no data'", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({
        domains: allDomains({
          software_environment: {
            reason: { code: "no_source_engine", detail: "nova-companion is Phase 4F's." },
          },
          productivity_patterns: {
            reason: {
              code: "no_autonomous_producer",
              detail: "The subject is real; nothing emits it in a stock deployment.",
            },
          },
        }),
      }),
    );
    render(<DigitalTwinPanel />, { wrapper: wrapper(client()) });

    await waitFor(() => expect(screen.getAllByTestId("twin-domain")).toHaveLength(11));
    const codes = screen.getAllByTestId("domain-reason-code").map((el) => el.textContent);
    // Three different reasons for three different absences. An operator reading
    // "no data" three times would conclude the system is broken; these say that
    // one is waiting for Phase 4F, one for an observation, one for a decision.
    expect(new Set(codes)).toEqual(
      new Set(["no_source_engine", "no_autonomous_producer", "no_evidence_observed"]),
    );
  });

  it("names the Part 16 fields a domain cannot fill", async () => {
    render(<DigitalTwinPanel />, { wrapper: wrapper(client()) });

    await waitFor(() => expect(screen.getAllByTestId("twin-domain")).toHaveLength(11));
    expect(screen.getAllByTestId("domain-unavailable-fields")[0]).toHaveTextContent("priority");
  });

  it("shows no evidence count for a domain with no evidence", async () => {
    // Not "0 evidence records" -- a count of zero invites reading the domain as
    // measured-and-empty rather than as never-observed.
    render(<DigitalTwinPanel />, { wrapper: wrapper(client()) });

    await waitFor(() => expect(screen.getAllByTestId("twin-domain")).toHaveLength(11));
    const goals = screen
      .getAllByTestId("twin-domain")
      .find((el) => el.dataset.domain === "goals")!;
    expect(within(goals).queryByTestId("domain-evidence-count")).toBeNull();
  });

  it("renders a multi-week gap as days since last activity", async () => {
    render(<DigitalTwinPanel />, { wrapper: wrapper(client()) });

    await waitFor(() => expect(screen.getAllByTestId("twin-project")).toHaveLength(1));
    expect(screen.getByTestId("twin-project-gap")).toHaveTextContent(
      "41 days since last activity",
    );
  });

  it("renders a null gap as 'no dated activity', never as a zero", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({
        projects: [
          project({ gap_days: null, first_activity_at: null, last_activity_at: null }),
        ],
      }),
    );
    render(<DigitalTwinPanel />, { wrapper: wrapper(client()) });

    await waitFor(() => expect(screen.getAllByTestId("twin-project")).toHaveLength(1));
    const gap = screen.getByTestId("twin-project-gap");
    expect(gap).toHaveTextContent("no dated activity");
    expect(gap.textContent).not.toMatch(/\b0\b/);
    expect(gap.textContent).not.toMatch(/active today/);
  });

  it("reconstructs a project on demand -- the AC-6 surface", async () => {
    const user = userEvent.setup();
    render(<DigitalTwinPanel />, { wrapper: wrapper(client()) });

    await waitFor(() => expect(screen.getAllByTestId("twin-project")).toHaveLength(1));
    await user.click(screen.getByTestId("reconstruct-project"));

    await waitFor(() => expect(screen.getByTestId("project-reconstruction")).toBeTruthy());
    expect(screen.getByTestId("project-gap")).toHaveTextContent("41 days since last activity");
    expect(screen.getByTestId("project-memory-count")).toHaveTextContent("3 memory records");
    expect(screen.getByTestId("project-activity-window")).toHaveTextContent("2026-06-01");
  });

  it("renders the projects domain's own reason when there are no projects", async () => {
    vi.stubGlobal("fetch", mockFetch({ projects: [] }));
    render(<DigitalTwinPanel />, { wrapper: wrapper(client()) });

    await waitFor(() => expect(screen.getByTestId("panel-empty")).toBeTruthy());
    expect(screen.queryAllByTestId("twin-project")).toHaveLength(0);
  });

  it("does not render a re-derive as derived when the server still reports empty", async () => {
    // The no-optimistic-mutation rule, at the one place it would be tempting
    // to break: the button POSTs, the server answers `empty`, and the panel
    // must show `empty`.
    const user = userEvent.setup();
    vi.stubGlobal("fetch", mockFetch({ refresh: domain({ state: "empty" }) }));
    render(<DigitalTwinPanel />, { wrapper: wrapper(client()) });

    await waitFor(() => expect(screen.getAllByTestId("twin-domain")).toHaveLength(11));
    await user.click(screen.getAllByTestId("refresh-domain")[0]);

    await waitFor(() =>
      expect(screen.getAllByTestId("twin-domain")[0].dataset.state).toBe("empty"),
    );
  });

  // "never polls" and the other source-level properties live in
  // `security-boundary.test.ts`: jsdom serves `import.meta.url` over http:,
  // which `fileURLToPath` rejects, and an interval firing every 30s would not
  // fire inside a test anyway -- it would look identical to no polling.

  it("reads only through the gateway, never a socket or an engine directly", async () => {
    render(<DigitalTwinPanel />, { wrapper: wrapper(client()) });

    await waitFor(() => expect(screen.getAllByTestId("twin-domain")).toHaveLength(11));
    const calls = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.map((c) =>
      String(c[0]),
    );
    expect(calls.length).toBeGreaterThan(0);
    for (const url of calls) {
      expect(url).toMatch(/\/v1\/digital-twin\//);
      expect(url).not.toMatch(/^ws/);
      expect(url).not.toMatch(/:800\d/);
    }
  });
});
