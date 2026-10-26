import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";
import type { QueryKey } from "@tanstack/react-query";

import { GatewayError } from "../entities/envelope";
import { sessionKeys } from "../entities/session";

/**
 * The cache `realtime/` hydrates.
 *
 * Refetching is off across the board, and that is the architecture rather
 * than a tuning choice: TDD 4A §5.2 property 1 says **reads are pushed,
 * never polled**. Every 4A query except the session probe has no `queryFn`
 * at all -- `ws-gateway` writes into these keys. A background refetch would
 * either do nothing or, worse, invent a fetch for a key that has no source.
 *
 * *(Added 2026-10-16.)* **A 401 anywhere re-asks the session probe** -- TDD
 * 4A §7: *"`api-gateway` rejects with 401; the frontend re-runs the first-run
 * session flow"*. Until then a refused request only showed "This session is
 * no longer valid" in its own panel, and nothing returned the user to the
 * token prompt. The probe is re-asked rather than overwritten, so the prompt
 * appears only when `GET /v1/auth/session` agrees the session is gone; a 401
 * it contradicts stays that request's own failure. No refetch is added for
 * anything else.
 */
export function createQueryClient(): QueryClient {
  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({
      onError: (error, query) => recheckSession(client, error, query.queryKey),
    }),
    mutationCache: new MutationCache({
      onError: (error, _variables, _context, mutation) =>
        recheckSession(client, error, mutation.options.mutationKey),
    }),
    defaultOptions: {
      queries: {
        refetchOnWindowFocus: false,
        refetchOnReconnect: false,
        refetchInterval: false,
        // Push-fed data is never stale in the polling sense; the connection
        // indicator is what tells the user whether it is current.
        staleTime: Infinity,
        retry: false,
      },
      mutations: { retry: false },
    },
  });
  return client;
}

/**
 * The session's own requests are excluded: the probe re-asking itself would
 * loop, and a refused token is already the answer `SessionGate` shows.
 */
function recheckSession(client: QueryClient, error: unknown, key: QueryKey | undefined): void {
  if (!(error instanceof GatewayError) || !error.isUnauthenticated) return;
  if (key !== undefined && key[0] === sessionKeys.current[0]) return;
  // Several panels failing at once share one in-flight probe.
  void client.invalidateQueries({ queryKey: sessionKeys.current }, { cancelRefetch: false });
}
