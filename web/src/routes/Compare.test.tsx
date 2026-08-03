import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import Compare from "./Compare";
import { AWAITING_DATASET_MESSAGE } from "../components/EmptyState";
import { clearDataCache } from "../lib/data";
import {
  expectNoUsernameArtifacts,
  stubDataFetch,
  syntheticFiles,
} from "../test/fixtures/stubFetch";

afterEach(() => {
  vi.unstubAllGlobals();
  clearDataCache();
});

function renderCompare(search = "") {
  return render(
    <MemoryRouter initialEntries={[`/compare${search}`]}>
      <Compare />
    </MemoryRouter>,
  );
}

describe("Compare with selections in the URL", () => {
  it("renders aligned side-by-side columns for the selected locations", async () => {
    stubDataFetch(syntheticFiles());
    renderCompare("?selected=US,DE");

    const list = await screen.findByRole("list", {
      name: "Selected locations, side by side",
    });
    const columns = within(list).getAllByRole("listitem");
    expect(columns).toHaveLength(2);
    expect(columns[0]).toHaveTextContent("United States");
    expect(columns[1]).toHaveTextContent("Germany");
    // Each column carries the same ordered component meters.
    expect(
      within(list).getAllByRole("meter", { name: "Expert supply" }),
    ).toHaveLength(2);
    expect(
      within(list).getAllByRole("meter", { name: "Ecosystem breadth" }),
    ).toHaveLength(2);
    // Supply, coverage, and breadth rows exist per column.
    expect(within(columns[0]).getByText("Observable experts")).toBeInTheDocument();
    expect(
      within(columns[1]).getByText("Located-profile coverage"),
    ).toBeInTheDocument();
  });

  it("produces the exact templated factual summary for a crafted pair", async () => {
    stubDataFetch(syntheticFiles());
    renderCompare("?selected=US,DE");

    expect(
      await screen.findByText("United States leads on opportunity (90.0 vs 80.0)."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("United States has higher confidence (80.0 vs 70.0)."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "United States and Germany are tied on expert supply (90.0).",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "United States and Germany are tied on expert quality (80.0).",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Observable expert pools: United States 900, Germany 500.",
      ),
    ).toBeInTheDocument();
  });

  it("labels provisional momentum in the summary and the meters", async () => {
    stubDataFetch(syntheticFiles());
    renderCompare("?selected=US,IN");

    expect(
      await screen.findByText(
        "Momentum is provisional for India (pilot window too short for a full trend).",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("meter", { name: "Momentum (provisional)" }),
    ).toBeInTheDocument();
  });

  it("hides columns beyond the second on small screens via responsive classes", async () => {
    stubDataFetch(syntheticFiles());
    renderCompare("?selected=US,DE,IN");

    const list = await screen.findByRole("list", {
      name: "Selected locations, side by side",
    });
    const columns = within(list).getAllByRole("listitem", { hidden: true });
    expect(columns).toHaveLength(3);
    expect(columns[0].className).not.toContain("hidden");
    expect(columns[1].className).not.toContain("hidden");
    expect(columns[2].className).toContain("hidden");
  });

  it("removes a location from the comparison", async () => {
    stubDataFetch(syntheticFiles());
    renderCompare("?selected=US,DE");

    fireEvent.click(
      await screen.findByRole("button", {
        name: "Remove Germany from comparison",
      }),
    );
    expect(
      screen.getByText("Select at least two locations to compare"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/United States is selected — add one more location/),
    ).toBeInTheDocument();
  });

  it("never renders a username-like string", async () => {
    stubDataFetch(syntheticFiles());
    renderCompare("?selected=US,DE,IN");

    await screen.findByRole("list", {
      name: "Selected locations, side by side",
    });
    expectNoUsernameArtifacts(document.body.textContent);
  });
});

describe("Compare picker", () => {
  it("adds locations through the accessible picker", async () => {
    stubDataFetch(syntheticFiles());
    renderCompare();

    expect(
      await screen.findByText("Select at least two locations to compare"),
    ).toBeInTheDocument();

    const select = screen.getByRole("combobox", { name: /Add location/ });
    fireEvent.change(select, { target: { value: "US" } });
    fireEvent.click(screen.getByRole("button", { name: "Add" }));
    fireEvent.change(select, { target: { value: "DE" } });
    fireEvent.click(screen.getByRole("button", { name: "Add" }));

    const list = await screen.findByRole("list", {
      name: "Selected locations, side by side",
    });
    expect(list).toHaveTextContent("United States");
    expect(list).toHaveTextContent("Germany");
  });

  it("offers cities as well as countries and caps at four selections", async () => {
    stubDataFetch(syntheticFiles());
    renderCompare("?selected=US,DE,IN,US-testville");

    expect(await screen.findByText(/4\/4/)).toBeInTheDocument();
    expect(
      screen.getByText(/Maximum of 4 locations — remove one to add another\./),
    ).toBeInTheDocument();
    const list = screen.getByRole("list", {
      name: "Selected locations, side by side",
    });
    expect(
      within(list).getAllByRole("listitem", { hidden: true }),
    ).toHaveLength(4);
    expect(list).toHaveTextContent("Testville");
  });
});

describe("Compare without data", () => {
  it("renders the awaiting-pipeline empty state when compare.json is missing", async () => {
    stubDataFetch({});
    renderCompare();

    expect(
      await screen.findByText(AWAITING_DATASET_MESSAGE),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Location selection and comparison panels activate/),
    ).toBeInTheDocument();
  });
});
