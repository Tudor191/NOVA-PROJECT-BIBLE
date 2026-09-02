import { StatusDot } from "@nova/ui";
import type { StatusTone } from "@nova/ui";

import type { ConnectionStatus } from "../realtime/client";
import { useRealtime } from "../realtime/provider";

/**
 * Whether the realtime stream is actually live.
 *
 * Visible at all times, per TDD 4A §7: when the socket drops, the cache is
 * marked stale rather than cleared, so the panels keep showing the last
 * known truth. That is the right behaviour *only* if the user can also see
 * that it is the last known truth rather than the current one. This is that
 * disclosure.
 */

const TONE: Record<ConnectionStatus, StatusTone> = {
  idle: "unknown",
  connecting: "unknown",
  open: "healthy",
  reconnecting: "degraded",
  closed: "down",
};

const LABEL: Record<ConnectionStatus, string> = {
  idle: "Stream idle",
  connecting: "Connecting…",
  open: "Live",
  reconnecting: "Reconnecting — showing last known state",
  closed: "Disconnected",
};

export function ConnectionState() {
  const { status, lastError } = useRealtime();
  return (
    <span className="flex items-center gap-2">
      <StatusDot status={TONE[status]} label={LABEL[status]} />
      {lastError ? (
        <span className="nova-correlation" role="status" data-testid="realtime-error">
          {lastError}
        </span>
      ) : null}
    </span>
  );
}
