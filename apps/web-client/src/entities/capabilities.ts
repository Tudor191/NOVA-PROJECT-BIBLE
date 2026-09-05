import { useQuery } from "@tanstack/react-query";
import { z } from "zod";

import { gatewayFetch } from "./http";

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
