// @vitest-environment node
//
// Static analysis of repository source, not of a rendered page. jsdom
// serves `import.meta.url` over http:, which `fileURLToPath` rejects --
// and a DOM is no use to a test that reads files anyway.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { PUBLIC_TOPICS } from "../../src/realtime/protocol";

/**
 * The client's topic list and the gateway's must be the same set.
 *
 * This is a cross-language contract test, and it is the only thing standing
 * between the two copies. A client list that drifts fails in one of two
 * ways: it asks for a topic the gateway rejects (noisy but visible), or it
 * silently stops asking for one it needs, and a panel goes quiet with no
 * error anywhere. The second is the one worth a test.
 *
 * Reading the Python source is deliberate. Any indirection -- a shared JSON
 * file, a generated constant -- would be a third artifact that can itself
 * drift; the gateway's own module is the authority.
 */

const GATEWAY_PROTOCOL = fileURLToPath(
  new URL(
    "../../../../services/ws-gateway/src/nova_ws_gateway/domain/protocol.py",
    import.meta.url,
  ),
);

function gatewayPublicTopics(): string[] {
  const source = readFileSync(GATEWAY_PROTOCOL, "utf8");
  const block = source.match(/PUBLIC_TOPICS: frozenset\[str\] = frozenset\(\s*\{([\s\S]*?)\}\s*\)/);
  if (!block) {
    throw new Error(
      `Could not find PUBLIC_TOPICS in ${GATEWAY_PROTOCOL}. If the gateway ` +
        `changed shape, fix this parser rather than deleting the test.`,
    );
  }
  // Only string literals, so the `#:`-comment lines above the set (which
  // mention retired topic names) cannot be mistaken for entries.
  return [...block[1].matchAll(/"([^"]+)"/g)].map((match) => match[1]);
}

describe("PUBLIC_TOPICS", () => {
  it("matches ws-gateway's set exactly", () => {
    expect([...PUBLIC_TOPICS].sort()).toEqual(gatewayPublicTopics().sort());
  });

  it("really did read a non-trivial list out of the gateway", () => {
    // Anti-decoration control: a parser that silently returned [] would make
    // the comparison above pass only when our own list was empty too.
    const topics = gatewayPublicTopics();
    expect(topics.length).toBeGreaterThanOrEqual(5);
    expect(topics).toContain("nova.heartbeat");
  });

  it("contains no wildcards", () => {
    // The gateway refuses them, but a client that offers `>` in its UI would
    // be advertising a capability the architecture forbids (doc 09 §6).
    for (const topic of PUBLIC_TOPICS) {
      expect(topic).not.toContain("*");
      expect(topic).not.toContain(">");
    }
  });
});
