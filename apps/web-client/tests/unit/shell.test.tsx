import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { presenceKeys } from "../../src/entities/presence";
import { pulseKeys } from "../../src/entities/pulse";
import type { PulseState } from "../../src/entities/pulse";
import { PresenceIndicator } from "../../src/app/PresenceIndicator";
import { SessionGate } from "../../src/app/SessionGate";
import { SystemPulse } from "../../src/app/SystemPulse";

function wrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

const envelope = (data: unknown) => ({
  data,
  meta: { correlation_id: "corr", generated_at: "2026-09-02T10:00:00Z" },
  error: null,
});

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

/**
 * The shell's three indicators. Each one either shows real telemetry or
 * shows that it has none -- doc 04 §4 and Bible Part 6's "never generate
 * fake animations", tested at the component rather than argued in a comment.
 */

describe("SystemPulse", () => {
  it("is unknown and still before any heartbeat", () => {
    const client = new QueryClient();
    const { container } = render(<SystemPulse />, { wrapper: wrapper(client) });

    expect(screen.getByTestId("status-dot")).toHaveAttribute("data-status", "unknown");
    expect(container.querySelector(".nova-status-dot")).toHaveAttribute("data-animated", "false");
    expect(screen.getByTestId("status-dot")).toHaveTextContent("No heartbeat yet");
  });

  it("animates once a real heartbeat has arrived", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-02T10:00:01Z"));
    const client = new QueryClient();
    client.setQueryData<PulseState>(pulseKeys.current, {
      "nova-core": {
        module: "nova-core",
        status: "healthy",
        uptimeSeconds: 12,
        at: "2026-09-02T10:00:00Z",
        sequence: 1,
      },
    });

    const { container } = render(<SystemPulse />, { wrapper: wrapper(client) });
    expect(screen.getByTestId("status-dot")).toHaveAttribute("data-status", "healthy");
    expect(container.querySelector(".nova-status-dot")).toHaveAttribute("data-animated", "true");
  });

  it("stops animating and reports the loss when the heartbeat goes stale", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-02T10:05:00Z"));
    const client = new QueryClient();
    client.setQueryData<PulseState>(pulseKeys.current, {
      "nova-core": {
        module: "nova-core",
        status: "healthy",
        uptimeSeconds: 12,
        at: "2026-09-02T10:00:00Z",
        sequence: 1,
      },
    });

    const { container } = render(<SystemPulse />, { wrapper: wrapper(client) });
    expect(screen.getByTestId("status-dot")).toHaveAttribute("data-status", "unknown");
    expect(container.querySelector(".nova-status-dot")).toHaveAttribute("data-animated", "false");
    expect(screen.getByTestId("status-dot")).toHaveTextContent("Heartbeat lost");
  });
});

describe("PresenceIndicator", () => {
  it("says presence is unknown before any observation", () => {
    const client = new QueryClient();
    render(<PresenceIndicator />, { wrapper: wrapper(client) });
    expect(screen.getByTestId("status-dot")).toHaveTextContent("Presence unknown");
  });

  it("distinguishes 'we heard, nobody recognised' from 'we have not heard'", () => {
    const client = new QueryClient();
    client.setQueryData(presenceKeys.present, []);
    render(<PresenceIndicator />, { wrapper: wrapper(client) });
    expect(screen.getByTestId("status-dot")).toHaveTextContent("Nobody recognised");
  });

  it("reports who perception actually observed", () => {
    const client = new QueryClient();
    client.setQueryData(presenceKeys.present, [
      { userId: "u1", confidence: 0.9, confidenceTier: "high", observedAt: "2026-09-02T10:00:00Z" },
    ]);
    render(<PresenceIndicator />, { wrapper: wrapper(client) });
    expect(screen.getByTestId("status-dot")).toHaveTextContent("1 person present");
  });

  it("never animates -- presence is a state, not an event", () => {
    const client = new QueryClient();
    client.setQueryData(presenceKeys.present, [
      { userId: "u1", confidence: 0.9, confidenceTier: "high", observedAt: "2026-09-02T10:00:00Z" },
    ]);
    const { container } = render(<PresenceIndicator />, { wrapper: wrapper(client) });
    expect(container.querySelector(".nova-status-dot")).toHaveAttribute("data-animated", "false");
  });
});

describe("SessionGate", () => {
  it("asks for the token when no session is held", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(envelope({ authenticated: false }))),
    );
    const client = new QueryClient();
    render(
      <SessionGate>
        <p>workspace</p>
      </SessionGate>,
      { wrapper: wrapper(client) },
    );

    expect(await screen.findByLabelText("Session token")).toBeInTheDocument();
    expect(screen.queryByText("workspace")).not.toBeInTheDocument();
  });

  it("shows the workspace once a session is held", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(envelope({ authenticated: true }))),
    );
    const client = new QueryClient();
    render(
      <SessionGate>
        <p>workspace</p>
      </SessionGate>,
      { wrapper: wrapper(client) },
    );

    expect(await screen.findByText("workspace")).toBeInTheDocument();
  });

  it("does not present an unreachable gateway as 'please log in'", async () => {
    // Otherwise the user goes hunting for a token when the real problem is
    // that api-gateway is down -- a diagnosis the UI actively misdirects.
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            data: null,
            meta: { correlation_id: "corr-y", generated_at: "2026-09-02T10:00:00Z" },
            error: { code: "upstream_unavailable", message: "No route to the gateway." },
          },
          502,
        ),
      ),
    );
    const client = new QueryClient();
    render(
      <SessionGate>
        <p>workspace</p>
      </SessionGate>,
      { wrapper: wrapper(client) },
    );

    expect(await screen.findByTestId("degradation-notice")).toHaveTextContent(
      "No route to the gateway.",
    );
    expect(screen.queryByLabelText("Session token")).not.toBeInTheDocument();
  });

  it("exchanges the token and never puts it in the URL", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(envelope({ authenticated: false })))
      .mockResolvedValueOnce(jsonResponse(envelope({ authenticated: true })));
    vi.stubGlobal("fetch", fetchMock);

    const client = new QueryClient();
    render(
      <SessionGate>
        <p>workspace</p>
      </SessionGate>,
      { wrapper: wrapper(client) },
    );

    await userEvent.type(await screen.findByLabelText("Session token"), "local-token");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const [url, init] = fetchMock.mock.calls[1];
    expect(url).toBe("/v1/auth/session");
    expect(String(url)).not.toContain("local-token");
    expect(JSON.parse(init.body)).toEqual({ token: "local-token" });
    expect(init.credentials).toBe("include");

    expect(await screen.findByText("workspace")).toBeInTheDocument();
  });

  it("distinguishes an unprovisioned instance from a wrong token", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(envelope({ authenticated: false })))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            data: null,
            meta: { correlation_id: "corr-z", generated_at: "2026-09-02T10:00:00Z" },
            error: {
              code: "session_not_configured",
              message: "No local session token is provisioned for this instance.",
            },
          },
          503,
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    const client = new QueryClient();
    render(
      <SessionGate>
        <p>workspace</p>
      </SessionGate>,
      { wrapper: wrapper(client) },
    );

    await userEvent.type(await screen.findByLabelText("Session token"), "anything");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByTestId("degradation-notice")).toHaveTextContent(
      "This instance has no session token provisioned",
    );
  });
});
