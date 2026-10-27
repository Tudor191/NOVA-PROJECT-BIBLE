import { Button, Panel } from "@nova/ui";
import { useState } from "react";

import type { ProjectView, TwinDomainName, TwinDomainView } from "../../entities/digitalTwin";
import {
  useRefreshDomain,
  useTwinDomains,
  useTwinProject,
  useTwinProjects,
} from "../../entities/digitalTwin";
import { AsyncPanelBody } from "../shared/AsyncPanelBody";

/**
 * What NOVA has learned about the user's digital world -- Bible Part 16's
 * eleven domains, and the AC-6 project reconstruction (TDD 4E §13).
 *
 * **The hardest thing this panel does is render an absence honestly.** Seven of
 * the eleven domains are unpopulated on a fresh install, and each is unpopulated
 * for a *different* reason: `Software Environment` has no producing engine at all
 * until Phase 4F, `Productivity Patterns` has a real subscription that nothing in
 * a stock deployment emits, and `Goals` is simply waiting for this user's first
 * recorded decision. Rendering all three as an empty card would tell the operator
 * that NOVA knows nothing, when what is true is that NOVA knows nothing *yet*,
 * for three quite different reasons. So the reason is rendered, always, and the
 * machine-readable code is what decides the wording rather than a heuristic over
 * the prose.
 *
 * **Nothing here is fabricated, defaulted or zero-filled.** An unpopulated domain
 * shows its reason, never a `0`. A project with no timestamped evidence shows
 * "no dated activity", never "0 days ago" -- which would read as *active today*,
 * the opposite of what is known. This is Part 16 §69 (*"Never create assumptions
 * without evidence"*) at the rendering edge, and it is where a violation would be
 * most convincing and least visible.
 *
 * **Refresh mutates, and that is the distinction the no-optimistic-mutation rule
 * turns on.** It is an explicit user action with a server round trip: it POSTs,
 * then invalidates, and nothing is drawn as derived until the server says it is.
 *
 * **No polling and no realtime.** `PUBLIC_TOPICS` gains no `digital_twin.*`
 * entry (§8.3) -- a derived model that changes over weeks has nothing worth
 * pushing, and inventing a subject to subscribe to is how three dead topics
 * reached the browser before 4A caught them.
 */

/** Part 16's domain names, rendered as Part 16 writes them. */
const DOMAIN_LABELS: Record<TwinDomainName, string> = {
  personal_workflow: "Personal Workflow",
  projects: "Projects",
  software_environment: "Software Environment",
  hardware_environment: "Hardware Environment",
  knowledge_profile: "Knowledge Profile",
  skill_profile: "Skill Profile",
  communication_style: "Communication Style",
  productivity_patterns: "Productivity Patterns",
  goals: "Goals",
  preferences: "Preferences",
  learning_progress: "Learning Progress",
};

const STATE_LABELS: Record<string, string> = {
  populated: "derived",
  partially_populated: "partly derived",
  empty: "nothing yet",
  unavailable: "source unreachable",
};

/**
 * `null` is "no dated activity". **Never render it as a number.**
 *
 * A `0` here would read as *active today*, which is the exact inverse of what a
 * missing timestamp means -- the same discipline 2D-D applied to a `null` trust
 * score, where `0` would have read as perfect trust.
 */
function renderGap(project: ProjectView): string {
  if (project.gap_days === null) return "no dated activity";
  const days = Math.floor(project.gap_days);
  if (days === 0) return "active today";
  if (days === 1) return "1 day since last activity";
  return `${days} days since last activity`;
}

function DomainReasonLine({ domain }: { domain: TwinDomainView }) {
  if (domain.reason === null) return null;
  return (
    <p className="m-0 pt-1 text-sm opacity-80" data-testid="domain-reason">
      <span data-testid="domain-reason-code">{domain.reason.code}</span> — {domain.reason.detail}
    </p>
  );
}

function DomainCard({ domain }: { domain: TwinDomainView }) {
  const refresh = useRefreshDomain();
  return (
    <li
      className="list-none border-b border-[var(--nova-border)] py-2 last:border-b-0"
      data-testid="twin-domain"
      data-domain={domain.domain}
      data-state={domain.state}
    >
      <div className="flex items-baseline justify-between gap-2">
        <strong data-testid="domain-name">{DOMAIN_LABELS[domain.domain]}</strong>
        <span className="text-sm opacity-70" data-testid="domain-state">
          {STATE_LABELS[domain.state] ?? domain.state}
          {domain.shipped_before_4e ? " · shipped in 2D-D" : null}
        </span>
      </div>

      <DomainReasonLine domain={domain} />

      {domain.evidence_count > 0 ? (
        <p className="m-0 pt-1 text-sm opacity-70" data-testid="domain-evidence-count">
          derived from {domain.evidence_count} evidence record
          {domain.evidence_count === 1 ? "" : "s"}
        </p>
      ) : null}

      {/* Named rather than summarised: "partly derived" is not something an
          operator can act on unless it says which part is missing. */}
      {domain.unavailable_fields.length > 0 ? (
        <p className="m-0 pt-1 text-sm opacity-60" data-testid="domain-unavailable-fields">
          no source yet for: {domain.unavailable_fields.join(", ")}
        </p>
      ) : null}

      <div className="pt-1">
        <Button
          type="button"
          onClick={() => refresh.mutate(domain.domain)}
          disabled={refresh.isPending}
          data-testid="refresh-domain"
        >
          {refresh.isPending ? "Re-deriving…" : "Re-derive"}
        </Button>
      </div>
    </li>
  );
}

