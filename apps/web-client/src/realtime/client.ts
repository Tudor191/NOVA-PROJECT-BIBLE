import { streamUrl } from "../shared/config";
import type { Frame } from "./protocol";
import { MalformedFrameError, PUBLIC_TOPICS, parseFrame, subscribeMessage } from "./protocol";

/**
 * The client's one connection to the outside world's event stream.
 *
 * **This is the only WebSocket in the application.** Doc 09 §6 makes
 * `ws-gateway` the sole component permitted to bridge bus subjects to a
 * browser; `constructUrl` therefore refuses anything that is not `ws:`/`wss:`,
 * and `no-restricted-imports` in `eslint.config.js` plus
 * `tests/unit/security-boundary.test.ts` make sure no NATS client can appear
 * beside it. The session rides the httpOnly cookie on the handshake -- the
 * token is never placed in a query string, where it would leak into access
 * logs and referrers.
 *
 * Reconnection is exponential with jitter and a cap. On a drop the client
 * reports `reconnecting` and **does not touch the cache**: TDD 4A §7 says the
 * Query cache is marked stale, never cleared, so a transient blip does not
 * produce a flash of empty state.
 */

export type ConnectionStatus = "idle" | "connecting" | "open" | "reconnecting" | "closed";

export type RealtimeClientOptions = {
  /** Injected in tests; defaults to the platform `WebSocket`. */
  webSocketImpl?: typeof WebSocket;
  url?: string;
  topics?: readonly string[];
  onFrame: (frame: Frame) => void;
  onStatus?: (status: ConnectionStatus) => void;
  onProtocolError?: (error: Error) => void;
  /** Injected in tests so backoff does not make the suite slow. */
  setTimeoutImpl?: typeof setTimeout;
  clearTimeoutImpl?: typeof clearTimeout;
  randomImpl?: () => number;
};

export const BACKOFF_BASE_MS = 500;
export const BACKOFF_MAX_MS = 30_000;

/**
 * Full jitter: `random(0, min(cap, base * 2^attempt))`.
 *
 * Exported because the shape of the backoff is worth asserting directly --
 * a reconnect loop that hammers the gateway is a defect that only shows up
 * under the exact conditions (an outage) where it does the most harm.
 */
export function backoffDelay(attempt: number, random: () => number = Math.random): number {
  const ceiling = Math.min(BACKOFF_MAX_MS, BACKOFF_BASE_MS * 2 ** attempt);
  return Math.round(random() * ceiling);
}

export class RealtimeClient {
  private socket: WebSocket | null = null;
  private attempt = 0;
  private closedByCaller = false;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private status: ConnectionStatus = "idle";

  private readonly url: string;
  private readonly topics: readonly string[];
  private readonly WebSocketImpl: typeof WebSocket;
  private readonly setTimeoutImpl: typeof setTimeout;
  private readonly clearTimeoutImpl: typeof clearTimeout;
  private readonly random: () => number;

  constructor(private readonly options: RealtimeClientOptions) {
    this.url = options.url ?? streamUrl();
    this.topics = options.topics ?? PUBLIC_TOPICS;
    this.WebSocketImpl = options.webSocketImpl ?? WebSocket;
    this.setTimeoutImpl = options.setTimeoutImpl ?? setTimeout;
    this.clearTimeoutImpl = options.clearTimeoutImpl ?? clearTimeout;
    this.random = options.randomImpl ?? Math.random;
    assertGatewayUrl(this.url);
  }

  get currentStatus(): ConnectionStatus {
    return this.status;
  }

  connect(): void {
    this.closedByCaller = false;
    this.open();
  }

  close(): void {
    this.closedByCaller = true;
    if (this.reconnectTimer !== null) {
      this.clearTimeoutImpl(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.socket?.close();
    this.socket = null;
    this.setStatus("closed");
  }

  private setStatus(status: ConnectionStatus): void {
    if (this.status === status) return;
    this.status = status;
    this.options.onStatus?.(status);
  }

  private open(): void {
    this.setStatus(this.attempt === 0 ? "connecting" : "reconnecting");
    const socket = new this.WebSocketImpl(this.url);
    this.socket = socket;

    socket.onopen = () => {
      this.attempt = 0;
      this.setStatus("open");
      socket.send(subscribeMessage(this.topics));
    };

    socket.onmessage = (event: MessageEvent) => {
      try {
        this.options.onFrame(parseFrame(String(event.data)));
      } catch (error) {
        // A frame we cannot read is reported, not swallowed. Swallowing it
        // would leave the panel silently missing turns with no explanation.
        if (error instanceof MalformedFrameError) {
          this.options.onProtocolError?.(error);
          return;
        }
        throw error;
      }
    };

    socket.onclose = () => {
      this.socket = null;
      if (this.closedByCaller) return;
      this.scheduleReconnect();
    };

    socket.onerror = () => {
      // `onclose` always follows, and it is where reconnection is decided.
      // Handling both would schedule two reconnects for one failure.
    };
  }

  private scheduleReconnect(): void {
    this.setStatus("reconnecting");
    const delay = backoffDelay(this.attempt, this.random);
    this.attempt += 1;
    this.reconnectTimer = this.setTimeoutImpl(() => {
      this.reconnectTimer = null;
      if (!this.closedByCaller) this.open();
    }, delay);
  }
}

/** The realtime endpoint must be the gateway, over a WebSocket scheme. */
export function assertGatewayUrl(url: string): void {
  const scheme = url.slice(0, url.indexOf(":") + 1).toLowerCase();
  if (scheme !== "ws:" && scheme !== "wss:") {
    throw new Error(
      `Refusing to open a realtime connection to ${JSON.stringify(url)}. ` +
        `The browser may only connect to ws-gateway over ws:// or wss:// ` +
        `(doc 09 §6). It must never speak to NATS or any other internal bus.`,
    );
  }
}
