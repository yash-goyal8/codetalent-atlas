/** Geography display helpers shared by the analytical pages. */

import { subdomainDisplayName } from "../../lib/subdomains";

/**
 * Flag emoji from an ISO alpha-2 country code ("DE" -> 🇩🇪).
 * Returns an empty string for anything that is not two ASCII letters,
 * so bad data degrades to no flag rather than mojibake.
 */
export function countryFlag(countryCode: string): string {
  const cc = countryCode.trim().toUpperCase();
  if (!/^[A-Z]{2}$/.test(cc)) {
    return "";
  }
  return String.fromCodePoint(
    ...[...cc].map((char) => 0x1f1e6 + (char.charCodeAt(0) - 65)),
  );
}

/**
 * Human label for a subdomain id when no displayName travels with it.
 * Delegates to the shared resolver (lib/subdomains):
 * "containers_orchestration" -> "Containers and Orchestration".
 */
export function subdomainIdLabel(subdomainId: string): string {
  return subdomainDisplayName(subdomainId);
}
