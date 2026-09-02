import { z } from "zod";

/**
 * Doc 11 §4's response envelope, and the one place it is parsed.
 *
 * `api-gateway` wraps every response as `{data, meta, error}`. Parsing it
 * here rather than in each hook means `meta.confidence` and
 * `meta.correlation_id` are available to every panel by construction, which
 * is what TDD 4A §5.2 property 4 ("the envelope is rendered, not hidden")
 * needs to be cheap enough that nobody skips it.
 *
 * A response that does not match this shape raises rather than being coerced.
 * TDD 4A §7's last row: a contract mismatch surfaces as a parse error, never
 * as partially-rendered data -- a panel showing half a payload is worse than
 * a panel saying it could not read the answer.
 */

export const envelopeMetaSchema = z.object({
  correlation_id: z.string(),
  generated_at: z.string(),
  // Absent and null both mean "no confidence was reported". Neither becomes
  // a number here; `ConfidenceBadge` renders the absence as an absence.
  confidence: z.number().nullable().optional(),
});

export const envelopeErrorSchema = z.object({
  code: z.string(),
  message: z.string(),
  upstream_status: z.number().nullable().optional(),
});

export const envelopeSchema = z.object({
  data: z.unknown().nullable().optional(),
  meta: envelopeMetaSchema,
  error: envelopeErrorSchema.nullable().optional(),
});

export type EnvelopeMeta = z.infer<typeof envelopeMetaSchema>;
export type EnvelopeError = z.infer<typeof envelopeErrorSchema>;

export type Envelope<T> = {
  data: T;
  meta: EnvelopeMeta;
};

/** The response was not shaped like doc 11 §4 says it must be. */
export class ContractViolationError extends Error {
  constructor(
    message: string,
    readonly detail: string,
  ) {
    super(message);
    this.name = "ContractViolationError";
  }
}

/** The gateway answered, and the answer was a structured failure. */
export class GatewayError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
    readonly correlationId: string | null,
    readonly upstreamStatus: number | null = null,
  ) {
    super(message);
    this.name = "GatewayError";
  }

  /** The session is gone or was never valid -- the shell re-runs first-run auth. */
  get isUnauthenticated(): boolean {
    return this.status === 401 || this.code === "unauthenticated";
  }

  get isRateLimited(): boolean {
    return this.status === 429 || this.code === "rate_limited";
  }
}

/**
 * Validate one envelope and narrow `data` with the caller's schema.
 *
 * The `data` schema is the point: `entities/` hooks pass a schema derived
 * from the generated contract types, so a panel cannot compile -- or run --
 * against a payload shape the engines do not produce.
 */
export function parseEnvelope<T>(body: unknown, dataSchema: z.ZodType<T>): Envelope<T> {
  const outer = envelopeSchema.safeParse(body);
  if (!outer.success) {
    throw new ContractViolationError(
      "The gateway returned a response that is not a doc 11 §4 envelope.",
      outer.error.issues.map((i) => `${i.path.join(".") || "<root>"}: ${i.message}`).join("; "),
    );
  }
  const parsedData = dataSchema.safeParse(outer.data.data);
  if (!parsedData.success) {
    throw new ContractViolationError(
      "The gateway returned an envelope whose data does not match the contract.",
      parsedData.error.issues
        .map((i) => `${i.path.join(".") || "<root>"}: ${i.message}`)
        .join("; "),
    );
  }
  return { data: parsedData.data, meta: outer.data.meta };
}
