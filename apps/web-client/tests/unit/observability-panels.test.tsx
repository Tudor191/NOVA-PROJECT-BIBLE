import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { approvalKeys } from "../../src/entities/approvals";
import { capabilityKeys } from "../../src/entities/capabilities";
import { eventKeys } from "../../src/entities/events";
import { healthKeys } from "../../src/entities/health";
import { planningKeys } from "../../src/entities/planning";
import { reasoningKeys } from "../../src/entities/reasoning";
import { ApprovalsPanel } from "../../src/panels/approvals/ApprovalsPanel";
import { CapabilitiesPanel } from "../../src/panels/capabilities/CapabilitiesPanel";
import { EventsPanel } from "../../src/panels/events/EventsPanel";
import { HealthPanel } from "../../src/panels/health/HealthPanel";
import { PlanningPanel } from "../../src/panels/planning/PlanningPanel";
import { ReasoningTracePanel } from "../../src/panels/reasoning/ReasoningTracePanel";

/**
 * The six 4B panels: each renders its data, and each says so honestly when
 * it has none. The empty case gets as much attention as the populated one --
 * an observability surface that looks broken when the system is merely idle
 * trains the operator to ignore it.
 */

function wrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

/**
 * Mirrors `createQueryClient`'s options, `staleTime: Infinity` included.
 *
 * Not a convenience: with the default `staleTime` of 0, seeding a key and
 * then rendering refetches immediately, so every test would exercise the
 * `fetch` stub rather than the data it seeded -- and a panel would be
 * asserted against whatever the stub happened to return.
 */
function client(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: Infinity, refetchOnMount: false },
      mutations: { retry: false },
    },
  });
}

const envelope = (data: unknown) => ({
  data,
  meta: {
    correlation_id: "4f1d9c2a-0000-4000-8000-000000000000",
    generated_at: "2026-09-05T12:00:00.000Z",
  },
  error: null,
});

beforeEach(() => {
  // Every REST-backed panel goes through `gatewayFetch`, so one stub covers
  // them; each test seeds the cache it needs instead of relying on ordering.
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(envelope([])), { status: 200 })),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("PlanningPanel", () => {
  it("says no plans exist rather than looking broken", async () => {
    const queryClient = client();
    queryClient.setQueryData(planningKeys.all, envelope([]));
    render(<PlanningPanel />, { wrapper: wrapper(queryClient) });
    expect(await screen.findByTestId("panel-empty")).toBeInTheDocument();
  });

  it("renders a graph, its nodes, and which are on the critical path", async () => {
    const queryClient = client();
    queryClient.setQueryData(
      planningKeys.all,
      envelope([
        {
          id: "graph-1",
          root_objective: "Ship the feature",
          nodes: [
            { id: "n1", objective: "Write it", depends_on: [], status: "ready", risk: "low" },
            { id: "n2", objective: "Test it", depends_on: ["n1"], status: "pending", risk: "low" },
          ],
          critical_path: ["n1"],
          approved_at: null,
        },
      ]),
    );
    render(<PlanningPanel />, { wrapper: wrapper(queryClient) });

    expect(await screen.findByText("Ship the feature")).toBeInTheDocument();
    expect(screen.getAllByTestId("plan-node")).toHaveLength(2);
    expect(screen.getAllByTestId("critical-path")).toHaveLength(1);
  });

  it("offers to record an approval, not to run anything", async () => {
    // The label matters: `planning-engine` records `approved_at` and nothing
    // consumes it, so a "Run" button would promise execution the system
    // cannot perform.
    const queryClient = client();
    queryClient.setQueryData(
      planningKeys.all,
      envelope([
        { id: "g", root_objective: "o", nodes: [], critical_path: [], approved_at: null },
      ]),
    );
    render(<PlanningPanel />, { wrapper: wrapper(queryClient) });
    expect(await screen.findByRole("button", { name: "Record approval" })).toBeInTheDocument();
  });
});

describe("CapabilitiesPanel", () => {
  it("renders installed capabilities with what they require", async () => {
    const queryClient = client();
    queryClient.setQueryData(
      capabilityKeys.all,
      envelope([
        {
          id: "c1",
          name: "Send email",
          description: "Sends mail",
          category: "communication",
          version: "1.0.0",
          required_permissions: ["mail.send"],
          dependencies: [],
        },
      ]),
    );
    render(<CapabilitiesPanel />, { wrapper: wrapper(queryClient) });

    expect(await screen.findByText("Send email")).toBeInTheDocument();
    expect(screen.getByTestId("capability-permissions")).toHaveTextContent("mail.send");
  });

  it("says when it last read, since nothing pushes updates to it", async () => {
    const queryClient = client();
    queryClient.setQueryData(capabilityKeys.all, envelope([]));
    render(<CapabilitiesPanel />, { wrapper: wrapper(queryClient) });
    // capability-engine publishes no domain events; the panel must not let
    // an absence of updates read as confirmed stability.
    expect(await screen.findByTestId("capabilities-read-at")).toBeInTheDocument();
  });
});

