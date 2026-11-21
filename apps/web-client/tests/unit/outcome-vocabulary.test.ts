// @vitest-environment node
//
// Static analysis of repository source, as `topics.test.ts` does: jsdom
// serves `import.meta.url` over http:, which `fileURLToPath` rejects.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { DECISION_OUTCOMES } from "../../src/entities/autonomy";

/**
 * F-4FP-10: the client's decision outcomes and `autonomy-engine`'s
 * `DecisionOutcome` must be the same set.
 *
 * A strict client schema that lacks a served value turns a valid response
 * into a contract-violation notice. Reading the engine's own module is
 * deliberate, for the reason `topics.test.ts` gives: any shared copy would be
 * a third artifact that can itself drift.
 */

const DOMAIN_MODELS = fileURLToPath(
  new URL(
    "../../../../services/autonomy-engine/src/nova_autonomy_engine/domain/models.py",
    import.meta.url,
  ),
);

function servedOutcomes(): string[] {
  const source = readFileSync(DOMAIN_MODELS, "utf8");
  const body = source.match(/class DecisionOutcome\(StrEnum\):([\s\S]*?)\n(?:class |\S)/);
  if (!body) {
    throw new Error(
      `Could not find DecisionOutcome in ${DOMAIN_MODELS}. If the engine ` +
        `changed shape, fix this parser rather than deleting the test.`,
    );
  }
  // Member assignments only, so docstring text that names an outcome cannot
  // be mistaken for one.
  return [...body[1].matchAll(/^ {4}[A-Z_]+ = "([^"]+)"$/gm)].map((match) => match[1]);
}

describe("DECISION_OUTCOMES", () => {
  it("matches autonomy-engine's DecisionOutcome exactly", () => {
    expect([...DECISION_OUTCOMES].sort()).toEqual(servedOutcomes().sort());
  });

  it("really did read the engine's members", () => {
    // Anti-decoration control: a parser returning [] would pass the
    // comparison above only if the client list were empty too.
    const outcomes = servedOutcomes();
    expect(outcomes.length).toBeGreaterThanOrEqual(5);
    expect(outcomes).toContain("propose");
    expect(outcomes).toContain("execution_failed");
  });
});
