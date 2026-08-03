import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import LocationDetail from "./LocationDetail";
import { LOAD_ERROR_MESSAGE } from "../features/shared/LoadErrorState";
import { clearDataCache } from "../lib/data";
import {
  expectNoUsernameArtifacts,
  SERVER_ERROR,
  stubDataFetch,
  syntheticFiles,
  syntheticProvisionalDetail,
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

/** Probe rendered at /compare so navigation can be asserted. */
function LocationProbe() {
  const location = useLocation();
  return <output data-testid="probe">{location.pathname + location.search}</output>;
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/location/:geoId" element={<LocationDetail />} />
        <Route path="/compare" element={<LocationProbe />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("LocationDetail with full data", () => {
  it("renders the hero: name, scores side by side, tier, statement", async () => {
    stubDataFetch(syntheticFiles());
    renderAt("/location/US");

    expect(
      await screen.findByRole("heading", { level: 1, name: /United States/ }),
    ).toBeInTheDocument();
    expect(screen.getByText("Opportunity score")).toBeInTheDocument();
    expect(screen.getByText("Confidence score")).toBeInTheDocument();
    expect(screen.getAllByText("90.0").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("80.0").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Priority").length).toBeGreaterThanOrEqual(1);
    // Concise tier-derived recommendation statement, not free text.
    expect(
      screen.getByText(/Priority sourcing location: high opportunity/),
    ).toBeInTheDocument();
  });

  it("renders the five-component score decomposition as meters", async () => {
    stubDataFetch(syntheticFiles());
    renderAt("/location/US");

    expect(await screen.findByRole("meter", { name: "Expert supply" }))
      .toHaveAttribute("aria-valuenow", "90");
    expect(screen.getByRole("meter", { name: "Expert quality" }))
      .toHaveAttribute("aria-valuenow", "80");
    expect(screen.getByRole("meter", { name: "Collaboration depth" }))
      .toHaveAttribute("aria-valuenow", "70");
    expect(screen.getByRole("meter", { name: "Momentum" }))
      .toHaveAttribute("aria-valuenow", "60");
    expect(screen.getByRole("meter", { name: "Ecosystem breadth" }))
      .toHaveAttribute("aria-valuenow", "50");
  });

  it("renders supply, breadth, concentration, trend, and mix sections", async () => {
    stubDataFetch(syntheticFiles());
    renderAt("/location/US");

    expect(
      await screen.findByText("Observable experts (raw)"),
    ).toBeInTheDocument();
    expect(screen.getByText("Weighted experts")).toBeInTheDocument();
    expect(screen.getByText("Qualified repositories")).toBeInTheDocument();
    expect(screen.getByText("Distinct organizations")).toBeInTheDocument();
    expect(screen.getByText("No concentration flag")).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "Monthly activity trend for United States" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "Subdomain mix for United States" }),
    ).toBeInTheDocument();
  });

  it("templates the why-this-ranks statements from actual values", async () => {
    stubDataFetch(syntheticFiles());
    renderAt("/location/US");

    expect(
      await screen.findByText(
        "United States ranks #1 among ranked countries for Cloud and DevOps with an opportunity score of 90.0.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Its strongest component is expert supply (90.0); its weakest is ecosystem breadth (50.0).",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Confidence is 80.0 (high confidence): 40% of observable experts have a usable location, and 60% of those locations are high-confidence.",
      ),
    ).toBeInTheDocument();
  });

  it("surfaces pipeline caveats verbatim", async () => {
    stubDataFetch(syntheticFiles());
    renderAt("/location/US");

    expect(
      await screen.findByText("Synthetic caveat one — fixture text only."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Synthetic caveat two — fixture text only."),
    ).toBeInTheDocument();
  });

  it("labels provisional momentum in bars and statements", async () => {
    const files = syntheticFiles();
    files["/data/locations/countries/IN.json"] = syntheticProvisionalDetail;
    stubDataFetch(files);
    renderAt("/location/IN");

    expect(
      await screen.findByRole("meter", { name: "Momentum (provisional)" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Momentum is provisional: the pilot window is too short for a full trend comparison.",
      ),
    ).toBeInTheDocument();
  });

  it("adds the location to the URL selection and navigates to compare", async () => {
    stubDataFetch(syntheticFiles());
    renderAt("/location/US");

    fireEvent.click(
      await screen.findByRole("button", { name: /Compare United States/ }),
    );
    expect(screen.getByTestId("probe")).toHaveTextContent(
      "/compare?selected=US",
    );
  });

  it("never renders a username-like string", async () => {
    stubDataFetch(syntheticFiles());
    renderAt("/location/US");

    await screen.findByRole("heading", { level: 1, name: /United States/ });
    expectNoUsernameArtifacts(document.body.textContent);
  });
});

describe("LocationDetail without data", () => {
  it("renders the designed not-found/insufficient-data state for an unknown geoId", async () => {
    stubDataFetch(syntheticFiles());
    renderAt("/location/ZZ");

    expect(
      await screen.findByText('No published data for location "ZZ"'),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Browse ranked locations/ }),
    ).toHaveAttribute("href", "/explore");
  });

  it("renders the awaiting-pipeline state when no dataset exists at all", async () => {
    stubDataFetch({});
    renderAt("/location/US");

    expect(
      await screen.findByText('No published data for location "US"'),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 1, name: "Location detail" }),
    ).toBeInTheDocument();
  });

  it("renders the load-failure state when the file errors", async () => {
    const files = syntheticFiles();
    files["/data/locations/countries/US.json"] = SERVER_ERROR;
    stubDataFetch(files);
    renderAt("/location/US");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      LOAD_ERROR_MESSAGE,
    );
  });
});
