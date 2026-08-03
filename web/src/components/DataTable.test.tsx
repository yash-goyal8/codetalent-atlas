import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { DataTable, type DataTableColumn } from "./DataTable";
import { syntheticCountryRows } from "../test/fixtures/dataset";
import type { GeographicRankingRow } from "../types/data";
import { formatScore } from "../lib/format";

const columns: DataTableColumn<GeographicRankingRow>[] = [
  {
    key: "name",
    header: "Location",
    cell: (row) => row.name,
    sortValue: (row) => row.name,
  },
  {
    key: "opportunity",
    header: "Opportunity",
    align: "right",
    cellClassName: "score-value",
    cell: (row) => formatScore(row.opportunityScore),
    sortValue: (row) => row.opportunityScore,
  },
  {
    key: "tier",
    header: "Tier",
    cell: (row) => row.recommendationTier,
  },
];

function renderTable(initialSort?: { key: string; direction: "asc" | "desc" }) {
  return render(
    <DataTable
      columns={columns}
      rows={syntheticCountryRows}
      rowKey={(row) => row.geoId}
      caption="Synthetic country rankings"
      initialSort={initialSort}
    />,
  );
}

function renderedNames(): string[] {
  return screen
    .getAllByRole("row")
    .slice(1) // skip header row
    .map((row) => row.querySelector("td")?.textContent ?? "");
}

describe("DataTable", () => {
  it("renders semantic table markup with an accessible caption", () => {
    renderTable();

    expect(
      screen.getByRole("table", { name: "Synthetic country rankings" }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("columnheader")).toHaveLength(3);
    // 1 header row + 3 synthetic data rows
    expect(screen.getAllByRole("row")).toHaveLength(4);
  });

  it("applies the initial sort", () => {
    renderTable({ key: "opportunity", direction: "asc" });

    expect(renderedNames()).toEqual(["India", "Germany", "United States"]);
  });

  it("sorts descending on first header click and flips on the second", () => {
    renderTable();

    const button = screen.getByRole("button", { name: /Opportunity/ });
    fireEvent.click(button);
    expect(renderedNames()).toEqual(["United States", "Germany", "India"]);

    fireEvent.click(button);
    expect(renderedNames()).toEqual(["India", "Germany", "United States"]);
  });

  it("exposes sort state via aria-sort", () => {
    renderTable();

    const header = screen.getByRole("columnheader", { name: /Opportunity/ });
    expect(header).not.toHaveAttribute("aria-sort");

    fireEvent.click(screen.getByRole("button", { name: /Opportunity/ }));
    expect(header).toHaveAttribute("aria-sort", "descending");

    fireEvent.click(screen.getByRole("button", { name: /Opportunity/ }));
    expect(header).toHaveAttribute("aria-sort", "ascending");
  });

  it("does not render a sort button for non-sortable columns", () => {
    renderTable();

    expect(
      screen.queryByRole("button", { name: /Tier/ }),
    ).not.toBeInTheDocument();
  });
});
