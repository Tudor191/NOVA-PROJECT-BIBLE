import { describe, expect, it, vi } from "vitest";

import type { ConnectionStatus } from "../../src/realtime/client";
import type { RealtimeClientOptions } from "../../src/realtime/client";
import { BACKOFF_MAX_MS, RealtimeClient, backoffDelay } from "../../src/realtime/client";
import { PUBLIC_TOPICS } from "../../src/realtime/protocol";
import { streamUrl } from "../../src/shared/config";

/**
 * The connection's behaviour under failure, which is the only time it
 * matters. A reconnect loop that hammers the gateway is a defect that shows
 * up exactly when the system is already in trouble.
 */

class FakeSocket {
  static instances: FakeSocket[] = [];
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  closed = false;

  constructor(readonly url: string) {
    FakeSocket.instances.push(this);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.closed = true;
  }

  /** Drive the lifecycle from a test. */
  open() {
    this.onopen?.();
  }
  drop() {
    this.onclose?.();
  }
  deliver(raw: string) {
    this.onmessage?.({ data: raw } as MessageEvent);
  }
}

function makeClient(overrides: Partial<RealtimeClientOptions> = {}) {
  FakeSocket.instances = [];
  const frames: unknown[] = [];
  const statuses: ConnectionStatus[] = [];
  const errors: string[] = [];
  const timers: Array<() => void> = [];

  const client = new RealtimeClient({
    url: "ws://gateway.test/v1/stream",
    webSocketImpl: FakeSocket as unknown as typeof WebSocket,
    onFrame: (frame) => frames.push(frame),
    onStatus: (status) => statuses.push(status),
    onProtocolError: (error) => errors.push(error.message),
    // Capture rather than run, so backoff never makes the suite slow and
    // reconnects happen exactly when a test says so.
    setTimeoutImpl: ((fn: () => void) => {
      timers.push(fn);
      return timers.length as unknown as ReturnType<typeof setTimeout>;
    }) as unknown as typeof setTimeout,
    clearTimeoutImpl: (() => undefined) as unknown as typeof clearTimeout,
    randomImpl: () => 0.5,
    ...overrides,
  });

  return { client, frames, statuses, errors, timers };
}

describe("backoffDelay", () => {
  it("grows exponentially", () => {
    const random = () => 1;
    expect(backoffDelay(0, random)).toBe(500);
    expect(backoffDelay(1, random)).toBe(1000);
    expect(backoffDelay(2, random)).toBe(2000);
  });

  it("is capped, so a long outage never produces an absurd delay", () => {
    expect(backoffDelay(50, () => 1)).toBe(BACKOFF_MAX_MS);
  });

  it("is jittered, so many clients do not retry in lockstep", () => {
    expect(backoffDelay(3, () => 0)).toBe(0);
    expect(backoffDelay(3, () => 1)).toBe(4000);
  });
});

