import { useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";

import { gatewayFetch } from "./http";

/**
 * What NOVA is currently thinking about, and what it last heard from its
 * sensors -- `cognitive-state-engine`'s `/v1/cognitive-state/*` surface (Bible
 * Part 6; TDD 4F.7 §7), read through `api-gateway`.
 *
 * **Read-only, by construction.** Three `GET`s and nothing else: the engine
 * declares no other method (405 for every one), and this module declares no
 * mutation. The panel never creates or promotes a thought, never authors a
 * proposal, never asks for a decision, never executes anything, never changes
 * an autonomy level and never touches a sensor (RS-1b).
 *
 * **No polling and no realtime.** No `refetchInterval`, no `setInterval`, no
 * socket subscription (A-4F7-3 (a); D-4F-6). Data is read on mount, and again
 * only when the operator presses Refresh, which re-issues the same three
 * `GET`s. `perception.sensor.health_changed` does reach the browser on the
 * public topic, but the panel does not listen to it: a refetch triggered by
 * that frame would race the engine's own write and could show the old state.
 *
 * **No user identity is sent.** ADR-025 gives one trusted user per instance and
 * the engine resolves it server-side, so these paths carry no `user_id`.
 *
 * **The schemas are strict** (`.strict()`): an unknown field fails the parse
 * rather than being dropped, so a contract drift surfaces through the
 * degradation notice instead of as data the panel half-understands. The
 * sensor `state` is exactly `perception-engine`'s six lifecycle values
 * (A-4F7-2); any other value is a contract violation, never a state.
 */

/** Bible Part 6's five attention layers, in Part 6's order. */
export const ATTENTION_LAYERS = ["immediate", "active", "passive", "dormant", "archived"] as const;

/** `perception-engine`'s `SensorState`, exactly (A-4F7-2). No health vocabulary. */
export const SENSOR_STATES = [
  "uninitialized",
  "initialized",
  "running",
  "paused",
  "stopped",
  "failed",
] as const;

const proposedActionSchema = z
  .object({
    category: z.string(),
    risk: z.string(),
    action_type: z.string(),
    execution_target: z.string(),
    verification_method: z.string(),
    title: z.string(),
    detail: z.string(),
  })
  .strict();

const thoughtSchema = z
  .object({
    thought_id: z.string(),
    description: z.string(),
    priority: z.number(),
    confidence: z.number(),
    dependencies: z.array(z.string()),
    /** `null` is "not estimated" -- never a date, never a zero. */
    estimated_completion: z.string().nullable(),
    related_memories: z.array(z.string()),
    related_projects: z.array(z.string()),
    current_progress: z.number(),
    attention_layer: z.enum(ATTENTION_LAYERS),
    created_at: z.string(),
    updated_at: z.string(),
    /** A proposal NOVA holds, and nothing about what happened to it (RS-4c). */
    proposed_action: proposedActionSchema.nullable(),
  })
  .strict();

const thoughtListSchema = z.object({ thoughts: z.array(thoughtSchema) }).strict();

const focusEntrySchema = z
  .object({
    thought: thoughtSchema,
    score: z.number(),
    /** Always `[]` today: no production code computes a focus signal (K-5). */
    signals_used: z.array(z.string()),
  })
  .strict();

const focusSchema = z
  .object({
    capacity: z.number(),
    entries: z.array(focusEntrySchema),
  })
  .strict();

const sensorSchema = z
  .object({
    sensor_id: z.string(),
    sensor_type: z.string(),
    state: z.enum(SENSOR_STATES),
    /** When `perception-engine`'s outbox dispatched the report (K-3). */
    reported_at: z.string(),
  })
  .strict();

const sensorListSchema = z.object({ sensors: z.array(sensorSchema) }).strict();

export const cognitiveStateSchemas = {
  thoughts: thoughtListSchema,
  focus: focusSchema,
  sensors: sensorListSchema,
} as const;

export type AttentionLayer = (typeof ATTENTION_LAYERS)[number];
export type SensorLifecycleState = (typeof SENSOR_STATES)[number];
export type ThoughtView = z.infer<typeof thoughtSchema>;
export type ProposedActionView = z.infer<typeof proposedActionSchema>;
export type FocusView = z.infer<typeof focusSchema>;
export type FocusEntryView = z.infer<typeof focusEntrySchema>;
export type SensorView = z.infer<typeof sensorSchema>;

export const cognitiveStateKeys = {
  all: ["cognitive-state"] as const,
  thoughts: ["cognitive-state", "thoughts"] as const,
  focus: ["cognitive-state", "focus"] as const,
  sensors: ["cognitive-state", "sensors"] as const,
};

export function useThoughts() {
  return useQuery({
    queryKey: cognitiveStateKeys.thoughts,
    queryFn: async ({ signal }) =>
      await gatewayFetch("/v1/cognitive-state/thoughts", thoughtListSchema, { signal }),
  });
}

export function useFocus() {
  return useQuery({
    queryKey: cognitiveStateKeys.focus,
    queryFn: async ({ signal }) =>
      await gatewayFetch("/v1/cognitive-state/focus", focusSchema, { signal }),
  });
}

export function useSensors() {
  return useQuery({
    queryKey: cognitiveStateKeys.sensors,
    queryFn: async ({ signal }) =>
      await gatewayFetch("/v1/cognitive-state/sensors", sensorListSchema, { signal }),
  });
}

/**
 * **Refresh** -- re-issue the same three `GET`s, and nothing else.
 *
 * Not a mutation: nothing is written, nothing is patched into the cache, and
 * what renders afterwards is exactly what the engine answered. Invalidating
 * marks the three queries stale, and the mounted ones refetch through their
 * own `queryFn`s -- the same `GET`s the panel issued on mount.
 */
export function useRefreshCognitiveState(): () => Promise<void> {
  const queryClient = useQueryClient();
  return async () => {
    await queryClient.invalidateQueries({ queryKey: cognitiveStateKeys.all });
  };
}
