import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation, useParams } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AtlasMapProps } from "../features/map/AtlasMap";
import { AWAITING_DATASET_MESSAGE } from "../components/EmptyState";
import { LOAD_ERROR_MESSAGE } from "../features/shared/LoadErrorState";
import { loadRankings } from "../lib/data";
import {
  syntheticCityRankings,
  syntheticCountryRankings,
} from "../test/fixtures/dataset";
import Explorer from "./Explorer";

/*
 * The map is stubbed at the component boundary (maplibre-gl never loads
 * in jsdom): the stub records its props as data attributes and exposes
 * one button per row so onSelect wiring can be exercised.
 */
vi.mock("../features/map/AtlasMap", () => ({
  AtlasMap: (props: AtlasMapProps) => (
    <div
      data-testid="atlas-map"
      data-layer={props.layer}
      data-level={props.level}
      data-selected={props.selectedGeoId ?? ""}
      data-geo-ids={props.rows.map((row) => row.geoId).join(",")}
      data-described-by={props.describedBy ?? ""}
    >
      {props.rows.map((row) => (
        <button
          key={row.geoId}
          type="button"
          onClick={() => props.onSelect(row.geoId)}
        >
          map-select-{row.geoId}
        </button>
      ))}
    </div>
  ),
}));

vi.mock("../lib/data", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/data")>();
  return { ...actual, loadRankings: vi.fn() };
});

const loadRankingsMock = vi.mocked(loadRankings);

beforeEach(() => {
  loadRankingsMock.mockReset();
  loadRankingsMock.mockImplementation((level) =>
    Promise.resolve({
      status: "ok" as const,
      data: level === "country" ? syntheticCountryRankings : syntheticCityRankings,
    }),
  );
});

/** Shows the live URL so URL persistence can be asserted. */
function UrlProbe() {
  const location = useLocation();
  return <div data-testid="url">{location.pathname + location.search}</div>;
}

function DetailStub() {
  const { geoId } = useParams();
  return <h1>detail:{geoId}</h1>;
}

function renderExplorer(initialEntry = "/explore") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/explore" element={<Explorer />} />
        <Route path="/location/:geoId" element={<DetailStub />} />
      </Routes>
      <UrlProbe />
    </MemoryRouter>,
  );
}

function mapStub() {
  return screen.getByTestId("atlas-map");
}

describe("Explorer rail", () => {
  it("renders one ranked row per country with scores and tier", async () => {
    renderExplorer();
    expect(
      await screen.findByRole("button", { name: /United States/ }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Germany/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /India/ })).toBeInTheDocument();
    expect(screen.getByText("3 of 3")).toBeInTheDocument();
    // Row content: opportunity score, tier label, top subdomain.
    const table = screen.getByRole("table");
    expect(within(table).getByText("90.0")).toBeInTheDocument();
    expect(within(table).getAllByText("Priority").length).toBeGreaterThan(0);
    expect(within(table).getAllByText("Containers").length).toBeGreaterThan(0);
  });

  it("passes the filtered rows and active layer to the map", async () => {
    renderExplorer();
    await screen.findByRole("button", { name: /United States/ });
    expect(mapStub()).toHaveAttribute("data-geo-ids", "US,DE,IN");
    expect(mapStub()).toHaveAttribute("data-layer", "opportunity");
    expect(mapStub()).toHaveAttribute("data-level", "country");
    // The rail container is wired as the map's accessible description.
    const describedBy = mapStub().getAttribute("data-described-by");
    expect(describedBy).toBeTruthy();
    const rail = document.getElementById(describedBy as string);
    expect(rail).toContainElement(screen.getByRole("table"));
  });
});

