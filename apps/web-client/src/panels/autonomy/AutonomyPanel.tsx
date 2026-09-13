import { Button, DegradationNotice, Panel, TextField } from "@nova/ui";
import { useState } from "react";

import type {
  GateReport,
  PermissionGrant,
  Policy,
  PolicyEffect,
  Suggestion,
  TrustScore,
} from "../../entities/autonomy";
import {
  POLICY_EFFECTS,
  isAutonomyUnavailable,
  useAutonomyOverview,
  useAutonomyPolicies,
  useCreatePolicy,
  useDecideSuggestion,
  useDeletePolicy,
  useSetAutonomyLevel,
  useSetPolicyEnabled,
  useSuggestions,
} from "../../entities/autonomy";
import { AsyncPanelBody } from "../shared/AsyncPanelBody";

/**
 * How much NOVA may do on its own -- Bible Part 14's four dashboard widgets
 * that 4D can honestly provide: the level selector, per-category trust, the
 * policy editor, and the AC-5 suggestion inbox.
 *
 * **This panel mutates, and that is not a violation of the
 * no-optimistic-mutation rule -- it is the distinction the rule turns on.**
 * Setting a level, editing a policy and deciding a suggestion are explicit
 * user actions with a server round trip. What the rule forbids is patching
 * shared cognitive state into the cache *before* the server agrees. Every
 * mutation here POSTs, then invalidates; nothing is drawn as decided until
 * the server says it is. A later reader tempted to "fix" the perceived
 * latency by adding an optimistic update would be removing the one guarantee
 * AC-5 measures -- that an approval which the server refuses is not shown as
 * an approval.
 *
 * **No polling.** No `refetchInterval`, no `setInterval`. There is also no
 * realtime subscription, and that is structural rather than missing:
 * `autonomy-engine` claims no Event Bus subject (decision D-4D-1), so there
 * is nothing to subscribe to -- and at Levels 0-1 the user is the only actor
 * that changes suggestion state, through this panel.
 *
 * **Nothing is fabricated.** An empty inbox renders as a healthy empty state
 * that says *why* it is empty; a trust score of `null` renders as
 * "insufficient evidence", never as `0`.
 */

/** `null` is insufficient evidence. **Never render it as a number.** */
function renderTrust(score: TrustScore): string {
  if (score.score !== null) return score.score.toFixed(2);
  return score.status === "unavailable"
    ? "unavailable"
    : "insufficient evidence";
}

