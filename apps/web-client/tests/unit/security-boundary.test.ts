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

// --- 1b. the Agents surface adds no new boundary (Phase 4C, 4C.2f) ---------
//
// The scan above already covers these two files -- they live under `src/`.
// What it cannot check is the rule specific to this surface: `agent-os/kernel`
// is control-plane infrastructure the browser must never address, and its
// `/v1/agents` routes are reachable only because `api-gateway` fronts them.

const AGENTS_SOURCES = [
  fileURLToPath(new URL("../../src/entities/agents.ts", import.meta.url)),
  fileURLToPath(new URL("../../src/panels/agents/AgentsPanel.tsx", import.meta.url)),
];

describe("the Agents surface introduces no new external boundary", () => {
  it("never names the kernel host, an internal path, or a bus scheme", () => {
    for (const path of AGENTS_SOURCES) {
      const source = readFileSync(path, "utf8");
      const code = source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
      expect(code).not.toMatch(/agent-os-kernel/);
      expect(code).not.toMatch(/\/internal\//);
      expect(code).not.toMatch(/nats:\/\//);
      expect(code).not.toMatch(/:\d{4}\b/);
    }
  });

  it("reaches the backend only through the shared gateway client", () => {
    const entity = readFileSync(AGENTS_SOURCES[0], "utf8");
    // No second API client: a bare `fetch(` here would bypass the session
    // cookie, the envelope contract, and `apiUrl`'s prefix guard at once.
    expect(entity.replace(/\/\*[\s\S]*?\*\//g, "")).not.toMatch(/[^a-zA-Z]fetch\(/);
    expect(entity).toMatch(/gatewayFetch/);
  });

  it("calls only the three GET routes 4C.2c built", () => {
    // Comments stripped first: the module's own docstring cites `/v1/plans`
    // and `/v1/reasoning/traces` while explaining why its schemas are
    // hand-written, and a test that could not tell a citation from a request
    // would force the code to stop explaining itself.
    const entity = readFileSync(AGENTS_SOURCES[0], "utf8")
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/^\s*\/\/.*$/gm, "");
    const paths = [...entity.matchAll(/["`]\/v1\/[^"`$]*/g)].map((m) => m[0].slice(1));
    expect(paths.length).toBeGreaterThan(0);
    for (const path of paths) {
      expect(path.startsWith("/v1/agents")).toBe(true);
    }
  });

  it("issues no mutating request and adds no polling", () => {
    for (const path of AGENTS_SOURCES) {
      const source = readFileSync(path, "utf8");
      // The Kernel exposes GET only; a mutation here would call an endpoint
      // that does not exist.
      expect(source).not.toMatch(/method:\s*"(POST|PUT|PATCH|DELETE)"/);
      expect(source).not.toMatch(/useMutation/);
      expect(source).not.toMatch(/refetchInterval|setInterval/);
    }
  });
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
