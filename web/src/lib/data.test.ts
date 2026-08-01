import { afterEach, describe, expect, it, vi } from "vitest";
import type { Manifest } from "../types/manifest";
import { loadManifest, MANIFEST_URL } from "./data";

afterEach(() => {
  vi.unstubAllGlobals();
});

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
