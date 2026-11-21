import { cn } from "../cn";

/**
 * How a failure is shown to the user.
 *
 * The project's standing rule is *never silence, always disclose
 * degradation* -- and TDD 4A §7 applies it to every frontend failure mode:
 * an unreachable engine, an expired session, a rate limit, a contract
 * mismatch. Each of those surfaces here rather than as an empty panel.
 *
 * `correlationId` is rendered, not hidden. Doc 11 §4 puts it in the envelope
 * so a user looking at a wrong answer can hand one string to a log search;
 * a UI that drops it throws that away.
 */

export type DegradationNoticeProps = {
  title: string;
  detail: string;
  code?: string | null;
  correlationId?: string | null;
  onRetry?: () => void;
  className?: string;
};

export function DegradationNotice({
  title,
  detail,
  code,
  correlationId,
  onRetry,
  className,
}: DegradationNoticeProps) {
  return (
    <div
      className={cn("nova-degradation", className)}
      role="alert"
      data-testid="degradation-notice"
    >
      <p className="nova-degradation-title">{title}</p>
      <p className="nova-degradation-detail">{detail}</p>
      <dl className="nova-degradation-meta">
        {code ? (
          <>
            <dt>code</dt>
            <dd data-testid="degradation-code">{code}</dd>
          </>
        ) : null}
        {correlationId ? (
          <>
            <dt>correlation</dt>
            <dd data-testid="degradation-correlation">{correlationId}</dd>
          </>
        ) : null}
      </dl>
      {onRetry ? (
        <button type="button" className="nova-button nova-button-ghost" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}
