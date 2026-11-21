import { Button, Panel } from "@nova/ui";
import { useState } from "react";

import type {
  AttentionLayer,
  FocusEntryView,
  ProposedActionView,
  SensorView,
  ThoughtView,
} from "../../entities/cognitiveState";
import {
  ATTENTION_LAYERS,
  useFocus,
  useRefreshCognitiveState,
  useSensors,
  useThoughts,
} from "../../entities/cognitiveState";
import { AsyncPanelBody } from "../shared/AsyncPanelBody";

/**
 * NOVA's cognitive state, as `cognitive-state-engine` holds it -- Bible Part 6's
 * Active Thoughts, Focus and Attention Layers, and the last lifecycle state each
 * sensor reported (TDD 4F.7 §12).
 *
 * **A window, not a control.** Nothing here creates, promotes or moves a
 * thought, authors or approves a proposal, asks for a decision, executes
 * anything, changes an autonomy level or touches a sensor. The only button
 * re-reads.
 *
 * **Every value is the engine's.** Nothing is defaulted, averaged, inferred or
 * invented: an empty list renders as the statement it is, `null` renders as
 * "not estimated", an empty `signals_used` says that focus was ranked by
 * priority alone, and a sensor's state is exactly what `perception-engine`
 * last reported, shown with when -- never inferred from silence or from age.
 * An error renders the degradation notice; it is never an empty panel.
 *
 * **In production the thought sections are empty** until the promotion slice
 * (4F.P) exists -- nothing in NOVA creates an Active Thought yet (K-4). The
 * empty states say so plainly rather than looking broken.
 *
 * **Nothing moves by itself.** No polling, no realtime, no animation: loading is
 * static text, and freshness is the Refresh button (A-4F7-3 (a)).
 */

/** Part 6's layer names, in Part 6's order. */
const LAYER_LABELS: Record<AttentionLayer, string> = {
  immediate: "Immediate",
  active: "Active",
  passive: "Passive",
  dormant: "Dormant",
  archived: "Archived",
};

function list(values: string[]): string {
  return values.length === 0 ? "none" : values.join(", ");
}

/**
 * A proposal NOVA holds about itself (RS-4c) -- rendered as exactly that. The
 * persisted value carries nothing about what happened to it, so nothing here
 * says it was acted on.
 */
function ProposalBlock({ proposal }: { proposal: ProposedActionView }) {
  return (
    <section
      className="mt-2 border-l-2 border-[var(--nova-border)] pl-2"
      data-testid="thought-proposal"
    >
      <h4 className="m-0 text-sm font-semibold">Proposal</h4>
      <p className="m-0 text-sm" data-testid="proposal-title">
        {proposal.title}
      </p>
      <p className="m-0 text-sm opacity-80" data-testid="proposal-detail">
        {proposal.detail}
      </p>
      <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-2 text-sm opacity-80">
        <dt>category</dt>
        <dd className="m-0" data-testid="proposal-category">
          {proposal.category}
        </dd>
        <dt>risk</dt>
        <dd className="m-0" data-testid="proposal-risk">
          {proposal.risk}
        </dd>
        <dt>action type</dt>
        <dd className="m-0" data-testid="proposal-action-type">
          {proposal.action_type}
        </dd>
        <dt>execution target</dt>
        <dd className="m-0" data-testid="proposal-execution-target">
          {proposal.execution_target}
        </dd>
        <dt>verification</dt>
        <dd className="m-0" data-testid="proposal-verification-method">
          {proposal.verification_method}
        </dd>
      </dl>
    </section>
  );
}

function ThoughtCard({ thought }: { thought: ThoughtView }) {
  return (
    <li
      className="list-none border-b border-[var(--nova-border)] py-2 last:border-b-0"
      data-testid="thought"
      data-thought-id={thought.thought_id}
      data-layer={thought.attention_layer}
    >
      <p className="m-0" data-testid="thought-description">
        {thought.description}
      </p>
      <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-2 pt-1 text-sm opacity-80">
        <dt>priority</dt>
        <dd className="m-0" data-testid="thought-priority">
          {thought.priority}
        </dd>
        <dt>confidence</dt>
        <dd className="m-0" data-testid="thought-confidence">
          {thought.confidence}
        </dd>
        <dt>progress</dt>
        <dd className="m-0" data-testid="thought-progress">
          {thought.current_progress}
        </dd>
        <dt>estimated completion</dt>
        <dd className="m-0" data-testid="thought-estimated-completion">
          {thought.estimated_completion ?? "not estimated"}
        </dd>
        <dt>dependencies</dt>
        <dd className="m-0" data-testid="thought-dependencies">
          {list(thought.dependencies)}
        </dd>
        <dt>related memories</dt>
        <dd className="m-0" data-testid="thought-related-memories">
          {list(thought.related_memories)}
        </dd>
        <dt>related projects</dt>
        <dd className="m-0" data-testid="thought-related-projects">
          {list(thought.related_projects)}
        </dd>
        <dt>created</dt>
        <dd className="m-0" data-testid="thought-created-at">
          {thought.created_at}
        </dd>
        <dt>updated</dt>
        <dd className="m-0" data-testid="thought-updated-at">
          {thought.updated_at}
        </dd>
        <dt>id</dt>
        <dd className="m-0" data-testid="thought-id">
          <code>{thought.thought_id}</code>
        </dd>
      </dl>
      {thought.proposed_action !== null ? (
        <ProposalBlock proposal={thought.proposed_action} />
      ) : null}
    </li>
  );
}

