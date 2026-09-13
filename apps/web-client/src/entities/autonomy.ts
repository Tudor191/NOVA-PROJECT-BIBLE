import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";

import { GatewayError } from "./envelope";
import { gatewayFetch, gatewayFetchNoContent } from "./http";

/**
 * How much NOVA may do on its own -- `autonomy-engine`'s `/v1/autonomy`
 * surface (Bible Part 14, TDD 4D §8.1), read through `api-gateway`.
 *
 * **This is the first Phase 4 panel with no realtime half, and the reason is
 * structural rather than an omission.** Decision D-4D-1: `autonomy-engine`
 * claims no `autonomy.*` Event Bus subject, publishes nothing and subscribes
 * to nothing, so there is no subject for this module to listen on. Giving it
 * one would have meant inventing a subject nothing emits -- exactly how
 * `PUBLIC_TOPICS` acquired three dead topics before 4A caught them.
 *
 * That is sound here in a way it would not be for the Agents panel: at
 * Autonomy Levels 0-1 the **user** is the only actor that changes suggestion
 * state, and they change it through this panel. There is nothing to push.
 *
 * **Mutations exist here for the first time in a Phase 4 panel.** Setting a
 * level, editing a policy and deciding a suggestion are explicit user actions
 * with a server round trip -- categorically different from the optimistic
 * cache writes the no-optimistic-mutation rule forbids. Every one of them
 * POSTs, then invalidates; the server's response is the truth. Nothing here
 * patches a cache to make the UI look faster, because a suggestion that
 * *looked* approved while the server refused it is the one failure this whole
 * surface exists to prevent.
 *
 * **No polling.** There is no `refetchInterval` and no `setInterval`.
 *
 * The schemas are strict: an unknown field fails the parse rather than being
 * silently dropped, so a contract that drifts surfaces as a violation instead
 * of as `undefined` reaching a widget.
 */

/** Bible Part 14's five risk tiers, the one canonical scale. */
export const RISK_LEVELS = ["negligible", "low", "moderate", "high", "critical"] as const;
const riskLevelSchema = z.enum(RISK_LEVELS);

/** Bible Part 14's ten permission categories, verbatim and in its order. */
export const PERMISSION_CATEGORIES = [
  "read",
  "analyze",
  "recommend",
  "create",
  "modify",
  "delete",
  "execute",
  "deploy",
  "purchase",
  "communicate",
] as const;
const permissionCategorySchema = z.enum(PERMISSION_CATEGORIES);

/** `deny` and `require_approval` only -- 4D ships no `allow` effect (§6). */
export const POLICY_EFFECTS = ["deny", "require_approval"] as const;
const policyEffectSchema = z.enum(POLICY_EFFECTS);

/**
 * One selectable-or-not autonomy level.
 *
 * `selectable` is separate from the level being listed at all, because Level 2
 * (Assisted) is **defined and disabled**: decision D-1 assigns enabling it to
 * milestone 4F. Omitting it would leave the user unable to see that it exists
 * and is coming; rendering it as selectable would be a lie.
 */
const levelOptionSchema = z.object({
  level: z.number(),
  name: z.string(),
  selectable: z.boolean(),
  note: z.string().nullable(),
});

const levelSchema = z.object({
  level: z.number(),
  name: z.string(),
  updated_at: z.string().nullable(),
  configured: z.boolean(),
  options: z.array(levelOptionSchema),
});

/**
 * One category's trust score.
 *
 * **`score` is `number | null`, and `null` is a first-class answer.** It means
 * *insufficient evidence*, and it must never render as `0` -- 2D-D's own
 * discipline: *"'no data yet' is not the same claim as 'measured zero
 * corrections'"*, and zero corrections would read as **perfect** trust.
 *
 * `status` separates the two ways a score can be absent. `no_data` is a
 * healthy answer for a user with no history; `unavailable` means the upstream
 * could not be consulted at all, and reporting that as the former would be
 * reporting a degraded dependency as an ordinary empty result.
 */
const trustScoreSchema = z.object({
  category: permissionCategorySchema,
  score: z.number().nullable(),
  status: z.enum(["available", "no_data", "unavailable"]),
  evidence_count: z.number(),
  detail: z.string().nullable(),
});

/**
 * One category's grant. `granted: false` is a category with **no row at
 * all** -- no autonomous authority, the fail-closed default. All ten
 * categories are always present so the matrix can show an ungranted one *as*
 * ungranted rather than omitting it.
 */
