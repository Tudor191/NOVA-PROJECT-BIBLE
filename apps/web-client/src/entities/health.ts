import { skipToken, useQuery } from "@tanstack/react-query";

import type {
  HeartbeatPayload,
  ModelHealthChangedPayload,
  ModuleStatusChangedPayload,
} from "@nova/nova-contracts";

/**
 * Per-module health, as the modules themselves reported it.
 *
 * Three sources, all push-fed: `nova.heartbeat` (nova-core's own liveness),
 * `nova.module.status_changed` (a module changing state), and
 * `ai_model.model.health_changed` (a provider going up or down). There is
 * no REST fallback because there is no endpoint to fall back to --
 * `nova-core` exposes only `/internal/*`, which is never routable (doc 11
 * §3). The panel therefore shows what the bus reported or shows that it has
 * heard nothing, which is the honest pair.
 *
 * The System Pulse in the shell header summarises the same heartbeat into
 * one dot; this is the expanded reading behind it. Staleness is computed the
 * same way and for the same reason: a module that stopped reporting must go
 * `unknown`, never keep its last good status. That transition is driven by
 * time passing, not by an event arriving, so it cannot come from a reducer.
 */

export type ModuleStatus = "healthy" | "degraded" | "down" | "starting" | "unknown";

export type ModuleHealth = {
  module: string;
  status: ModuleStatus;
  /** The module's own reason, when it gave one. Never synthesised. */
  reason: string | null;
  /** Envelope `generated_at`: when the module said it, not when we drew it. */
  at: string;
  /** `heartbeat` | `status_changed` | `model` -- which stream said so. */
  source: string;
};

export type HealthState = Record<string, ModuleHealth>;

export const healthKeys = { modules: ["health", "modules"] as const };

/** Matches the System Pulse's own window, so the two never disagree. */
export const HEALTH_STALE_AFTER_MS = 45_000;

export function useModuleHealth() {
  return useQuery<HealthState>({
    queryKey: healthKeys.modules,
    queryFn: skipToken,
    initialData: {},
  });
}

function put(existing: HealthState | undefined, entry: ModuleHealth): HealthState {
  return { ...(existing ?? {}), [entry.module]: entry };
}

export function reduceHeartbeat(
  existing: HealthState | undefined,
  payload: HeartbeatPayload,
  at: string,
): HealthState {
  return put(existing, {
    module: payload.module,
    status: payload.status,
    reason: null,
    at,
    source: "heartbeat",
  });
}

export function reduceModuleStatus(
  existing: HealthState | undefined,
  payload: ModuleStatusChangedPayload,
  at: string,
): HealthState {
  return put(existing, {
    module: payload.module,
    status: payload.status,
    reason: typeof payload.reason === "string" ? payload.reason : null,
    at,
    source: "status_changed",
  });
}

export function reduceModelHealth(
  existing: HealthState | undefined,
  payload: ModelHealthChangedPayload,
  at: string,
): HealthState {
  // Namespaced so a provider named like an engine cannot overwrite it.
  const name = typeof payload.model_id === "string" ? payload.model_id : "unknown-model";
  return put(existing, {
    module: `model:${name}`,
    status: payload.healthy === true ? "healthy" : "down",
    reason: typeof payload.reason === "string" ? payload.reason : null,
    at,
    source: "model",
  });
}

/** A module we stopped hearing from is `unknown`, never its last good status. */
export function withStaleness(state: HealthState, now: number): ModuleHealth[] {
  return Object.values(state)
    .map((entry) =>
      now - Date.parse(entry.at) > HEALTH_STALE_AFTER_MS
        ? { ...entry, status: "unknown" as const }
        : entry,
    )
    .sort((a, b) => a.module.localeCompare(b.module));
}
