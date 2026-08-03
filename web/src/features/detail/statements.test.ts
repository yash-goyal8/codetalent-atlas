import { describe, expect, it } from "vitest";
import { extremeComponents, tierStatement, whyStatements } from "./statements";
import {
  syntheticCountryRows,
  syntheticLocationDetail,
} from "../../test/fixtures/dataset";

describe("tierStatement", () => {
  it("restates the configured tier definitions", () => {
    expect(tierStatement("priority")).toMatch(/^Priority sourcing location/);
    expect(tierStatement("promising")).toMatch(/^Promising sourcing location/);
    expect(tierStatement("monitor")).toMatch(/^Monitor/);
    expect(tierStatement("insufficient_data")).toMatch(/^Insufficient data/);
  });
});

describe("extremeComponents", () => {
  it("finds the strongest and weakest components by value", () => {
    expect(extremeComponents(syntheticLocationDetail.components)).toEqual({
      strongest: "expertSupplyScore",
      weakest: "ecosystemBreadthScore",
    });
  });
});

describe("whyStatements", () => {
  it("templates every sentence from the published values", () => {
    expect(whyStatements(syntheticLocationDetail)).toEqual([
      "United States ranks #1 among ranked countries for Cloud and DevOps with an opportunity score of 90.0.",
      "Its strongest component is expert supply (90.0); its weakest is ecosystem breadth (50.0).",
      "Confidence is 80.0 (high confidence): 40% of observable experts have a usable location, and 60% of those locations are high-confidence.",
    ]);
  });

  it("appends the provisional note when momentum is provisional", () => {
    const provisional = {
      ...syntheticLocationDetail,
      ranking: syntheticCountryRows[2],
    };
    const sentences = whyStatements(provisional);
    expect(sentences.at(-1)).toBe(
      "Momentum is provisional: the pilot window is too short for a full trend comparison.",
    );
    expect(sentences[0]).toBe(
      "India ranks #3 among ranked countries for Cloud and DevOps with an opportunity score of 70.0.",
    );
  });
});
