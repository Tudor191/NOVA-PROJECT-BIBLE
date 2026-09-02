import { Button } from "@nova/ui";
import { useState } from "react";

import { useEndSession } from "../entities/session";
import { ConversationPanel } from "../panels/conversation/ConversationPanel";
import { RealtimeProvider } from "../realtime/provider";
import { ConnectionState } from "./ConnectionState";
import { PresenceIndicator } from "./PresenceIndicator";
import { SystemPulse } from "./SystemPulse";

/**
 * The workspace frame (doc 04 §2).
 *
 * A header of always-visible instrument readings plus a panel area. 4A fills
 * the panel area with one panel; 4B onward add theirs beside it without
 * touching this file.
 *
 * The three header indicators are the shell's whole job: what NOVA's
 * background modules are doing, who it believes is present, and whether what
 * is on screen is live. Each one renders real telemetry or renders that it
 * has none.
 */
export function AppShell() {
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const endSession = useEndSession();

  return (
    <RealtimeProvider activeSessionId={activeSessionId}>
      <div className="flex h-screen flex-col" style={{ background: "var(--nova-bg)" }}>
        <header
          className="flex items-center justify-between gap-4 border-b px-4 py-2"
          style={{ borderColor: "var(--nova-border)", color: "var(--nova-text)" }}
        >
          <div className="flex items-center gap-4">
            <span className="text-sm font-semibold tracking-wide">NOVA</span>
            <SystemPulse />
            <PresenceIndicator />
          </div>
          <div className="flex items-center gap-3">
            <ConnectionState />
            <Button
              variant="ghost"
              busy={endSession.isPending}
              onClick={() => endSession.mutate()}
            >
              Sign out
            </Button>
          </div>
        </header>

        <main className="flex min-h-0 flex-1 gap-4 p-4">
          <ConversationPanel onSessionChange={setActiveSessionId} />
        </main>
      </div>
    </RealtimeProvider>
  );
}
