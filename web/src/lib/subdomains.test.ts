import { afterEach, describe, expect, it } from "vitest";
import {
  clearRegisteredSubdomainNames,
  PILOT_SUBDOMAIN_NAMES,
  prettifySubdomainId,
  registerSubdomainNames,
  subdomainDisplayName,
} from "./subdomains";

afterEach(() => {
  clearRegisteredSubdomainNames();
});

describe("subdomainDisplayName", () => {
  it("resolves the eight pilot taxonomy ids to their display names", () => {
    expect(subdomainDisplayName("cicd_developer_tooling")).toBe(
      "CI/CD and Developer Tooling",
    );
    expect(subdomainDisplayName("infrastructure_as_code")).toBe(
      "Infrastructure as Code",
    );
    expect(subdomainDisplayName("sre_reliability")).toBe(
      "SRE and Reliability Engineering",
    );
    expect(Object.keys(PILOT_SUBDOMAIN_NAMES)).toHaveLength(8);
  });

  it("prefers pipeline-registered display names over everything", () => {
    registerSubdomainNames([
      // Synthetic pair — fixture text only.
      { subdomainId: "sre_reliability", displayName: "Synthetic SRE Name" },
      { subdomainId: "novel_subdomain", displayName: "Novel Subdomain" },
    ]);
    expect(subdomainDisplayName("sre_reliability")).toBe("Synthetic SRE Name");
    expect(subdomainDisplayName("novel_subdomain")).toBe("Novel Subdomain");
  });

  it("falls back to the mechanical prettifier for unknown ids", () => {
    expect(subdomainDisplayName("edge_of_network")).toBe("Edge of Network");
  });
});

describe("prettifySubdomainId", () => {
  it("never uppercases connector words like 'as'", () => {
    expect(prettifySubdomainId("infrastructure_as_code")).toBe(
      "Infrastructure as Code",
    );
  });

  it("uppercases known initialisms", () => {
    expect(prettifySubdomainId("ci_cd")).toBe("CI CD");
    expect(prettifySubdomainId("platform_sdks")).toBe("Platform SDKs");
  });

  it("title-cases ordinary words", () => {
    expect(prettifySubdomainId("containers")).toBe("Containers");
    expect(prettifySubdomainId("service-mesh")).toBe("Service Mesh");
  });
});
