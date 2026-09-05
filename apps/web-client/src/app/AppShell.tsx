import { Button } from "@nova/ui";
import { Link, Outlet } from "@tanstack/react-router";

import { useEndSession } from "../entities/session";
import { RealtimeProvider } from "../realtime/provider";
import { useUiStore } from "../shared/store";
import { ConnectionState } from "./ConnectionState";
import { PresenceIndicator } from "./PresenceIndicator";
import { SystemPulse } from "./SystemPulse";

/**
 * The workspace frame (doc 04 §2).
 *
 * A header of always-visible instrument readings, a panel switcher, and one
 * panel at a time. 4A filled the panel area with a single component; 4B
 * turns it into an `Outlet` so each panel is its own lazily-loaded route.
 *
 * **The socket lives here, above the outlet, and that is load-bearing.**
 * `RealtimeProvider` must not remount when the operator switches panels: a
 * remount would drop the WebSocket, resubscribe, and lose every frame in
 * the gap -- so the Events panel would show a hole exactly when someone
 * navigated to look at it. One connection serves every panel, and the
 * panels read the cache it fills.
 *
 * The three header indicators are the shell's whole job: what NOVA's
 * background modules are doing, who it believes is present, and whether
 * what is on screen is live.
 */

const PANELS = [
  { path: "/", label: "Conversation" },
  { path: "/planning", label: "Planning" },
  { path: "/reasoning", label: "Reasoning" },
  { path: "/capabilities", label: "Capabilities" },
  { path: "/approvals", label: "Approvals" },
  { path: "/events", label: "Events" },
  { path: "/health", label: "Health" },
] as const;

export function AppShell() {
  const activeSessionId = useUiStore((state) => state.activeSessionId);
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
            <Button variant="ghost" busy={endSession.isPending} onClick={() => endSession.mutate()}>
              Sign out
            </Button>
          </div>
        </header>

        <nav
          className="flex items-center gap-1 border-b px-4 py-1"
          style={{ borderColor: "var(--nova-border)" }}
          aria-label="Panels"
          data-testid="panel-nav"
        >
          {PANELS.map((panel) => (
            <Link
              key={panel.path}
              to={panel.path}
              className="nova-nav-link"
              activeProps={{ "data-active": "true" }}
              data-testid={`nav-${panel.label.toLowerCase()}`}
            >
              {panel.label}
            </Link>
          ))}
        </nav>

        <main className="flex min-h-0 flex-1 gap-4 p-4">
          <Outlet />
        </main>
      </div>
    </RealtimeProvider>
  );
}
