import { describe, expect, it } from "vitest";

import { reduceDecided, reduceRequested } from "../../src/entities/approvals";
import {
  EMPTY_EVENT_FILTERS,
  EVENT_FEED_LIMIT,
  filterEvents,
  observedFromFrame,
  reduceEventFeed,
} from "../../src/entities/events";
import {
  HEALTH_STALE_AFTER_MS,
  reduceHeartbeat,
  reduceModelHealth,
  reduceModuleStatus,
  withStaleness,
} from "../../src/entities/health";
import { reduceTaskGraphCreated } from "../../src/entities/planning";
import {
  type ReasoningTrace,
  processFromCompleted,
  processFromFailed,
  reduceProcess,
  recursionDepth,
} from "../../src/entities/reasoning";
import type { EventFrame } from "../../src/realtime/protocol";

/**
 * The 4B panels' reducers, tested without React, a socket, or a gateway --
 * the same split 4A used, and for the same reason: what a frame does to
 * what the operator sees is the interesting part, and it is pure.
 */

const AT = "2026-09-05T12:00:00.000Z";

function frame(overrides: Partial<EventFrame> = {}): EventFrame {
  return {
    type: "event",
    topic: "nova.heartbeat",
    data: {},
    meta: { correlation_id: "corr-1", generated_at: AT, confidence: null },
    ...overrides,
  } as EventFrame;
}

// --- approvals -------------------------------------------------------------

describe("approvals", () => {
  const requested = (id: string, minute: number) =>
    ({ action_id: id, risk: "high", requested_at: `2026-09-05T12:0${minute}:00.000Z` }) as never;

  it("orders the queue oldest first, matching the endpoint", () => {
    let queue = reduceRequested(undefined, requested("b", 5));
    queue = reduceRequested(queue, requested("a", 1));
    expect(queue.map((approval) => approval.action_id)).toEqual(["a", "b"]);
  });

  it("does not duplicate an approval redelivered by an at-least-once bus", () => {
    const first = reduceRequested(undefined, requested("a", 1));
    expect(reduceRequested(first, requested("a", 1))).toHaveLength(1);
  });

  it("removes an approval only when the bus says it was decided", () => {
    const queue = reduceRequested(undefined, requested("a", 1));
    const after = reduceDecided(queue, {
      action_id: "a",
      decision: "approved",
      decided_at: AT,
    } as never);
    expect(after).toEqual([]);
  });

  it("ignores a decision for something not in the queue", () => {
    const queue = reduceRequested(undefined, requested("a", 1));
    const after = reduceDecided(queue, {
      action_id: "someone-elses",
      decision: "denied",
      decided_at: AT,
    } as never);
    expect(after).toHaveLength(1);
  });
});

// --- planning --------------------------------------------------------------

describe("planning", () => {
  const graph = (id: string) =>
    ({
      id,
      root_objective: "Ship it",
      nodes: [],
      critical_path: [],
      approved_at: null,
    }) as never;

  it("puts a newly created graph first", () => {
    const after = reduceTaskGraphCreated([{ id: "old" } as never], graph("new"));
    expect(after[0]?.id).toBe("new");
  });

  it("does not duplicate a redelivered graph", () => {
    const once = reduceTaskGraphCreated(undefined, graph("a"));
    expect(reduceTaskGraphCreated(once, graph("a"))).toHaveLength(1);
  });

  it("drops a payload it cannot read rather than rendering it half-formed", () => {
    const after = reduceTaskGraphCreated(undefined, { id: 42 } as never);
    expect(after).toEqual([]);
  });
});

// --- reasoning -------------------------------------------------------------

