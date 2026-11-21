import { skipToken, useQuery } from "@tanstack/react-query";

import type { HeartbeatPayload } from "@nova/nova-contracts";

/**
 * The System Pulse's data, from `nova.heartbeat` and nothing else.
 *
 * Doc 04 §4 requires the idle state to be driven by **real background-engine
 * telemetry**, and Bible Part 6 forbids fake animation. So this module has
 * no timer, no simulated beat, and no default status: until a heartbeat
 * arrives the pulse is `null`, which the shell renders as *unknown*.
 *
 * Staleness is computed, not assumed. A heartbeat that stopped arriving is
 * the interesting case -- it is exactly when a decorative UI would keep
 * animating and tell the user everything is fine.
 */

export type ModuleHeartbeat = {
  module: string;
  status: HeartbeatPayload["status"];
  uptimeSeconds: number;
  /** Envelope `generated_at`: when the module beat, not when we rendered. */
  at: string;
  /** Monotonically increasing per beat; drives the one-shot pulse animation. */
  sequence: number;
};

export type PulseState = Record<string, ModuleHeartbeat>;

export const pulseKeys = { current: ["pulse"] as const };

/**
 * A heartbeat older than this is treated as no longer live.
 *
 * `nova-core` beats on a fixed interval; this is a generous multiple of it,
 * so a single missed beat does not flip the indicator, while a stopped
 * process does.
 */
export const HEARTBEAT_STALE_AFTER_MS = 45_000;

export function reducePulse(
  existing: PulseState | null,
  payload: HeartbeatPayload,
  at: string,
): PulseState {
  const previous = existing?.[payload.module];
  return {
    ...(existing ?? {}),
    [payload.module]: {
      module: payload.module,
      status: payload.status,
      uptimeSeconds: payload.uptime_seconds,
      at,
      sequence: (previous?.sequence ?? 0) + 1,
    },
  };
}

/**
 * Fold every module's beat into one indicator.
 *
 * Worst status wins, and silence beats everything: a module we stopped
 * hearing from is `unknown`, never `healthy` left over from its last beat.
 */
export function summarisePulse(
  state: PulseState | null,
  now: number,
): { status: "healthy" | "degraded" | "down" | "unknown"; sequence: number; modules: number } {
  const beats = Object.values(state ?? {});
  if (beats.length === 0) {
    return { status: "unknown", sequence: 0, modules: 0 };
  }
  const sequence = beats.reduce((total, beat) => total + beat.sequence, 0);
  const fresh = beats.filter((beat) => now - Date.parse(beat.at) <= HEARTBEAT_STALE_AFTER_MS);
  if (fresh.length === 0) {
    return { status: "unknown", sequence, modules: beats.length };
  }
  if (fresh.some((beat) => beat.status === "down")) {
    return { status: "down", sequence, modules: beats.length };
  }
  if (fresh.some((beat) => beat.status === "degraded" || beat.status === "starting")) {
    return { status: "degraded", sequence, modules: beats.length };
  }
  // Some modules were heard from and none is unhealthy -- but if others have
  // gone silent, that is a degradation, not a clean bill of health.
  if (fresh.length < beats.length) {
    return { status: "degraded", sequence, modules: beats.length };
  }
  return { status: "healthy", sequence, modules: beats.length };
}

export function usePulse() {
  return useQuery<PulseState | null>({
    queryKey: pulseKeys.current,
    queryFn: skipToken,
    initialData: null,
  });
}
