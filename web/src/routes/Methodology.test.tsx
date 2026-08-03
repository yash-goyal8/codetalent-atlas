import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import Methodology from "./Methodology";
import { AWAITING_DATASET_MESSAGE } from "../components/EmptyState";
import { REPRESENTATION_LIMITATIONS } from "../features/methodology/content";
import { clearDataCache } from "../lib/data";
import {
  stubDataFetch,
  syntheticFiles,
  syntheticSensitivity,
} from "../test/fixtures/stubFetch";

// jsdom has no canvas: stub the lazily imported echarts module.
vi.mock("../lib/echarts", () => ({
  echarts: {
    init: () => ({ setOption: () => {}, resize: () => {}, dispose: () => {} }),
  },
}));

afterEach(() => {
  vi.unstubAllGlobals();
  clearDataCache();
});

function renderMethodology() {
  return render(
    <MemoryRouter initialEntries={["/methodology"]}>
      <Methodology />
    </MemoryRouter>,
  );
}

/**
 * The exact configured weights (spec 16.1, 16.2, 17). If any of these
 * assertions fail, the UI no longer matches the scoring configuration.
 */
const EXPECTED_FORMULAS: Array<[title: string, rows: Array<[string, number]>]> = [
  [
    "Repository quality score",
    [
      ["Recent activity", 30],
      ["Contributor diversity", 25],
      ["Collaboration quality", 20],
      ["Technical relevance", 15],
      ["Repository maturity", 10],
    ],
  ],
  [
    "Contributor expert score",
    [
      ["Domain activity", 35],
      ["Contribution quality", 25],
      ["Repository quality exposure", 20],
      ["Continuity", 10],
      ["Collaboration", 10],
    ],
  ],
  [
    "Opportunity score",
    [
      ["Expert supply", 35],
      ["Expert quality", 30],
      ["Collaboration depth", 15],
      ["Momentum", 10],
      ["Ecosystem breadth", 10],
    ],
  ],
  [
    "Confidence score",
    [
      ["Located profile coverage", 35],
      ["Location certainty", 25],
      ["Sample size adequacy", 20],
      ["Repository diversity", 10],
      ["Organization diversity", 10],
    ],
  ],
];

describe("Methodology static content (renders in every data state)", () => {
  it("shows the four score formula cards with the exact configured weights", async () => {
    stubDataFetch({});
    renderMethodology();

    for (const [title, rows] of EXPECTED_FORMULAS) {
      const card = (
        await screen.findByRole("heading", { level: 3, name: title })
      ).closest("div");
      expect(card).not.toBeNull();
      let sum = 0;
      for (const [label, weight] of rows) {
        const row = within(card as HTMLElement)
          .getByText(label)
          .closest("div");
        expect(row).toHaveTextContent(`${weight}%`);
        sum += weight;
      }
      expect(sum).toBe(100);
    }
  });

  it("renders the pipeline diagram and inclusion/exclusion rules", async () => {
    stubDataFetch({});
    renderMethodology();

    expect(
      await screen.findByText("GH Archive monthly tables"),
    ).toBeInTheDocument();
    expect(screen.getByText("BigQuery discovery SQL")).toBeInTheDocument();
    expect(screen.getByText("Static web datasets")).toBeInTheDocument();
    expect(
      screen.getByText("At least five unique human contributors"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Bots and automation accounts"),
    ).toBeInTheDocument();
  });

  it("lists all six representation limitations verbatim", async () => {
    stubDataFetch({});
    renderMethodology();

    expect(REPRESENTATION_LIMITATIONS).toHaveLength(6);
    for (const limitation of REPRESENTATION_LIMITATIONS) {
      expect(await screen.findByText(limitation)).toBeInTheDocument();
    }
  });

  it("explains the opportunity/confidence separation", async () => {
    stubDataFetch({});
    renderMethodology();

    expect(
      await screen.findByText(/never merged into one opaque number/),
    ).toBeInTheDocument();
  });
});

describe("Methodology with full data", () => {
  it("renders the data funnel with formatted stage counts", async () => {
    stubDataFetch(syntheticFiles());
    renderMethodology();

    const funnel = await screen.findByRole("list", {
      name: "Data funnel stages with counts",
    });
    expect(within(funnel).getByText("Candidate repositories")).toBeInTheDocument();
    expect(within(funnel).getByText("10k")).toBeInTheDocument();
    expect(within(funnel).getByText("Qualified repositories")).toBeInTheDocument();
    expect(within(funnel).getByText("2k")).toBeInTheDocument();
  });

  it("renders validation precision, quality checks, and budget", async () => {
    stubDataFetch(syntheticFiles());
    renderMethodology();

    const precisionCard = (
      await screen.findByRole("heading", {
        level: 3,
        name: "Manual validation precision",
      })
    ).closest("div") as HTMLElement;
    expect(
      within(precisionCard)
        .getByText("Repository classification precision")
        .closest("div"),
    ).toHaveTextContent("90%");
    expect(
      within(precisionCard).getByText("Location precision (city)").closest("div"),
    ).toHaveTextContent("80%");
    expect(precisionCard).toHaveTextContent("1.0 GB");

    expect(screen.getByText("Synthetic check A").closest("li")).toHaveTextContent(
      "Pass",
    );
    expect(screen.getByText("Synthetic check B").closest("li")).toHaveTextContent(
      "Warn",
    );
  });

  it("renders both location-coverage charts", async () => {
    stubDataFetch(syntheticFiles());
    renderMethodology();

    expect(
      await screen.findByRole("img", { name: "Located-profile share by country" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "Location-confidence distribution" }),
    ).toBeInTheDocument();
  });

  it("shows dataset freshness from the manifest and download links", async () => {
    stubDataFetch(syntheticFiles());
    renderMethodology();

    expect(
      await screen.findByText("0000.00.00-synthetic.1"),
    ).toBeInTheDocument();
    expect(screen.getByText("0.0.0-synthetic")).toBeInTheDocument();
    expect(screen.getByText("2000-01-01 00:00 UTC")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Dataset manifest/ }),
    ).toHaveAttribute("href", "/data/manifest.json");
    expect(
      screen.getByRole("link", { name: /Country rankings/ }),
    ).toHaveAttribute("href", "/data/rankings/cloud_devops/countries.json");
  });

  it("omits the sensitivity section until the file is published", async () => {
    stubDataFetch(syntheticFiles());
    renderMethodology();

    await screen.findByText("0000.00.00-synthetic.1");
    expect(screen.queryByText("Ranking sensitivity")).not.toBeInTheDocument();
  });

  it("renders the sensitivity section only when the file exists", async () => {
    const files = syntheticFiles();
    files["/data/methodology/sensitivity.json"] = syntheticSensitivity;
    stubDataFetch(files);
    renderMethodology();

    expect(await screen.findByText("Ranking sensitivity")).toBeInTheDocument();
    expect(
      screen.getByText("Synthetic sensitivity summary — fixture text only."),
    ).toBeInTheDocument();
    expect(screen.getByText("Synthetic scenario A")).toBeInTheDocument();
  });
});

describe("Methodology without data", () => {
  it("renders designed empty states for the data-driven sections", async () => {
    stubDataFetch({});
    renderMethodology();

    const empties = await screen.findAllByText(AWAITING_DATASET_MESSAGE);
    // Funnel, coverage, validation, downloads.
    expect(empties.length).toBeGreaterThanOrEqual(4);
    expect(
      screen.getByText(/Dataset freshness appears here after the first/),
    ).toBeInTheDocument();
    expect(screen.queryByText("Ranking sensitivity")).not.toBeInTheDocument();
  });
});