describe("reasoning", () => {
  it("carries the engine's own confidence and never invents one", () => {
    const completed = processFromCompleted(
      { reasoning_process_id: "p1", correlation_id: "c1", confidence_score: 0.9 } as never,
      AT,
    );
    expect(completed.confidence).toBe(0.9);
  });

  it("reports no confidence for a failed process rather than zero", () => {
    const failed = processFromFailed(
      { reasoning_process_id: "p2", correlation_id: "c2", error: "boom" } as never,
      AT,
    );
    // 0 would claim the engine was certain it was wrong. Absence is the fact.
    expect(failed.confidence).toBeNull();
    expect(failed.error).toBe("boom");
  });

  it("bounds the live list so an all-day session cannot grow it forever", () => {
    let live = undefined as never;
    for (let index = 0; index < 60; index += 1) {
      live = reduceProcess(live, {
        reasoningProcessId: `p${index}`,
        correlationId: "c",
        outcome: "completed",
        confidence: null,
        error: null,
        at: AT,
      }) as never;
    }
    expect((live as unknown as unknown[]).length).toBe(50);
  });
});

// --- events ----------------------------------------------------------------

describe("event feed", () => {
  it("records the browser's arrival time separately from the event's own", () => {
    const observed = observedFromFrame(frame(), 1, "2026-09-05T12:00:09.000Z");
    expect(observed.generatedAt).toBe(AT);
    expect(observed.receivedAt).toBe("2026-09-05T12:00:09.000Z");
  });

  it("keeps arrival order rather than re-sorting by event time", () => {
    // Deliberately the opposite of every other reducer here: re-ordering
    // would hide the out-of-order delivery this panel exists to show.
    let feed = reduceEventFeed(undefined, observedFromFrame(frame(), 1, AT));
    feed = reduceEventFeed(
      feed,
      observedFromFrame(frame({ meta: { correlation_id: "c", generated_at: "2020-01-01T00:00:00.000Z" } } as never), 2, AT),
    );
    expect(feed.map((event) => event.seq)).toEqual([2, 1]);
  });

  it("caps the feed", () => {
    let feed: ReturnType<typeof reduceEventFeed> = [];
    for (let index = 0; index < EVENT_FEED_LIMIT + 25; index += 1) {
      feed = reduceEventFeed(feed, observedFromFrame(frame(), index, AT));
    }
    expect(feed).toHaveLength(EVENT_FEED_LIMIT);
  });
});

// --- event filters (DEV-2) -------------------------------------------------

describe("event filters", () => {
  const feed = [
    { ...observedFromFrame(frame({ topic: "nova.heartbeat" }), 1, AT), correlationId: "aaa-111" },
    {
      ...observedFromFrame(frame({ topic: "action.approval.decided" }), 2, AT),
      correlationId: "bbb-222",
    },
    {
      ...observedFromFrame(frame({ topic: "action.approval.requested" }), 3, AT),
      correlationId: "aaa-111",
    },
  ];

  it("returns everything when nothing is asked for", () => {
    expect(filterEvents(feed, EMPTY_EVENT_FILTERS)).toHaveLength(3);
  });

  it("matches a subject prefix, so one filter covers a whole family", () => {
    const shown = filterEvents(feed, { ...EMPTY_EVENT_FILTERS, topic: "action.approval" });
    expect(shown.map((event) => event.seq)).toEqual([2, 3]);
  });

  it("ignores case, because subjects are typed by hand", () => {
    expect(filterEvents(feed, { ...EMPTY_EVENT_FILTERS, topic: "NOVA.HEART" })).toHaveLength(1);
  });

  it("follows one interaction across subjects by correlation id", () => {
    const shown = filterEvents(feed, { ...EMPTY_EVENT_FILTERS, correlationId: "aaa-111" });
    expect(shown.map((event) => event.seq)).toEqual([1, 3]);
  });

  it("intersects the two dimensions rather than unioning them", () => {
    const shown = filterEvents(feed, { topic: "action.approval", correlationId: "aaa-111" });
    expect(shown.map((event) => event.seq)).toEqual([3]);
  });

  it("does not mutate or re-order the feed it filters", () => {
    const before = [...feed];
    const shown = filterEvents(feed, { ...EMPTY_EVENT_FILTERS, topic: "action" });
    expect(feed).toEqual(before);
    // Arrival order preserved through the filter, same as without it.
    expect(shown.map((event) => event.seq)).toEqual([2, 3]);
  });

  it("keeps recording while a filter hides everything", () => {
    // The property that makes filtering safe: the reducer never sees the
    // filter, so a frame arriving while nothing matches is still kept and
    // reappears when the filter clears.
    const filtered = filterEvents(feed, { ...EMPTY_EVENT_FILTERS, topic: "nothing-matches-this" });
    expect(filtered).toHaveLength(0);
    const grown = reduceEventFeed(feed, observedFromFrame(frame({ topic: "nova.heartbeat" }), 4, AT));
    expect(grown).toHaveLength(4);
    expect(filterEvents(grown, EMPTY_EVENT_FILTERS)).toHaveLength(4);
  });
});

