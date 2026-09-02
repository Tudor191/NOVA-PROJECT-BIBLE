/**
 * Where the client is allowed to talk to.
 *
 * Two addresses, both gateways. There is deliberately no engine URL in this
 * file and no way to configure one: doc 11 §1 makes `api-gateway` the single
 * external surface, and doc 09 §6 makes `ws-gateway` the only bridge from
 * the bus to a browser. A `VITE_COMMUNICATION_ENGINE_URL` would be the
 * architecture quietly coming apart, so the option does not exist.
 *
 * Both default to the current origin, which is what the dev proxy and any
 * sane single-origin deployment give you. Overriding them is for a split
 * deployment only.
 */

const REQUIRED_API_PREFIX = "/v1/";

export class ForbiddenRequestPathError extends Error {}

export const config = {
  /** Base for REST calls. Empty string means "same origin". */
  apiBaseUrl: (import.meta.env.VITE_API_GATEWAY_URL ?? "").replace(/\/$/, ""),
  /** Base for the realtime socket. Empty string means "derive from origin". */
  wsBaseUrl: (import.meta.env.VITE_WS_GATEWAY_URL ?? "").replace(/\/$/, ""),
} as const;

/**
 * Build a REST URL, refusing anything outside the versioned public surface.
 *
 * `api-gateway` already refuses to route `/internal/*` (doc 11 §3, and its
 * own `RouteTable` rejects such a prefix at construction). This is the same
 * rule restated on the client, for a reason worth stating: a gateway that
 * says no is the guarantee, but a client that never asks means a mistake
 * shows up in a unit test here rather than as a 404 in production traffic.
 */
export function apiUrl(path: string): string {
  if (!path.startsWith(REQUIRED_API_PREFIX)) {
    throw new ForbiddenRequestPathError(
      `Refusing to request ${JSON.stringify(path)}: the web client may only ` +
        `call the versioned public surface under '${REQUIRED_API_PREFIX}'. ` +
        `'/internal/*' is never routable (doc 11 §3), and no engine is ` +
        `addressable directly (doc 11 §1).`,
    );
  }
  return `${config.apiBaseUrl}${path}`;
}

/**
 * Resolve the realtime endpoint, upgrading the page's own scheme.
 *
 * Only `ws:`/`wss:` come out of here. A `nats://` URL is not merely
 * unsupported, it is the thing AC-2 exists to make impossible.
 */
export function streamUrl(path = "/v1/stream"): string {
  if (config.wsBaseUrl) {
    const base = new URL(config.wsBaseUrl);
    if (base.protocol !== "ws:" && base.protocol !== "wss:") {
      throw new ForbiddenRequestPathError(
        `VITE_WS_GATEWAY_URL must be ws:// or wss://, got ${base.protocol}. ` +
          `The browser connects to ws-gateway and to nothing else (doc 09 §6).`,
      );
    }
    return `${config.wsBaseUrl}${path}`;
  }
  const scheme = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${scheme}//${window.location.host}/ws${path}`;
}
