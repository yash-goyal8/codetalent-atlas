/**
 * Shared subdomainId -> display-name resolution.
 *
 * Display names published by the pipeline are the source of truth: any
 * loaded file that pairs ids with displayNames (summary.subdomainHubs,
 * location subdomainMix) registers them here at load time. The static
 * table below covers the eight pilot taxonomy ids (transcribed from the
 * spec section 8.1 taxonomy — labels, not findings) so surfaces that
 * only see bare ids (ranking rows' topSubdomains) still render the real
 * names. A mechanical prettifier is the last resort for unknown ids —
 * it never invents wording beyond casing.
 */

/** Pilot taxonomy display names (spec 8.1), keyed by subdomain id. */
export const PILOT_SUBDOMAIN_NAMES: Readonly<Record<string, string>> = {
  cicd_developer_tooling: "CI/CD and Developer Tooling",
  cloud_platforms_sdks: "Cloud Platforms and SDKs",
  configuration_management: "Configuration Management",
  containers_orchestration: "Containers and Orchestration",
  infrastructure_as_code: "Infrastructure as Code",
  observability_monitoring: "Observability and Monitoring",
  service_mesh_networking: "Service Mesh and Networking",
  sre_reliability: "SRE and Reliability Engineering",
};

/** Names registered at runtime from pipeline-published displayName pairs. */
const registered = new Map<string, string>();

export interface SubdomainNamePair {
  subdomainId: string;
  displayName: string;
}

/**
 * Register pipeline-published id/displayName pairs (called by the data
 * loaders when summary or location-detail files resolve). Published
 * names always win over the static table.
 */
export function registerSubdomainNames(
  pairs: ReadonlyArray<SubdomainNamePair>,
): void {
  for (const pair of pairs) {
    if (pair.subdomainId && pair.displayName) {
      registered.set(pair.subdomainId, pair.displayName);
    }
  }
}

/** Test helper: drop every runtime-registered name. */
export function clearRegisteredSubdomainNames(): void {
  registered.clear();
}

/** Connector words kept lowercase by the mechanical fallback. */
const SMALL_WORDS = new Set(["and", "as", "of", "the", "for", "in", "on"]);

/** Initialisms the mechanical fallback uppercases. */
const ACRONYMS = new Set(["ci", "cd", "sre", "api", "sdk", "iac", "cli"]);

function prettifyWord(word: string, index: number): string {
  if (ACRONYMS.has(word)) return word.toUpperCase();
  if (word === "sdks") return "SDKs";
  if (index > 0 && SMALL_WORDS.has(word)) return word;
  return word.length > 0 ? word[0].toUpperCase() + word.slice(1) : word;
}

/**
 * Mechanical last-resort label for an unknown id: "ci_cd" -> "CI CD",
 * "infrastructure_as_code" -> "Infrastructure as Code". Casing only —
 * never invents words.
 */
export function prettifySubdomainId(id: string): string {
  return id
    .split(/[_-]+/)
    .filter((word) => word.length > 0)
    .map((word, index) => prettifyWord(word.toLowerCase(), index))
    .join(" ");
}

/**
 * Best available display name for a subdomain id: runtime-registered
 * pipeline name, then the static pilot taxonomy table, then the
 * mechanical prettifier.
 */
export function subdomainDisplayName(id: string): string {
  return (
    registered.get(id) ?? PILOT_SUBDOMAIN_NAMES[id] ?? prettifySubdomainId(id)
  );
}
