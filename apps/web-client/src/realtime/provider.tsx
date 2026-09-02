import { useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

import type { ConnectionStatus, RealtimeClientOptions } from "./client";
import { RealtimeClient } from "./client";
import { isEventFrame } from "./protocol";
import { applyFrame } from "./reconcile";

/**
 * Wires the one socket to the one cache.
 *
 * The provider owns exactly two things: the connection's lifecycle, and the
 * decision about what a disconnect does to cached data. That decision is
 * TDD 4A §7's: on a drop the cache is **marked stale, never cleared**, so a
 * transient blip does not blank the panels. Clearing would also be a lie in
 * the other direction -- the turns already exchanged did happen.
 */

type RealtimeContextValue = {
  status: ConnectionStatus;
  /** Last protocol-level failure, surfaced in the shell rather than logged away. */
  lastError: string | null;
};

const RealtimeContext = createContext<RealtimeContextValue>({
  status: "idle",
  lastError: null,
});

export function useRealtime(): RealtimeContextValue {
  return useContext(RealtimeContext);
}

export type RealtimeProviderProps = {
  children: ReactNode;
  /** The conversation whose frames this client renders. */
  activeSessionId: string | null;
  /** Skips connecting until the shell holds a session (D-3). */
  enabled?: boolean;
  /** Test seam: everything the client needs that is not the frame handler. */
  clientOptions?: Partial<Omit<RealtimeClientOptions, "onFrame" | "onStatus">>;
};

export function RealtimeProvider({
  children,
  activeSessionId,
  enabled = true,
  clientOptions,
}: RealtimeProviderProps) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<ConnectionStatus>("idle");
  const [lastError, setLastError] = useState<string | null>(null);

  // The socket must not be torn down and rebuilt every time the active
  // session changes -- resubscribing on each new conversation would drop
  // frames during the gap. The id is read through a ref instead.
  //
  // Synced in an effect, not during render: React 18 may render and then
  // discard, which would leave this pointing at a session that never
  // committed, and the frame handler would silently filter against it.
  const sessionRef = useRef(activeSessionId);
  useEffect(() => {
    sessionRef.current = activeSessionId;
  }, [activeSessionId]);

  const options = useMemo(() => clientOptions, [clientOptions]);

  useEffect(() => {
    if (!enabled) return;

    const client = new RealtimeClient({
      ...options,
      onFrame: (frame) => {
        if (isEventFrame(frame)) {
          applyFrame(queryClient, frame, sessionRef.current);
          return;
        }
        if (frame.type === "error" && frame.error) {
          setLastError(`${frame.error.code}: ${frame.error.message}`);
        }
      },
      onStatus: (next) => {
        setStatus(next);
        if (next === "reconnecting") {
          // Stale, not gone. Every 4A query is push-fed and has no
          // `queryFn`, so this marks them without triggering a refetch --
          // exactly the "no flash of empty state" behaviour §7 asks for.
          queryClient.invalidateQueries({ refetchType: "none" });
        }
        if (next === "open") {
          setLastError(null);
        }
      },
      onProtocolError: (error) => setLastError(error.message),
    });

    client.connect();
    return () => client.close();
  }, [enabled, options, queryClient]);

  const value = useMemo(() => ({ status, lastError }), [status, lastError]);
  return <RealtimeContext.Provider value={value}>{children}</RealtimeContext.Provider>;
}
