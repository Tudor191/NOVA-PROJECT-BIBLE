import { DegradationNotice } from "@nova/ui";
import type { ReactNode } from "react";

import { GatewayError } from "../../entities/envelope";

/**
 * The three states every REST-backed panel has, in one place.
 *
 * Six panels repeating this would be six chances to disagree about what an
 * upstream failure looks like -- and the failure rendering is the part that
 * matters most, because it is what the operator sees when an engine is
 * down. It stays one component for that reason, not to save lines.
 *
 * **"Loading" and "empty" are different, and neither is an error.** An
 * engine with nothing to report renders `emptyLabel`; a panel that has not
 * finished asking renders nothing yet. Collapsing them would let a slow
 * gateway look like an idle system.
 */

export type AsyncPanelBodyProps = {
  isPending: boolean;
  error: unknown;
  isEmpty: boolean;
  emptyLabel: string;
  children: ReactNode;
};

export function AsyncPanelBody({
  isPending,
  error,
  isEmpty,
  emptyLabel,
  children,
}: AsyncPanelBodyProps) {
  if (error) {
    const gatewayError = error instanceof GatewayError ? error : null;
    return (
      <DegradationNotice
        title={
          gatewayError?.isUnauthenticated
            ? "This session is no longer valid"
            : "This panel could not read its data"
        }
        detail={error instanceof Error ? error.message : String(error)}
        code={gatewayError?.code ?? null}
        correlationId={gatewayError?.correlationId ?? null}
      />
    );
  }

  if (isPending) {
    return (
      <p className="m-auto text-sm opacity-60" data-testid="panel-loading">
        Reading…
      </p>
    );
  }

  if (isEmpty) {
    return (
      <p className="m-auto text-sm opacity-60" data-testid="panel-empty">
        {emptyLabel}
      </p>
    );
  }

  return <>{children}</>;
}
