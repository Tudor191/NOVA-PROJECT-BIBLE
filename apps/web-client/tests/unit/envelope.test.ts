import { describe, expect, it } from "vitest";
import { z } from "zod";

import { ContractViolationError, parseEnvelope } from "../../src/entities/envelope";

/**
 * TDD 4A §7's last row: a contract mismatch surfaces as a parse error rather
 * than rendering partial data. A panel showing half a payload is worse than
 * one saying it could not read the answer, because only the second is
 * distinguishable from the truth.
 */

const dataSchema = z.object({ session_id: z.string(), turn_count: z.number() });

const validMeta = {
  correlation_id: "4f1d9c2a-0000-4000-8000-000000000000",
  generated_at: "2026-09-02T10:00:00Z",
};

describe("parseEnvelope", () => {
  it("returns the data and the meta from a well-formed envelope", () => {
    const result = parseEnvelope(
      { data: { session_id: "s1", turn_count: 3 }, meta: validMeta, error: null },
      dataSchema,
    );
    expect(result.data).toEqual({ session_id: "s1", turn_count: 3 });
    expect(result.meta.correlation_id).toBe(validMeta.correlation_id);
  });

  it("keeps an absent confidence absent rather than defaulting it", () => {
    const result = parseEnvelope(
      { data: { session_id: "s1", turn_count: 0 }, meta: validMeta },
      dataSchema,
    );
    expect(result.meta.confidence).toBeUndefined();
  });

  it("preserves a reported zero confidence", () => {
    const result = parseEnvelope(
      { data: { session_id: "s1", turn_count: 0 }, meta: { ...validMeta, confidence: 0 } },
      dataSchema,
    );
    expect(result.meta.confidence).toBe(0);
  });

  it("rejects a response that is not an envelope at all", () => {
    expect(() => parseEnvelope({ session_id: "s1" }, dataSchema)).toThrow(ContractViolationError);
  });

  it("rejects an envelope whose data does not match the contract", () => {
    expect(() =>
      parseEnvelope({ data: { session_id: "s1", turn_count: "three" }, meta: validMeta }, dataSchema),
    ).toThrow(ContractViolationError);
  });

  it("never returns partial data when a field is missing", () => {
    // The failure mode this whole module exists to prevent: rendering a
    // session id with no turn count would look like a working panel.
    expect(() => parseEnvelope({ data: { session_id: "s1" }, meta: validMeta }, dataSchema)).toThrow(
      ContractViolationError,
    );
  });

  it("reports which field was wrong, so the mismatch is diagnosable", () => {
    try {
      parseEnvelope({ data: { session_id: 1, turn_count: 2 }, meta: validMeta }, dataSchema);
      expect.unreachable("should have thrown");
    } catch (error) {
      expect(error).toBeInstanceOf(ContractViolationError);
      expect((error as ContractViolationError).detail).toContain("session_id");
    }
  });
});