describe("Explorer filters", () => {
  it("search filters the rail and persists in the URL", async () => {
    renderExplorer();
    await screen.findByRole("button", { name: /United States/ });
    fireEvent.change(screen.getByRole("searchbox", { name: /Search locations/ }), {
      target: { value: "ger" },
    });
    expect(screen.getByRole("button", { name: /Germany/ })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /United States/ }),
    ).not.toBeInTheDocument();
    expect(mapStub()).toHaveAttribute("data-geo-ids", "DE");
    expect(screen.getByTestId("url")).toHaveTextContent("search=ger");
  });

  it("minimum confidence hides rows below the threshold", async () => {
    renderExplorer();
    await screen.findByRole("button", { name: /India/ });
    fireEvent.change(screen.getByRole("slider", { name: /Minimum confidence/ }), {
      target: { value: "60" },
    });
    // India's synthetic confidence is 50 — filtered out at 60.
    expect(screen.queryByRole("button", { name: /India/ })).not.toBeInTheDocument();
    expect(mapStub()).toHaveAttribute("data-geo-ids", "US,DE");
    expect(screen.getByTestId("url")).toHaveTextContent("minConfidence=60");
  });

  it("tier filter keeps only matching rows", async () => {
    renderExplorer();
    await screen.findByRole("button", { name: /United States/ });
    fireEvent.change(screen.getByRole("combobox", { name: /Recommendation tier/ }), {
      target: { value: "priority" },
    });
    expect(mapStub()).toHaveAttribute("data-geo-ids", "US");
    expect(screen.getByTestId("url")).toHaveTextContent("tier=priority");
  });

  it("subdomain filter keeps rows whose top subdomains include it", async () => {
    renderExplorer();
    await screen.findByRole("button", { name: /United States/ });
    fireEvent.change(screen.getByRole("combobox", { name: /Subdomain/ }), {
      target: { value: "observability" },
    });
    // Only Germany lists observability among its top subdomains.
    expect(mapStub()).toHaveAttribute("data-geo-ids", "DE");
    expect(screen.getByTestId("url")).toHaveTextContent("subdomain=observability");
  });

  it("shows the designed no-match state with a working reset", async () => {
    renderExplorer("/explore?minConfidence=95");
    await screen.findByText(/No locations match the current filters/);
    // Both the filter bar and the no-match panel offer a reset — use the panel's.
    fireEvent.click(
      within(screen.getByRole("status")).getByRole("button", {
        name: /Reset filters/,
      }),
    );
    expect(
      await screen.findByRole("button", { name: /United States/ }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("url")).not.toHaveTextContent("minConfidence");
  });

  it("round-trips URL state into controls and the map", async () => {
    renderExplorer("/explore?layer=confidence&tier=promising&search=Ger");
    await screen.findByRole("button", { name: /Germany/ });
    expect(mapStub()).toHaveAttribute("data-layer", "confidence");
    expect(mapStub()).toHaveAttribute("data-geo-ids", "DE");
    expect(
      screen.getByRole("combobox", { name: /Recommendation tier/ }),
    ).toHaveValue("promising");
    expect(
      screen.getByRole("searchbox", { name: /Search locations/ }),
    ).toHaveValue("Ger");
    const layerGroup = screen.getByRole("group", { name: "Score layer" });
    expect(
      within(layerGroup).getByRole("button", { name: "Confidence" }),
    ).toHaveAttribute("aria-pressed", "true");
    // Changing the layer writes back to the URL.
    fireEvent.click(within(layerGroup).getByRole("button", { name: "Momentum" }));
    expect(screen.getByTestId("url")).toHaveTextContent("layer=momentum");
  });
});

describe("Explorer selection", () => {
  it("selects on first rail click and opens the detail route on the second", async () => {
    renderExplorer();
    const germany = await screen.findByRole("button", { name: /Germany/ });
    fireEvent.click(germany);
    expect(mapStub()).toHaveAttribute("data-selected", "DE");
    expect(screen.getByTestId("url")).toHaveTextContent("selected=DE");
    // The score breakdown panel shows the five component bars.
    expect(screen.getByRole("meter", { name: "Expert supply" })).toBeInTheDocument();
    expect(
      screen.getByRole("meter", { name: "Ecosystem breadth" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Germany/ }));
    expect(await screen.findByText("detail:DE")).toBeInTheDocument();
  });

  it("wires map clicks: select first, navigate on the second", async () => {
    renderExplorer();
    fireEvent.click(await screen.findByRole("button", { name: "map-select-US" }));
    expect(mapStub()).toHaveAttribute("data-selected", "US");
    fireEvent.click(screen.getByRole("button", { name: "map-select-US" }));
    expect(await screen.findByText("detail:US")).toBeInTheDocument();
  });

  it("clears the selection from the breakdown panel", async () => {
    renderExplorer("/explore?selected=US");
    await screen.findByRole("button", { name: /United States/ });
    expect(mapStub()).toHaveAttribute("data-selected", "US");
    fireEvent.click(screen.getByRole("button", { name: /Clear selection/ }));
    expect(mapStub()).toHaveAttribute("data-selected", "");
    expect(
      screen.getByText(/Select a location on the map or in the ranked table/),
    ).toBeInTheDocument();
  });
});

describe("Explorer geographic levels", () => {
  it("lazy-loads city rankings only when the level is toggled", async () => {
    renderExplorer();
    await screen.findByRole("button", { name: /United States/ });
    expect(loadRankingsMock).toHaveBeenCalledWith("country", "cloud_devops");
    expect(loadRankingsMock).not.toHaveBeenCalledWith("city", "cloud_devops");

    const levelGroup = screen.getByRole("group", { name: "Geographic level" });
    fireEvent.click(within(levelGroup).getByRole("button", { name: "Cities" }));

    expect(await screen.findByRole("button", { name: /Testville/ })).toBeInTheDocument();
    expect(loadRankingsMock).toHaveBeenCalledWith("city", "cloud_devops");
    expect(mapStub()).toHaveAttribute("data-level", "city");
    expect(screen.getByTestId("url")).toHaveTextContent("level=city");
  });
});

describe("Explorer data states", () => {
  it("renders the awaiting-pipeline empty state when rankings are missing", async () => {
    loadRankingsMock.mockResolvedValue({ status: "missing" });
    renderExplorer();
    expect(await screen.findByText(AWAITING_DATASET_MESSAGE)).toBeInTheDocument();
  });

  it("renders the load-failure state on fetch errors", async () => {
    loadRankingsMock.mockResolvedValue({ status: "error", message: "HTTP 500" });
    renderExplorer();
    expect(await screen.findByText(LOAD_ERROR_MESSAGE)).toBeInTheDocument();
    expect(screen.getByText("HTTP 500")).toBeInTheDocument();
  });

  it("renders the designed unsupported-domain state with a switch action", async () => {
    renderExplorer("/explore?domain=quantum");
    expect(
      await screen.findByText(/is not part of this dataset/),
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: /Switch to Cloud and DevOps/ }),
    );
    expect(
      await screen.findByRole("button", { name: /United States/ }),
    ).toBeInTheDocument();
  });
});
