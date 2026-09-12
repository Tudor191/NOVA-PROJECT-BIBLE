import { Button, CorrelationTag, DegradationNotice, Panel, StatusDot } from "@nova/ui";
import type { StatusTone } from "@nova/ui";
import { useState } from "react";

import type { AgentInstance } from "../../entities/agents";
import {
  isRegistryUnavailable,
  isUnknownInstance,
  useAgentActivity,
  useAgents,
} from "../../entities/agents";
import { AsyncPanelBody } from "../shared/AsyncPanelBody";

/**
 * What NOVA can run, what it is running, and what those runs have done.
 *
 * Three sections, because `GET /v1/agents` returns three different things
 * owned by two different components: packages come from `agent-os/registry`
 * over the bus, instances are the Kernel's own table, and the supervisor
 * topology is a declared fact about the deployment rather than a query
 * result. Rendering them as one list would imply a relationship none of them
 * has.
 *
 * **An empty instance list is a healthy answer here, and the panel says so.**
 * An `agent_instance` row exists only after a Kernel dispatch, which is
 * reached only from `planning.task_graph.created`, which `planning-engine`
 * publishes only from an LLM-backed decomposition. With no model provider
 * configured the table is legitimately empty -- master scope §1.1 defers
 * AC-4's instance and peer-review clauses for exactly this reason. Rendering
 * that as an error, or filling it with placeholder agents, would both be
 * lying about the state of the system.
 *
 * **Read-only.** The Kernel exposes three `GET` routes and no mutation path;
 * there is no button here that changes anything, because there is nothing to
 * call.
 */

/** Health words the Kernel actually emits, mapped to the shared indicator. */
function toneFor(healthStatus: string): StatusTone {
  if (healthStatus === "healthy") return "healthy";
  if (healthStatus === "degraded") return "degraded";
  if (healthStatus === "unhealthy") return "down";
  // `"unknown"` is the Kernel's own default for an instance that has not
  // reported. Shown as unknown rather than promoted to healthy.
  return "unknown";
}

