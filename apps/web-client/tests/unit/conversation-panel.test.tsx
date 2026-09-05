import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { conversationKeys } from "../../src/entities/conversation";
import type { TranscriptEntry } from "../../src/entities/conversation";
import { ConversationPanel } from "../../src/panels/conversation/ConversationPanel";
import { applyFrame } from "../../src/realtime/reconcile";
import type { EventFrame } from "../../src/realtime/protocol";
import { useUiStore } from "../../src/shared/store";

const SESSION = "11111111-1111-4111-8111-111111111111";

function wrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

function seedSession(client: QueryClient) {
  client.setQueryData(conversationKeys.session, {
    session_id: SESSION,
    user_id: "user-1",
    channel: "text",
    device_id: "device-1",
    state: "idle",
    objective: null,
    created_at: "2026-09-02T10:00:00Z",
    updated_at: "2026-09-02T10:00:00Z",
    closed_at: null,
  });
}

const envelope = (data: unknown) => ({
  data,
  meta: { correlation_id: "4f1d9c2a-0000-4000-8000-000000000000", generated_at: "2026-09-02T10:00:00Z" },
  error: null,
});

beforeEach(() => {
  useUiStore.setState({ drafts: {} });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ConversationPanel", () => {
  it("says nothing has been said rather than looking broken", () => {
    const client = new QueryClient();
    seedSession(client);
    render(<ConversationPanel />, { wrapper: wrapper(client) });
    expect(screen.getByTestId("transcript-empty")).toBeInTheDocument();
  });

  it("renders both halves of a real exchange, reply included", () => {
    const client = new QueryClient();
    seedSession(client);
    const frames: EventFrame[] = [
      {
        type: "event",
        topic: "communication.turn.received",
        data: {
          session_id: SESSION,
          turn_id: "t1",
          user_id: "user-1",
          content: "How did the build go?",
          channel: "text",
          created_at: "2026-09-02T10:00:00Z",
        },
        meta: { correlation_id: "corr-a", generated_at: "2026-09-02T10:00:00Z" },
      },
      {
        type: "event",
        topic: "communication.intent.delivered",
        data: {
          session_id: SESSION,
          turn_id: "t2",
          user_id: "user-1",
          content: "The build finished.",
          channel: "text",
          confidence_tier: "high",
          personality_validated: true,
          degraded: false,
          delivered_at: "2026-09-02T10:00:05Z",
        },
        meta: { correlation_id: "corr-b", generated_at: "2026-09-02T10:00:05Z" },
      },
    ];
    for (const frame of frames) applyFrame(client, frame, SESSION);

    render(<ConversationPanel />, { wrapper: wrapper(client) });

    const entries = screen.getAllByTestId("transcript-entry");
    expect(entries).toHaveLength(2);
    expect(entries[0]).toHaveTextContent("How did the build go?");
    expect(entries[1]).toHaveTextContent("The build finished.");
    expect(entries[1]).toHaveAttribute("data-author", "nova");
  });

  it("shows the reply's confidence as a word, never a percentage", () => {
    const client = new QueryClient();
    seedSession(client);
    client.setQueryData<TranscriptEntry[]>(conversationKeys.transcript(SESSION), [
      {
        id: "t2",
        author: "nova",
        content: "The build finished.",
        at: "2026-09-02T10:00:05Z",
        confidenceTier: "high",
        correlationId: "corr-b",
        degraded: false,
      },
    ]);
    render(<ConversationPanel />, { wrapper: wrapper(client) });

    const badge = screen.getByTestId("confidence-tier-badge");
    expect(badge).toHaveTextContent("high confidence");
    expect(badge.textContent).not.toMatch(/\d/);
  });

  it("says so when the source engine reported no confidence", () => {
    const client = new QueryClient();
    seedSession(client);
    client.setQueryData<TranscriptEntry[]>(conversationKeys.transcript(SESSION), [
      {
        id: "t2",
        author: "nova",
        content: "An answer.",
        at: "2026-09-02T10:00:05Z",
        confidenceTier: "unknown",
        correlationId: "corr-b",
        degraded: false,
      },
    ]);
    render(<ConversationPanel />, { wrapper: wrapper(client) });
    expect(screen.getByTestId("confidence-tier-badge")).toHaveTextContent("no confidence reported");
  });

  it("discloses a turn that went out unvalidated", () => {
    const client = new QueryClient();
    seedSession(client);
    client.setQueryData<TranscriptEntry[]>(conversationKeys.transcript(SESSION), [
      {
        id: "t2",
        author: "nova",
        content: "Unvalidated answer.",
        at: "2026-09-02T10:00:05Z",
        confidenceTier: "unknown",
        correlationId: "corr-b",
        degraded: true,
      },
    ]);
    render(<ConversationPanel />, { wrapper: wrapper(client) });
    expect(screen.getByTestId("degraded-turn")).toBeInTheDocument();
  });

  it("renders the correlation id rather than hiding it", () => {
    const client = new QueryClient();
    seedSession(client);
    client.setQueryData<TranscriptEntry[]>(conversationKeys.transcript(SESSION), [
      {
        id: "t1",
        author: "user",
        content: "Hello",
        at: "2026-09-02T10:00:00Z",
        confidenceTier: null,
        correlationId: "4f1d9c2a-0000-4000-8000-000000000000",
        degraded: false,
      },
    ]);
    render(<ConversationPanel />, { wrapper: wrapper(client) });
    expect(screen.getByTestId("correlation-tag")).toHaveAttribute(
      "data-correlation-id",
      "4f1d9c2a-0000-4000-8000-000000000000",
    );
  });

  it("does not render a sent turn until the system confirms it", async () => {
    // TDD 4A §5.2 property 2: nothing affecting shared cognitive state is
    // rendered optimistically. The turn appears when
    // `communication.turn.received` comes back, not when Send is clicked.
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(envelope({ turn_id: "t1", session_id: SESSION, accepted: true })), {
        status: 202,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const client = new QueryClient();
    seedSession(client);
    render(<ConversationPanel />, { wrapper: wrapper(client) });

    await userEvent.type(screen.getByPlaceholderText("Say something to NOVA"), "Hello");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`/v1/communication/sessions/${SESSION}/messages`);
    expect(init.method).toBe("POST");
    // The transcript is still empty: nothing was assumed.
    expect(screen.getByTestId("transcript-empty")).toBeInTheDocument();
  });

  it("sends the session cookie and never a token in the URL", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(envelope({ turn_id: "t1", session_id: SESSION, accepted: true })), {
        status: 202,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const client = new QueryClient();
    seedSession(client);
    render(<ConversationPanel />, { wrapper: wrapper(client) });

    await userEvent.type(screen.getByPlaceholderText("Say something to NOVA"), "Hello");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0];
    expect(init.credentials).toBe("include");
    expect(String(url)).not.toMatch(/token/i);
  });

  it("surfaces an unreachable engine instead of an empty panel", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          data: null,
          meta: { correlation_id: "corr-x", generated_at: "2026-09-02T10:00:00Z" },
          error: {
            code: "upstream_unavailable",
            message: "communication-engine did not answer.",
            upstream_status: null,
          },
        }),
        { status: 502, headers: { "content-type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const client = new QueryClient();
    seedSession(client);
    render(<ConversationPanel />, { wrapper: wrapper(client) });

    await userEvent.type(screen.getByPlaceholderText("Say something to NOVA"), "Hello");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    const notice = await screen.findByTestId("degradation-notice");
    expect(notice).toHaveTextContent("communication-engine did not answer.");
    expect(screen.getByTestId("degradation-code")).toHaveTextContent("upstream_unavailable");
    expect(screen.getByTestId("degradation-correlation")).toHaveTextContent("corr-x");
  });

  it("shows the engine's own conversation state, not an approximation", () => {
    const client = new QueryClient();
    seedSession(client);
    client.setQueryData(conversationKeys.state(SESSION), "speaking");
    render(<ConversationPanel />, { wrapper: wrapper(client) });
    expect(screen.getByTestId("conversation-state")).toHaveTextContent("speaking");
  });
});
