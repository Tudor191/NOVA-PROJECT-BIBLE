import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusDot } from "../src/components/StatusDot";

/**
 * Doc 04 §4 / Bible Part 6: "never generate fake animations." The component
 * must therefore be still unless a caller holding a real signal asks for a
 * pulse, and `unknown` must stay distinguishable from `down`.
 */
describe("StatusDot", () => {
  it("does not animate by default", () => {
    const { container } = render(<StatusDot status="healthy" label="Heartbeat" />);
    const dot = container.querySelector(".nova-status-dot");
    expect(dot).toHaveAttribute("data-animated", "false");
    expect(dot?.className).not.toContain("nova-status-dot-pulse");
  });

  it("animates only when a caller explicitly asks", () => {
    const { container } = render(<StatusDot status="healthy" label="Heartbeat" animate />);
    const dot = container.querySelector(".nova-status-dot");
    expect(dot).toHaveAttribute("data-animated", "true");
    expect(dot?.className).toContain("nova-status-dot-pulse");
  });

  it("keeps 'unknown' distinct from 'down'", () => {
    const { rerender } = render(<StatusDot status="unknown" label="Heartbeat" />);
    expect(screen.getByTestId("status-dot")).toHaveAttribute("data-status", "unknown");
    rerender(<StatusDot status="down" label="Heartbeat" />);
    expect(screen.getByTestId("status-dot")).toHaveAttribute("data-status", "down");
  });

  it("honours animate=false regardless of status", () => {
    const { container } = render(<StatusDot status="down" label="Heartbeat" animate={false} />);
    expect(container.querySelector(".nova-status-dot")).toHaveAttribute("data-animated", "false");
  });
});
