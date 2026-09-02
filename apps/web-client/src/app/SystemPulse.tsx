import { StatusDot } from "@nova/ui";
import { useEffect, useState } from "react";

import { summarisePulse, usePulse } from "../entities/pulse";

/**
 * The System Pulse (doc 04 §4), bound to `nova.heartbeat` and nothing else.
 *
 * Two properties this component exists to hold, both from Bible Part 6's
 * "never generate fake animations":
 *
 * 1. **No heartbeat, no animation.** Before the first beat the indicator is
 *    `unknown` and still. There is no timer driving a decorative loop.
 * 2. **The animation is one shot per real beat.** `pulseKey` is the summed
 *    beat count, so the CSS keyframe replays exactly when a heartbeat
 *    actually arrived. Nothing else can make it move.
 *
 * The interval below is not an animation clock -- it re-evaluates
 * *staleness*, which is the case a decorative UI gets wrong: a heartbeat
 * that stopped must turn the indicator to `unknown`, and that transition is
 * driven by time passing, not by an event arriving.
 */

const STALENESS_TICK_MS = 5_000;

export function SystemPulse() {
  const { data: pulse } = usePulse();
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), STALENESS_TICK_MS);
    return () => clearInterval(timer);
  }, []);

  const { status, sequence, modules } = summarisePulse(pulse ?? null, now);

  const label =
    status === "unknown"
      ? modules === 0
        ? "No heartbeat yet"
        : "Heartbeat lost"
      : `${modules} module${modules === 1 ? "" : "s"}`;

  return (
    <StatusDot
      status={status}
      label={label}
      // Only a real beat can be a reason to move.
      animate={status !== "unknown"}
      pulseKey={sequence}
    />
  );
}