// --- reasoning recursion depth (DEV-3) -------------------------------------

describe("recursion depth", () => {
  const trace = (overrides: Partial<ReasoningTrace> = {}): ReasoningTrace =>
    ({
      id: "t",
      reasoning_process_id: "p",
      correlation_id: "c",
      reasoning_mode: "multi_step",
      reasoning_level: 2,
      confidence_score: 0.5,
      selected_capabilities: [],
      steps: [],
      multistep_recursion_exhausted: false,
      ...overrides,
    }) as ReasoningTrace;

  it("counts a single-step trace as depth 1, the way max_step_depth counts", () => {
    // `ModeConfig.max_step_depth` defaults to 1 and ">1 engages recursion",
    // so an un-recursed trace must read 1 for the two to be comparable.
    expect(recursionDepth(trace())).toBe(1);
  });

  it("counts nested steps, not how many there are", () => {
    // Three siblings at one level is still depth 2 -- breadth is not depth.
    const wide = trace({ steps: [trace(), trace(), trace()] });
    expect(recursionDepth(wide)).toBe(2);
  });

  it("takes the deepest branch when branches differ", () => {
    const lopsided = trace({
      steps: [trace(), trace({ steps: [trace({ steps: [trace()] })] })],
    });
    expect(recursionDepth(lopsided)).toBe(4);
  });

  it("is not reasoning_level, which is a different fact", () => {
    // A level-4 request that never recursed: the dial the caller set is 4,
    // what the pipeline did is 1. Reporting the level as the depth is the
    // substitution DEV-3 was raised about.
    const shallow = trace({ reasoning_level: 4 });
    expect(shallow.reasoning_level).toBe(4);
    expect(recursionDepth(shallow)).toBe(1);
  });
});

// --- health ----------------------------------------------------------------

describe("module health", () => {
  it("keeps one row per module, latest wins", () => {
    let state = reduceHeartbeat(undefined, { module: "nova-core", status: "healthy" } as never, AT);
    state = reduceModuleStatus(
      state,
      { module: "nova-core", status: "degraded", reason: "slow" } as never,
      AT,
    );
    expect(Object.keys(state)).toEqual(["nova-core"]);
    expect(state["nova-core"]?.status).toBe("degraded");
    expect(state["nova-core"]?.reason).toBe("slow");
  });

  it("namespaces models so a provider cannot overwrite an engine's row", () => {
    let state = reduceHeartbeat(undefined, { module: "gpt", status: "healthy" } as never, AT);
    state = reduceModelHealth(state, { model_id: "gpt", healthy: false } as never, AT);
    expect(Object.keys(state).sort()).toEqual(["gpt", "model:gpt"]);
  });

  it("falls back to unknown when a module stops reporting", () => {
    const state = reduceHeartbeat(
      undefined,
      { module: "nova-core", status: "healthy" } as never,
      AT,
    );
    const fresh = withStaleness(state, Date.parse(AT) + 1_000);
    const stale = withStaleness(state, Date.parse(AT) + HEALTH_STALE_AFTER_MS + 1);
    expect(fresh[0]?.status).toBe("healthy");
    // Never its last good status: silence is not health.
    expect(stale[0]?.status).toBe("unknown");
  });
});
