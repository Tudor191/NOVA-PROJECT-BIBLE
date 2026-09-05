import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import type { TranscriptEntry } from "../../src/entities/conversation";
import { conversationKeys } from "../../src/entities/conversation";
import { presenceKeys } from "../../src/entities/presence";
import type { PresentIdentity } from "../../src/entities/presence";
import { pulseKeys, summarisePulse } from "../../src/entities/pulse";
import type { PulseState } from "../../src/entities/pulse";
import type { EventFrame } from "../../src/realtime/protocol";
import { applyFrame, reduceTranscript } from "../../src/realtime/reconcile";

/**
 * Bus frame -> what the user sees.
 *
 * Kept free of React and sockets on purpose: the reconciliation rules are
 * where a realtime UI actually goes wrong -- duplicate rows from at-least-
 * once delivery, a reply rendered above the question it answers, another
 * session's turns leaking into this transcript -- and none of those need a
 * browser to reproduce.
 */

const SESSION = "11111111-1111-4111-8111-111111111111";
const OTHER_SESSION = "22222222-2222-4222-8222-222222222222";

function frame(topic: string, data: Record<string, unknown>, generatedAt = "2026-09-02T10:00:00Z"): EventFrame {
  return {
    type: "event",
    topic,
    data,
    meta: { correlation_id: "corr-1", generated_at: generatedAt },
  };
}

function turnFrame(overrides: Record<string, unknown> = {}) {
  return frame("communication.turn.received", {
    session_id: SESSION,
    turn_id: "turn-1",
    user_id: "user-1",
    content: "How did the build go?",
    channel: "text",
    created_at: "2026-09-02T10:00:00Z",
    ...overrides,
  });
}

function deliveredFrame(overrides: Record<string, unknown> = {}) {
  return frame("communication.intent.delivered", {
    session_id: SESSION,
    turn_id: "turn-2",
    user_id: "user-1",
    content: "The build finished.",
    channel: "text",
    confidence_tier: "high",
    personality_validated: true,
    degraded: false,
    delivered_at: "2026-09-02T10:00:05Z",
    ...overrides,
  });
}

function transcriptOf(client: QueryClient): TranscriptEntry[] {
  return client.getQueryData<TranscriptEntry[]>(conversationKeys.transcript(SESSION)) ?? [];
}

describe("reduceTranscript", () => {
  const entry = (id: string, at: string): TranscriptEntry => ({
    id,
    author: "user",
    content: id,
    at,
    confidenceTier: null,
    correlationId: "corr",
    degraded: false,
  });

  it("orders by the event's own time, not arrival order", () => {
    // The bus makes no cross-subject ordering promise. A reply rendered
    // above the question it answers is a wrong transcript.
    let entries = reduceTranscript(undefined, entry("second", "2026-09-02T10:00:05Z"));
    entries = reduceTranscript(entries, entry("first", "2026-09-02T10:00:00Z"));
    expect(entries.map((e) => e.id)).toEqual(["first", "second"]);
  });

  it("ignores a redelivered event rather than duplicating the row", () => {
    // At-least-once delivery is normal, not exceptional.
    const once = reduceTranscript(undefined, entry("turn-1", "2026-09-02T10:00:00Z"));
    const twice = reduceTranscript(once, entry("turn-1", "2026-09-02T10:00:00Z"));
    expect(twice).toHaveLength(1);
  });

  it("breaks a same-millisecond tie stably", () => {
    const a = reduceTranscript(undefined, entry("b", "2026-09-02T10:00:00Z"));
    const b = reduceTranscript(a, entry("a", "2026-09-02T10:00:00Z"));
    expect(b.map((e) => e.id)).toEqual(["a", "b"]);
  });
});