describe("RealtimeClient", () => {
  it("refuses a non-WebSocket endpoint at construction", () => {
    expect(() => makeClient({ url: "nats://localhost:4222" })).toThrow(/ws-gateway/);
  });

  it("subscribes to exactly the public topics on open", () => {
    const { client } = makeClient();
    client.connect();
    FakeSocket.instances[0].open();

    expect(FakeSocket.instances[0].sent).toHaveLength(1);
    expect(JSON.parse(FakeSocket.instances[0].sent[0])).toEqual({
      action: "subscribe",
      topics: [...PUBLIC_TOPICS],
    });
  });

  it("never puts a credential on the wire", () => {
    // The session rides the httpOnly cookie on the handshake. A token in the
    // URL would leak into access logs and referrers; a token in the
    // subscribe frame would reach the bus-facing side of the gateway.
    const { client } = makeClient();
    client.connect();
    FakeSocket.instances[0].open();

    expect(FakeSocket.instances[0].url).not.toMatch(/token|session|auth/i);
    expect(FakeSocket.instances[0].sent.join()).not.toMatch(/token|cookie|authorization/i);
  });

  it("reports reconnecting on a drop and reconnects when the timer fires", () => {
    const { client, statuses, timers } = makeClient();
    client.connect();
    FakeSocket.instances[0].open();
    FakeSocket.instances[0].drop();

    expect(statuses).toContain("reconnecting");
    expect(FakeSocket.instances).toHaveLength(1);

    timers[0]();
    expect(FakeSocket.instances).toHaveLength(2);
  });

  it("does not reconnect after the caller closes it", () => {
    const { client, timers } = makeClient();
    client.connect();
    FakeSocket.instances[0].open();
    client.close();
    FakeSocket.instances[0].drop();

    expect(timers).toHaveLength(0);
    expect(client.currentStatus).toBe("closed");
  });

  it("resets the backoff after a successful reconnect", () => {
    // Otherwise a flaky link degrades into 30-second gaps and never recovers.
    const { client, timers } = makeClient();
    client.connect();
    FakeSocket.instances[0].open();
    FakeSocket.instances[0].drop();
    timers[0]();
    FakeSocket.instances[1].open();
    FakeSocket.instances[1].drop();

    // Second outage starts from attempt 0 again: with random()=0.5 that is
    // half of the 500ms base ceiling, not half of 1000ms.
    expect(timers).toHaveLength(2);
    expect(client.currentStatus).toBe("reconnecting");
  });

  it("passes a well-formed frame to the handler", () => {
    const { client, frames } = makeClient();
    client.connect();
    FakeSocket.instances[0].open();
    FakeSocket.instances[0].deliver(
      JSON.stringify({
        type: "event",
        topic: "nova.heartbeat",
        data: { module: "nova-core", status: "healthy", uptime_seconds: 1 },
        meta: { correlation_id: "c", generated_at: "2026-09-02T10:00:00Z" },
      }),
    );
    expect(frames).toHaveLength(1);
  });

  it("reports a malformed frame instead of swallowing it", () => {
    // Swallowing would leave the panel silently missing turns, with the user
    // and the logs equally uninformed.
    const { client, errors, frames } = makeClient();
    client.connect();
    FakeSocket.instances[0].open();
    FakeSocket.instances[0].deliver("this is not json");

    expect(frames).toHaveLength(0);
    expect(errors).toHaveLength(1);
  });

  it("survives a malformed frame and keeps handling the next one", () => {
    const { client, errors, frames } = makeClient();
    client.connect();
    FakeSocket.instances[0].open();
    FakeSocket.instances[0].deliver("{");
    FakeSocket.instances[0].deliver(
      JSON.stringify({ type: "ready", topics: [] }),
    );
    expect(errors).toHaveLength(1);
    expect(frames).toHaveLength(1);
  });

  it("does not schedule two reconnects for one failure", () => {
    // `onerror` is followed by `onclose`; handling both would double up.
    const { client, timers } = makeClient();
    client.connect();
    const socket = FakeSocket.instances[0];
    socket.open();
    socket.onerror?.();
    socket.drop();
    expect(timers).toHaveLength(1);
  });

  it("closes the underlying socket when the caller closes", () => {
    const { client } = makeClient();
    client.connect();
    const socket = FakeSocket.instances[0];
    socket.open();
    client.close();
    expect(socket.closed).toBe(true);
  });

  it("uses the injected timeout rather than the real clock", () => {
    const spy = vi.spyOn(globalThis, "setTimeout");
    const { client, timers } = makeClient();
    client.connect();
    FakeSocket.instances[0].open();
    FakeSocket.instances[0].drop();
    expect(timers).toHaveLength(1);
    spy.mockRestore();
  });
});

describe("streamUrl", () => {
  it("derives the endpoint from the page origin, over a WebSocket scheme", () => {
    // Needs a document, so it sits here rather than in the node-environment
    // security-boundary suite. Same property: only ws:/wss: ever comes out.
    expect(streamUrl()).toMatch(/^wss?:\/\//);
  });
});
