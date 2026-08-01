import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import App, { AppRoutes } from "./App";
import { AWAITING_DATASET_MESSAGE } from "./components/EmptyState";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe("App shell", () => {
  it("renders the product name in the header", async () => {
    render(<App />);
    expect(
      await screen.findByRole("link", { name: /CodeTalent Atlas/ }),
    ).toBeInTheDocument();
  });

  it("shows the disabled pilot domain selector", async () => {
    render(<App />);
    const selector = await screen.findByRole("button", {
      name: /Cloud and DevOps/,
    });
    expect(selector).toBeDisabled();
  });
});

describe("routes", () => {
  const cases: Array<[path: string, heading: RegExp]> = [
    ["/", /Executive overview/],
    ["/explore", /Geographic explorer/],
    ["/compare", /Compare locations/],
    ["/location/us", /Location detail/],
    ["/methodology", /Methodology/],
    ["/recommendations", /Recommendations/],
    ["/about", /About CodeTalent Atlas/],
  ];

  it.each(cases)("renders %s with its h1", async (path, heading) => {
    renderAt(path);
    expect(
      await screen.findByRole("heading", { level: 1, name: heading }),
    ).toBeInTheDocument();
  });

  it("renders the awaiting-dataset empty state on data routes", async () => {
    renderAt("/explore");
    expect(await screen.findByText(AWAITING_DATASET_MESSAGE)).toBeInTheDocument();
  });

  it("renders the designed 404 for unknown paths", async () => {
    renderAt("/definitely/not/a/route");
    expect(
      await screen.findByRole("heading", { level: 1, name: /Page not found/ }),
    ).toBeInTheDocument();
    expect(screen.getByText("404")).toBeInTheDocument();
  });
});
