import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { Skeleton } from "./Skeleton";

describe("Skeleton", () => {
  it("is hidden from assistive technology", () => {
    const { container } = render(<Skeleton />);

    expect(container.firstChild).toHaveAttribute("aria-hidden", "true");
  });

  it("pulses by default but stands down under reduced motion", () => {
    const { container } = render(<Skeleton />);
    const el = container.firstChild as HTMLElement;

    expect(el.className).toContain("animate-pulse");
    expect(el.className).toContain("motion-reduce:animate-none");
  });

  it("accepts sizing classes", () => {
    const { container } = render(<Skeleton className="h-4 w-32" />);
    const el = container.firstChild as HTMLElement;

    expect(el.className).toContain("h-4");
    expect(el.className).toContain("w-32");
  });
});
