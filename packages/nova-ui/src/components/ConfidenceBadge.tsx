import { cn } from "../cn";

/**
 * Renders `meta.confidence` from doc 11 §4's envelope.
 *
 * The rule this component exists to enforce is that **a missing confidence
 * is displayed as missing**. Part 8's Confidence System is only worth
 * anything if the absence of a signal is distinguishable from a low one, so
 * `null` renders "no confidence reported" rather than 0%, "—", or a hidden
 * element. `api-gateway` and `ws-gateway` both refuse to synthesise the
 * value upstream; this is the same rule at the last mile.
 */

export type ConfidenceBadgeProps = {
  confidence: number | null | undefined;
  className?: string;
};

/** Bands, not a gradient: a reader should not have to interpret a hue. */
function band(value: number): { label: string; tone: string } {
  if (value >= 0.85) return { label: "high", tone: "nova-confidence-high" };
  if (value >= 0.6) return { label: "moderate", tone: "nova-confidence-moderate" };
  return { label: "low", tone: "nova-confidence-low" };
}

export function ConfidenceBadge({ confidence, className }: ConfidenceBadgeProps) {
  if (confidence === null || confidence === undefined) {
    return (
      <span
        className={cn("nova-badge nova-confidence-absent", className)}
        data-testid="confidence-badge"
        data-confidence="absent"
        title="The engine reported no confidence for this result."
      >
        no confidence reported
      </span>
    );
  }

  const clamped = Math.min(1, Math.max(0, confidence));
  const { label, tone } = band(clamped);
  return (
    <span
      className={cn("nova-badge", tone, className)}
      data-testid="confidence-badge"
      data-confidence={label}
      title={`Confidence reported by the engine: ${clamped.toFixed(2)}`}
    >
      {`${Math.round(clamped * 100)}% ${label}`}
    </span>
  );
}

/**
 * The *tier* variant, for sources that report a word instead of a number.
 *
 * `communication.intent.delivered` carries `confidence_tier` -- a string the
 * content-source engine supplied -- and nothing anywhere on that path
 * converts it to a float. Rendering it through `ConfidenceBadge` would mean
 * inventing a number here at the last possible moment, which is the one
 * thing every layer below has refused to do. So the tier gets its own
 * component and is shown as the word it is.
 *
 * `"unknown"` is the engine's own default for "nobody told me", and reads
 * the same as an absent numeric confidence.
 */

const TIER_TONE: Record<string, string> = {
  high: "nova-confidence-high",
  moderate: "nova-confidence-moderate",
  medium: "nova-confidence-moderate",
  low: "nova-confidence-low",
};

export type ConfidenceTierBadgeProps = {
  tier: string | null | undefined;
  className?: string;
};

export function ConfidenceTierBadge({ tier, className }: ConfidenceTierBadgeProps) {
  const normalised = tier?.trim().toLowerCase();
  if (!normalised || normalised === "unknown") {
    return (
      <span
        className={cn("nova-badge nova-confidence-absent", className)}
        data-testid="confidence-tier-badge"
        data-tier="unknown"
        title="No confidence tier was reported for this utterance."
      >
        no confidence reported
      </span>
    );
  }
  return (
    <span
      className={cn("nova-badge", TIER_TONE[normalised] ?? "nova-confidence-absent", className)}
      data-testid="confidence-tier-badge"
      data-tier={normalised}
      title={`Confidence tier reported by the source engine: ${normalised}`}
    >
      {`${normalised} confidence`}
    </span>
  );
}