function DomainOverview() {
  const { data, isPending, error } = useTwinDomains();
  const domains = data?.data.domains ?? [];

  return (
    <Panel title="Domains">
      <AsyncPanelBody
        isPending={isPending}
        error={error}
        isEmpty={domains.length === 0}
        emptyLabel="The Digital Twin reported no domains at all, which should not happen."
      >
        <ul className="m-0 p-0" data-testid="twin-domains">
          {domains.map((domain) => (
            <DomainCard key={domain.domain} domain={domain} />
          ))}
        </ul>
      </AsyncPanelBody>
    </Panel>
  );
}

/** **The AC-6 surface** -- the reconstruction for one project. */
function ProjectReconstruction({ projectId }: { projectId: string }) {
  const { data, isPending, error } = useTwinProject(projectId);
  const project = data?.data.project;

  return (
    <AsyncPanelBody
      isPending={isPending}
      error={error}
      isEmpty={project === undefined}
      emptyLabel="No reconstruction for this project."
    >
      {project ? (
        <div data-testid="project-reconstruction" data-project-id={project.project_id}>
          <p className="m-0" data-testid="project-gap">
            {renderGap(project)}
          </p>
          <p className="m-0 pt-1 text-sm opacity-80" data-testid="project-activity-window">
            {project.first_activity_at === null || project.last_activity_at === null
              ? "no dated activity recorded"
              : `activity from ${project.first_activity_at} to ${project.last_activity_at}`}
          </p>
          <p className="m-0 pt-1 text-sm opacity-70" data-testid="project-memory-count">
            {project.memory_count} memory record
            {project.memory_count === 1 ? "" : "s"} reference this project
          </p>
          <ul className="m-0 list-none p-0 pt-1" data-testid="project-memory-types">
            {Object.entries(project.memory_type_counts).map(([type, count]) => (
              <li key={type} className="text-sm opacity-70" data-testid="project-memory-type">
                {type}: {count}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </AsyncPanelBody>
  );
}

function Projects() {
  const { data, isPending, error } = useTwinProjects();
  const [selected, setSelected] = useState<string | null>(null);
  const projects = data?.data.projects ?? [];
  const domain = data?.data.domain;

  return (
    <Panel title="Projects">
      <AsyncPanelBody
        isPending={isPending}
        error={error}
        isEmpty={projects.length === 0}
        emptyLabel={
          // The domain's own machine-readable reason, not a generic blank
          // state: "nothing references a project yet" and "the source could
          // not be reached" are different things for an operator to do next.
          domain?.reason?.detail ??
          "No memory carrying a project has been observed for this user."
        }
      >
        <ul className="m-0 list-none p-0" data-testid="twin-projects">
          {projects.map((project) => (
            <li
              key={project.project_id}
              className="border-b border-[var(--nova-border)] py-2 last:border-b-0"
              data-testid="twin-project"
              data-project-id={project.project_id}
            >
              <div className="flex items-baseline justify-between gap-2">
                <code className="text-sm" data-testid="twin-project-id">
                  {project.project_id}
                </code>
                <span className="text-sm opacity-70" data-testid="twin-project-gap">
                  {renderGap(project)}
                </span>
              </div>
              <div className="pt-1">
                <Button
                  type="button"
                  onClick={() =>
                    setSelected((current) =>
                      current === project.project_id ? null : project.project_id,
                    )
                  }
                  data-testid="reconstruct-project"
                >
                  {selected === project.project_id ? "Hide reconstruction" : "Reconstruct"}
                </Button>
              </div>
              {selected === project.project_id ? (
                <ProjectReconstruction projectId={project.project_id} />
              ) : null}
            </li>
          ))}
        </ul>
      </AsyncPanelBody>
    </Panel>
  );
}

export function DigitalTwinPanel() {
  return (
    <div className="grid h-full grid-cols-1 gap-3 overflow-auto p-3 lg:grid-cols-2">
      <DomainOverview />
      <Projects />
    </div>
  );
}
