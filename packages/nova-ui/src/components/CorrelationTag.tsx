import { cn } from "../cn";

/**
 * The envelope's `correlation_id`, made visible.
 *
 * TDD 4A §5.2 property 4: "the envelope is rendered, not hidden". This is
 * the smallest piece of that -- the id that links what the user is looking
 * at to the event chain that produced it. Truncated for the chrome, full
 * value in `title` and in `data-correlation-id` so it stays copyable and
 * assertable from a test.
 */

export type CorrelationTagProps = {
  correlationId: string;
  className?: string;
};

export function CorrelationTag({ correlationId, className }: CorrelationTagProps) {
  return (
    <span
      className={cn("nova-correlation", className)}
      title={correlationId}
      data-testid="correlation-tag"
      data-correlation-id={correlationId}
    >
      {correlationId.slice(0, 8)}
    </span>
  );
}
