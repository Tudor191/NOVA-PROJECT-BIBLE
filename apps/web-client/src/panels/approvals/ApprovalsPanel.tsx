import { Button, CorrelationTag, Panel } from "@nova/ui";

import { useApprovals, useDecideApproval } from "../../entities/approvals";
import { AsyncPanelBody } from "../shared/AsyncPanelBody";

/**
 * What is blocked on a human.
 *
 * The row leaves this list when `action.approval.decided` arrives over the
 * bus, not when the button is clicked. That is deliberate and it is the
 * rule TDD 4A §5.2 set for shared cognitive state: an optimistic removal
 * would show a decision that a 409 -- someone else decided it first -- or a
 * dropped request never actually made, and an approval is the last thing
 * that should be reported as done before it is.
 *
 * So the button goes busy and stays busy until the event lands. The
 * connection indicator in the shell header is what tells the operator
 * whether that wait is meaningful or whether the socket is down.
 */
export function ApprovalsPanel() {
  const { data, isPending, error } = useApprovals();
  const decide = useDecideApproval();
  const approvals = data?.data ?? [];

  return (
    <Panel
      title="Approvals"
      accessory={
        <span className="nova-status" data-testid="approval-count">
          {approvals.length} waiting
        </span>
      }
    >
      <AsyncPanelBody
        isPending={isPending}
        error={error ?? decide.error}
        isEmpty={approvals.length === 0}
        emptyLabel="Nothing is waiting on you."
      >
        <ul
          className="flex list-none flex-col gap-3 overflow-y-auto p-0"
          data-testid="approval-list"
        >
          {approvals.map((approval) => (
            <li key={approval.action_id} className="nova-card" data-testid="approval">
              <div className="flex items-baseline justify-between gap-3">
                <span className="nova-badge" data-testid="approval-risk">
                  {approval.risk} risk
                </span>
                <span className="nova-status">
                  requested {new Date(approval.requested_at).toLocaleTimeString()}
                </span>
              </div>
              <div className="flex items-center gap-2 pt-2">
                <Button
                  busy={decide.isPending}
                  onClick={() =>
                    decide.mutate({ actionId: approval.action_id, approved: true })
                  }
                >
                  Approve
                </Button>
                <Button
                  variant="ghost"
                  busy={decide.isPending}
                  onClick={() =>
                    decide.mutate({ actionId: approval.action_id, approved: false })
                  }
                >
                  Deny
                </Button>
                <CorrelationTag correlationId={approval.action_id} />
              </div>
            </li>
          ))}
        </ul>
      </AsyncPanelBody>
    </Panel>
  );
}
