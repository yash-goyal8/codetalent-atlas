import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ConfidenceBadge } from "./ConfidenceBadge";

describe("ConfidenceBadge", () => {
  it("renders a text label plus the numeric score", () => {
    render(<ConfidenceBadge score={82} />);

    expect(screen.getByText("High confidence")).toBeInTheDocument();
    expect(screen.getByText("82.0")).toBeInTheDocument();
  });

  it("buckets medium and low scores with distinct labels", () => {
    const { rerender } = render(<ConfidenceBadge score={55} />);
    expect(screen.getByText("Medium confidence")).toBeInTheDocument();

    rerender(<ConfidenceBadge score={12} />);
    expect(screen.getByText("Low confidence")).toBeInTheDocument();
  });

  it("can hide the score when a neighboring cell shows it", () => {
    render(<ConfidenceBadge score={82} showScore={false} />);

    expect(screen.getByText("High confidence")).toBeInTheDocument();
    expect(screen.queryByText("82.0")).not.toBeInTheDocument();
  });

  it("marks the icon as decorative", () => {
    const { container } = render(<ConfidenceBadge score={82} />);

    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });
});
