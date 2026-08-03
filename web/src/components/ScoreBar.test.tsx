import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ScoreBar } from "./ScoreBar";

describe("ScoreBar", () => {
  it("renders an accessible meter with the 0-100 range", () => {
    render(<ScoreBar label="Expert supply" value={72.4} />);

    const meter = screen.getByRole("meter", { name: "Expert supply" });
    expect(meter).toHaveAttribute("aria-valuemin", "0");
    expect(meter).toHaveAttribute("aria-valuemax", "100");
    expect(meter).toHaveAttribute("aria-valuenow", "72.4");
  });

  it("always prints the numeric value, never color alone", () => {
    render(<ScoreBar label="Momentum" value={72.44} />);

    expect(screen.getByText("72.4")).toBeInTheDocument();
    expect(screen.getByText("Momentum")).toBeInTheDocument();
  });

  it("clamps the bar to the 0-100 range", () => {
    render(<ScoreBar label="Overflow" value={140} />);

    expect(
      screen.getByRole("meter", { name: "Overflow" }),
    ).toHaveAttribute("aria-valuenow", "100");
  });
});