function GateSummary({ gates }: { gates: GateReport }) {
  return (
    <div className="pt-1 text-sm opacity-80" data-testid="suggestion-gates">
      {gates.denied ? (
        <span data-testid="gate-denied">
          Denied by the {gates.gate} gate — {gates.reason}
        </span>
      ) : (
        <span data-testid="gate-passed">
          Policy and permission gates passed; approval is required.
        </span>
      )}
      {gates.policy_checks.length > 0 ? (
        <ul className="m-0 list-none p-0 pt-1" data-testid="policy-checks">
          {gates.policy_checks.map((check) => (
            <li key={check.policy_id} data-testid="policy-check">
              {check.name} — {check.matched ? "matched" : "consulted, did not match"}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function LevelSelector() {
  const { data } = useAutonomyOverview();
  const setLevel = useSetAutonomyLevel();
  const level = data?.data.level;

  return (
    <section data-testid="autonomy-level">
      <h3 className="m-0 pb-2 text-sm font-medium opacity-80">Autonomy level</h3>
      <p className="m-0 pb-2 text-sm opacity-70" data-testid="current-level">
        {level === undefined
          ? "Reading…"
          : level.configured
            ? `Level ${level.level} — ${level.name}`
            : `Level ${level.level} — ${level.name} (never configured; this is the default)`}
      </p>
      <ul className="m-0 flex list-none flex-col gap-2 p-0">
        {(level?.options ?? []).map((option) => (
          <li key={option.level} className="nova-card" data-testid="level-option">
            <div className="flex items-center justify-between gap-3">
              <span className="font-medium" data-testid="level-name">
                {option.level} — {option.name}
              </span>
              <Button
                variant="ghost"
                // Level 2 is rendered and **disabled**: decision D-1 assigns
                // enabling it to milestone 4F. Hiding it would leave the user
                // unable to see that it exists; enabling it would be a lie.
                disabled={!option.selectable || setLevel.isPending}
                data-testid={option.selectable ? "level-select" : "level-disabled"}
                onClick={() => setLevel.mutate(option.level)}
              >
                {option.selectable ? "Select" : "Not available"}
              </Button>
            </div>
            {option.note !== null ? (
              <p className="m-0 pt-1 text-sm opacity-60" data-testid="level-note">
                {option.note}
              </p>
            ) : null}
          </li>
        ))}
      </ul>
      {setLevel.error ? (
        // A refused level (422) is shown with the server's reason rather than
        // silently clamped to the nearest allowed one.
        <div className="pt-2" data-testid="level-error">
          <DegradationNotice
            title="That autonomy level was refused"
            detail={setLevel.error instanceof Error ? setLevel.error.message : "Refused."}
            code={null}
            correlationId={null}
          />
        </div>
      ) : null}
    </section>
  );
}

function TrustScores({ scores }: { scores: TrustScore[] }) {
  return (
    <section data-testid="autonomy-trust">
      <h3 className="m-0 pb-2 text-sm font-medium opacity-80">
        Trust by category ({scores.length})
      </h3>
      <ul className="m-0 flex list-none flex-col gap-1 p-0">
        {scores.map((score) => (
          <li
            key={score.category}
            className="flex items-baseline justify-between gap-3 text-sm"
            data-testid="trust-score"
          >
            <span data-testid="trust-category">{score.category}</span>
            <span className="nova-status" data-testid="trust-value">
              {renderTrust(score)}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function PermissionMatrixView({ grants }: { grants: PermissionGrant[] }) {
  return (
    <section data-testid="autonomy-permissions">
      <h3 className="m-0 pb-2 text-sm font-medium opacity-80">
        Permission matrix ({grants.length})
      </h3>
      <ul className="m-0 flex list-none flex-col gap-1 p-0">
        {grants.map((grant) => (
          <li
            key={grant.category}
            className="flex items-baseline justify-between gap-3 text-sm"
            data-testid="permission-grant"
          >
            <span data-testid="permission-category">{grant.category}</span>
            <span className="nova-status" data-testid="permission-ceiling">
              {/* An ungranted category is shown as ungranted, not omitted:
                  no row means no autonomous authority, the fail-closed
                  default, and the user has to be able to see that. */}
              {grant.max_risk ?? "no autonomous authority"}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function PolicyEditor({ policies }: { policies: Policy[] }) {
  const create = useCreatePolicy();
  const setEnabled = useSetPolicyEnabled();
  const remove = useDeletePolicy();
  const [name, setName] = useState("");
  const [effect, setEffect] = useState<PolicyEffect>("deny");

  return (
    <section data-testid="autonomy-policies">
      <h3 className="m-0 pb-2 text-sm font-medium opacity-80">
        Policies ({policies.length})
      </h3>
      <div className="flex items-end gap-2 pb-2">
        <TextField
          label="Policy name"
          value={name}
          data-testid="policy-name"
          onChange={(event) => setName(event.target.value)}
        />
        <select
          className="nova-status"
          value={effect}
          data-testid="policy-effect"
          aria-label="Policy effect"
          onChange={(event) => setEffect(event.target.value as PolicyEffect)}
        >
          {/* `deny` and `require_approval` only. There is no `allow` effect
              in this release, so none is offered. */}
          {POLICY_EFFECTS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
        <Button
          data-testid="policy-create"
          disabled={name.trim().length === 0 || create.isPending}
          onClick={() => {
            create.mutate({
              name: name.trim(),
              effect,
              match_category: null,
              match_min_risk: null,
              match_capability_class: null,
              enabled: true,
            });
            setName("");
          }}
        >
          Add policy
        </Button>
      </div>
      {policies.length === 0 ? (
        <p className="m-0 text-sm opacity-60" data-testid="policies-empty">
          No policies are configured. An empty policy set is not permissive — it
          means no policy overrides the level&apos;s own behaviour, and at
          Levels 0–1 that behaviour is never execution.
        </p>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-2 p-0">
          {policies.map((policy) => (
            <li key={policy.id} className="nova-card" data-testid="policy">
              <div className="flex items-baseline justify-between gap-3">
                <span className="font-medium" data-testid="policy-label">
                  {policy.name}
                </span>
                <span className="nova-status" data-testid="policy-effect-value">
                  {policy.effect}
                </span>
              </div>
              <div className="flex items-center gap-3 pt-2">
                <Button
                  variant="ghost"
                  data-testid="policy-toggle"
                  onClick={() =>
                    setEnabled.mutate({ id: policy.id, enabled: !policy.enabled })
                  }
                >
                  {policy.enabled ? "Disable" : "Enable"}
                </Button>
                <Button
                  variant="ghost"
                  data-testid="policy-delete"
                  onClick={() => remove.mutate(policy.id)}
                >
                  Delete
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function SuggestionInbox({ suggestions }: { suggestions: Suggestion[] }) {
  const decide = useDecideSuggestion();

  return (
    <section data-testid="autonomy-suggestions">
      <h3 className="m-0 pb-2 text-sm font-medium opacity-80">
        Suggestions ({suggestions.length})
      </h3>
      {suggestions.length === 0 ? (
        // A healthy empty state that names why it is empty -- never seeded
        // with example suggestions.
        <p className="m-0 text-sm opacity-60" data-testid="suggestions-empty">
          Nothing is awaiting your decision. NOVA proposes at Autonomy Level 1
          and above; no suggestion source is enabled in this release, so the
          inbox stays empty until one is.
        </p>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-2 p-0">
          {suggestions.map((suggestion) => (
            <li key={suggestion.id} className="nova-card" data-testid="suggestion">
              <div className="flex items-baseline justify-between gap-3">
                <span className="font-medium" data-testid="suggestion-title">
                  {suggestion.title}
                </span>
                <span className="nova-status" data-testid="suggestion-risk">
                  {suggestion.risk}
                </span>
              </div>
              <p className="m-0 pt-1 text-sm opacity-70" data-testid="suggestion-status">
                {suggestion.status} · {suggestion.category}
              </p>
              <GateSummary gates={suggestion.gates} />
              <div className="flex items-center gap-3 pt-2">
                {/* The only transition out of `proposed`. Nothing executes on
                    render, and nothing executes on approval either --
                    approving records the user's decision. */}
                <Button
                  data-testid="suggestion-approve"
                  disabled={decide.isPending || suggestion.gates.denied}
                  onClick={() => decide.mutate({ id: suggestion.id, decision: "approve" })}
                >
                  Approve
                </Button>
                <Button
                  variant="ghost"
                  data-testid="suggestion-reject"
                  disabled={decide.isPending}
                  onClick={() => decide.mutate({ id: suggestion.id, decision: "reject" })}
                >
                  Reject
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {decide.error ? (
        <div className="pt-2" data-testid="decision-error">
          <DegradationNotice
            title="That decision was not applied"
            detail={decide.error instanceof Error ? decide.error.message : "Refused."}
            code={null}
            correlationId={null}
          />
        </div>
      ) : null}
    </section>
  );
}

export function AutonomyPanel() {
  const overview = useAutonomyOverview();
  const policies = useAutonomyPolicies();
  const suggestions = useSuggestions();

  // An unreachable engine is a different fact from an unconfigured one, and
  // only the first is a fault. Handled before `AsyncPanelBody` so the notice
  // can name the actual upstream; no level, policy or score is invented.
  if (isAutonomyUnavailable(overview.error)) {
    return (
      <Panel title="Autonomy">
        <DegradationNotice
          title="The Autonomy Engine could not be reached"
          detail={
            "The current autonomy level, policies and permissions are unknown " +
            "while the engine is unavailable. This is not the same as autonomy " +
            "being switched off, so nothing is shown."
          }
          code={overview.error instanceof Error ? overview.error.name : null}
          correlationId={null}
        />
      </Panel>
    );
  }

  const data = overview.data?.data;
  const degraded = data?.degraded ?? [];

  return (
    <Panel title="Autonomy">
      <AsyncPanelBody
        isPending={overview.isPending}
        error={overview.error}
        isEmpty={false}
        emptyLabel="The Autonomy Engine reported nothing."
      >
        <div className="flex flex-col gap-4 overflow-y-auto">
          {degraded.includes("conversational_trust") ? (
            // A named degradation, surfaced rather than shown as an ordinary
            // empty result. Every trust score below reads "unavailable"
            // because of this, and the operator should know which it is.
            <p className="m-0 text-sm opacity-60" data-testid="trust-degraded">
              The conversational trust signal could not be read, so every trust
              score below is reported as unavailable rather than as a number.
            </p>
          ) : null}

          <LevelSelector />
          <TrustScores scores={data?.trust ?? []} />
          <PermissionMatrixView grants={data?.permissions.categories ?? []} />
          <PolicyEditor policies={policies.data?.data ?? []} />
          <SuggestionInbox suggestions={suggestions.data?.data.items ?? []} />
        </div>
      </AsyncPanelBody>
    </Panel>
  );
}
