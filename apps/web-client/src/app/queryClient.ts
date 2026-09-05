import { QueryClient } from "@tanstack/react-query";

/**
 * The cache `realtime/` hydrates.
 *
 * Refetching is off across the board, and that is the architecture rather
 * than a tuning choice: TDD 4A §5.2 property 1 says **reads are pushed,
 * never polled**. Every 4A query except the session probe has no `queryFn`
 * at all -- `ws-gateway` writes into these keys. A background refetch would
 * either do nothing or, worse, invent a fetch for a key that has no source.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
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
}
