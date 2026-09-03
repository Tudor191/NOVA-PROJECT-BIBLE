import { StatusDot } from "@nova/ui";

import { usePresentIdentities } from "../entities/presence";

/**
 * Who NOVA believes is present (doc 04 §4's shell-level indicator).
 *
 * The distinction the component is built around: **`null` is "we have not
 * heard", `[]` is "perception told us nobody is here".** Rendering both as
 * "nobody present" would be the UI asserting something the system never
 * said, which is the same failure as a fabricated confidence.
 *
 * It never animates. Presence is a state, not an event, and there is no
 * honest beat to bind a pulse to.
 */
export function PresenceIndicator() {
  const { data: identities } = usePresentIdentities();

  if (identities === null || identities === undefined) {
    return <StatusDot status="unknown" label="Presence unknown" instrument="presence" />;
  }

  if (identities.length === 0) {
    return <StatusDot status="degraded" label="Nobody recognised" instrument="presence" />;
  }

  return (
    <StatusDot
      status="healthy"
      instrument="presence"
      label={
        identities.length === 1
          ? `1 person present`
          : `${identities.length} people present`
      }
    />
  );
}
