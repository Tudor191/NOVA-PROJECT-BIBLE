import { useQuery } from "@tanstack/react-query";
import { z } from "zod";

import type {
  ReasoningProcessCompletedPayload,
  ReasoningProcessFailedPayload,
} from "@nova/nova-contracts";

import { gatewayFetch } from "./http";

/**
 * How NOVA reached its conclusions.
 *
 * `GET /v1/reasoning/traces` for the recorded history,
 * `reasoning.process.completed` / `.failed` for processes that finish while
 * the panel is open.
 *
 * **Confidence is carried, never computed.** `confidence_score` is
 * reasoning-engine's own number and is rendered as a tier word by
 * `ConfidenceTierBadge`; nothing here averages, rounds into a band, or
 * invents one for a trace that reports none. A failed process has no
 * confidence at all, and that is shown as an absence rather than a zero --
 * "the reasoning failed" and "the reasoning was certain it was wrong" are
 * different facts.
 */

const traceSchema = z.object({
  id: z.string(),
  reasoning_process_id: z.string(),
  correlation_id: z.string(),
  reasoning_mode: z.string(),
  reasoning_level: z.number(),
  confidence_score: z.number().nullable(),
  selected_capabilities: z.array(z.string()),
});

export type ReasoningTrace = z.infer<typeof traceSchema>;

const tracesSchema = z.array(traceSchema);

/** A process that finished while we were watching, completed or failed. */
export type LiveProcess = {
  reasoningProcessId: string;
  correlationId: string;
  outcome: "completed" | "failed";
  /** Only ever reasoning-engine's own number, or absent. */
  confidence: number | null;
  /** Present only on failure; the engine's own reason, not a rendering of one. */
  error: string | null;
  at: string;
};

export const reasoningKeys = {
  traces: ["reasoning", "traces"] as const,
  live: ["reasoning", "live"] as const,
};

export function useReasoningTraces() {
  return useQuery({
    queryKey: reasoningKeys.traces,
    queryFn: async ({ signal }) => {
      return await gatewayFetch<ReasoningTrace[]>("/v1/reasoning/traces", tracesSchema, { signal });
    },
  });
}

/** Push-fed: no `queryFn`, so this key has no fetcher and never polls. */
export function useLiveProcesses() {
  return useQuery<LiveProcess[]>({
    queryKey: reasoningKeys.live,
    queryFn: undefined,
    initialData: [],
    enabled: false,
  });
}

const LIVE_PROCESS_LIMIT = 50;

export function reduceProcess(
  existing: LiveProcess[] | undefined,
  entry: LiveProcess,
): LiveProcess[] {
  const current = existing ?? [];
  if (current.some((process) => process.reasoningProcessId === entry.reasoningProcessId)) {
    return current;
  }
  // Newest first, bounded: a session left open for a day must not grow this
  // list without limit.
  return [entry, ...current].slice(0, LIVE_PROCESS_LIMIT);
}

export function processFromCompleted(
  payload: ReasoningProcessCompletedPayload,
  at: string,
): LiveProcess {
  return {
    reasoningProcessId: payload.reasoning_process_id,
    correlationId: payload.correlation_id,
    outcome: "completed",
    confidence:
      typeof payload.confidence_score === "number" ? payload.confidence_score : null,
    error: null,
    at,
  };
}

export function processFromFailed(
  payload: ReasoningProcessFailedPayload,
  at: string,
): LiveProcess {
  return {
    reasoningProcessId: payload.reasoning_process_id,
    correlationId: payload.correlation_id,
    outcome: "failed",
    // A failure reports no confidence. Rendering 0 would claim the engine
    // was certain of something.
    confidence: null,
    error: typeof payload.error === "string" ? payload.error : null,
    at,
  };
}
