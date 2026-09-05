import { describe, expect, it } from "vitest";

import { reduceDecided, reduceRequested } from "../../src/entities/approvals";
import { EVENT_FEED_LIMIT, observedFromFrame, reduceEventFeed } from "../../src/entities/events";
import {
  HEALTH_STALE_AFTER_MS,
  reduceHeartbeat,
  reduceModelHealth,
  reduceModuleStatus,
  withStaleness,
} from "../../src/entities/health";
import { reduceTaskGraphCreated } from "../../src/entities/planning";
import {
  processFromCompleted,
  processFromFailed,
  reduceProcess,
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
