import { afterEach, describe, expect, it, vi } from "vitest";
import type { Manifest } from "../types/manifest";
import {
  clearDataCache,
  fetchJson,
  loadCompare,
  loadCoverage,
  loadLocationDetail,
  loadManifest,
  loadRankings,
  loadRecommendations,
  loadSummary,
  loadValidation,
  locationDetailPath,
  MANIFEST_URL,
} from "./data";

afterEach(() => {
  vi.unstubAllGlobals();
  clearDataCache();
});

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
  });
}

describe("loadManifest", () => {
  it("returns missing when the manifest 404s", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response("not found", { status: 404 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await loadManifest();

    expect(fetchMock).toHaveBeenCalledWith(MANIFEST_URL);
    expect(result).toEqual({ kind: "missing", reason: "HTTP 404" });
  });

  it("returns missing when fetch rejects", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );

    const result = await loadManifest();

    expect(result).toEqual({ kind: "missing", reason: "Failed to fetch" });
  });

  it("returns missing when the body is not valid JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("<html>oops</html>")),
    );

    const result = await loadManifest();

    expect(result.kind).toBe("missing");
  });

  it("returns the parsed manifest when the fetch succeeds", async () => {
    // Synthetic fixture — shape mirrors the spec section 20 example.
    const manifest: Manifest = {
      datasetVersion: "0000.00.00-test.0",
      generatedAt: "2000-01-01T00:00:00Z",
      window: { start: "2000-01-01", end: "2000-01-31" },
      domains: ["cloud_devops"],
      files: { summary: "summary.json" },
      methodologyVersion: "0.0.0",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(manifest), {
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    const result = await loadManifest();

    expect(result).toEqual({ kind: "ok", manifest });
  });
});

describe("fetchJson", () => {
  it("returns ok with parsed data and caches the result", async () => {
    // Synthetic payload — shape only, not real results.
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ value: 1 }));
    vi.stubGlobal("fetch", fetchMock);

    const first = await fetchJson<{ value: number }>("/data/x.json");
    const second = await fetchJson<{ value: number }>("/data/x.json");

    expect(first).toEqual({ status: "ok", data: { value: 1 } });
    expect(second).toEqual(first);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("returns missing on 404 and does not cache it", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response("not found", { status: 404 }));
    vi.stubGlobal("fetch", fetchMock);

    expect(await fetchJson("/data/x.json")).toEqual({ status: "missing" });
    expect(await fetchJson("/data/x.json")).toEqual({ status: "missing" });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("returns error on a non-404 HTTP failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("boom", { status: 500 })),
    );

    expect(await fetchJson("/data/x.json")).toEqual({
      status: "error",
      message: "HTTP 500",
    });
  });

  it("returns error when fetch rejects, then retries on the next call", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    expect(await fetchJson("/data/x.json")).toEqual({
      status: "error",
      message: "Failed to fetch",
    });
    expect(await fetchJson("/data/x.json")).toEqual({
      status: "ok",
      data: { ok: true },
    });
  });

  it("returns error when the body is not valid JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("<html>oops</html>")),
    );

    const result = await fetchJson("/data/x.json");

    expect(result.status).toBe("error");
  });

  it("treats a 200 text/html response as missing (SPA-fallback hosts)", async () => {
    // vite preview / Cloudflare Pages answer missing .json paths with
    // 200 + index.html — that is the file being absent, not an error.
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("<!doctype html><html><body>app</body></html>", {
          headers: { "Content-Type": "text/html; charset=utf-8" },
        }),
      ),
    );

    expect(await fetchJson("/data/x.json")).toEqual({ status: "missing" });
  });

  it("keeps genuine parse failures of JSON-typed responses as errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("{broken", {
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    expect(await fetchJson("/data/x.json")).toEqual({
      status: "error",
      message: "Invalid JSON in /data/x.json",
    });
  });

  it("shares one in-flight request for concurrent calls", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ n: 2 }));
    vi.stubGlobal("fetch", fetchMock);

    const [a, b] = await Promise.all([
      fetchJson("/data/x.json"),
      fetchJson("/data/x.json"),
    ]);

    expect(a).toEqual({ status: "ok", data: { n: 2 } });
    expect(b).toEqual(a);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("locationDetailPath", () => {
  it("maps country geoIds to locations/countries/<CC>.json", () => {
    expect(locationDetailPath("de")).toBe("/data/locations/countries/DE.json");
    expect(locationDetailPath("US")).toBe("/data/locations/countries/US.json");
  });

  it("maps pipeline city geoIds (CC-slug) to locations/cities/<slug>.json", () => {
    // Real emitted id shape: "GB-london" -> gb-london.json.
    expect(locationDetailPath("GB-london")).toBe(
      "/data/locations/cities/gb-london.json",
    );
    expect(locationDetailPath("US-san-francisco")).toBe(
      "/data/locations/cities/us-san-francisco.json",
    );
    // Slugs may carry non-ASCII characters ("BR-são-paulo").
    expect(locationDetailPath("BR-são-paulo")).toBe(
      "/data/locations/cities/br-são-paulo.json",
    );
  });

  it("still accepts the draft-contract CC/slug city format", () => {
    expect(locationDetailPath("US/san-francisco")).toBe(
      "/data/locations/cities/us-san-francisco.json",
    );
  });
});

describe("contract loaders", () => {
  it("request the spec section 20 paths", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response("not found", { status: 404 }));
    vi.stubGlobal("fetch", fetchMock);

    await loadSummary();
    await loadRankings("country");
    await loadRankings("city");
    await loadLocationDetail("IN");
    await loadCompare();
    await loadValidation();
    await loadCoverage();
    await loadRecommendations();

    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      "/data/summary.json",
      "/data/rankings/cloud_devops/countries.json",
      "/data/rankings/cloud_devops/cities.json",
      "/data/locations/countries/IN.json",
      "/data/compare/cloud_devops.json",
      "/data/methodology/validation.json",
      "/data/methodology/coverage.json",
      "/data/recommendations/cloud_devops.json",
    ]);
  });

  it("every loader returns missing while the pipeline has not published", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("not found", { status: 404 })),
    );

    for (const load of [
      loadSummary,
      () => loadRankings("country"),
      () => loadLocationDetail("DE"),
      () => loadCompare(),
      loadValidation,
      loadCoverage,
      () => loadRecommendations(),
    ]) {
      expect(await load()).toEqual({ status: "missing" });
    }
  });
});
