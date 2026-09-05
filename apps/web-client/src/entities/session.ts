import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";

import { gatewayFetch } from "./http";

/**
 * Decision **D-3**: one long-lived local token, exchanged once for an
 * httpOnly cookie.
 *
 * The token is presented exactly once, here, and never again reaches
 * JavaScript -- `api-gateway` sets the cookie, and every later call rides it
 * via `credentials: "include"`. Doc 04 §5's `useSession()` row, and the whole
 * of Phase 4's auth surface: no registration, no refresh rotation, no
 * external identity provider. Phase 7's `nova-auth` replaces the gateway
 * side without touching this module's shape.
 */

const sessionStateSchema = z.object({ authenticated: z.boolean() });

export const sessionKeys = { current: ["session"] as const };

/**
 * Whether a valid session is currently held.
 *
 * `GET /v1/auth/session` exists so the shell can answer this on boot without
 * provoking a 401 on a real endpoint first -- a 401 would be indistinguishable
 * from a genuine failure of whatever it was asked to do.
 */
export function useSession() {
  return useQuery({
    queryKey: sessionKeys.current,
    queryFn: async () => {
      const { data } = await gatewayFetch("/v1/auth/session", sessionStateSchema);
      return data;
    },
    // An unauthenticated answer is a fact, not a transient failure; retrying
    // it just delays the login form.
    retry: false,
    staleTime: 30_000,
  });
}

export function useIssueSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (token: string) => {
      const { data } = await gatewayFetch("/v1/auth/session", sessionStateSchema, {
        method: "POST",
        body: { token },
      });
      return data;
    },
    onSuccess: (state) => {
      queryClient.setQueryData(sessionKeys.current, state);
    },
  });
}

export function useEndSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await gatewayFetch("/v1/auth/session", sessionStateSchema, {
        method: "DELETE",
      });
      return data;
    },
    onSuccess: () => {
      // Signing out is the one case where dropping cached cognitive state is
      // right: it belonged to a session that no longer exists.
      queryClient.clear();
    },
  });
}
