import { render, screen } from "@testing-library/react";
import { createRef } from "react";
import { describe, expect, it } from "vitest";

import { cn } from "../src/cn";
import { Button } from "../src/components/Button";
import { CorrelationTag } from "../src/components/CorrelationTag";
import { DegradationNotice } from "../src/components/DegradationNotice";
import { Panel } from "../src/components/Panel";
import { TextField } from "../src/components/TextField";

describe("cn", () => {
  it("drops falsey parts rather than stringifying them", () => {
    expect(cn("a", false, null, undefined, "b")).toBe("a b");
  });
});

describe("Button", () => {
  it("is disabled and announced while busy", () => {
    render(<Button busy>Send</Button>);
    const button = screen.getByRole("button", { name: "Send" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
  });

  it("defaults to type=button so it cannot submit a form by accident", () => {
    render(<Button>Send</Button>);
    expect(screen.getByRole("button", { name: "Send" })).toHaveAttribute("type", "button");
  });

  it("still honours an explicit type", () => {
    render(<Button type="submit">Send</Button>);
    expect(screen.getByRole("button", { name: "Send" })).toHaveAttribute("type", "submit");
  });
});

describe("TextField", () => {
  it("forwards its ref, which React Hook Form's register() requires", () => {
    const ref = createRef<HTMLInputElement>();
    render(<TextField label="Session token" ref={ref} />);
    expect(ref.current).toBeInstanceOf(HTMLInputElement);
  });

  it("associates an error with the input for assistive technology", () => {
    render(<TextField label="Session token" error="That token is not valid." />);
    const input = screen.getByLabelText("Session token");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("alert")).toHaveTextContent("That token is not valid.");
    expect(input.getAttribute("aria-describedby")).toBe(screen.getByRole("alert").id);
  });
});

describe("DegradationNotice", () => {
  it("renders the correlation id rather than hiding it", () => {
    render(
      <DegradationNotice
        title="communication-engine is unavailable"
        detail="The gateway could not reach the engine."
        code="upstream_unavailable"
        correlationId="4f1d9c2a-0000-4000-8000-000000000000"
      />,
    );
    expect(screen.getByTestId("degradation-code")).toHaveTextContent("upstream_unavailable");
    expect(screen.getByTestId("degradation-correlation")).toHaveTextContent(
      "4f1d9c2a-0000-4000-8000-000000000000",
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});

describe("CorrelationTag", () => {
  it("truncates for display but keeps the full id addressable", () => {
    render(<CorrelationTag correlationId="4f1d9c2a-0000-4000-8000-000000000000" />);
    const tag = screen.getByTestId("correlation-tag");
    expect(tag).toHaveTextContent("4f1d9c2a");
    expect(tag).toHaveAttribute("data-correlation-id", "4f1d9c2a-0000-4000-8000-000000000000");
  });
});

describe("Panel", () => {
  it("exposes its title as an accessible region name", () => {
    render(
      <Panel title="Conversation">
        <p>body</p>
      </Panel>,
    );
    expect(screen.getByRole("region", { name: "Conversation" })).toBeInTheDocument();
  });
});
