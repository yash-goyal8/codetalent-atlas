import { describe, expect, it } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import {
  DEFAULT_URL_STATE,
  MAX_SELECTED,
  normalizeSelected,
  parseUrlState,
  serializeUrlState,
  useUrlState,
} from "./urlstate";

describe("parseUrlState", () => {
  it("returns defaults for empty params", () => {
    expect(parseUrlState(new URLSearchParams())).toEqual(DEFAULT_URL_STATE);
  });

  it("reads valid values", () => {
    const params = new URLSearchParams(
      "domain=cloud_devops&subdomain=observability&level=city&layer=momentum" +
        "&minConfidence=55&tier=priority&selected=US,DE&search=ber",
    );
    expect(parseUrlState(params)).toEqual({
      domain: "cloud_devops",
      subdomain: "observability",
      level: "city",
      layer: "momentum",
      minConfidence: 55,
      tier: "priority",
      selected: ["US", "DE"],
      search: "ber",
    });
  });

  it("falls back to defaults on invalid enum values", () => {
    const params = new URLSearchParams("level=galaxy&layer=vibes&tier=amazing");
    const state = parseUrlState(params);
    expect(state.level).toBe("country");
    expect(state.layer).toBe("opportunity");
    expect(state.tier).toBeNull();
  });

  it("clamps minConfidence to 0-100 and ignores garbage", () => {
    expect(parseUrlState(new URLSearchParams("minConfidence=250")).minConfidence).toBe(100);
    expect(parseUrlState(new URLSearchParams("minConfidence=-5")).minConfidence).toBe(0);
    expect(parseUrlState(new URLSearchParams("minConfidence=abc")).minConfidence).toBe(0);
  });

  it("dedupes and caps selected", () => {
    const params = new URLSearchParams("selected=US,US,DE,IN,US/austin,XX");
    expect(parseUrlState(params).selected).toEqual(["US", "DE", "IN", "US/austin"]);
    expect(parseUrlState(params).selected).toHaveLength(MAX_SELECTED);
  });
});

describe("normalizeSelected", () => {
  it("drops empties and duplicates, keeps order, caps at four", () => {
    expect(normalizeSelected(["", "DE", "DE", " US ", "IN", "FR", "GB"])).toEqual([
      "DE",
      "US",
      "IN",
      "FR",
    ]);
  });
});

describe("serializeUrlState", () => {
  it("omits every default", () => {
    expect(serializeUrlState(DEFAULT_URL_STATE).toString()).toBe("");
  });

  it("round-trips a full state", () => {
    const state = {
      domain: "other_domain",
      subdomain: "containers",
      level: "city" as const,
      layer: "supply" as const,
      minConfidence: 40,
      tier: "promising" as const,
      selected: ["US/austin", "DE"],
      search: "aus",
    };
    expect(parseUrlState(serializeUrlState(state))).toEqual(state);
  });

  it("preserves params it does not manage", () => {
    const base = new URLSearchParams("utm_source=x&level=city");
    const params = serializeUrlState(DEFAULT_URL_STATE, base);
    expect(params.get("utm_source")).toBe("x");
    expect(params.get("level")).toBeNull();
  });
});

function wrapper({ children }: { children: ReactNode }) {
  return createElement(
    MemoryRouter,
    { initialEntries: ["/explore?minConfidence=30&utm_source=x"] },
    children,
  );
}

describe("useUrlState", () => {
  it("parses the current search params", () => {
    const { result } = renderHook(() => useUrlState(), { wrapper });
    expect(result.current[0].minConfidence).toBe(30);
  });

  it("merges patches and preserves foreign params", () => {
    const { result } = renderHook(() => useUrlState(), { wrapper });

    act(() => {
      result.current[1]({ level: "city", selected: ["US", "DE"] });
    });

    const [state] = result.current;
    expect(state.level).toBe("city");
    expect(state.selected).toEqual(["US", "DE"]);
    expect(state.minConfidence).toBe(30);
  });

  it("resets to defaults when patched with default values", () => {
    const { result } = renderHook(() => useUrlState(), { wrapper });

    act(() => {
      result.current[1]({ minConfidence: 0 });
    });

    expect(result.current[0].minConfidence).toBe(0);
  });
});
