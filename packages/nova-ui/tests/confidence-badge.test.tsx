import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ConfidenceBadge, ConfidenceTierBadge } from "../src/components/ConfidenceBadge";

/**
 * The rule under test is Part 8's, not a styling preference: a confidence
 * that was never reported must not be rendered as a confidence of zero, and
 * must not silently disappear. Both failure modes would tell the user
 * something the system never said.
 */
describe("ConfidenceBadge", () => {
  it("says so when no confidence was reported", () => {
    render(<ConfidenceBadge confidence={null} />);
    const badge = screen.getByTestId("confidence-badge");
    expect(badge).toHaveAttribute("data-confidence", "absent");
    expect(badge).toHaveTextContent("no confidence reported");
    expect(badge.textContent).not.toMatch(/\d/);
  });

  it("treats undefined the same as null rather than as zero", () => {
    render(<ConfidenceBadge confidence={undefined} />);
    expect(screen.getByTestId("confidence-badge")).toHaveAttribute("data-confidence", "absent");
  });

  it("renders a reported zero as a real low confidence, not as absent", () => {
    render(<ConfidenceBadge confidence={0} />);
    const badge = screen.getByTestId("confidence-badge");
    expect(badge).toHaveAttribute("data-confidence", "low");
    expect(badge).toHaveTextContent("0% low");
  });

  it.each([
    [0.95, "high", "95% high"],
    [0.72, "moderate", "72% moderate"],
    [0.31, "low", "31% low"],
  ])("bands %s as %s", (value, expectedBand, expectedText) => {
    render(<ConfidenceBadge confidence={value} />);
    const badge = screen.getByTestId("confidence-badge");
    expect(badge).toHaveAttribute("data-confidence", expectedBand);
    expect(badge).toHaveTextContent(expectedText);
  });

  it("clamps an out-of-range value instead of rendering 140%", () => {
    render(<ConfidenceBadge confidence={1.4} />);
    expect(screen.getByTestId("confidence-badge")).toHaveTextContent("100% high");
  });
});

/**
 * `communication.intent.delivered` reports a tier *word*. No layer beneath
 * this converts it to a number, and this component must not either -- a
 * percentage rendered here would be invented at the last possible moment.
 */
describe("ConfidenceTierBadge", () => {
  it("never renders a number", () => {
    render(<ConfidenceTierBadge tier="high" />);
    expect(screen.getByTestId("confidence-tier-badge").textContent).not.toMatch(/\d/);
  });

  it.each(["unknown", "UNKNOWN", "  ", "", null, undefined])(
    "treats %s as no confidence reported",
    (tier) => {
      render(<ConfidenceTierBadge tier={tier} />);
      const badge = screen.getByTestId("confidence-tier-badge");
      expect(badge).toHaveAttribute("data-tier", "unknown");
      expect(badge).toHaveTextContent("no confidence reported");
    },
  );

  it("renders a reported tier as the word the engine used", () => {
    render(<ConfidenceTierBadge tier="Low" />);
    const badge = screen.getByTestId("confidence-tier-badge");
    expect(badge).toHaveAttribute("data-tier", "low");
    expect(badge).toHaveTextContent("low confidence");
  });

  it("passes an unrecognised tier through rather than dropping it", () => {
    // A future engine may report a tier this component has no colour for.
    // Showing the word is still strictly better than showing nothing.
    render(<ConfidenceTierBadge tier="speculative" />);
    expect(screen.getByTestId("confidence-tier-badge")).toHaveTextContent(
      "speculative confidence",
    );
  });
});
