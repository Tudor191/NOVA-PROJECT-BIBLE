import { QueryClientProvider, useMutation, useQuery } from "@tanstack/react-query";
import type { QueryClient } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";

import { createQueryClient } from "../../src/app/queryClient";
import { SessionGate } from "../../src/app/SessionGate";
import { GatewayError } from "../../src/entities/envelope";
import { gatewayFetch } from "../../src/entities/http";
import { AsyncPanelBody } from "../../src/panels/shared/AsyncPanelBody";

/**
 * TDD 4A §7's two request failure rows, tested against the production query
 * client rather than a bare `new QueryClient()`:
 *
 * - **"Session token expired or invalid"**: `api-gateway` rejects with 401,
 *   and *the frontend re-runs the first-run session flow (§4)*.
 * - **"Rate limit exceeded"**: 429 *with a structured retry hint; the panel
 *   surfaces it rather than retrying invisibly*.
 */

const meta = { correlation_id: "corr-f", generated_at: "2026-10-16T10:00:00Z" };
const ok = (data: unknown) => ({ data, meta, error: null });
const failure = (code: string, message: string) => ({ data: null, meta, error: { code, message } });

function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
}

type Route = (init: RequestInit | undefined, call: number) => Response;

/** A fetch that answers by `METHOD path`, and counts each one's calls. */
function stubGateway(routes: Record<string, Route>) {
  const calls: Record<string, number> = {};
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost");
    const key = `${(init?.method ?? "GET").toUpperCase()} ${url.pathname}`;
    calls[key] = (calls[key] ?? 0) + 1;
    const route = routes[key];
    if (!route) throw new Error(`unexpected request: ${key}`);
    return route(init, calls[key]);
  });
  vi.stubGlobal("fetch", fetchMock);
  return { calls, fetchMock };
}

const unauthenticated = () =>
  jsonResponse(failure("unauthenticated", "A valid session is required."), 401);

function wrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

const thoughtsSchema = z.object({ thoughts: z.array(z.unknown()) });

function ReadingPanel() {
  const query = useQuery({
    queryKey: ["test", "thoughts"],
    queryFn: async () => (await gatewayFetch("/v1/cognitive-state/thoughts", thoughtsSchema)).data,
  });
  return (
    <AsyncPanelBody
      isPending={query.isPending}
      error={query.error}
      isEmpty={false}
      emptyLabel="nothing"
    >
      <p>thoughts read</p>
    </AsyncPanelBody>
  );
}