function ActiveThoughts() {
  const { data, isPending, error } = useThoughts();
  const thoughts = data?.data.thoughts ?? [];

  return (
    <Panel title="Active Thoughts">
      <AsyncPanelBody
        isPending={isPending}
        error={error}
        isEmpty={thoughts.length === 0}
        emptyLabel="No Active Thoughts."
      >
        <div data-testid="cognitive-thoughts">
          {ATTENTION_LAYERS.map((layer) => {
            const inLayer = thoughts.filter((thought) => thought.attention_layer === layer);
            return (
              <section key={layer} data-testid="thought-layer" data-layer={layer}>
                <h3 className="m-0 pt-2 text-sm font-semibold">{LAYER_LABELS[layer]}</h3>
                {inLayer.length === 0 ? (
                  <p className="m-0 text-sm opacity-60" data-testid="thought-layer-empty">
                    No thoughts in this layer.
                  </p>
                ) : (
                  <ul className="m-0 p-0">
                    {inLayer.map((thought) => (
                      <ThoughtCard key={thought.thought_id} thought={thought} />
                    ))}
                  </ul>
                )}
              </section>
            );
          })}
        </div>
      </AsyncPanelBody>
    </Panel>
  );
}

function FocusRow({ entry }: { entry: FocusEntryView }) {
  return (
    <li
      className="list-none border-b border-[var(--nova-border)] py-2 last:border-b-0"
      data-testid="focus-entry"
      data-thought-id={entry.thought.thought_id}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span data-testid="focus-description">{entry.thought.description}</span>
        <span className="text-sm opacity-70" data-testid="focus-score">
          score {entry.score}
        </span>
      </div>
      <p className="m-0 text-sm opacity-70" data-testid="focus-layer">
        {LAYER_LABELS[entry.thought.attention_layer]} · priority {entry.thought.priority}
      </p>
      <p className="m-0 text-sm opacity-60" data-testid="focus-signals">
        {entry.signals_used.length === 0
          ? "ranked by priority alone — no focus signals were supplied"
          : `signals: ${entry.signals_used.join(", ")}`}
      </p>
    </li>
  );
}

function Focus() {
  const { data, isPending, error } = useFocus();
  const focus = data?.data;
  const entries = focus?.entries ?? [];

  return (
    <Panel title="Focus">
      <AsyncPanelBody
        isPending={isPending}
        error={error}
        isEmpty={entries.length === 0}
        emptyLabel="Nothing is in focus."
      >
        <p className="m-0 text-sm opacity-70" data-testid="focus-capacity">
          {entries.length} of capacity {focus?.capacity}
        </p>
        <ol className="m-0 p-0" data-testid="cognitive-focus">
          {entries.map((entry) => (
            <FocusRow key={entry.thought.thought_id} entry={entry} />
          ))}
        </ol>
      </AsyncPanelBody>
    </Panel>
  );
}

function SensorRow({ sensor }: { sensor: SensorView }) {
  return (
    <li
      className="list-none border-b border-[var(--nova-border)] py-2 last:border-b-0"
      data-testid="sensor"
      data-sensor-id={sensor.sensor_id}
      data-state={sensor.state}
    >
      <div className="flex items-baseline justify-between gap-2">
        <code className="text-sm" data-testid="sensor-id">
          {sensor.sensor_id}
        </code>
        <span className="text-sm opacity-70" data-testid="sensor-type">
          {sensor.sensor_type}
        </span>
      </div>
      <p className="m-0 text-sm" data-testid="sensor-state">
        lifecycle state: {sensor.state}
      </p>
      <p className="m-0 text-sm opacity-70" data-testid="sensor-reported-at">
        last reported {sensor.reported_at}
      </p>
    </li>
  );
}

function Sensors() {
  const { data, isPending, error } = useSensors();
  const sensors = data?.data.sensors ?? [];

  return (
    <Panel title="Sensors">
      <AsyncPanelBody
        isPending={isPending}
        error={error}
        isEmpty={sensors.length === 0}
        emptyLabel="No sensor report has been received."
      >
        <p className="m-0 text-sm opacity-60" data-testid="sensors-note">
          The lifecycle state each sensor last reported, and when. Nothing is inferred from
          silence or from age.
        </p>
        <ul className="m-0 p-0" data-testid="cognitive-sensors">
          {sensors.map((sensor) => (
            <SensorRow key={sensor.sensor_id} sensor={sensor} />
          ))}
        </ul>
      </AsyncPanelBody>
    </Panel>
  );
}

export function CognitiveStatePanel() {
  const refresh = useRefreshCognitiveState();
  const [refreshing, setRefreshing] = useState(false);

  return (
    <div className="flex h-full flex-col gap-3 overflow-auto p-3">
      <div>
        <Button
          type="button"
          disabled={refreshing}
          onClick={() => {
            setRefreshing(true);
            void refresh().finally(() => setRefreshing(false));
          }}
          data-testid="cognitive-state-refresh"
        >
          {refreshing ? "Reading…" : "Refresh"}
        </Button>
      </div>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <Sensors />
        <Focus />
      </div>
      <ActiveThoughts />
    </div>
  );
}
