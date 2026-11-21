import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";

import { gatewayFetch } from "./http";

/**
 * What NOVA has learned about the user's digital world -- `digital-twin-engine`'s
 * `/v1/digital-twin/domains*` surface (Bible Part 16, TDD 4E §7), read through
 * `api-gateway`.
 *
 * **No realtime half, and like the Autonomy panel the reason is structural.**
 * `PUBLIC_TOPICS` stays at its 18 strings and gains no `digital_twin.*` entry
 * (TDD 4E §8.3): the Digital Twin is a slowly-evolving *derived* model, not an
 * event stream, so there is nothing meaningful to push. Adding a topic would
 * have meant inventing a subject nothing emits -- exactly how `PUBLIC_TOPICS`
 * acquired three dead topics before 4A caught them.
 *
 * **No polling.** No `refetchInterval`, no `setInterval`. Freshness comes from
 * the explicit refresh control, which POSTs and then invalidates; the server's
 * answer is the truth. Nothing here patches a cache to look faster, because a
 * domain that *looked* derived while the server reported it empty is precisely
 * the failure Part 16 §69 exists to prevent.
 *
 * **No user identity is sent.** ADR-025 gives one trusted user per instance and
 * the engine resolves it server-side, so these paths carry no `user_id`.
 *
 * The schemas are strict: an unknown field fails the parse rather than being
 * silently dropped, so a contract drift surfaces as a violation instead of as
 * `undefined` reaching a widget.
 */

/** Bible Part 16 §§71-95's eleven domains, verbatim and in Part 16's order. */
export const TWIN_DOMAINS = [
  "personal_workflow",
  "projects",
  "software_environment",
  "hardware_environment",
  "knowledge_profile",
  "skill_profile",
  "communication_style",
  "productivity_patterns",
  "goals",
  "preferences",
  "learning_progress",
] as const;
const twinDomainSchema = z.enum(TWIN_DOMAINS);

/**
 * TDD 4E §12's four evidence states.
 *
 * `partially_populated` is the one that could not be expressed by 4D's
 * three-state model: `Knowledge Profile` and `Skill Profile` are genuinely
 * half-derived, and rounding that either way is a false claim.
 */
export const DOMAIN_STATES = [
  "populated",
  "partially_populated",
  "empty",
  "unavailable",
] as const;
const domainStateSchema = z.enum(DOMAIN_STATES);

/**
 * Why a domain is not populated -- **an enumerated code, never free text alone**
 * (TDD 4E §14.5 control 10).
 *
 * `code` is what this panel branches on, so the distinctions survive rendering:
 * `no_source_engine` (nothing produces this yet -- Phase 4F's `nova-companion`)
 * is a different statement from `no_autonomous_producer` (the wiring is real and
 * one posted observation would start it), and both differ from
 * `no_evidence_observed` (a new install). `detail` is what a person reads.
 */
const domainReasonSchema = z.object({
  code: z.string(),
  detail: z.string(),
});

const domainSchema = z.object({
  domain: twinDomainSchema,
  state: domainStateSchema,
  reason: domainReasonSchema.nullable(),
  evidence_count: z.number(),
  /** Counts, timestamps and bounded identifiers. Never a memory's content. */
  facts: z.record(z.string(), z.unknown()),
  /**
   * Part 16 fields this domain names that have no evidence source in this
   * release. Rendered rather than hidden: "partial" is not something a reader
   * can act on unless it says which part.
   */
  unavailable_fields: z.array(z.string()),
  derived_at: z.string(),
  /** `communication_style` and `preferences` -- shipped in Phase 2D-D. */
  shipped_before_4e: z.boolean(),
});

const domainListSchema = z.object({
  domains: z.array(domainSchema),
});

const projectSchema = z.object({
  project_id: z.string(),
  memory_count: z.number(),
  memory_type_counts: z.record(z.string(), z.number()),
  first_activity_at: z.string().nullable(),
  last_activity_at: z.string().nullable(),
  /**
   * **`number | null`, and `null` is a first-class answer.** It means no
   * evidence carried a timestamp, and it must never render as `0` -- zero would
   * read as "active today", the opposite of what is known. The same discipline
   * 2D-D applied to a trust score of `null`.
   */
  gap_days: z.number().nullable(),
  derived_at: z.string(),
});

const projectListSchema = z.object({
  domain: domainSchema,
  projects: z.array(projectSchema),
});

const projectDetailSchema = z.object({
  project: projectSchema,
});

export type TwinDomainName = (typeof TWIN_DOMAINS)[number];
export type DomainState = (typeof DOMAIN_STATES)[number];
export type DomainReason = z.infer<typeof domainReasonSchema>;
export type TwinDomainView = z.infer<typeof domainSchema>;
export type ProjectView = z.infer<typeof projectSchema>;
export type ProjectListView = z.infer<typeof projectListSchema>;

export const digitalTwinKeys = {
  domains: ["digital-twin", "domains"] as const,
  projects: ["digital-twin", "projects"] as const,
  project: (id: string) => ["digital-twin", "projects", id] as const,
};

export function useTwinDomains() {
  return useQuery({
    queryKey: digitalTwinKeys.domains,
    queryFn: async ({ signal }) =>
      await gatewayFetch("/v1/digital-twin/domains", domainListSchema, { signal }),
  });
}

export function useTwinProjects() {
  return useQuery({
    queryKey: digitalTwinKeys.projects,
    queryFn: async ({ signal }) =>
      await gatewayFetch("/v1/digital-twin/domains/projects", projectListSchema, { signal }),
  });
}

/**
 * **The AC-6 read** -- *"what was I doing on Project X"* after a multi-week gap.
 *
 * `enabled` gates on a selection rather than fetching a placeholder: with no
 * project chosen there is no question to ask, and requesting one anyway would
 * show a 404 as though the panel had failed.
 */
export function useTwinProject(projectId: string | null) {
  return useQuery({
    queryKey: digitalTwinKeys.project(projectId ?? ""),
    enabled: projectId !== null,
    queryFn: async ({ signal }) =>
      await gatewayFetch(
        `/v1/digital-twin/domains/${encodeURIComponent("projects")}/${encodeURIComponent(
          projectId ?? "",
        )}`,
        projectDetailSchema,
        { signal },
      ),
  });
}

/**
 * Re-derive one domain from its own accumulated evidence.
 *
 * An explicit user action with a server round trip -- categorically different
 * from the optimistic cache writes the no-optimistic-mutation rule forbids. It
 * POSTs, then invalidates; nothing is patched locally. A refresh that *looked*
 * like it had populated a domain the server still reports empty would be the
 * one lie this whole surface exists to prevent.
 */
export function useRefreshDomain() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (domain: TwinDomainName) =>
      await gatewayFetch(
        `/v1/digital-twin/domains/${encodeURIComponent(domain)}/refresh`,
        domainSchema,
        { method: "POST" },
      ),
    onSuccess: (_result, domain) => {
      void queryClient.invalidateQueries({ queryKey: digitalTwinKeys.domains });
      // Refreshing `projects` re-derives every project row with it, so the
      // list and any open detail are stale too.
      if (domain === "projects") {
        void queryClient.invalidateQueries({ queryKey: digitalTwinKeys.projects });
      }
    },
  });
}
