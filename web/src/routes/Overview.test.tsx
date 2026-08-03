import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import Overview from "./Overview";
import { AWAITING_DATASET_MESSAGE } from "../components/EmptyState";
import { LOAD_ERROR_MESSAGE } from "../features/shared/LoadErrorState";
import { clearDataCache } from "../lib/data";
import {
  expectNoUsernameArtifacts,
  SERVER_ERROR,
  stubDataFetch,
  syntheticFiles,
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

function renderOverview() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Overview />
    </MemoryRouter>,
  );
}

describe("Overview with full data", () => {
  it("renders the four KPI cards with formatted values", async () => {
    stubDataFetch(syntheticFiles());
    renderOverview();

    expect(
      await screen.findByLabelText("Qualified repositories: 1k"),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Observable experts: 2k")).toBeInTheDocument();
    expect(
      screen.getByLabelText("Located-profile coverage: 40%"),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("Countries with sufficient data: 3"),
    ).toBeInTheDocument();
  });

  it("shows the data-window label from the manifest", async () => {
    stubDataFetch(syntheticFiles());
    renderOverview();

    const badge = await screen.findByText(/Data window:/);
    expect(badge).toHaveTextContent("2000-01-01");
    expect(badge).toHaveTextContent("2000-03-31");
  });

  it("lists the top priority locations with scores, tiers, and links", async () => {
    stubDataFetch(syntheticFiles());
    renderOverview();

    const usLink = await screen.findByRole("link", { name: /United States/ });
    expect(usLink).toHaveAttribute("href", "/location/US");
    expect(usLink).toHaveTextContent("90.0");
    expect(usLink).toHaveTextContent("80.0");
    expect(usLink).toHaveTextContent("Priority");
    expect(screen.getByRole("link", { name: /Germany/ })).toHaveTextContent(
      "Promising",
    );
    expect(screen.getByRole("link", { name: /India/ })).toHaveTextContent(
      "Monitor",
    );
  });

  it("renders the opportunity-vs-confidence scatter with threshold summary and table fallback", async () => {
    stubDataFetch(syntheticFiles());
    renderOverview();

    expect(
      await screen.findByRole("img", {
        name: "Opportunity versus confidence scatterplot of ranked countries",
      }),
    ).toBeInTheDocument();
    // Quadrant guides at the configured tier thresholds (spec 17: 75/70).
    expect(
      screen.getByText(/thresholds at confidence 70 and opportunity 75/),
    ).toBeInTheDocument();
    expect(screen.getByText("View data as table")).toBeInTheDocument();
  });

  it("renders subdomain hubs, methodology summary, teasers, and limitations", async () => {
    stubDataFetch(syntheticFiles());
    renderOverview();

    expect(
      await screen.findByText("Containers and orchestration"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Observability and monitoring"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Full methodology/ }),
    ).toHaveAttribute("href", "/methodology");
    expect(
      await screen.findByRole("link", { name: /full recommendations memo/ }),
    ).toHaveAttribute("href", "/recommendations");
    // Prominent limitations note, verbatim spec-18 text.
    expect(
      screen.getByText("GitHub activity is not the total developer workforce."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("complementary", { name: "Known limitations" }),
    ).toBeInTheDocument();
  });

  it("never introduces a username-like string", async () => {
    stubDataFetch(syntheticFiles());
    renderOverview();

    await screen.findByLabelText("Qualified repositories: 1k");
    expectNoUsernameArtifacts(document.body.textContent);
  });
});

describe("Overview with partial data", () => {
  it("renders KPIs while missing files fall back to designed empty states", async () => {
    const files = syntheticFiles();
    delete files["/data/rankings/cloud_devops/countries.json"];
    delete files["/data/recommendations/cloud_devops.json"];
    stubDataFetch(files);
    renderOverview();

    expect(
      await screen.findByLabelText("Qualified repositories: 1k"),
    ).toBeInTheDocument();
    // Map preview + scatter + teasers sections each show the
    // awaiting-pipeline state (the first two gate on country rankings).
    const empties = await screen.findAllByText(AWAITING_DATASET_MESSAGE);
    expect(empties).toHaveLength(3);
    expect(
      screen.queryByRole("img", { name: /scatterplot/ }),
    ).not.toBeInTheDocument();
  });
});

describe("Overview with no data", () => {
  it("renders placeholder KPIs and empty states without crashing", async () => {
    stubDataFetch({});
    renderOverview();

    expect(
      await screen.findByLabelText("Qualified repositories: not yet available"),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText("Populated after the first pipeline run").length,
    ).toBe(4);
    expect(
      screen.getByText("Data window: awaiting first dataset"),
    ).toBeInTheDocument();
    expect(
      (await screen.findAllByText(AWAITING_DATASET_MESSAGE)).length,
    ).toBeGreaterThanOrEqual(3);
    // Static blocks render regardless of data.
    expect(
      screen.getByText("GitHub activity is not the total developer workforce."),
    ).toBeInTheDocument();
  });
});

describe("Overview with a failing data file", () => {
  it("renders the designed load-failure state", async () => {
    const files = syntheticFiles();
    files["/data/summary.json"] = SERVER_ERROR;
    stubDataFetch(files);
    renderOverview();

    expect(
      (await screen.findAllByText("Data file failed to load")).length,
    ).toBe(4);
    // Top locations + subdomain hubs both gate on the failing summary file.
    const alerts = await screen.findAllByRole("alert");
    expect(alerts.length).toBeGreaterThanOrEqual(1);
    for (const alert of alerts) {
      expect(alert).toHaveTextContent(LOAD_ERROR_MESSAGE);
    }
  });
});
