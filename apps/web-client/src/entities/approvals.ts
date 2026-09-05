import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";

import type {
  ActionApprovalDecidedPayload,
  ActionApprovalRequestedPayload,
} from "@nova/nova-contracts";

import { gatewayFetch } from "./http";

/**
 * Actions waiting on a human decision.
 *
 * Two halves, and the split is the point. `GET /v1/action/approvals` gives
 * the queue as it stands when the panel opens; `action.approval.requested`
 * and `.decided` keep it current afterwards. A queue whose whole purpose is
 * to change while someone is looking at it is exactly what doc 04's "reads
 * are pushed, never polled" is about -- re-fetching on a timer would show a
 * request up to one interval late, which for an approval is the interval
 * during which NOVA is blocked.
 *
 * **No optimistic update.** Deciding an approval is shared cognitive state:
 * the row leaves this list when `action.approval.decided` says
 * action-engine recorded the decision, never when the button was clicked.
 * An optimistic removal would show a decision that a 409 (already decided
 * by someone else) or a network failure never actually made.
 */

const pendingApprovalSchema = z.object({
  action_id: z.string(),
  risk: z.string(),
  requested_at: z.string(),
});

export type PendingApproval = z.infer<typeof pendingApprovalSchema>;

const pendingApprovalsSchema = z.array(pendingApprovalSchema);

export const approvalKeys = { pending: ["approvals", "pending"] as const };

export function useApprovals() {
  return useQuery({
    queryKey: approvalKeys.pending,
    queryFn: async ({ signal }) => {
      return await gatewayFetch<PendingApproval[]>("/v1/action/approvals", pendingApprovalsSchema, { signal });
    },
  });
}

const decisionSchema = z.object({
  action_id: z.string(),
  decision: z.enum(["approved", "denied"]),
});

export function useDecideApproval() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ actionId, approved }: { actionId: string; approved: boolean }) => {
      return await gatewayFetch(
        `/v1/action/approvals/${actionId}/decide`,
        decisionSchema,
        { method: "POST", body: { approved } },
      );
    },
    // Deliberately no `onMutate` optimistic removal, and no `setQueryData`
    // on success either: the row disappears when the bus confirms it. What
    // this does do is mark the query stale so a reconnect re-reads a queue
    // that may have moved on without us.
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: approvalKeys.pending, refetchType: "none" });
    },
  });
}

/** Fold a newly requested approval into the pending list, newest-last. */
export function reduceRequested(
  existing: PendingApproval[] | undefined,
  payload: ActionApprovalRequestedPayload,
): PendingApproval[] {
  const current = existing ?? [];
  if (current.some((approval) => approval.action_id === payload.action_id)) {
    return current;
  }
  const entry: PendingApproval = {
    action_id: payload.action_id,
    risk: payload.risk,
    requested_at: payload.requested_at,
  };
  // Oldest first, matching the endpoint: what has been blocked longest is
  // what most likely matters.
  return [...current, entry].sort((a, b) =>
    Date.parse(a.requested_at) - Date.parse(b.requested_at),
  );
}

/** Drop a decided approval. The queue answers "what is waiting", not "what happened". */
export function reduceDecided(
  existing: PendingApproval[] | undefined,
  payload: ActionApprovalDecidedPayload,
): PendingApproval[] {
  return (existing ?? []).filter((approval) => approval.action_id !== payload.action_id);
}
