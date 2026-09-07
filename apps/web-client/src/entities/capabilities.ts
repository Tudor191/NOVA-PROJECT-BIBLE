import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";

import { gatewayFetch, gatewayFetchNoContent } from "./http";

/**
 * What NOVA can currently do -- `capability-engine`'s installed registry.
 *
 * **The one 4B panel with no realtime half, and deliberately so.**
 * `capability-engine` publishes no domain events at all; its
 * `events/published.py` lists only outbound RPC requests. Giving this panel
 * a subject to subscribe to would have meant inventing one, which is how
 * `PUBLIC_TOPICS` acquired three dead topics before 4A caught them. A
 * client that subscribes to a topic nothing emits waits forever and looks
 * identical to one that is simply idle.
 *
 * So this is a plain read, refetched only when the operator asks. That is
 * not a polling exemption -- the registry changes when someone installs a
 * capability, which is not a stream of events, and the panel says when it
 * last read it rather than implying it is live.
 */

const capabilitySchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  category: z.string(),
  version: z.string(),
  required_permissions: z.array(z.string()),
  dependencies: z.array(z.string()),
});

export type Capability = z.infer<typeof capabilitySchema>;

const capabilitiesSchema = z.array(capabilitySchema);

export const capabilityKeys = { all: ["capabilities"] as const };

export function useCapabilities() {
  return useQuery({
    queryKey: capabilityKeys.all,
    queryFn: async ({ signal }) => {
      const envelope = await gatewayFetch<Capability[]>("/v1/capabilities", capabilitiesSchema, { signal });
      return envelope;
    },
  });
}

/**
 * The install manifest, exactly `CapabilityManifest` in
 * `capability-engine/domain/models.py` -- "every field `Capability` has,
 * minus the three the installation pipeline itself mints (`id`,
 * `health_status`, `installed_at`)". Named and shaped after the engine's
 * own model rather than a UI-convenient subset, because the engine
 * validates the whole thing and a partial body would 422 on a field the
 * operator was never shown.
 */
export type CapabilityManifest = {
  name: string;
  description: string;
  category: string;
  version: string;
  dependencies: string[];
  required_permissions: string[];
  required_resources: string[];
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  execution_adapter: string;
};

/**
 * Install runs `capability-engine`'s real 8-stage pipeline (TDD 3C §7) --
 * dependency resolution, permission review, an adversarial sandbox probe,
 * registration. It is **not** routed through `action-engine`'s approval
 * loop, and that is the existing policy boundary rather than an omission:
 * the pipeline's own stage 4 is explicitly best-effort disclosure that
 * "never blocks the pipeline ... nothing in TDD 3C says installation blocks
 * pending a reply (unlike `action-engine`'s Critical-risk approval loop)".
 * Sending it through Approvals would invent a second gate the architecture
 * does not have.
 *
 * `POST /v1/capabilities/install` is idempotent on `(name, version)` --
 * Fork 3C-4, Option B -- so a repeated install returns the existing row
 * rather than a duplicate or a 409. A rejected manifest comes back 422 with
 * the failing stage in the message, which `DegradationNotice` renders.
 *
 * **No optimistic insert.** The registry is shared state: the row appears
 * when the engine says it installed, never when the button was pressed. A
 * capability that failed sandbox testing would otherwise have already been
 * drawn as installed.
 */
export function useInstallCapability() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (manifest: CapabilityManifest) => {
      return await gatewayFetch<Capability>("/v1/capabilities/install", capabilitySchema, {
        method: "POST",
        body: manifest,
      });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: capabilityKeys.all }),
  });
}

/**
 * `DELETE /v1/capabilities/{id}` -- 204 on success, 404 if the id is
 * unknown. Same rule as install: nothing is removed from the list until
 * the engine confirms it, because a failed delete that had already
 * disappeared from the panel is worse than a slow one.
 */
export function useUninstallCapability() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (capabilityId: string) => {
      await gatewayFetchNoContent(`/v1/capabilities/${capabilityId}`, { method: "DELETE" });
      return capabilityId;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: capabilityKeys.all }),
  });
}