describe("ApprovalsPanel", () => {
  it("says nothing is waiting rather than looking empty-because-broken", async () => {
    const queryClient = client();
    queryClient.setQueryData(approvalKeys.pending, envelope([]));
    render(<ApprovalsPanel />, { wrapper: wrapper(queryClient) });
    expect(await screen.findByTestId("panel-empty")).toHaveTextContent("Nothing is waiting");
  });

  it("does not remove a row optimistically when a decision is clicked", async () => {
    // Shared cognitive state: the row leaves when `action.approval.decided`
    // arrives, never when the button is pressed. A 409 (someone else decided
    // it first) would otherwise have already been rendered as done.
    const queryClient = client();
    queryClient.setQueryData(
      approvalKeys.pending,
      envelope([{ action_id: "a1", risk: "high", requested_at: "2026-09-05T12:00:00.000Z" }]),
    );
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify(envelope({ action_id: "a1", decision: "approved" })), {
            status: 200,
          }),
      ),
    );
    render(<ApprovalsPanel />, { wrapper: wrapper(queryClient) });

    await userEvent.click(await screen.findByRole("button", { name: "Approve" }));

    await waitFor(() => expect(vi.mocked(fetch)).toHaveBeenCalled());
    expect(screen.getAllByTestId("approval")).toHaveLength(1);
  });
});

describe("ReasoningTracePanel", () => {
  it("renders a tier word and never a raw confidence number", async () => {
    const queryClient = client();
    queryClient.setQueryData(
      reasoningKeys.traces,
      envelope([
        {
          id: "t1",
          reasoning_process_id: "p1",
          correlation_id: "c1",
          reasoning_mode: "analytical",
          reasoning_level: 2,
          confidence_score: 0.91,
          selected_capabilities: ["search"],
        },
      ]),
    );
    render(<ReasoningTracePanel />, { wrapper: wrapper(queryClient) });

    expect(await screen.findByTestId("trace")).toBeInTheDocument();
    expect(screen.getByTestId("trace")).not.toHaveTextContent("0.91");
    expect(screen.getByTestId("trace")).not.toHaveTextContent("91%");
  });

  it("keeps live processes separate from recorded traces", async () => {
    // A process that completed on the bus is not the same fact as a trace
    // persisted by the engine; merging them would imply durability.
    const queryClient = client();
    queryClient.setQueryData(reasoningKeys.traces, envelope([]));
    queryClient.setQueryData(reasoningKeys.live, [
      {
        reasoningProcessId: "p1",
        correlationId: "c1",
        outcome: "failed",
        confidence: null,
        error: "upstream timeout",
        at: "2026-09-05T12:00:00.000Z",
      },
    ]);
    render(<ReasoningTracePanel />, { wrapper: wrapper(queryClient) });

    expect(await screen.findByTestId("live-process")).toHaveTextContent("failed");
    expect(screen.getByTestId("live-process-error")).toHaveTextContent("upstream timeout");
    // No confidence badge on a failure: absence, not zero.
    expect(screen.getByTestId("live-process")).not.toHaveTextContent("very_low");
  });
});

describe("EventsPanel", () => {
  it("says nothing has arrived rather than implying the system is idle", () => {
    const queryClient = client();
    queryClient.setQueryData(eventKeys.feed, []);
    render(<EventsPanel />, { wrapper: wrapper(queryClient) });
    expect(screen.getByTestId("panel-empty")).toHaveTextContent("No events received");
  });

  it("shows both the event's own time and when it arrived here", () => {
    const queryClient = client();
    queryClient.setQueryData(eventKeys.feed, [
      {
        seq: 1,
        topic: "nova.heartbeat",
        correlationId: "c1",
        generatedAt: "2026-09-05T12:00:00.000Z",
        receivedAt: "2026-09-05T12:00:09.000Z",
        confidence: null,
        data: {},
      },
    ]);
    render(<EventsPanel />, { wrapper: wrapper(queryClient) });

    expect(screen.getByTestId("event-topic")).toHaveTextContent("nova.heartbeat");
    const times = screen.getByTestId("event-times");
    expect(times).toHaveTextContent("occurred");
    expect(times).toHaveTextContent("received");
  });
});

describe("HealthPanel", () => {
  it("says no module has reported rather than showing a healthy board", () => {
    const queryClient = client();
    queryClient.setQueryData(healthKeys.modules, {});
    render(<HealthPanel />, { wrapper: wrapper(queryClient) });
    expect(screen.getByTestId("panel-empty")).toHaveTextContent("No module has reported");
  });

  it("renders each module with which stream reported it", () => {
    const queryClient = client();
    queryClient.setQueryData(healthKeys.modules, {
      "nova-core": {
        module: "nova-core",
        status: "healthy",
        reason: null,
        at: new Date().toISOString(),
        source: "heartbeat",
      },
    });
    render(<HealthPanel />, { wrapper: wrapper(queryClient) });

    expect(screen.getByTestId("health-module")).toBeInTheDocument();
    expect(screen.getByTestId("health-source")).toHaveTextContent("heartbeat");
  });

  it("turns a module unknown once it stops reporting", () => {
    const queryClient = client();
    queryClient.setQueryData(healthKeys.modules, {
      "nova-core": {
        module: "nova-core",
        status: "healthy",
        reason: null,
        // Long enough ago to be stale on the first render.
        at: new Date(Date.now() - 120_000).toISOString(),
        source: "heartbeat",
      },
    });
    render(<HealthPanel />, { wrapper: wrapper(queryClient) });

    expect(screen.getByTestId("status-dot")).toHaveAttribute("data-status", "unknown");
  });
});
