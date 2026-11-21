import { Button, CorrelationTag, Panel } from "@nova/ui";

import { useApprovePlan, usePlans } from "../../entities/planning";
import { AsyncPanelBody } from "../shared/AsyncPanelBody";

/**
 * What NOVA has planned, and what it is waiting to be told it may do.
 *
 * Approving records `approved_at` and nothing else. `planning-engine`'s own
 * endpoint is scoped that way (TDD 3B §5) because no dispatcher exists to
 * honour it yet, so the button says "Record approval" rather than "Run" --
 * a label promising execution would be the UI claiming a capability the
 * system does not have.
 */
export function PlanningPanel() {
  const { data, isPending, error } = usePlans();
  const approve = useApprovePlan();
  const plans = data?.data ?? [];

  return (
    <Panel title="Planning">
      <AsyncPanelBody
        isPending={isPending}
        error={error ?? approve.error}
        isEmpty={plans.length === 0}
        emptyLabel="No plans yet. NOVA has not decomposed an objective."
      >
        <ol className="flex list-none flex-col gap-3 overflow-y-auto p-0" data-testid="plan-list">
          {plans.map((plan) => (
            <li key={plan.id} className="nova-card" data-testid="plan">
              <div className="flex items-baseline justify-between gap-3">
                <span className="font-medium">{plan.root_objective}</span>
                <span className="nova-status" data-testid="plan-node-count">
                  {plan.nodes.length} task{plan.nodes.length === 1 ? "" : "s"}
                </span>
              </div>
              <ol className="m-0 flex list-none flex-col gap-1 p-0 pt-2 text-sm opacity-80">
                {plan.nodes.map((node) => (
                  <li key={node.id} data-testid="plan-node">
                    <span data-testid="plan-node-status">{node.status}</span>
                    {" · "}
                    {node.objective}
                    {plan.critical_path.includes(node.id) ? (
                      <span className="nova-badge" data-testid="critical-path">
                        critical path
                      </span>
                    ) : null}
                  </li>
                ))}
              </ol>
              <div className="flex items-center gap-3 pt-2">
                {plan.approved_at ? (
                  <span className="nova-status" data-testid="plan-approved">
                    Approval recorded
                  </span>
                ) : (
                  <Button
                    busy={approve.isPending}
                    onClick={() => approve.mutate(plan.id)}
                  >
                    Record approval
                  </Button>
                )}
                <CorrelationTag correlationId={plan.id} />
              </div>
            </li>
          ))}
        </ol>
      </AsyncPanelBody>
    </Panel>
  );
}
