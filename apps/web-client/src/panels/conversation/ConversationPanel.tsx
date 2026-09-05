import { Button, DegradationNotice, Panel } from "@nova/ui";
import { skipToken, useQuery } from "@tanstack/react-query";

import type { ConversationSession } from "../../entities/conversation";
import {
  conversationKeys,
  useConversationState,
  useCreateConversationSession,
  useSendMessage,
  useTranscript,
} from "../../entities/conversation";
import { GatewayError } from "../../entities/envelope";
import { Composer } from "./Composer";
import { Transcript } from "./Transcript";

/**
 * The one panel Phase 4A builds (TDD 4A §6).
 *
 * It closes the loop the whole milestone exists for: a turn goes out over
 * REST through `api-gateway`, the engines do their work, and both halves of
 * the exchange come back as bus events through `ws-gateway`. Nothing here
 * talks to an engine, and nothing here renders a turn the system has not
 * confirmed.
 */

export function ConversationPanel({ onSessionChange }: { onSessionChange: (id: string | null) => void }) {
  const { data: session } = useQuery<ConversationSession | undefined>({
    queryKey: conversationKeys.session,
    queryFn: skipToken,
  });
  const sessionId = session?.session_id ?? null;

  const create = useCreateConversationSession();
  const send = useSendMessage(sessionId);
  const { data: entries } = useTranscript(sessionId);
  const { data: state } = useConversationState(sessionId);

  const failure = create.error ?? send.error;

  if (!sessionId) {
    return (
      <Panel title="Conversation">
        <div className="m-auto flex flex-col items-center gap-3">
          <p className="m-0 text-sm opacity-70">No conversation is open.</p>
          <Button
            busy={create.isPending}
            onClick={() =>
              create.mutate(
                { userId: crypto.randomUUID(), deviceId: crypto.randomUUID() },
                { onSuccess: (created) => onSessionChange(created.session_id) },
              )
            }
          >
            Start a conversation
          </Button>
          {failure ? <FailureNotice error={failure} /> : null}
        </div>
      </Panel>
    );
  }

  return (
    <Panel
      title="Conversation"
      accessory={
        // The engine's own FSM state, pushed over
        // `communication.session.state_changed` -- doc 04 §4's "the real
        // current state, never an approximation".
        <span className="nova-status" data-testid="conversation-state">
          {state ?? "unknown"}
        </span>
      }
    >
      <Transcript entries={entries ?? []} />
      {failure ? <FailureNotice error={failure} /> : null}
      <Composer
        sessionId={sessionId}
        busy={send.isPending}
        onSend={(content) => send.mutate(content)}
      />
    </Panel>
  );
}

function FailureNotice({ error }: { error: unknown }) {
  const gatewayError = error instanceof GatewayError ? error : null;
  return (
    <DegradationNotice
      title={
        gatewayError?.isRateLimited
          ? "Too many requests"
          : gatewayError?.isUnauthenticated
            ? "This session is no longer valid"
            : "The request did not go through"
      }
      detail={error instanceof Error ? error.message : String(error)}
      code={gatewayError?.code ?? null}
      correlationId={gatewayError?.correlationId ?? null}
    />
  );
}
