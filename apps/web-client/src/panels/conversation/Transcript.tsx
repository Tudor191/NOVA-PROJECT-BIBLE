import { ConfidenceTierBadge, CorrelationTag } from "@nova/ui";

import type { TranscriptEntry } from "../../entities/conversation";

/**
 * The conversation itself.
 *
 * Every NOVA turn carries its confidence tier and its correlation id, per
 * TDD 4A §5.2 property 4 -- the envelope is rendered, not hidden. That is
 * what makes this a debugging instrument rather than a chat window: a user
 * looking at a wrong answer can read the tier NOVA had and hand one id to a
 * log search.
 *
 * `degraded` is disclosed in place. It means personality validation was
 * skipped because the RPC failed and the content was delivered anyway
 * (design doc Sec9's fallback) -- the user is entitled to know which of
 * these answers went out unchecked.
 */
export function Transcript({ entries }: { entries: TranscriptEntry[] }) {
  if (entries.length === 0) {
    return (
      <p className="m-auto text-sm opacity-60" data-testid="transcript-empty">
        Nothing said yet. Messages appear here when the system confirms them, not when
        they are typed.
      </p>
    );
  }

  return (
    <ol className="flex flex-1 list-none flex-col gap-3 overflow-y-auto p-0" data-testid="transcript">
      {entries.map((entry) => (
        <li
          key={entry.id}
          data-testid="transcript-entry"
          data-author={entry.author}
          className={entry.author === "user" ? "self-end text-right" : "self-start"}
        >
          <p className="m-0 whitespace-pre-wrap text-sm">{entry.content}</p>
          <div className="mt-1 flex items-center gap-2 text-xs opacity-70">
            <span>{entry.author === "user" ? "You" : "NOVA"}</span>
            {entry.author === "nova" ? (
              <ConfidenceTierBadge tier={entry.confidenceTier} />
            ) : null}
            {entry.degraded ? (
              <span className="nova-badge nova-confidence-low" data-testid="degraded-turn">
                unvalidated
              </span>
            ) : null}
            <CorrelationTag correlationId={entry.correlationId} />
          </div>
        </li>
      ))}
    </ol>
  );
}
