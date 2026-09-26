import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ATTENTION_LAYERS,
  SENSOR_STATES,
  cognitiveStateSchemas,
} from "../../src/entities/cognitiveState";
import { CognitiveStatePanel } from "../../src/panels/cognitiveState/CognitiveStatePanel";

/**
 * The Cognitive State panel (Phase 4F.7) -- TDD 4F.7 §12 and §16 **P-18**, with
 * §28.4's change to its sensor case.
 *
 * **Every fixture is parsed by the panel's own strict schemas before use**
 * (`fixture()` below), so a fixture that drifts from §7's contract fails here
 * rather than proving the panel against a shape the engine never serves.
 *
 * What gets the attention is what an ordinary implementation gets wrong in the
 * dangerous direction: an empty list that renders as something, a `null` that
 * renders as a date, a proposal that reads as though it was acted on, a sensor
 * state the engine did not send, and an error that looks like an empty panel.
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
      queries: { retry: false, staleTime: Infinity, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  });
}

const META = {
  correlation_id: "4f7d9c2a-0000-4000-8000-000000000000",
  generated_at: "2026-09-26T12:00:00.000Z",
};

const envelope = (data: unknown) => ({ data, meta: META, error: null });
const failure = (code: string, message: string, upstreamStatus: number | null) => ({
  data: null,
  meta: META,
  error: { code, message, upstream_status: upstreamStatus },
});

type Route = "thoughts" | "focus" | "sensors";

/** Parse with the panel's own schema first: a drifted fixture fails here. */
function fixture<R extends Route>(route: R, body: unknown): unknown {
  cognitiveStateSchemas[route].parse(body);
  return body;
}

const DEP = "11111111-1111-4111-8111-111111111111";
const MEM = "22222222-2222-4222-8222-222222222222";
const PROJ = "33333333-3333-4333-8333-333333333333";

function thought(overrides: Record<string, unknown> = {}) {
  return {
    thought_id: "aaaaaaaa-0000-4000-8000-000000000001",
    description: "Investigate recurring build failures",
    priority: 4,
    confidence: 0.7,
    dependencies: [],
    estimated_completion: null,
    related_memories: [],
    related_projects: [],
    current_progress: 0.25,
    attention_layer: "active",
    created_at: "2026-09-26T08:00:00Z",
    updated_at: "2026-09-26T09:00:00Z",
    proposed_action: null,
    ...overrides,
  };
}

const PROPOSAL = {
  category: "create",
  risk: "low",
  action_type: "terminal",
  execution_target: "terminal",
  verification_method: "exit_code",
  title: "prune stale build artifacts",
  detail: "older than thirty days",
};

function sensor(overrides: Record<string, unknown> = {}) {
  return {
    sensor_id: "companion-filesystem",
    sensor_type: "filesystem",
    state: "running",
    reported_at: "2026-09-26T08:00:10Z",
    ...overrides,
  };
}

type Reply = { status?: number; body: unknown };

