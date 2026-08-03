import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { ChartContainer } from "./ChartContainer";
import type { ECOption } from "../lib/echarts";

const { setOption, dispose, init } = vi.hoisted(() => {
  const setOption = vi.fn();
  const resize = vi.fn();
  const dispose = vi.fn();
  const init = vi.fn(() => ({ setOption, resize, dispose }));
  return { setOption, resize, dispose, init };
});

// Stub the lazy echarts module so jsdom never loads the real renderer.
vi.mock("../lib/echarts", () => ({ echarts: { init } }));

// Synthetic option — shape only, no real data.
const option: ECOption = {
  xAxis: { type: "category", data: ["a", "b"] },
  yAxis: { type: "value" },
  series: [{ type: "bar", data: [1, 2] }],
};

describe("ChartContainer", () => {
  it("exposes the chart as an image with the required aria-label", async () => {
    render(<ChartContainer option={option} ariaLabel="Test chart" />);

    expect(screen.getByRole("img", { name: "Test chart" })).toBeInTheDocument();
    await waitFor(() => expect(init).toHaveBeenCalledTimes(1));
    expect(setOption).toHaveBeenCalledWith(option, { notMerge: true });
  });

  it("renders a visually hidden data summary", async () => {
    render(
      <ChartContainer
        option={option}
        ariaLabel="Test chart"
        summary="Two synthetic bars, b is higher than a."
      />,
    );

    const summary = screen.getByText("Two synthetic bars, b is higher than a.");
    expect(summary).toHaveClass("sr-only");
    await waitFor(() => expect(init).toHaveBeenCalled());
  });

  it("falls back to the aria-label for the hidden summary", async () => {
    render(<ChartContainer option={option} ariaLabel="Fallback label" />);

    const captions = screen.getAllByText("Fallback label");
    expect(captions.some((el) => el.classList.contains("sr-only"))).toBe(true);
    await waitFor(() => expect(init).toHaveBeenCalled());
  });

  it("renders the accessible table fallback in a disclosure", async () => {
    render(
      <ChartContainer
        option={option}
        ariaLabel="Test chart"
        tableFallback={
          <table>
            <caption>Synthetic fallback table</caption>
            <tbody>
              <tr>
                <td>a</td>
              </tr>
            </tbody>
          </table>
        }
      />,
    );

    expect(screen.getByText("View data as table")).toBeInTheDocument();
    expect(
      screen.getByRole("table", { name: "Synthetic fallback table", hidden: true }),
    ).toBeInTheDocument();
    await waitFor(() => expect(init).toHaveBeenCalled());
  });

  it("applies the height prop and disposes the chart on unmount", async () => {
    const { unmount } = render(
      <ChartContainer option={option} ariaLabel="Test chart" height={240} />,
    );

    expect(screen.getByRole("img", { name: "Test chart" })).toHaveStyle({
      height: "240px",
    });
    await waitFor(() => expect(init).toHaveBeenCalled());
    unmount();
    expect(dispose).toHaveBeenCalled();
  });
});