describe("applyFrame", () => {
  it("renders both halves of an exchange", () => {
    const client = new QueryClient();
    applyFrame(client, turnFrame(), SESSION);
    applyFrame(client, deliveredFrame(), SESSION);

    const entries = transcriptOf(client);
    expect(entries.map((e) => e.author)).toEqual(["user", "nova"]);
    expect(entries[1].content).toBe("The build finished.");
  });

  it("carries the reply's tier as a word and never as a number", () => {
    const client = new QueryClient();
    applyFrame(client, deliveredFrame(), SESSION);
    expect(transcriptOf(client)[0].confidenceTier).toBe("high");
  });

  it("gives the user's own turn no confidence at all", () => {
    const client = new QueryClient();
    applyFrame(client, turnFrame(), SESSION);
    expect(transcriptOf(client)[0].confidenceTier).toBeNull();
  });

  it("marks a degraded delivery as degraded", () => {
    const client = new QueryClient();
    applyFrame(client, deliveredFrame({ degraded: true, personality_validated: false }), SESSION);
    expect(transcriptOf(client)[0].degraded).toBe(true);
  });

  it("drops frames belonging to another session", () => {
    const client = new QueryClient();
    applyFrame(client, turnFrame({ session_id: OTHER_SESSION, turn_id: "other" }), SESSION);
    expect(transcriptOf(client)).toEqual([]);
  });

  it("drops every conversation frame when no session is open", () => {
    const client = new QueryClient();
    applyFrame(client, turnFrame(), null);
    expect(transcriptOf(client)).toEqual([]);
  });

  it("records the engine's own FSM state verbatim", () => {
    const client = new QueryClient();
    applyFrame(
      client,
      frame("communication.session.state_changed", {
        session_id: SESSION,
        from_state: "thinking",
        to_state: "speaking",
        changed_at: "2026-09-02T10:00:01Z",
      }),
      SESSION,
    );
    expect(client.getQueryData(conversationKeys.state(SESSION))).toBe("speaking");
  });

  it("times a presence observation by the envelope, not by arrival", () => {
    const client = new QueryClient();
    applyFrame(
      client,
      frame(
        "perception.identity.observed",
        {
          user_id: "user-1",
          confidence: 0.91,
          confidence_tier: "high",
          modality_summary: "face",
        },
        "2026-09-02T09:59:00Z",
      ),
      SESSION,
    );
    const present = client.getQueryData<PresentIdentity[]>(presenceKeys.present);
    expect(present).toEqual([
      { userId: "user-1", confidence: 0.91, confidenceTier: "high", observedAt: "2026-09-02T09:59:00Z" },
    ]);
  });

  it("leaves presence unknown when an observation names nobody", () => {
    const client = new QueryClient();
    applyFrame(
      client,
      frame("perception.identity.observed", { confidence: 0.4, modality_summary: "voice" }),
      SESSION,
    );
    // Still `undefined` -- an unidentified presence must not become an
    // empty list, which would read as "we checked and nobody is here".
    expect(client.getQueryData(presenceKeys.present)).toBeUndefined();
  });

  it("counts each heartbeat so the pulse animates once per real beat", () => {
    const client = new QueryClient();
    const beat = (uptime: number, at: string) =>
      frame("nova.heartbeat", { module: "nova-core", status: "healthy", uptime_seconds: uptime }, at);

    applyFrame(client, beat(10, "2026-09-02T10:00:00Z"), SESSION);
    applyFrame(client, beat(20, "2026-09-02T10:00:10Z"), SESSION);

    const pulse = client.getQueryData<PulseState>(pulseKeys.current);
    expect(pulse?.["nova-core"].sequence).toBe(2);
    expect(pulse?.["nova-core"].uptimeSeconds).toBe(20);
  });

  it("ignores a subscribed topic no 4A panel renders, without erroring", () => {
    const client = new QueryClient();
    expect(() =>
      applyFrame(client, frame("communication.session.completed", { session_id: SESSION }), SESSION),
    ).not.toThrow();
  });
});

describe("summarisePulse", () => {
  const at = (iso: string) => Date.parse(iso);
  const state = (status: string, iso: string): PulseState => ({
    "nova-core": {
      module: "nova-core",
      status: status as PulseState[string]["status"],
      uptimeSeconds: 1,
      at: iso,
      sequence: 1,
    },
  });

  it("is unknown before any heartbeat", () => {
    expect(summarisePulse(null, Date.now()).status).toBe("unknown");
  });

  it("is unknown -- not healthy -- once the heartbeat goes stale", () => {
    // The case a decorative UI gets wrong: it would keep animating the last
    // known "healthy" and tell the user everything is fine.
    const summary = summarisePulse(
      state("healthy", "2026-09-02T10:00:00Z"),
      at("2026-09-02T10:05:00Z"),
    );
    expect(summary.status).toBe("unknown");
  });

  it("is healthy while the beat is fresh", () => {
    const summary = summarisePulse(
      state("healthy", "2026-09-02T10:00:00Z"),
      at("2026-09-02T10:00:05Z"),
    );
    expect(summary.status).toBe("healthy");
  });

  it("reports a degraded module as degraded", () => {
    const summary = summarisePulse(
      state("degraded", "2026-09-02T10:00:00Z"),
      at("2026-09-02T10:00:05Z"),
    );
    expect(summary.status).toBe("degraded");
  });

  it("is degraded when some modules have gone silent but others have not", () => {
    const mixed: PulseState = {
      ...state("healthy", "2026-09-02T10:00:00Z"),
      "memory-engine": {
        module: "memory-engine",
        status: "healthy",
        uptimeSeconds: 1,
        at: "2026-09-02T09:50:00Z",
        sequence: 1,
      },
    };
    expect(summarisePulse(mixed, at("2026-09-02T10:00:05Z")).status).toBe("degraded");
  });
});