/** Routes the panel's three GETs by path, and records every request made. */
function stubFetch(replies: Partial<Record<Route, Reply>>) {
  const defaults: Record<Route, Reply> = {
    thoughts: { body: envelope(fixture("thoughts", { thoughts: [] })) },
    focus: { body: envelope(fixture("focus", { capacity: 7, entries: [] })) },
    sensors: { body: envelope(fixture("sensors", { sensors: [] })) },
  };
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const route = (["thoughts", "focus", "sensors"] as const).find((r) =>
      url.endsWith(`/v1/cognitive-state/${r}`),
    );
    if (route === undefined) throw new Error(`unexpected request ${init?.method ?? "GET"} ${url}`);
    const reply = replies[route] ?? defaults[route];
    return new Response(JSON.stringify(reply.body), {
      status: reply.status ?? 200,
      headers: { "content-type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", mock);
  return mock;
}

function requests(mock: ReturnType<typeof stubFetch>): string[] {
  return mock.mock.calls.map(([input, init]) => `${init?.method ?? "GET"} ${String(input)}`);
}

function renderPanel() {
  return render(<CognitiveStatePanel />, { wrapper: wrapper(client()) });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

// --- honest empty states ---------------------------------------------------------

describe("empty states", () => {
  it("renders each empty statement and nothing else", async () => {
    stubFetch({});
    renderPanel();

    await waitFor(() => expect(screen.getAllByTestId("panel-empty")).toHaveLength(3));
    const statements = screen.getAllByTestId("panel-empty").map((el) => el.textContent);
    expect(statements.sort()).toEqual(
      ["No Active Thoughts.", "No sensor report has been received.", "Nothing is in focus."].sort(),
    );
    // No placeholder cards, sample rows, layer skeletons or capacity line.
    for (const id of [
      "thought",
      "thought-layer",
      "focus-entry",
      "focus-capacity",
      "sensor",
      "sensors-note",
    ]) {
      expect(screen.queryByTestId(id)).toBeNull();
    }
  });
});

// --- Active Thoughts ---------------------------------------------------------------

describe("Active Thoughts", () => {
  it("groups thoughts by Part 6's five layers, in order, and shows an empty layer as empty", async () => {
    stubFetch({
      thoughts: {
        body: envelope(
          fixture("thoughts", {
            thoughts: [
              thought({ thought_id: "aaaaaaaa-0000-4000-8000-00000000000d", attention_layer: "dormant" }),
              thought({ thought_id: "aaaaaaaa-0000-4000-8000-00000000000a", attention_layer: "immediate" }),
            ],
          }),
        ),
      },
    });
    renderPanel();

    await waitFor(() => expect(screen.getAllByTestId("thought-layer")).toHaveLength(5));
    const layers = screen.getAllByTestId("thought-layer");
    expect(layers.map((el) => el.dataset.layer)).toEqual([...ATTENTION_LAYERS]);
    expect(layers.map((el) => within(el).getByRole("heading").textContent)).toEqual([
      "Immediate",
      "Active",
      "Passive",
      "Dormant",
      "Archived",
    ]);
    const counts = layers.map((el) => within(el).queryAllByTestId("thought").length);
    expect(counts).toEqual([1, 0, 0, 1, 0]);
    expect(within(layers[1]).getByTestId("thought-layer-empty").textContent).toBe(
      "No thoughts in this layer.",
    );
  });

  it("renders every Part 6 field, exactly as served", async () => {
    stubFetch({
      thoughts: {
        body: envelope(
          fixture("thoughts", {
            thoughts: [
              thought({
                dependencies: [DEP],
                related_memories: [MEM],
                related_projects: [PROJ],
                estimated_completion: "2026-10-01T09:30:00Z",
              }),
            ],
          }),
        ),
      },
    });
    renderPanel();

    const card = await screen.findByTestId("thought");
    const field = (id: string) => within(card).getByTestId(id).textContent;
    expect(field("thought-description")).toBe("Investigate recurring build failures");
    expect(field("thought-priority")).toBe("4");
    expect(field("thought-confidence")).toBe("0.7");
    expect(field("thought-progress")).toBe("0.25");
    expect(field("thought-estimated-completion")).toBe("2026-10-01T09:30:00Z");
    expect(field("thought-dependencies")).toBe(DEP);
    expect(field("thought-related-memories")).toBe(MEM);
    expect(field("thought-related-projects")).toBe(PROJ);
    expect(field("thought-created-at")).toBe("2026-09-26T08:00:00Z");
    expect(field("thought-updated-at")).toBe("2026-09-26T09:00:00Z");
    expect(field("thought-id")).toBe("aaaaaaaa-0000-4000-8000-000000000001");
    expect(card.dataset.layer).toBe("active");
  });

  it("renders a null estimated completion as 'not estimated', never a date or a zero", async () => {
    stubFetch({
      thoughts: { body: envelope(fixture("thoughts", { thoughts: [thought()] })) },
    });
    renderPanel();

    const card = await screen.findByTestId("thought");
    expect(within(card).getByTestId("thought-estimated-completion").textContent).toBe(
      "not estimated",
    );
  });

  it("renders a proposal as a proposal, and nothing about it as acted on", async () => {
    stubFetch({
      thoughts: {
        body: envelope(fixture("thoughts", { thoughts: [thought({ proposed_action: PROPOSAL })] })),
      },
    });
    renderPanel();

    const block = await screen.findByTestId("thought-proposal");
    expect(within(block).getByRole("heading").textContent).toBe("Proposal");
    expect(within(block).getByTestId("proposal-title").textContent).toBe(PROPOSAL.title);
    expect(within(block).getByTestId("proposal-detail").textContent).toBe(PROPOSAL.detail);
    expect(within(block).getByTestId("proposal-category").textContent).toBe("create");
    expect(within(block).getByTestId("proposal-risk").textContent).toBe("low");
    expect(within(block).getByTestId("proposal-action-type").textContent).toBe("terminal");
    expect(within(block).getByTestId("proposal-execution-target").textContent).toBe("terminal");
    expect(within(block).getByTestId("proposal-verification-method").textContent).toBe(
      "exit_code",
    );
    // P-9 / M9: no word that says the proposal was acted on.
    expect(block.textContent?.toLowerCase()).not.toMatch(
      /triggered|decided|approved|executing|executed|dispatched/,
    );
  });

  it("renders no proposal block for a thought without one", async () => {
    stubFetch({
      thoughts: { body: envelope(fixture("thoughts", { thoughts: [thought()] })) },
    });
    renderPanel();

    await screen.findByTestId("thought");
    expect(screen.queryByTestId("thought-proposal")).toBeNull();
  });
});

// --- Focus ---------------------------------------------------------------------------

describe("Focus", () => {
  it("shows score and capacity, and labels an empty signals_used honestly (P-7)", async () => {
    stubFetch({
      focus: {
        body: envelope(
          fixture("focus", {
            capacity: 3,
            entries: [
              { thought: thought({ priority: 9 }), score: 9, signals_used: [] },
              {
                thought: thought({
                  thought_id: "aaaaaaaa-0000-4000-8000-000000000002",
                  priority: 5,
                  attention_layer: "immediate",
                }),
                score: 5,
                signals_used: [],
              },
            ],
          }),
        ),
      },
    });
    renderPanel();

    await waitFor(() => expect(screen.getAllByTestId("focus-entry")).toHaveLength(2));
    expect(screen.getByTestId("focus-capacity").textContent).toBe("2 of capacity 3");
    expect(screen.getAllByTestId("focus-score").map((el) => el.textContent)).toEqual([
      "score 9",
      "score 5",
    ]);
    for (const line of screen.getAllByTestId("focus-signals")) {
      expect(line.textContent).toBe("ranked by priority alone — no focus signals were supplied");
    }
  });
});

// --- Sensors -------------------------------------------------------------------------

describe("Sensors", () => {
  it.each(SENSOR_STATES)("renders the lifecycle state %s exactly, with when it was reported", async (state) => {
    stubFetch({
      sensors: { body: envelope(fixture("sensors", { sensors: [sensor({ state })] })) },
    });
    renderPanel();

    const row = await screen.findByTestId("sensor");
    expect(row.dataset.state).toBe(state);
    expect(within(row).getByTestId("sensor-state").textContent).toBe(`lifecycle state: ${state}`);
    expect(within(row).getByTestId("sensor-reported-at").textContent).toBe(
      "last reported 2026-09-26T08:00:10Z",
    );
    expect(row.textContent?.toLowerCase()).not.toMatch(/healthy|unhealthy/);
  });

  it("renders an out-of-vocabulary state as a contract violation, never as a state", async () => {
    const drifted = { sensors: [sensor({ state: "healthy" })] };
    expect(() => cognitiveStateSchemas.sensors.parse(drifted)).toThrow();
    stubFetch({ sensors: { body: envelope(drifted) } });
    renderPanel();

    const notice = await screen.findByTestId("degradation-notice");
    expect(notice.textContent).toContain("This panel could not read its data");
    expect(screen.queryByTestId("sensor")).toBeNull();
    expect(screen.queryByText(/healthy/)).toBeNull();
  });
});

// --- degradation ---------------------------------------------------------------------

describe("errors", () => {
  it.each(["thoughts", "focus", "sensors"] as const)(
    "renders a notice for a failed %s read, never an empty panel",
    async (route) => {
      stubFetch({
        [route]: { status: 500, body: failure("upstream_error", "Internal Server Error", 500) },
      });
      renderPanel();

      const notice = await screen.findByTestId("degradation-notice");
      expect(notice.textContent).toContain("This panel could not read its data");
      await waitFor(() => expect(screen.getAllByTestId("panel-empty")).toHaveLength(2));
      expect(screen.getAllByTestId("degradation-notice")).toHaveLength(1);
    },
  );
});

// --- Refresh ---------------------------------------------------------------------------

describe("Refresh", () => {
  it("re-issues the three GETs, and only GETs", async () => {
    const mock = stubFetch({});
    renderPanel();
    await waitFor(() => expect(screen.getAllByTestId("panel-empty")).toHaveLength(3));
    const onMount = requests(mock);
    expect(onMount.sort()).toEqual([
      "GET /v1/cognitive-state/focus",
      "GET /v1/cognitive-state/sensors",
      "GET /v1/cognitive-state/thoughts",
    ]);

    await userEvent.click(screen.getByTestId("cognitive-state-refresh"));
    await waitFor(() => expect(requests(mock)).toHaveLength(6));
    expect(requests(mock).slice(3).sort()).toEqual(onMount.sort());
  });

  it("shows what the engine answered after a refresh, and nothing it did not", async () => {
    const mock = stubFetch({});
    renderPanel();
    await waitFor(() => expect(screen.getAllByTestId("panel-empty")).toHaveLength(3));

    const reported = sensor({ state: "stopped" });
    mock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      const body = url.endsWith("/sensors")
        ? fixture("sensors", { sensors: [reported] })
        : url.endsWith("/focus")
          ? fixture("focus", { capacity: 7, entries: [] })
          : fixture("thoughts", { thoughts: [] });
      return new Response(JSON.stringify(envelope(body)), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    });
    await userEvent.click(screen.getByTestId("cognitive-state-refresh"));

    const row = await screen.findByTestId("sensor");
    expect(row.dataset.state).toBe("stopped");
    expect(screen.getAllByTestId("sensor")).toHaveLength(1);
  });

  it("does not poll: nothing is requested again without the operator asking", async () => {
    const mock = stubFetch({});
    renderPanel();
    await waitFor(() => expect(screen.getAllByTestId("panel-empty")).toHaveLength(3));
    const initial = requests(mock).length;

    await new Promise((resolve) => setTimeout(resolve, 250));
    expect(requests(mock)).toHaveLength(initial);
  });
});
