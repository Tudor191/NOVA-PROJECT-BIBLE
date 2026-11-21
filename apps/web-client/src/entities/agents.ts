import { skipToken, useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { z } from "zod";

import { GatewayError } from "./envelope";
import { gatewayFetch } from "./http";

/**
 * What agents are installed, what is running, and what each one has done.
 *
 * Reads `agent-os/kernel`'s read-only `/v1/agents` surface (decision D-4,
 * built in 4C.2c) through `api-gateway`, plus `agent_os.task.completed` for
 * completions that land while the panel is open.
 *
 * **Read-only, structurally.** The Kernel exposes three `GET` routes and no
 * mutation path at all -- agent lifecycle stays Event-Bus-driven -- so there
 * is deliberately no mutation hook in this module. Adding one would need an
 * endpoint that does not exist.
 *
 * **The shapes below are hand-written, and that is the existing convention.**
 * `AgentPackageView`/`AgentInstanceView`/`ActivityView` are FastAPI response
 * models internal to the Kernel, not `nova_contracts` bus types, so no
 * TypeScript is generated for them -- exactly as for `/v1/plans` and
 * `/v1/reasoning/traces`, whose schemas are hand-written here too. They are
 * strict rather than permissive: a field the Kernel stops sending should
 * surface as a contract violation, not as `undefined` reaching a panel.
 * `AgentOsTaskCompletedPayload` *is* generated, and the realtime half uses it.
 */

/**
 * One installed Agent Package.
 *
 * A projection, not the wire snapshot: the Kernel deliberately does not send
 * `manifest_json` (it carries the package's declared permissions, which
 * nothing here renders), and lifts `manifest_id` out as the human-readable
 * name. `null` is real -- a package whose manifest declares no `id`.
 */
const agentPackageSchema = z.object({
  id: z.string(),
  manifest_id: z.string().nullable(),
  category: z.string(),
  version: z.string(),
  health_status: z.string(),
});

/**
 * One agent instance, field-for-field from `agent_os.agent_instance`.
 *
 * `supervisor_id` is **always `null` today** and is carried rather than
 * dropped: the column exists but no code path writes it, because
 * `agent-os/supervisors` has no identity to write. Surfacing the emptiness is
 * the honest rendering; hiding the field would imply the concept is absent.
 */
const agentInstanceSchema = z.object({
  id: z.string(),
  agent_package_id: z.string(),
  category: z.string(),
  execution_backend: z.string(),
  status: z.string(),
  health_status: z.string(),
  assigned_task_node_id: z.string().nullable(),
  supervisor_id: z.string().nullable(),
  started_at: z.string(),
});

/**
 * The observed supervision topology.
 *
 * `membership_is_derived` is the Kernel telling the truth about its own
 * answer: Phase 3E ships exactly one supervisor, so every instance is
 * supervised by it *by construction* rather than by a row in a table. The
 * panel renders that disclosure rather than swallowing it, and there is no
 * supervisor `id` here because none exists to invent.
 */
const supervisorSchema = z.object({
  category: z.string(),
  instance_ids: z.array(z.string()),
  membership_is_derived: z.boolean(),
});

const agentsSchema = z.object({
  packages: z.array(agentPackageSchema),
  instances: z.array(agentInstanceSchema),
  supervisors: z.array(supervisorSchema),
});

/** One activity row. `correlation_id` is first-class provenance (4C.2b). */
const activitySchema = z.object({
  id: z.string(),
  agent_instance_id: z.string(),
  occurred_at: z.string(),
  kind: z.string(),
  correlation_id: z.string().nullable(),
  detail: z.record(z.string(), z.unknown()),
});

const activityPageSchema = z.object({
  items: z.array(activitySchema),
  next_cursor: z.string().nullable(),
});

export type AgentPackage = z.infer<typeof agentPackageSchema>;
export type AgentInstance = z.infer<typeof agentInstanceSchema>;
export type Supervisor = z.infer<typeof supervisorSchema>;
export type AgentsOverview = z.infer<typeof agentsSchema>;
export type AgentActivity = z.infer<typeof activitySchema>;
export type AgentActivityPage = z.infer<typeof activityPageSchema>;

export const agentKeys = {
  all: ["agents"] as const,
  instance: (id: string) => ["agents", "instance", id] as const,
  activity: (id: string) => ["agents", "activity", id] as const,
};

export function useAgents() {
  return useQuery({
    queryKey: agentKeys.all,
    queryFn: async ({ signal }) => {
      return await gatewayFetch<AgentsOverview>("/v1/agents", agentsSchema, { signal });
    },
  });
}

export function useAgentInstance(instanceId: string | null) {
  return useQuery({
    queryKey: agentKeys.instance(instanceId ?? "none"),
    queryFn:
      instanceId === null
        ? skipToken
        : async ({ signal }) => {
            return await gatewayFetch<AgentInstance>(
              `/v1/agents/${instanceId}`,
              agentInstanceSchema,
              { signal },
            );
          },
  });
}

/**
 * One instance's activity, newest first, **keyset-paginated**.
 *
 * `useInfiniteQuery` because the backend contract is a cursor, not a page
 * number: `next_cursor` is `null` exactly when no further row exists, so
 * "is there more" is the server's answer rather than a length comparison
 * here. Nothing computes an offset, and nothing slices a full list client
 * side -- both would drift under the concurrent inserts an append-only
 * table growing at the head produces, and the second would need the whole
 * history in memory to be wrong with.
 *
 * A rejected cursor is a `400` from the Kernel, which reaches the panel as a
 * `GatewayError` rather than a silent restart at page one.
 */
export function useAgentActivity(instanceId: string | null) {
  return useInfiniteQuery({
    queryKey: agentKeys.activity(instanceId ?? "none"),
    initialPageParam: null as string | null,
    queryFn:
      instanceId === null
        ? skipToken
        : async ({ pageParam, signal }) => {
            const query = pageParam === null ? "" : `?cursor=${encodeURIComponent(pageParam)}`;
            const envelope = await gatewayFetch<AgentActivityPage>(
              `/v1/agents/${instanceId}/activity${query}`,
              activityPageSchema,
              { signal },
            );
            return envelope.data;
          },
    getNextPageParam: (lastPage) => lastPage.next_cursor,
  });
}

/**
 * The Registry could not be reached -- **not** "no packages are installed".
 *
 * Decision D-1 keeps those two answers distinct the whole way up: `200` with
 * `packages: []` means a healthy Registry holding nothing, and `503` means it
 * is unreachable. The Kernel refuses to collapse them, `api-gateway` carries
 * the status through with `error.upstream_status`, and this is where the
 * panel reads the difference. Reporting a degraded Registry as an empty
 * install list would tell the operator the opposite of what is true.
 */
export function isRegistryUnavailable(error: unknown): boolean {
  return error instanceof GatewayError && (error.status === 503 || error.upstreamStatus === 503);
}

/** No such instance -- distinct from an instance that has done nothing yet. */
export function isUnknownInstance(error: unknown): boolean {
  return error instanceof GatewayError && error.status === 404;
}

/** The cursor was not one this backend issued (`400`), never page one again. */
export function isInvalidCursor(error: unknown): boolean {
  return error instanceof GatewayError && error.status === 400;
}
