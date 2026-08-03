import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../App";
import { clearDataCache } from "../lib/data";
import { stubDataFetch, syntheticFiles } from "../test/fixtures/stubFetch";

afterEach(() => {
  vi.unstubAllGlobals();
  clearDataCache();
});

function renderAbout() {
  return render(
    <MemoryRouter initialEntries={["/about"]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe("About", () => {
  it("states the project principles", async () => {
    stubDataFetch(syntheticFiles());
    renderAbout();

    expect(
      await screen.findByRole("heading", { level: 1, name: /About CodeTalent Atlas/ }),
    ).toBeInTheDocument();
    expect(screen.getByText("Public data only")).toBeInTheDocument();
    expect(screen.getByText("Aggregate-only output")).toBeInTheDocument();
    expect(screen.getByText("Reproducible methodology")).toBeInTheDocument();
  });
});

describe("Footer dataset wiring", () => {
  it("surfaces datasetVersion and methodologyVersion from the manifest", async () => {
    stubDataFetch(syntheticFiles());
    renderAbout();

    expect(
      await screen.findByText("Dataset: 0000.00.00-synthetic.1"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Methodology v0.0.0-synthetic"),
    ).toBeInTheDocument();
  });

  it("shows the pending label when no manifest is published", async () => {
    stubDataFetch({});
    renderAbout();

    expect(
      await screen.findByText("Dataset: pending first pipeline run"),
    ).toBeInTheDocument();
  });
});
