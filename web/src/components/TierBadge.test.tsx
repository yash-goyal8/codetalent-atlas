import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { TierBadge } from "./TierBadge";
import type { RecommendationTier } from "../types/rankings";

const cases: Array<[RecommendationTier, string]> = [
  ["priority", "Priority"],
  ["promising", "Promising"],
  ["monitor", "Monitor"],
  ["insufficient_data", "Insufficient data"],
];

describe("TierBadge", () => {
  it.each(cases)("renders a text label for %s (never color alone)", (tier, label) => {
    render(<TierBadge tier={tier} />);

    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("marks the icon as decorative", () => {
    const { container } = render(<TierBadge tier="priority" />);

    const icon = container.querySelector("svg");
    expect(icon).not.toBeNull();
    expect(icon).toHaveAttribute("aria-hidden", "true");
  });
});