function WritingPanel() {
  const mutation = useMutation({
    mutationFn: async () =>
      (await gatewayFetch("/v1/autonomy/level", z.unknown(), { method: "PUT", body: {} })).data,
  });
  return (
    <button type="button" onClick={() => mutation.mutate()}>
      set level
    </button>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("a 401 re-runs the first-run session flow (TDD 4A §7)", () => {
  it("returns to the token prompt when a panel's read is refused and the session is gone", async () => {
    const { calls } = stubGateway({
      // Valid at boot; expired by the time anyone asks again.
      "GET /v1/auth/session": (_, call) => jsonResponse(ok({ authenticated: call === 1 })),
      "GET /v1/cognitive-state/thoughts": unauthenticated,
    });
    render(
      <SessionGate>
        <ReadingPanel />
      </SessionGate>,
      { wrapper: wrapper(createQueryClient()) },
    );

    expect(await screen.findByLabelText("Session token")).toBeInTheDocument();
    expect(screen.queryByText("thoughts read")).not.toBeInTheDocument();
    // The prompt is the gateway's answer, not a guess: the probe was re-asked.
    expect(calls["GET /v1/auth/session"]).toBe(2);
  });

  it("returns to the token prompt when a write is refused and the session is gone", async () => {
    const { calls } = stubGateway({
      "GET /v1/auth/session": (_, call) => jsonResponse(ok({ authenticated: call === 1 })),
      "PUT /v1/autonomy/level": unauthenticated,
    });
    render(
      <SessionGate>
        <WritingPanel />
      </SessionGate>,
      { wrapper: wrapper(createQueryClient()) },
    );

    await userEvent.click(await screen.findByRole("button", { name: "set level" }));

    expect(await screen.findByLabelText("Session token")).toBeInTheDocument();
    expect(calls["PUT /v1/autonomy/level"]).toBe(1);
    expect(calls["GET /v1/auth/session"]).toBe(2);
  });

  it("keeps the workspace when the gateway says the session is still valid", async () => {
    // A 401 the session probe contradicts is that request's failure, shown
    // in its panel -- not grounds to sign anyone out.
    const { calls } = stubGateway({
      "GET /v1/auth/session": () => jsonResponse(ok({ authenticated: true })),
      "GET /v1/cognitive-state/thoughts": unauthenticated,
    });
    render(
      <SessionGate>
        <ReadingPanel />
      </SessionGate>,
      { wrapper: wrapper(createQueryClient()) },
    );

    expect(await screen.findByText("This session is no longer valid")).toBeInTheDocument();
    await waitFor(() => expect(calls["GET /v1/auth/session"]).toBe(2));
    expect(screen.queryByLabelText("Session token")).not.toBeInTheDocument();
  });

  it("does not re-ask the probe when the token itself is refused", async () => {
    // The refusal *is* the answer, and it is already on screen.
    const { calls } = stubGateway({
      "GET /v1/auth/session": () => jsonResponse(ok({ authenticated: false })),
      "POST /v1/auth/session": () =>
        jsonResponse(failure("invalid_token", "That token was not accepted."), 401),
    });
    render(
      <SessionGate>
        <p>workspace</p>
      </SessionGate>,
      { wrapper: wrapper(createQueryClient()) },
    );

    await userEvent.type(await screen.findByLabelText("Session token"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("That token was not accepted")).toBeInTheDocument();
    expect(calls["POST /v1/auth/session"]).toBe(1);
    expect(calls["GET /v1/auth/session"]).toBe(1);
  });

  it("never loops when the session probe itself is refused", async () => {
    const { calls } = stubGateway({ "GET /v1/auth/session": unauthenticated });
    render(
      <SessionGate>
        <p>workspace</p>
      </SessionGate>,
      { wrapper: wrapper(createQueryClient()) },
    );

    expect(await screen.findByLabelText("Session token")).toBeInTheDocument();
    // Give a re-ask loop every chance to show itself before counting.
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(calls["GET /v1/auth/session"]).toBe(1);
  });
});

describe("a 429 is surfaced with its retry hint, never retried invisibly (TDD 4A §7)", () => {
  it("carries the gateway's Retry-After as a number and in the message", async () => {
    stubGateway({
      "GET /v1/cognitive-state/thoughts": () =>
        jsonResponse(failure("rate_limited", "Too many requests for this endpoint class."), 429, {
          "retry-after": "17",
        }),
    });

    const error = await gatewayFetch("/v1/cognitive-state/thoughts", thoughtsSchema).catch(
      (caught: unknown) => caught,
    );

    expect(error).toBeInstanceOf(GatewayError);
    const gatewayError = error as GatewayError;
    expect(gatewayError.isRateLimited).toBe(true);
    expect(gatewayError.retryAfterSeconds).toBe(17);
    expect(gatewayError.message).toBe("Too many requests for this endpoint class. Try again in 17 s.");
  });

  it("invents no hint when the gateway sent none, or one that is not delta-seconds", async () => {
    const variants: Record<string, string>[] = [
      {},
      { "retry-after": "Fri, 16 Oct 2026 10:00:00 GMT" },
      { "retry-after": "-3" },
    ];
    for (const headers of variants) {
      stubGateway({
        "GET /v1/cognitive-state/thoughts": () =>
          jsonResponse(failure("rate_limited", "Too many requests for this endpoint class."), 429, headers),
      });
      const error = (await gatewayFetch("/v1/cognitive-state/thoughts", thoughtsSchema).catch(
        (caught: unknown) => caught,
      )) as GatewayError;
      expect(error.retryAfterSeconds).toBeNull();
      expect(error.message).toBe("Too many requests for this endpoint class.");
    }
  });

  it("is named as a rate limit in the panel, with the hint, and asked exactly once", async () => {
    const { calls } = stubGateway({
      "GET /v1/cognitive-state/thoughts": () =>
        jsonResponse(failure("rate_limited", "Too many requests for this endpoint class."), 429, {
          "retry-after": "17",
        }),
    });
    render(<ReadingPanel />, { wrapper: wrapper(createQueryClient()) });

    expect(await screen.findByText("Too many requests")).toBeInTheDocument();
    expect(screen.getByText(/Try again in 17 s\./)).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(calls["GET /v1/cognitive-state/thoughts"]).toBe(1);
  });
});