const permissionGrantSchema = z.object({
  category: permissionCategorySchema,
  max_risk: riskLevelSchema.nullable(),
  requires_approval_above: riskLevelSchema.nullable(),
  granted: z.boolean(),
  updated_at: z.string().nullable(),
});

const permissionMatrixSchema = z.object({
  categories: z.array(permissionGrantSchema),
});

const policyCheckSchema = z.object({
  policy_id: z.string(),
  name: z.string(),
  effect: policyEffectSchema,
  matched: z.boolean(),
});

const policySchema = z.object({
  id: z.string(),
  name: z.string(),
  effect: policyEffectSchema,
  match_category: permissionCategorySchema.nullable(),
  match_min_risk: riskLevelSchema.nullable(),
  match_capability_class: z.string().nullable(),
  enabled: z.boolean(),
  created_at: z.string(),
  updated_at: z.string(),
});

/**
 * Which gates a suggestion passes **now**, not when it was proposed.
 *
 * `policy_checks` lists every policy that was *consulted*, not only those that
 * fired -- without the non-matching entries a reader cannot tell a policy that
 * did not match from a policy that did not exist.
 */
const gateReportSchema = z.object({
  denied: z.boolean(),
  gate: z.string().nullable(),
  reason: z.string().nullable(),
  requires_approval: z.boolean(),
  policy_checks: z.array(policyCheckSchema),
});

const suggestionSchema = z.object({
  id: z.string(),
  category: permissionCategorySchema,
  risk: riskLevelSchema,
  title: z.string(),
  detail: z.string(),
  status: z.enum(["proposed", "approved", "rejected", "expired"]),
  created_at: z.string(),
  decided_at: z.string().nullable(),
  gates: gateReportSchema,
});

const suggestionListSchema = z.object({
  items: z.array(suggestionSchema),
  next_cursor: z.string().nullable(),
});

/**
 * What a decision did. **`executed` is always `false`** and is carried rather
 * than assumed: AC-5 measures exactly that an approved suggestion is recorded
 * and not executed, so the server states it and this panel renders it.
 */
const decisionResultSchema = z.object({
  suggestion: suggestionSchema,
  outcome: z.enum(["observe_only", "propose", "deny", "execute"]),
  executed: z.boolean(),
});

const overviewSchema = z.object({
  level: levelSchema,
  trust: z.array(trustScoreSchema),
  permissions: permissionMatrixSchema,
  proposed_count: z.number(),
  policy_count: z.number(),
  degraded: z.array(z.string()),
});

export type LevelOption = z.infer<typeof levelOptionSchema>;
export type AutonomyLevelView = z.infer<typeof levelSchema>;
export type TrustScore = z.infer<typeof trustScoreSchema>;
export type PermissionGrant = z.infer<typeof permissionGrantSchema>;
export type PermissionMatrix = z.infer<typeof permissionMatrixSchema>;
export type Policy = z.infer<typeof policySchema>;
export type PolicyCheck = z.infer<typeof policyCheckSchema>;
export type GateReport = z.infer<typeof gateReportSchema>;
export type Suggestion = z.infer<typeof suggestionSchema>;
export type SuggestionList = z.infer<typeof suggestionListSchema>;
export type DecisionResult = z.infer<typeof decisionResultSchema>;
export type AutonomyOverview = z.infer<typeof overviewSchema>;
export type PolicyEffect = (typeof POLICY_EFFECTS)[number];
export type PermissionCategory = (typeof PERMISSION_CATEGORIES)[number];
export type RiskLevel = (typeof RISK_LEVELS)[number];

export const autonomyKeys = {
  overview: ["autonomy", "overview"] as const,
  level: ["autonomy", "level"] as const,
  policies: ["autonomy", "policies"] as const,
  permissions: ["autonomy", "permissions"] as const,
  suggestions: ["autonomy", "suggestions"] as const,
};

export function useAutonomyOverview() {
  return useQuery({
    queryKey: autonomyKeys.overview,
    queryFn: async ({ signal }) =>
      await gatewayFetch<AutonomyOverview>("/v1/autonomy", overviewSchema, { signal }),
  });
}

export function useAutonomyPolicies() {
  return useQuery({
    queryKey: autonomyKeys.policies,
    queryFn: async ({ signal }) =>
      await gatewayFetch<Policy[]>("/v1/autonomy/policies", z.array(policySchema), { signal }),
  });
}

