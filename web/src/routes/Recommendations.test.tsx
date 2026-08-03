import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import Recommendations from "./Recommendations";
import { AWAITING_DATASET_MESSAGE } from "../components/EmptyState";
import { clearDataCache } from "../lib/data";
import {
  expectNoUsernameArtifacts,
  stubDataFetch,
  syntheticFiles,
} from "../test/fixtures/stubFetch";
import { syntheticRecommendations } from "../test/fixtures/dataset";

afterEach(() => {
  vi.unstubAllGlobals();
  clearDataCache();
});

function renderRecommendations() {
  return render(
    <MemoryRouter initialEntries={["/recommendations"]}>
      <Recommendations />
    </MemoryRouter>,
  );
}

describe("Recommendations with full data", () => {
  it("renders each memo item in the executive template structure", async () => {
    stubDataFetch(syntheticFiles());
    renderRecommendations();

    const heading = await screen.findByRole("heading", {
      level: 3,
      name: /Investigate United States for .* contributors/,
    });
    const memo = heading.closest("li") as HTMLElement;
    expect(within(memo).getByText("Why now")).toBeInTheDocument();
    expect(within(memo).getByText("Main risk")).toBeInTheDocument();
    expect(within(memo).getByText("Suggested next step")).toBeInTheDocument();
    expect(
      within(memo).getByText("Synthetic why-now rationale — fixture text only."),
    ).toBeInTheDocument();
    expect(
      within(memo).getByText("Synthetic risk statement — fixture text only."),
    ).toBeInTheDocument();
    expect(
      within(memo).getByText("Synthetic pilot suggestion — fixture text only."),
    ).toBeInTheDocument();
    expect(within(memo).getByText("Observable pool")).toBeInTheDocument();
    expect(within(memo).getByText("900")).toBeInTheDocument();
    expect(
      within(memo).getByRole("link", { name: /Full profile for United States/ }),
    ).toHaveAttribute("href", "/location/US");
  });

  it("shows generated time, scores, and confidence labels per item", async () => {
    stubDataFetch(syntheticFiles());
    renderRecommendations();

    expect(await screen.findByText(/Memo generated/)).toHaveTextContent(
      "2000-01-01 00:00 UTC",
    );
    expect(
      screen.getByRole("heading", { level: 3, name: /Investigate Germany/ }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("High confidence").length).toBe(2);
  });

  it("never renders a username-like string", async () => {
    stubDataFetch(syntheticFiles());
    renderRecommendations();

    await screen.findByText(/Memo generated/);
    expectNoUsernameArtifacts(document.body.textContent);
  });
});

describe("Recommendations without data", () => {
  it("renders the generated-after-validation empty state when the file is missing", async () => {
    stubDataFetch({});
    renderRecommendations();

    expect(
      await screen.findByText(AWAITING_DATASET_MESSAGE),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Recommendations are generated after the validated pilot dataset exists — none are pre-written.",
      ),
    ).toBeInTheDocument();
  });

  it("renders a designed state when the published file has zero items", async () => {
    const files = syntheticFiles();
    files["/data/recommendations/cloud_devops.json"] = {
      generatedAt: syntheticRecommendations.generatedAt,
      items: [],
    };
    stubDataFetch(files);
    renderRecommendations();

    expect(
      await screen.findByText(
        "The published recommendations file contains no items for this dataset window.",
      ),
    ).toBeInTheDocument();
  });
});
