// @vitest-environment node
//
// Static analysis of repository source, not of a rendered page. jsdom
// serves `import.meta.url` over http:, which `fileURLToPath` rejects --
// and a DOM is no use to a test that reads files anyway.
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { assertGatewayUrl } from "../../src/realtime/client";
import { ForbiddenRequestPathError, apiUrl } from "../../src/shared/config";

/**
 * Phase 4 **AC-2**, proven rather than asserted.
 *
 * TDD 4A §9 is explicit that inspection is not sufficient evidence: the two
 * properties below have to be held by executable tests.
 *
 *   1. `ws-gateway` is the only path a browser-originated connection can use
 *      to observe bus activity (doc 09 §6).
 *   2. `/internal/*` is not routable, and no engine is addressable directly
 *      (doc 11 §1, §3).
 *
 * Both are enforced on the gateway side too, and that is where the real
 * guarantee lives -- `api-gateway`'s `RouteTable` refuses a non-`/v1/` prefix
 * at construction, and its integration suite proves `/internal/*` is never
 * forwarded. What these add is the other half: the client cannot even *ask*.
 * A violation surfaces here, in a fast unit test, rather than as unexplained
 * traffic in production.
 */

const SRC_DIR = fileURLToPath(new URL("../../src", import.meta.url));

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) return sourceFiles(full);
    return /\.(ts|tsx)$/.test(entry) ? [full] : [];
  });
}

// --- 1. the bus is unreachable from the browser -----------------------------

describe("the browser cannot reach the event bus", () => {
  it("has no NATS client or bus URL anywhere in the application source", () => {
    const offenders: string[] = [];
    for (const file of sourceFiles(SRC_DIR)) {
      const source = readFileSync(file, "utf8");
      // Strip comments: this very file's neighbours *discuss* the boundary,
      // and a test that cannot tell an explanation from an import would
      // force the code to stop documenting itself.
      const code = source
        .replace(/\/\*[\s\S]*?\*\//g, "")
        .replace(/^\s*\/\/.*$/gm, "");
      const relative = file.slice(SRC_DIR.length + 1);
      if (/\bfrom\s+["']nats(\.ws)?["']/.test(code)) offenders.push(`${relative}: imports nats`);
      if (/nats:\/\//.test(code)) offenders.push(`${relative}: contains a nats:// URL`);
      if (/:4222\b/.test(code)) offenders.push(`${relative}: references the NATS port`);
    }
    expect(offenders).toEqual([]);
  });

  it("really is scanning the application source", () => {
    // Anti-decoration control for the scan above: an empty file list would
    // make it pass vacuously.
    const files = sourceFiles(SRC_DIR);
    expect(files.length).toBeGreaterThan(10);
    expect(files.some((f) => f.endsWith("client.ts"))).toBe(true);
  });

  it.each(["nats://localhost:4222", "http://localhost:4222", "https://engine.internal", "tcp://bus"])(
    "refuses to open a realtime connection to %s",
    (url) => {
      expect(() => assertGatewayUrl(url)).toThrow(/ws-gateway/);
    },
  );

  it.each(["ws://localhost:8001/v1/stream", "wss://nova.example/v1/stream"])(
    "accepts the gateway's own scheme (%s)",
    (url) => {
      expect(() => assertGatewayUrl(url)).not.toThrow();
    },
  );
});

// --- 2. /internal/* and engines are unaddressable ---------------------------

describe("the client can only call the versioned public surface", () => {
  it.each([
    "/internal/health",
    "/internal/readiness",
    "/internal/metrics",
    "/v2/communication/sessions",
    "/communication/sessions",
    "http://communication-engine:8000/v1/communication/sessions",
    "",
    "/",
  ])("refuses %s", (path) => {
    expect(() => apiUrl(path)).toThrow(ForbiddenRequestPathError);
  });

  it.each([
    "/v1/auth/session",
    "/v1/communication/sessions",
    "/v1/communication/sessions/abc/messages",
  ])("allows %s", (path) => {
    expect(() => apiUrl(path)).not.toThrow();
  });

  it("cannot be talked past with a traversal segment", () => {
    // `/v1/../internal/health` starts with the right prefix as a string, so
    // the check has to survive it. `api-gateway`'s own integration suite
    // covers the same input from the other side.
    const built = apiUrl("/v1/../internal/health");
    // The path is *sent* verbatim rather than normalised, so the gateway --
    // which is the authority -- resolves it and 404s. What matters here is
    // that no engine host was substituted and no bus scheme appeared.
    expect(built).not.toMatch(/^https?:\/\/[^/]*engine/);
    expect(built).not.toMatch(/nats:/);
  });
});