/**
 * The suggestion inbox -- the AC-5 surface.
 *
 * Keyset-paginated behind an opaque cursor; nothing here computes an offset.
 * A single page is requested because at Levels 0-1 the inbox is small and the
 * panel shows the newest first; `next_cursor` is carried so a later milestone
 * can page without changing the contract.
 */
export function useSuggestions() {
  return useQuery({
    queryKey: autonomyKeys.suggestions,
    queryFn: async ({ signal }) =>
      await gatewayFetch<SuggestionList>(
        "/v1/autonomy/suggestions?status=proposed",
        suggestionListSchema,
        { signal },
      ),
  });
}

/**
 * Set the autonomy level.
 *
 * **A level the server refuses is refused here too.** Levels 2-5 come back
 * `422` with the reason, which reaches the panel as a `GatewayError` and is
 * rendered -- never clamped to the nearest allowed level, which would leave
 * the user believing they had enabled something they had not.
 */
export function useSetAutonomyLevel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (level: number) =>
      await gatewayFetch<AutonomyLevelView>("/v1/autonomy/level", levelSchema, {
        method: "PUT",
        body: { level },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: autonomyKeys.overview });
      void queryClient.invalidateQueries({ queryKey: autonomyKeys.level });
    },
  });
}

export type PolicyDraft = {
  name: string;
  effect: PolicyEffect;
  match_category: PermissionCategory | null;
  match_min_risk: RiskLevel | null;
  match_capability_class: string | null;
  enabled: boolean;
};

export function useCreatePolicy() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (draft: PolicyDraft) =>
      await gatewayFetch<Policy>("/v1/autonomy/policies", policySchema, {
        method: "POST",
        body: draft,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: autonomyKeys.policies });
      void queryClient.invalidateQueries({ queryKey: autonomyKeys.overview });
      // A new policy can change which gates an existing suggestion passes.
      void queryClient.invalidateQueries({ queryKey: autonomyKeys.suggestions });
    },
  });
}

export function useSetPolicyEnabled() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, enabled }: { id: string; enabled: boolean }) =>
      await gatewayFetch<Policy>(`/v1/autonomy/policies/${id}`, policySchema, {
        method: "PATCH",
        body: { enabled },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: autonomyKeys.policies });
      void queryClient.invalidateQueries({ queryKey: autonomyKeys.suggestions });
    },
  });
}

export function useDeletePolicy() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await gatewayFetchNoContent(`/v1/autonomy/policies/${id}`, { method: "DELETE" });
      return id;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: autonomyKeys.policies });
      void queryClient.invalidateQueries({ queryKey: autonomyKeys.overview });
      void queryClient.invalidateQueries({ queryKey: autonomyKeys.suggestions });
    },
  });
}

export function useSetPermissions() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (grants: PermissionGrant[]) =>
      await gatewayFetch<PermissionMatrix>("/v1/autonomy/permissions", permissionMatrixSchema, {
        method: "PUT",
        body: { grants },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: autonomyKeys.overview });
      void queryClient.invalidateQueries({ queryKey: autonomyKeys.permissions });
      void queryClient.invalidateQueries({ queryKey: autonomyKeys.suggestions });
    },
  });
}

/**
 * **The AC-5 control.** The only transition out of `proposed`.
 *
 * Nothing is patched into the cache on success: the decision POSTs, the server
 * answers, and the inbox is invalidated and re-read. A suggestion the server
 * refuses -- already decided (`409`), or now denied by a policy (`409`) --
 * therefore never appears as decided here, which is the whole point.
 */
export function useDecideSuggestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, decision }: { id: string; decision: "approve" | "reject" }) =>
      await gatewayFetch<DecisionResult>(
        `/v1/autonomy/suggestions/${id}/decide`,
        decisionResultSchema,
        { method: "POST", body: { decision } },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: autonomyKeys.suggestions });
      void queryClient.invalidateQueries({ queryKey: autonomyKeys.overview });
    },
  });
}

/** The suggestion was already decided, or a policy now denies it (`409`). */
export function isDecisionConflict(error: unknown): boolean {
  return error instanceof GatewayError && error.status === 409;
}

/** The level was refused as not selectable, or a cursor was rejected (`422`). */
export function isRefused(error: unknown): boolean {
  return error instanceof GatewayError && error.status === 422;
}

/** `autonomy-engine` could not be reached -- not "nothing is configured". */
export function isAutonomyUnavailable(error: unknown): boolean {
  return error instanceof GatewayError && (error.status === 503 || error.upstreamStatus === 503);
}
