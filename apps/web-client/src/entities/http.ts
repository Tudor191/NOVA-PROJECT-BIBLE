import type { z } from "zod";

import { apiUrl } from "../shared/config";
import type { Envelope } from "./envelope";
import { GatewayError, envelopeSchema, parseEnvelope } from "./envelope";

/**
 * The only way this application performs a network request.
 *
 * Everything the client sends goes through `api-gateway` (doc 11 §1) and
 * carries the httpOnly session cookie (D-3), which is why `credentials`
 * is always `"include"` and why no call site is allowed to build its own
 * `fetch`. `apiUrl` refuses any path outside `/v1/`.
 *
 * A failure is never returned as an empty success. Either this resolves with
 * a parsed envelope, or it throws `GatewayError` (a structured failure the
 * gateway reported) or `ContractViolationError` (a response that was not
 * shaped like the contract). Both are rendered by `DegradationNotice`.
 */

export type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
};

function correlationOf(body: unknown): string | null {
  const parsed = envelopeSchema.safeParse(body);
  return parsed.success ? parsed.data.meta.correlation_id : null;
}

export async function gatewayFetch<T>(
  path: string,
  dataSchema: z.ZodType<T>,
  { method = "GET", body, signal }: RequestOptions = {},
): Promise<Envelope<T>> {
  const response = await fetch(apiUrl(path), {
    method,
    signal,
    // The session travels as an httpOnly cookie the JavaScript here cannot
    // read. That is the point of D-3's exchange endpoint: the token never
    // reaches this layer, so it cannot be exfiltrated from it either.
    credentials: "include",
    headers: body === undefined ? undefined : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    // A non-JSON body from the gateway is itself a contract violation, but
    // an unhelpful one to report as a parse error when the status already
    // explains what happened.
    payload = null;
  }

  if (!response.ok) {
    const parsed = envelopeSchema.safeParse(payload);
    const error = parsed.success ? parsed.data.error : null;
    throw new GatewayError(
      error?.code ?? "http_error",
      error?.message ?? `The gateway returned ${response.status}.`,
      response.status,
      correlationOf(payload),
      error?.upstream_status ?? null,
    );
  }

  return parseEnvelope(payload, dataSchema);
}
