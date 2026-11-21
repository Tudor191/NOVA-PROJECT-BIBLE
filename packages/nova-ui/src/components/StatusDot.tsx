import { cn } from "../cn";

/**
 * A live-status indicator bound to real telemetry.
 *
 * Doc 04 §4 and Bible Part 6 are explicit: **never generate fake
 * animations.** An idle NOVA must look idle because nothing is happening,
 * not because a decorative loop is running. So this component animates only
 * when the caller passes `animate`, and the only caller permitted to pass it
 * is one holding a real signal that just arrived.
 *
 * `unknown` is a first-class state, not a fallback rendering of `down`. "We
 * have not heard yet" and "we heard, and it is down" are different facts and
 * the shell must not blur them.
 */

export type StatusTone = "healthy" | "degraded" | "down" | "unknown";

export type StatusDotProps = {
  status: StatusTone;
  label: string;
  /**
   * Play a single pulse. Bind this to an actual event arrival -- never to a
   * timer, and never to a constant.
   */
  animate?: boolean;
  /** Changes on every real signal; restarts the one-shot pulse. */
  pulseKey?: string | number;
  /**
   * Which instrument this dot is, for tests that must target one of several.
   *
   * A shell header carries more than one of these, so `status-dot` alone
   * only ever resolves positionally -- and a positional selector reads the
   * wrong instrument the moment the header gains one. `data-testid` stays
   * `status-dot` on every dot so "no dot anywhere is animating while
   * unknown" remains one selector.
   */
  instrument?: string;
  className?: string;
};

const TONE: Record<StatusTone, string> = {
  healthy: "nova-status-healthy",
  degraded: "nova-status-degraded",
  down: "nova-status-down",
  unknown: "nova-status-unknown",
};

export function StatusDot({
  status,
  label,
  animate = false,
  pulseKey,
  instrument,
  className,
}: StatusDotProps) {
  return (
    <span
      className={cn("nova-status", className)}
      data-testid="status-dot"
      data-instrument={instrument}
      data-status={status}
    >
      <span
        key={pulseKey}
        aria-hidden="true"
        data-animated={animate ? "true" : "false"}
        className={cn("nova-status-dot", TONE[status], animate && "nova-status-dot-pulse")}
      />
      <span className="nova-status-label">{label}</span>
    </span>
  );
}