export function AgentsPanel() {
  const { data, isPending, error } = useAgents();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const overview = data?.data;
  const packages = overview?.packages ?? [];
  const instances = overview?.instances ?? [];
  const supervisors = overview?.supervisors ?? [];

  // Decision D-1, rendered. A 503 means the Agent Registry is unreachable --
  // a different fact from "nothing is installed", and the only one of the two
  // that is a fault. Handled before `AsyncPanelBody` so the notice can name
  // the actual upstream instead of saying "this panel could not read its
  // data"; no package list is invented to fill the gap.
  if (isRegistryUnavailable(error)) {
    return (
      <Panel title="Agents">
        <DegradationNotice
          title="The Agent Registry could not be reached"
          detail={
            "Installed packages are unknown while the Registry is unavailable. " +
            "This is not the same as no agents being installed, so none are shown."
          }
          code={error instanceof Error ? error.name : null}
          correlationId={null}
        />
      </Panel>
    );
  }

  return (
    <Panel title="Agents">
      <AsyncPanelBody
        isPending={isPending}
        error={error}
        isEmpty={packages.length === 0 && instances.length === 0 && supervisors.length === 0}
        emptyLabel="No agent packages are installed and nothing is running."
      >
        <div className="flex flex-col gap-4 overflow-y-auto">
          <section data-testid="agent-packages">
            <h3 className="m-0 pb-2 text-sm font-medium opacity-80">
              Installed packages ({packages.length})
            </h3>
            {packages.length === 0 ? (
              <p className="m-0 text-sm opacity-60" data-testid="packages-empty">
                The Registry is reachable and reports no installed packages.
              </p>
            ) : (
              <ul className="m-0 flex list-none flex-col gap-2 p-0">
                {packages.map((pkg) => (
                  <li key={pkg.id} className="nova-card" data-testid="agent-package">
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="font-medium" data-testid="package-name">
                        {pkg.manifest_id ?? pkg.id}
                      </span>
                      <span className="nova-status" data-testid="package-version">
                        v{pkg.version}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 pt-1 text-sm opacity-80">
                      {/* No `animate`: a package's health is a standing
                          reading, not an arrival. Doc 04 §4 forbids a pulse
                          that is not bound to a real signal. */}
                      <StatusDot
                        status={toneFor(pkg.health_status)}
                        label={pkg.health_status}
                        instrument="package-health"
                      />
                      <span data-testid="package-category">{pkg.category}</span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section data-testid="agent-instances">
            <h3 className="m-0 pb-2 text-sm font-medium opacity-80">
              Agent instances ({instances.length})
            </h3>
            {instances.length === 0 ? (
              // The provider-free steady state. Phrased as a fact about the
              // system rather than as a failure of this panel.
              <p className="m-0 text-sm opacity-60" data-testid="instances-empty">
                No agents have run yet. An instance is created when the Kernel
                dispatches a planned task, which needs a model provider to
                decompose an objective first.
              </p>
            ) : (
              <ul className="m-0 flex list-none flex-col gap-2 p-0">
                {instances.map((instance) => (
                  <li key={instance.id} className="nova-card" data-testid="agent-instance">
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="font-medium" data-testid="instance-category">
                        {instance.category}
                      </span>
                      <span className="nova-status" data-testid="instance-status">
                        {instance.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 pt-1 text-sm opacity-80">
                      <StatusDot
                        status={toneFor(instance.health_status)}
                        label={instance.health_status}
                        instrument="instance-health"
                      />
                      <span data-testid="instance-backend">{instance.execution_backend}</span>
                      {" · started "}
                      <span data-testid="instance-started">{instance.started_at}</span>
                    </div>
                    <div className="flex items-center gap-3 pt-2">
                      <Button
                        variant="ghost"
                        onClick={() =>
                          setSelectedId((current) =>
                            current === instance.id ? null : instance.id,
                          )
                        }
                      >
                        {selectedId === instance.id ? "Hide activity" : "Show activity"}
                      </Button>
                      <CorrelationTag correlationId={instance.id} />
                    </div>
                    {selectedId === instance.id ? <ActivityList instance={instance} /> : null}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section data-testid="agent-supervisors">
            <h3 className="m-0 pb-2 text-sm font-medium opacity-80">
              Supervisors ({supervisors.length})
            </h3>
            <ul className="m-0 flex list-none flex-col gap-2 p-0">
              {supervisors.map((supervisor) => (
                <li
                  key={supervisor.category}
                  className="nova-card"
                  data-testid="agent-supervisor"
                >
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="font-medium" data-testid="supervisor-category">
                      {supervisor.category}
                    </span>
                    <span className="nova-status" data-testid="supervisor-count">
                      {supervisor.instance_ids.length} instance
                      {supervisor.instance_ids.length === 1 ? "" : "s"}
                    </span>
                  </div>
                  {supervisor.membership_is_derived ? (
                    // The Kernel marks this answer as derived; repeating that
                    // to the operator is the difference between "these
                    // instances report to this supervisor" and "there is
                    // exactly one supervisor, so they all must".
                    <p className="m-0 pt-1 text-sm opacity-60" data-testid="supervisor-derived">
                      Membership is derived from the deployment topology, not
                      recorded per instance.
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          </section>
        </div>
      </AsyncPanelBody>
    </Panel>
  );
}

/**
 * One instance's activity history, a page at a time.
 *
 * **404 and an empty page are different answers and are rendered
 * differently.** The Kernel checks the instance exists before paging, so
 * "no such instance" is a `404` and "this instance has done nothing yet" is a
 * successful empty page. Collapsing them would make a stale id look like an
 * idle agent.
 */
function ActivityList({ instance }: { instance: AgentInstance }) {
  const { data, isPending, error, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useAgentActivity(instance.id);

  if (isUnknownInstance(error)) {
    return (
      <p className="m-0 pt-2 text-sm opacity-60" data-testid="activity-unknown-instance">
        This agent instance no longer exists.
      </p>
    );
  }

  const rows = data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <div className="pt-2" data-testid="activity">
      <AsyncPanelBody
        isPending={isPending}
        error={error}
        isEmpty={rows.length === 0}
        emptyLabel="This instance has no recorded activity yet."
      >
        <ol className="m-0 flex list-none flex-col gap-1 p-0 text-sm opacity-80">
          {rows.map((row) => (
            <li key={row.id} data-testid="activity-row">
              <span data-testid="activity-kind">{row.kind}</span>
              {" · "}
              <span data-testid="activity-at">{row.occurred_at}</span>
              {row.correlation_id ? <CorrelationTag correlationId={row.correlation_id} /> : null}
            </li>
          ))}
        </ol>
        {hasNextPage ? (
          <Button
            variant="ghost"
            busy={isFetchingNextPage}
            onClick={() => void fetchNextPage()}
          >
            Load older activity
          </Button>
        ) : null}
      </AsyncPanelBody>
    </div>
  );
}
