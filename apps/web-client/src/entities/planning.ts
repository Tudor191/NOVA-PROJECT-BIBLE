import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";

import type { PlanningTaskGraphCreatedPayload } from "@nova/nova-contracts";

import { gatewayFetch } from "./http";

/**
 * The task graphs NOVA has planned.
 *
 * `GET /v1/plans` for what already exists, `planning.task_graph.created` for
 * what appears while the panel is open.
 *
 * **`approved_at` is the only mutable thing here, and approving does not
 * gate anything yet.** `planning-engine`'s own endpoint records the
 * timestamp and nothing consumes it -- TDD 3B §5 scoped it that way because
 * no dispatcher existed to honour it. The panel says so rather than
 * implying a click starts work.
 */

const taskNodeSchema = z.object({
  id: z.string(),
  objective: z.string(),
  depends_on: z.array(z.string()),
  status: z.string(),
  risk: z.string(),
});

const taskGraphSchema = z.object({
  id: z.string(),
  root_objective: z.string(),
  nodes: z.array(taskNodeSchema),
  critical_path: z.array(z.string()),
  approved_at: z.string().nullable(),
});

export type TaskGraph = z.infer<typeof taskGraphSchema>;

const taskGraphsSchema = z.array(taskGraphSchema);

export const planningKeys = { all: ["plans"] as const };

export function usePlans() {
  return useQuery({
    queryKey: planningKeys.all,
    queryFn: async ({ signal }) => {
      return await gatewayFetch<TaskGraph[]>("/v1/plans", taskGraphsSchema, { signal });
    },
  });
}

export function useApprovePlan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (taskGraphId: string) => {
      return await gatewayFetch<TaskGraph>(`/v1/plans/${taskGraphId}/approve`, taskGraphSchema, {
        method: "POST",
      });
    },
    // The approved graph comes back from the engine, so this writes what the
    // engine said rather than what the click assumed -- not an optimistic
    // update, a response.
    onSuccess: (envelope) => {
      queryClient.setQueryData<TaskGraph[]>(planningKeys.all, (existing) =>
        (existing ?? []).map((graph) =>
          graph.id === envelope.data.id ? envelope.data : graph,
        ),
      );
    },
  });
}

/**
 * Fold a newly created graph in, newest first.
 *
 * The event payload carries the whole graph, so no follow-up read is needed
 * -- and a re-read would race the very event that told us to make it.
 */
export function reduceTaskGraphCreated(
  existing: TaskGraph[] | undefined,
  payload: PlanningTaskGraphCreatedPayload,
): TaskGraph[] {
  const current = existing ?? [];
  if (current.some((graph) => graph.id === payload.id)) {
    return current;
  }
  const parsed = taskGraphSchema.safeParse(payload);
  // A payload this client cannot read is dropped rather than rendered
  // half-formed; the Events panel still shows the raw frame arrived.
  if (!parsed.success) {
    return current;
  }
  return [parsed.data, ...current];
}
