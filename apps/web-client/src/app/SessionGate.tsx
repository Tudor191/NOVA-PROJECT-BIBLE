import { zodResolver } from "@hookform/resolvers/zod";
import { Button, DegradationNotice, TextField } from "@nova/ui";
import { useForm } from "react-hook-form";
import type { ReactNode } from "react";
import { z } from "zod";

import { GatewayError } from "../entities/envelope";
import { useIssueSession, useSession } from "../entities/session";

/**
 * The first-run session flow, and the gate in front of everything else.
 *
 * Decision **D-3**: the instance's single local token is presented once and
 * exchanged for an httpOnly cookie. Nothing here stores the token, and
 * nothing can read it back afterwards.
 *
 * Rendered as a gate rather than a route redirect on purpose: a redirect
 * would flash the shell before bouncing, and "are we authenticated" is
 * answered by a request that may still be in flight.
 */

const tokenFormSchema = z.object({
  token: z.string().min(1, "Enter the session token this instance was provisioned with."),
});

type TokenForm = z.infer<typeof tokenFormSchema>;

export function SessionGate({ children }: { children: ReactNode }) {
  const session = useSession();
  const issue = useIssueSession();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<TokenForm>({ resolver: zodResolver(tokenFormSchema) });

  if (session.isPending) {
    return (
      <p className="p-6 text-sm opacity-70" role="status">
        Checking session…
      </p>
    );
  }

  // A failure to *ask* is not the same as being unauthenticated, and must
  // not be presented as "please log in" -- that would send the user hunting
  // for a token when the gateway is simply unreachable.
  if (session.isError && !(session.error instanceof GatewayError && session.error.isUnauthenticated)) {
    return (
      <div className="p-6">
        <DegradationNotice
          title="Cannot reach the API gateway"
          detail={
            session.error instanceof Error
              ? session.error.message
              : "The session endpoint did not answer."
          }
          code={session.error instanceof GatewayError ? session.error.code : null}
          correlationId={
            session.error instanceof GatewayError ? session.error.correlationId : null
          }
          onRetry={() => void session.refetch()}
        />
      </div>
    );
  }

  if (session.data?.authenticated) {
    return <>{children}</>;
  }

  const issueError = issue.error;
  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-4 p-6">
      <div>
        <h1 className="text-lg font-semibold">NOVA</h1>
        <p className="mt-1 text-sm opacity-70">
          This instance is protected by a single local session token (decision D-3). Paste it
          once; it is exchanged for an httpOnly cookie and never stored in the browser.
        </p>
      </div>

      <form
        className="flex flex-col gap-3"
        onSubmit={handleSubmit((values) => issue.mutate(values.token))}
      >
        <TextField
          label="Session token"
          type="password"
          autoComplete="off"
          autoFocus
          error={errors.token?.message ?? null}
          {...register("token")}
        />
        <Button type="submit" busy={issue.isPending}>
          {issue.isPending ? "Signing in…" : "Sign in"}
        </Button>
      </form>

      {issueError ? (
        <DegradationNotice
          title={
            issueError instanceof GatewayError && issueError.code === "session_not_configured"
              ? "This instance has no session token provisioned"
              : "That token was not accepted"
          }
          detail={issueError instanceof Error ? issueError.message : String(issueError)}
          code={issueError instanceof GatewayError ? issueError.code : null}
          correlationId={issueError instanceof GatewayError ? issueError.correlationId : null}
        />
      ) : null}
    </div>
  );
}
