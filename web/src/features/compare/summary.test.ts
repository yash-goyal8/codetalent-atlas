import { describe, expect, it } from "vitest";
import { buildComparisonSummary } from "./summary";
import { syntheticCountryRows } from "../../test/fixtures/dataset";
import type { GeographicRankingRow } from "../../types/data";

const [us, de, india] = syntheticCountryRows;

/** Crafted variant with no ties so every leader sentence is exercised. */
const craftedGermany: GeographicRankingRow = {
  ...de,
  expertSupplyScore: 70,
  expertQualityScore: 85,
};

describe("buildComparisonSummary", () => {
  it("returns nothing below two locations", () => {
    expect(buildComparisonSummary([])).toEqual([]);
    expect(buildComparisonSummary([us])).toEqual([]);
  });

  it("produces the exact templated sentences for a crafted pair", () => {
    expect(buildComparisonSummary([us, craftedGermany])).toEqual([
      "United States leads on opportunity (90.0 vs 80.0).",
      "United States has higher confidence (80.0 vs 70.0).",
      "United States leads on expert supply (90.0 vs 70.0).",
      "Germany leads on expert quality (85.0 vs 80.0).",
      "Observable expert pools: United States 900, Germany 500.",
    ]);
  });

  it("is order-independent: the leader wins regardless of selection order", () => {
    const [first] = buildComparisonSummary([craftedGermany, us]);
    expect(first).toBe("United States leads on opportunity (90.0 vs 80.0).");
  });

  it("uses tie phrasing when the top values are equal", () => {
    const sentences = buildComparisonSummary([us, de]);
    expect(sentences).toContain(
      "United States and Germany are tied on expert supply (90.0).",
    );
    expect(sentences).toContain(
      "United States and Germany are tied on expert quality (80.0).",
    );
  });

  it("switches to next-value phrasing for three or more locations", () => {
    const sentences = buildComparisonSummary([us, craftedGermany, india]);
    expect(sentences[0]).toBe(
      "United States leads on opportunity (90.0; next 80.0).",
    );
    expect(sentences).toContain(
      "Observable expert pools: United States 900, Germany 500, India 700.",
    );
  });

  it("appends the provisional-momentum note only when flagged", () => {
    expect(
      buildComparisonSummary([us, craftedGermany]).some((s) =>
        s.includes("provisional"),
      ),
    ).toBe(false);
    expect(buildComparisonSummary([us, india])).toContain(
      "Momentum is provisional for India (pilot window too short for a full trend).",
    );
  });
});
