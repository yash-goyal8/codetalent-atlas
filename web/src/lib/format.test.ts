import { describe, expect, it } from "vitest";
import {
  confidenceLabel,
  confidenceLevel,
  formatCount,
  formatScore,
  formatShare,
  NO_VALUE,
  tierColorClass,
  tierLabel,
} from "./format";

describe("formatScore", () => {
  it("always shows one decimal", () => {
    expect(formatScore(72.44)).toBe("72.4");
    expect(formatScore(100)).toBe("100.0");
    expect(formatScore(0)).toBe("0.0");
    expect(formatScore(9.96)).toBe("10.0");
  });

  it("renders a placeholder for absent values", () => {
    expect(formatScore(null)).toBe(NO_VALUE);
    expect(formatScore(undefined)).toBe(NO_VALUE);
    expect(formatScore(Number.NaN)).toBe(NO_VALUE);
  });
});

describe("formatCount", () => {
  it("keeps small counts exact", () => {
    expect(formatCount(0)).toBe("0");
    expect(formatCount(987)).toBe("987");
  });

  it("compacts thousands with a lowercase k", () => {
    expect(formatCount(12_345)).toBe("12.3k");
    expect(formatCount(2_000)).toBe("2k");
    expect(formatCount(999_499)).toBe("999k");
  });

  it("compacts millions and billions", () => {
    expect(formatCount(4_500_000)).toBe("4.5M");
    expect(formatCount(1_200_000_000)).toBe("1.2B");
  });

  it("renders a placeholder for absent values", () => {
    expect(formatCount(null)).toBe(NO_VALUE);
    expect(formatCount(Number.POSITIVE_INFINITY)).toBe(NO_VALUE);
  });
});

describe("formatShare", () => {
  it("formats 0-1 shares as percentages", () => {
    expect(formatShare(0.62)).toBe("62%");
    expect(formatShare(1)).toBe("100%");
    expect(formatShare(0)).toBe("0%");
  });

  it("keeps one decimal below ten percent", () => {
    expect(formatShare(0.057)).toBe("5.7%");
    expect(formatShare(0.09)).toBe("9%");
  });

  it("renders a placeholder for absent values", () => {
    expect(formatShare(undefined)).toBe(NO_VALUE);
  });
});

describe("tier helpers", () => {
  it("labels every tier", () => {
    expect(tierLabel("priority")).toBe("Priority");
    expect(tierLabel("promising")).toBe("Promising");
    expect(tierLabel("monitor")).toBe("Monitor");
    expect(tierLabel("insufficient_data")).toBe("Insufficient data");
  });

  it("maps every tier to a token color class", () => {
    expect(tierColorClass("priority")).toBe("text-positive");
    expect(tierColorClass("promising")).toBe("text-accent");
    expect(tierColorClass("monitor")).toBe("text-warning");
    expect(tierColorClass("insufficient_data")).toBe("text-secondary");
  });
});

describe("confidence helpers", () => {
  it("buckets scores at the 70/40 thresholds", () => {
    expect(confidenceLevel(85)).toBe("high");
    expect(confidenceLevel(70)).toBe("high");
    expect(confidenceLevel(69.9)).toBe("medium");
    expect(confidenceLevel(40)).toBe("medium");
    expect(confidenceLevel(39.9)).toBe("low");
    expect(confidenceLevel(0)).toBe("low");
  });

  it("labels the bucket", () => {
    expect(confidenceLabel(90)).toBe("High confidence");
    expect(confidenceLabel(50)).toBe("Medium confidence");
    expect(confidenceLabel(10)).toBe("Low confidence");
  });
});
