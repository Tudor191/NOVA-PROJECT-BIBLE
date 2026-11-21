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

/**
 * **`reasoning_level` and recursion depth are two different facts**, and the
 * panel shows both because substituting one for the other loses the one
 * Phase 3A added.
 *
 * `reasoning_level` is Bible Part 8's "Levels of Reasoning" — a 1–4 cost/depth
 * *dial the caller sets*, carried on the request as `reasoning_level_hint`.
 * The recursion depth is *what the Multi-step pipeline actually did*: design
 * doc §11's `steps` tree, bounded by `ModeConfig.max_step_depth` (default 1,
 * ">1 engages recursion"). A level-4 request that recursed once and a
 * level-4 request that recursed three times report the same
 * `reasoning_level` and different depths.
 *
 * Both values are already on the trace the engine returns, so nothing new is
 * minted here: `steps` is the recursion tree itself, and
 * `multistep_recursion_exhausted` is the engine's own flag for "hit
 * `max_step_depth` while still below `verify_threshold`". Depth is derived
 * from the tree rather than stored, because the tree is the fact and a
 * stored integer beside it could disagree with it.
 */
export type ReasoningTrace = {
  id: string;
  reasoning_process_id: string;
  correlation_id: string;
  reasoning_mode: string;
  reasoning_level: number;
  confidence_score: number | null;
  selected_capabilities: string[];
  /** §11's recursion tree. Empty for a single-step trace. */
  steps: ReasoningTrace[];
  /** Phase 3A: `max_step_depth` was reached with confidence still too low. */
  multistep_recursion_exhausted: boolean;
};

const traceSchema: z.ZodType<ReasoningTrace> = z.lazy(() =>
  z.object({
    id: z.string(),
    reasoning_process_id: z.string(),
    correlation_id: z.string(),
    reasoning_mode: z.string(),
    reasoning_level: z.number(),
    confidence_score: z.number().nullable(),
    selected_capabilities: z.array(z.string()),
    steps: z.array(traceSchema),
    multistep_recursion_exhausted: z.boolean(),
  }),
);

/**
 * How many step-levels this trace actually used, counted the way
 * `max_step_depth` counts them: a trace that never recursed is depth 1, so
 * the number is directly comparable against the configured cap rather than
 * being an off-by-one away from it.
 */
export function recursionDepth(trace: ReasoningTrace): number {
  const children = trace.steps ?? [];
  if (children.length === 0) return 1;
  return 1 + Math.max(...children.map(recursionDepth));
}

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
